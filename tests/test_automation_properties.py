"""Seeded public-fixture properties; these do not establish in-game validity.

Reproduce a failure with KOEI_PROPERTY_SEED=<reported seed> and this module.
Every subtest reports the seed, profile and case; generation is deliberately
bounded so ordinary CI runs the same corpus without an optional fuzz dependency.
"""
from dataclasses import replace
import os
from pathlib import Path
import random
import tempfile
import unittest

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from tests.test_dw4hyper_format import procedural_raw as hyper_raw, repair_checksum
from tests.test_hyrule_fire_emblem_depth import instruction_slot
from tests.test_verified_editors import synthetic_raw
from tests.test_verified_snapshot_review import reseed


SEED = int(os.environ.get('KOEI_PROPERTY_SEED', '0x4b4f4549'), 0)


class AutomationPropertyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapters = {key: get_game(key).get_scalar_adapter()
                        for key in ('dw4hyper', 'dw8xl', 'pw3')}
        cls.documents = {
            key: adapter.decode(hyper_raw() if key == 'dw4hyper' else synthetic_raw(key))
            for key, adapter in cls.adapters.items()
        }

    def test_seeded_edit_sequences_roundtrip_readback_preservation_and_undo(self):
        rng = random.Random(SEED)
        for game, adapter in self.adapters.items():
            self.assertIsInstance(adapter, BoundScalarAdapter)
            original = self.documents[game]
            fields = [field for field in adapter.fields_for(original)
                      if type(field.value(original.payload)) is int
                      and field.minimum < field.maximum
                      and getattr(field, 'kind', 'integer') != 'text'
                      and field.group not in ('Equipment', 'General equipment')]
            # More cases for the cheap plain-byte profile, fewer native cipher
            # roundtrips. Each case selects a different multi-field operation.
            for case in range(16 if game == 'dw4hyper' else 4):
                chosen = rng.sample(fields, rng.randint(1, min(8, len(fields))))
                changes = {}
                with self.subTest(seed=SEED, game=game, case=case):
                    for field in chosen:
                        targets = [field.minimum, field.maximum,
                                   rng.randint(field.minimum, field.maximum)]
                        # Bounds can describe a discrete choice or stepped
                        # range. Its existing validator defines the domain.
                        valid = []
                        for target in targets:
                            try:
                                field.validate(target)
                            except SaveError:
                                continue
                            valid.append(target)
                        self.assertTrue(valid)
                        target = rng.choice(valid)
                        previous = changes
                        expected_previous = dict(previous)
                        changes = adapter.stage(original, previous, field.id, target)
                        self.assertEqual(previous, expected_previous)
                    pending = dict(changes)
                    raw = adapter.serialize(original, changes)
                    reopened = adapter.decode(raw)
                    allowed = {offset for field in chosen
                               for start in (field.offset, *getattr(field, 'mirrors', ()))
                               for offset in range(start, start + field.size)}
                    self.assertEqual(len(original.payload), len(reopened.payload))
                    touched = {offset for offset, (old, new) in
                               enumerate(zip(original.payload, reopened.payload)) if old != new}
                    self.assertLessEqual(touched, allowed)
                    for field in chosen:
                        actual = adapter.field_map(reopened)[field.id].value(reopened.payload)
                        self.assertIs(type(actual), int)
                        self.assertEqual(actual, changes.get(field.id, field.value(original.payload)))
                    self.assertEqual(changes, pending)
                    for field in reversed(chosen):
                        changes = adapter.stage(original, changes, field.id, field.value(original.payload))
                    self.assertEqual(changes, {})
                    self.assertEqual(adapter.serialize(original, changes), original.raw)
                    self.assertEqual(original.raw, self.documents[game].raw)
                    if hasattr(original, 'seed'):
                        self.assertEqual(reopened.seed, original.seed)

    def test_seeded_exact_opened_values_are_byte_identical_noops(self):
        rng = random.Random(SEED ^ 1)
        for game, adapter in self.adapters.items():
            document = self.documents[game]
            fields = adapter.fields_for(document)
            for case in range(6):
                chosen = rng.sample(list(fields), min(12, len(fields)))
                pending = {field.id: field.value(document.payload) for field in chosen}
                with self.subTest(seed=SEED, game=game, case=case):
                    self.assertEqual(adapter.review(document, pending), [])
                    self.assertEqual(adapter.serialize(document, pending), document.raw)
                    self.assertEqual(adapter.changed_payload(document, pending), document.payload)

    def test_seeded_invalid_pending_never_creates_output_or_mutates_original(self):
        rng = random.Random(SEED ^ 2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for game, adapter in self.adapters.items():
                source = root / (game + adapter.extension)
                source.write_bytes(self.documents[game].raw)
                document = adapter.read_save(source)
                chosen = rng.sample(list(adapter.fields_for(document)), 6)
                for case, field in enumerate(chosen):
                    for invalid in (True, float(field.value(document.payload)), '1', None,
                                    field.minimum - 1, field.maximum + 1):
                        pending = {field.id: invalid}
                        before = dict(pending)
                        destination = root / ('rejected-' + game + adapter.extension)
                        with self.subTest(seed=SEED, game=game, case=case, invalid=repr(invalid)):
                            for operation in (
                                lambda: adapter.stage(document, pending, field.id, field.value(document.payload)),
                                lambda: adapter.review(document, pending),
                                lambda: adapter.serialize(document, pending),
                                lambda: adapter.save_as(document, pending, destination),
                            ):
                                with self.assertRaises(SaveError):
                                    operation()
                            self.assertEqual(pending, before)
                            self.assertFalse(destination.exists())
                            self.assertEqual(source.read_bytes(), document.raw)
            self.assertFalse(any(root.rglob('UniversalEditorBackups')))

    def test_seeded_malformed_size_checksum_and_identity_corpus(self):
        rng = random.Random(SEED ^ 3)
        for game, adapter in self.adapters.items():
            document = self.documents[game]
            raw = document.raw
            corpus = [('empty', b''), ('oversized', raw + b'\0')]
            corpus.extend(('truncated-' + str(case), raw[:rng.randrange(1, len(raw))])
                          for case in range(5))
            for case in range(8):
                mutated = bytearray(raw)
                # Single-bit corruption under native checksum coverage cannot
                # be confused with arbitrary unchecksummed/opaque padding.
                offset = rng.randrange(0, len(document.payload)) if game == 'dw4hyper' else rng.randrange(4, len(raw) - 1)
                mutated[offset] ^= 1 << rng.randrange(8)
                corpus.append(('checksum-' + str(case), bytes(mutated)))
            if game == 'dw4hyper':
                invalid = bytearray(raw)
                invalid[0x9a] = 255
                corpus.append(('checksum-valid-invalid-difficulty', repair_checksum(invalid)))
                invalid = bytearray(raw)
                invalid[0xb8 + 5] = 41
                corpus.append(('checksum-valid-invalid-record-identity', repair_checksum(invalid)))
                invalid = bytearray(raw)
                invalid[-1] ^= 1
                corpus.append(('trailer', bytes(invalid)))
            else:
                payload = bytearray(document.payload)
                payload[0] ^= 0xff
                corpus.append(('checksum-valid-wrong-header', reseed(replace(document, payload=bytes(payload)), document.seed)))
            for label, malformed in corpus:
                with self.subTest(seed=SEED, game=game, mutation=label), self.assertRaises(SaveError):
                    adapter.decode(malformed)
            self.assertEqual(adapter.serialize(document, {}), raw)

    def test_dependency_invalid_final_maps_rejected_before_writes(self):
        adapter = get_game('three_houses').get_scalar_adapter()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for revision in (13, 23):
                source = root / ('revision-' + str(revision) + adapter.extension)
                source.write_bytes(instruction_slot(revision))
                document = adapter.read_save(source)
                for slot in (2, 3, 4):
                    for duplicate in (2, 9):
                        key = 'character:0:ability:' + str(slot)
                        pending = {key: duplicate}
                        destination = root / ('rejected' + adapter.extension)
                        with self.subTest(revision=revision, slot=slot, duplicate=duplicate):
                            for operation in (
                                lambda: adapter.stage(document, pending, key, 240),
                                lambda: adapter.changed_payload(document, pending),
                                lambda: adapter.serialize(document, pending),
                                lambda: adapter.save_as(document, pending, destination),
                            ):
                                with self.assertRaises(SaveError):
                                    operation()
                            self.assertEqual(pending, {key: duplicate})
                            self.assertFalse(destination.exists())
                            self.assertEqual(source.read_bytes(), document.raw)

    def test_seeded_safe_save_as_preserves_original_and_verifies_disk(self):
        rng = random.Random(SEED ^ 4)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for game, adapter in self.adapters.items():
                source = root / (game + adapter.extension)
                source.write_bytes(self.documents[game].raw)
                document = adapter.read_save(source)
                candidates = [f for f in adapter.fields_for(document)
                              if f.minimum < f.maximum and type(f.value(document.payload)) is int
                              and f.group not in ('Equipment', 'General equipment')]
                chosen = rng.sample(candidates, 3)
                pending = {}
                for field in chosen:
                    target = field.maximum if field.value(document.payload) != field.maximum else field.minimum
                    pending = adapter.stage(document, pending, field.id, target)
                destination = root / ('edited-' + game + adapter.extension)
                with self.subTest(seed=SEED, game=game):
                    saved = adapter.save_as(document, pending, destination)
                    disk = adapter.read_save(destination)
                    self.assertEqual(saved.raw, disk.raw)
                    for key, value in pending.items():
                        self.assertEqual(adapter.field_map(disk)[key].value(disk.payload), value)
                    self.assertEqual(source.read_bytes(), document.raw)
                    with self.assertRaises(FileExistsError):
                        adapter.save_as(document, pending, destination)
                    self.assertEqual(destination.read_bytes(), saved.raw)


if __name__ == '__main__':
    unittest.main()
