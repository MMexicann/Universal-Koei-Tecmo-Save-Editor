"""Generated format tests and opt-in genuine-file evidence; no game-load claim."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.nioh3 import balances, codec, inventory, parser
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from tests.scalar_contract import ScalarContractTests


def procedural_raw(revision=0x01040000):
    payload = bytearray(b'\xA5' * codec.USER_SIZE)
    payload[:8] = b'RNNUSR\0\0'
    struct.pack_into('<I', payload, 8, revision)
    struct.pack_into('<II', payload, 0x18, codec.HEADER_SIZE, codec.USER_SIZE - codec.HEADER_SIZE)
    struct.pack_into('<I', payload, 0x15C, revision)
    for pool in inventory.POOLS:
        payload[pool.start:pool.end] = bytes(pool.count * pool.stride)
        size = pool.count * pool.stride
        struct.pack_into('<III', payload, pool.tag_offset, pool.tag, size + 4, size)
    struct.pack_into('<II', payload, inventory.FOLLOWING_TAG[0], *inventory.FOLLOWING_TAG[1:])
    profile = balances.PROFILES[revision]
    for offset, tag, length in profile.markers:
        struct.pack_into('<II', payload, offset, tag, length)
    struct.pack_into('<Q', payload, profile.amrita_tag_offset + 8, 100_000)
    struct.pack_into('<Q', payload, profile.amrita_tag_offset + 0x18, 230_000)
    # Adjacent state is independent; its native name is not inferred from size.
    struct.pack_into('<I', payload, profile.amrita_tag_offset + 0x28, 314_721)
    for pool in inventory.POOLS[1:]:
        for slot, identity in enumerate(inventory.COMMON_ITEMS):
            offset = pool.start + slot * pool.stride
            struct.pack_into('<6H', payload, offset, identity, identity, 40 + slot, 0, 0, 0)
            struct.pack_into('<H', payload, offset + 0x1C, 100 + slot)
            payload[offset + 0x34:offset + 0xE8] = b'\x79' * (0xE8 - 0x34)
    # Source-backed equipment semantics: current and pre-forge levels can differ.
    equipment = inventory.POOLS[0]
    struct.pack_into('<6H', payload, equipment.start, 0x1234, 0x5678, 1, 16, 8, 3)
    payload[-8:] = b'TAILTEST'
    struct.pack_into('<I', payload, codec.CHECKSUM_SEED_OFFSET, 0x78563412)
    return resign(payload)


def resign(payload):
    payload = bytearray(payload)
    struct.pack_into('<I', payload, codec.CHECKSUM_OFFSET, codec.body_checksum(payload))
    return bytes(payload)


class Nioh3FormatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = procedural_raw()

    def setUp(self):
        self.adapter = BoundScalarAdapter('nioh3', '.bin', parser)
        self.document = self.adapter.decode(self.raw)

    def test_exact_noop_stage_unstage_review_and_surgical_payload(self):
        self.assertEqual(self.adapter.serialize(self.document, {}), self.raw)
        fields = self.adapter.fields_for(self.document)
        self.assertEqual(len(fields), 66)
        field = fields[0]
        original = field.value(self.document.payload)
        pending = {}
        changes = self.adapter.stage(self.document, pending, field.id, original - 1)
        self.assertEqual(pending, {})
        self.assertEqual(self.adapter.stage(self.document, changes, field.id, original), {})
        self.assertEqual(self.adapter.review(self.document, changes), [(field, original, original - 1)])
        edited = self.adapter.decode(self.adapter.serialize(self.document, changes))
        self.assertEqual(edited.payload, self.adapter.changed_payload(self.document, changes))
        touched = {offset for offset, (a, b) in enumerate(zip(self.raw, edited.payload)) if a != b}
        self.assertLessEqual(touched, set(range(field.offset, field.offset + 2))
                             | set(range(codec.CHECKSUM_OFFSET, codec.CHECKSUM_OFFSET + 4)))
        self.assertEqual(edited.payload[codec.CHECKSUM_SEED_OFFSET:codec.CHECKSUM_OFFSET],
                         self.raw[codec.CHECKSUM_SEED_OFFSET:codec.CHECKSUM_OFFSET])
        self.assertEqual(edited.payload[-8:], b'TAILTEST')
        rows = parser.inspection_rows(edited)
        self.assertTrue(any('Level 16; pre-forge level 8; +value 3' in row['value'] for row in rows))

    def test_equipment_modifier_view_is_numeric_read_only_and_preserved_by_edits(self):
        equipment = inventory.POOLS[0]
        equipment_offset = equipment.start
        payload = bytearray(self.raw)
        struct.pack_into('<H', payload, equipment_offset + 0x30, 0x0123)
        first_slot = equipment_offset + 0x38
        struct.pack_into('<H', payload, first_slot, 0xBEEF)
        struct.pack_into('<I', payload, first_slot + 4, 0x12345678)
        payload[first_slot + 9:first_slot + 0x0B] = b'\x04\x05'
        last_slot = equipment_offset + 0x38 + 6 * 0x18
        struct.pack_into('<H', payload, last_slot, 0x8001)
        struct.pack_into('<I', payload, last_slot + 4, 0xA0B0C0D0)
        payload[last_slot + 9:last_slot + 0x0B] = b'\xFE\x7F'

        document = parser.decode(resign(payload))
        rows = parser.inspection_rows(document)
        equipment_row = next(row for row in rows
                             if row['group'] == 'Equipment' and row['label'].startswith('Slot 1:'))
        self.assertIn('source-reported rarity u16=0x0123', equipment_row['value'])
        self.assertIn('1:id=0xBEEF,value=0x12345678,metadata=0x04/0x05', equipment_row['value'])
        self.assertIn('7:id=0x8001,value=0xA0B0C0D0,metadata=0xFE/0x7F', equipment_row['value'])

        mapping = parser.field_map(document)
        self.assertFalse(any(field_id.startswith('equipment_') for field_id in mapping))
        for key in ('equipment_0_rarity', 'equipment_0_modifier_0_id'):
            with self.subTest(key=key), self.assertRaises(SaveError):
                parser.stage(document, {}, key, 1)

        balance = mapping['amrita']
        item = mapping['inventory_0_quantity']
        changes = parser.stage(document, {}, balance.id, balance.value(document.payload) - 1)
        changes = parser.stage(document, changes, item.id, item.value(document.payload) - 1)
        edited = parser.decode(parser.serialize(document, changes))
        self.assertEqual(edited.payload[equipment.start:equipment.end],
                         document.payload[equipment.start:equipment.end])

    def test_no_increases_zero_or_bulk_max_and_all_pending_maps_validated(self):
        field = self.adapter.fields_for(self.document)[0]
        for value in (0, -1, field.maximum + 1, 65536, True, '2', 2.0):
            with self.subTest(value=value), self.assertRaises(SaveError):
                self.adapter.stage(self.document, {}, field.id, value)
        changed = {field.id: 20}
        self.assertEqual(self.adapter.maximums(self.document, changed), changed)
        self.assertEqual(self.adapter.limit_values(self.document, changed, [field.id]), {})
        for pending in ({field.id: True}, {field.id: 0}, {field.id: field.maximum + 1},
                        {'unmapped': 2}, [], None):
            actions = (
                lambda: parser.stage(self.document, pending, field.id, 20),
                lambda: parser.maximums(self.document, pending),
                lambda: parser.limit_values(self.document, pending, [field.id]),
                lambda: parser.review(self.document, pending),
                lambda: parser.changed_payload(self.document, pending),
                lambda: parser.serialize(self.document, pending),
            )
            for action in actions:
                with self.subTest(pending=pending), self.assertRaises(SaveError):
                    action()
        for key in ('unknown', 'equipment_0_level', 'inventory_1400_quantity', True):
            with self.subTest(key=key), self.assertRaises(SaveError):
                parser.stage(self.document, {}, key, 1)

    def test_unknown_empty_nonordinary_duplicates_and_high_values(self):
        pool = inventory.POOLS[1]
        payload = bytearray(self.raw)
        # Unknown IDs preserve all bytes but never generate writable fields.
        struct.pack_into('<HH', payload, pool.start, 0x9999, 0x9999)
        # Zero stacks, appearance changes, forged levels and missing ownership
        # instance indices all remain read only, even if the ID is known.
        struct.pack_into('<H', payload, pool.start + pool.stride + 4, 0)
        struct.pack_into('<H', payload, pool.start + 2 * pool.stride + 2, 0x8888)
        struct.pack_into('<H', payload, pool.start + 3 * pool.stride + 6, 1)
        struct.pack_into('<H', payload, pool.start + 4 * pool.stride + 0x1C, 0)
        struct.pack_into('<H', payload, pool.start + 5 * pool.stride + 4, 0xFFFF)
        doc = parser.decode(resign(payload))
        mapping = parser.field_map(doc)
        for slot in range(5):
            self.assertNotIn(f'inventory_{slot}_quantity', mapping)
        field = mapping['inventory_5_quantity']
        self.assertEqual(field.maximum, 0xFFFF)
        self.assertFalse(field.maxable)
        self.assertEqual(parser.maximums(doc, {}), {})
        changes = parser.stage(doc, {}, field.id, 30)
        self.assertEqual(parser.stage(doc, changes, field.id, 0xFFFF), {})
        self.assertEqual(parser.serialize(doc, {}), doc.raw)
        duplicate = bytearray(self.raw)
        duplicate[pool.start + 10 * pool.stride:pool.start + 11 * pool.stride] = duplicate[pool.start:pool.start + pool.stride]
        with self.assertRaises(SaveError):
            parser.decode(resign(duplicate))

    def test_revision_tags_inner_lengths_adjacency_and_relocation_fail_closed(self):
        for revision in codec.SUPPORTED_REVISIONS:
            doc = parser.decode(procedural_raw(revision))
            self.assertEqual(doc.revision, revision)
            self.assertEqual(len(parser.fields_for(doc)), 66)
        for pool in inventory.POOLS:
            for relative in (0, 4, 8):
                payload = bytearray(self.raw)
                payload[pool.tag_offset + relative] ^= 1
                with self.subTest(pool=pool.id, relative=relative), self.assertRaises(SaveError):
                    parser.decode(resign(payload))
        payload = bytearray(self.raw)
        payload[inventory.FOLLOWING_TAG[0]] ^= 1
        with self.assertRaises(SaveError):
            parser.decode(resign(payload))
        # A valid-looking tag elsewhere does not authorize a moved native array.
        payload = bytearray(self.raw)
        pool = inventory.POOLS[0]
        payload[0x200000:0x20000C] = payload[pool.tag_offset:pool.start]
        payload[pool.tag_offset] ^= 1
        with self.assertRaises(SaveError):
            parser.decode(resign(payload))

    def test_balance_u64_reductions_both_revisions_preserve_all_other_state(self):
        for revision, profile in balances.PROFILES.items():
            document = parser.decode(procedural_raw(revision))
            mapping = parser.field_map(document)
            self.assertEqual(mapping['amrita'].offset, profile.amrita_tag_offset + 8)
            self.assertEqual(mapping['gold'].offset, profile.amrita_tag_offset + 0x18)
            changes = {}
            for key in ('amrita', 'gold'):
                field = mapping[key]
                self.assertEqual(field.size, 8)
                self.assertEqual(field.minimum, 0)
                self.assertFalse(field.maxable)
                self.assertIn('does not perform a purchase or level-up', parser.field_hint(document, field))
                changes = parser.stage(document, changes, key, 0)
                self.assertNotIn(key, parser.stage(document, changes, key, field.maximum))
                for value in (-1, field.maximum + 1, 1 << 64, True, '0', 0.0):
                    with self.subTest(revision=revision, key=key, value=value), self.assertRaises(SaveError):
                        parser.stage(document, {}, key, value)
            self.assertEqual(parser.maximums(document, changes), changes)
            self.assertEqual(parser.limit_values(document, changes, ['amrita', 'gold']), {})
            edited = parser.decode(parser.serialize(document, changes))
            allowed = set(range(codec.CHECKSUM_OFFSET, codec.CHECKSUM_OFFSET + 4))
            for key in ('amrita', 'gold'):
                field = mapping[key]
                self.assertEqual(field.value(edited.payload), 0)
                allowed.update(range(field.offset, field.offset + field.size))
            touched = {offset for offset, (a, b) in enumerate(zip(document.payload, edited.payload)) if a != b}
            self.assertLessEqual(touched, allowed)
            self.assertEqual(edited.payload[profile.amrita_tag_offset + 0x20:profile.amrita_tag_offset + 0x55],
                             document.payload[profile.amrita_tag_offset + 0x20:profile.amrita_tag_offset + 0x55])
            for bad in ({'amrita': True}, {'gold': -1}, {'gold': 1 << 64}, {'amrita': 100_001}):
                for action in (parser.review, parser.maximums, parser.changed_payload, parser.serialize):
                    with self.subTest(bad=bad), self.assertRaises(SaveError):
                        action(document, bad)
                with self.assertRaises(SaveError):
                    parser.stage(document, bad, 'gold', 1)
                with self.assertRaises(SaveError):
                    parser.limit_values(document, bad, ['gold'])

        # A preexisting unusual amount is not replaced by a conventional cheat
        # cap, float-rounded or normalized; the opened value always undoes edits.
        payload = bytearray(self.raw)
        profile = balances.PROFILES[self.document.revision]
        struct.pack_into('<Q', payload, profile.amrita_tag_offset + 8, (1 << 64) - 1)
        document = parser.decode(resign(payload))
        field = parser.field_map(document)['amrita']
        self.assertEqual(field.maximum, (1 << 64) - 1)
        self.assertEqual(parser.serialize(document, {}), document.raw)
        changes = parser.stage(document, {}, 'amrita', (1 << 63) + 7)
        self.assertEqual(parser.stage(document, changes, 'amrita', field.maximum), {})
        edited = parser.decode(parser.serialize(document, changes))
        self.assertEqual(field.value(edited.payload), (1 << 63) + 7)
        zero = bytearray(self.raw)
        struct.pack_into('<Q', zero, profile.amrita_tag_offset + 8, 0)
        empty = parser.decode(resign(zero))
        self.assertEqual(parser.stage(empty, {}, 'amrita', 0), {})
        with self.assertRaises(SaveError):
            parser.stage(empty, {}, 'amrita', 1)

    def test_balance_revision_tag_width_neighbors_and_relocation_fail_closed(self):
        for revision, profile in balances.PROFILES.items():
            raw = procedural_raw(revision)
            for offset, tag, length in profile.markers:
                for relative in (0, 4):
                    payload = bytearray(raw)
                    payload[offset + relative] ^= 1
                    with self.subTest(revision=revision, offset=offset, relative=relative), self.assertRaises(SaveError):
                        parser.decode(resign(payload))
            # Identity alone cannot authorize another revision's field offsets,
            # nor a matching balance header sequence moved into arbitrary data.
            payload = bytearray(raw)
            start = profile.amrita_tag_offset
            payload[0x3E0000:0x3E0055] = payload[start:start + 0x55]
            payload[start] ^= 1
            with self.assertRaises(SaveError):
                parser.decode(resign(payload))
            other = next(key for key in balances.PROFILES if key != revision)
            wrong = bytearray(raw)
            struct.pack_into('<I', wrong, 8, other)
            struct.pack_into('<I', wrong, 0x15C, other)
            with self.assertRaises(SaveError):
                parser.decode(resign(wrong))
    def test_corruption_foreign_titles_revisions_and_forged_snapshots(self):
        for position in (0, 8, 0x18, 0x15C, codec.BODY_START, codec.CHECKSUM_OFFSET):
            raw = bytearray(self.raw)
            raw[position] ^= 1
            with self.subTest(position=position), self.assertRaises(SaveError):
                parser.decode(raw)
        for raw in (b'', self.raw[:-1], self.raw + b'\0', None, 'save'):
            with self.assertRaises(SaveError):
                parser.decode(raw)
        for document in (replace(self.document, payload=bytearray(self.raw)),
                         replace(self.document, raw=bytearray(self.raw)),
                         replace(self.document, revision=True),
                         replace(self.document, encrypted=0),
                         replace(self.document, revision=0x01030001),
                         replace(self.document, payload=self.raw[:-1] + b'\0'),
                         replace(self.document, source='copy.bin'),
                         replace(self.document, format=replace(parser.FORMAT, id='nioh2'))):
            for action in (lambda: parser.fields_for(document),
                           lambda: parser.serialize(document, {}),
                           lambda: parser.maximums(document, {})):
                with self.assertRaises(SaveError):
                    action()
        with patch.object(codec.katana_codec, '_nioh_decrypt') as cipher:
            with self.assertRaises(SaveError):
                parser.decode(bytes(codec.USER_SIZE))
            cipher.assert_not_called()

    def test_save_backup_restore_source_changes_and_serialization_race(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / 'source.bin'
            source.write_bytes(self.raw)
            doc = parser.read_save(source)
            field = parser.fields_for(doc)[0]
            changes = parser.stage(doc, {}, field.id, 20)
            saved = parser.save_as(doc, changes, folder / 'edited.bin')
            self.assertEqual(field.value(saved.payload), 20)
            self.assertEqual(source.read_bytes(), self.raw)
            backups = list((folder / 'WarriorsEditorBackups').glob('*.bin'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), self.raw)
            restored = parser.restore(backups[0], folder / 'restored.bin')
            self.assertEqual(restored.read_bytes(), self.raw)
            with self.assertRaises(FileExistsError):
                parser.save_as(doc, {}, saved.source)
            damaged = bytearray(self.raw)
            damaged[codec.BODY_START] ^= 1
            corrupt_backup = folder / 'corrupt.bin'
            corrupt_backup.write_bytes(damaged)
            manifest = json.loads(backups[0].with_suffix('.json').read_text())
            manifest['sha256'] = hashlib.sha256(damaged).hexdigest()
            corrupt_backup.with_suffix('.json').write_text(json.dumps(manifest))
            with self.assertRaises(SaveError):
                parser.restore(corrupt_backup, folder / 'bad-restore.bin')
            self.assertFalse((folder / 'bad-restore.bin').exists())
            original_serialize = parser.serialize
            def raced(document, pending):
                encoded = original_serialize(document, pending)
                source.write_bytes(damaged)
                return encoded
            with patch.object(parser, 'serialize', side_effect=raced), self.assertRaises(SaveError):
                parser.save_as(doc, changes, folder / 'raced.bin')
            self.assertFalse((folder / 'raced.bin').exists())
            self.assertEqual(len(list((folder / 'WarriorsEditorBackups').glob('*.bin'))), 1)


class Nioh3ScalarContractTests(ScalarContractTests, unittest.TestCase):
    game_id = 'nioh3'
    payload_integrity_offsets = frozenset(range(codec.CHECKSUM_OFFSET, codec.CHECKSUM_OFFSET + 4))

    def fixture_bytes(self):
        return Nioh3FormatTests.raw if hasattr(Nioh3FormatTests, 'raw') else procedural_raw()


class Nioh3NativeAdapterTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('NIOH3_NATIVE_DIR'), 'Private native Nioh 3 USER copies are not configured.')
    def test_genuine_both_revisions_tagged_pools_reductions_and_unchanged_source(self):
        copies = []
        for path in Path(os.environ['NIOH3_NATIVE_DIR']).rglob('*'):
            if path.is_file() and path.suffix.lower() == '.bin' and path.stat().st_size == codec.USER_SIZE:
                with path.open('rb') as stream:
                    if stream.read(8) == b'RNNUSR\0\0':
                        copies.append(path)
        self.assertTrue(copies)
        revisions = set()
        for path in copies:
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).digest()
            doc = parser.decode(raw)
            revisions.add(doc.revision)
            self.assertEqual(parser.serialize(doc, {}), raw)
            field = next(field for field in parser.fields_for(doc) if field.maximum > 1)
            changes = parser.stage(doc, {}, field.id, field.maximum - 1)
            edited = parser.decode(parser.serialize(doc, changes))
            touched = {offset for offset, (a, b) in enumerate(zip(doc.payload, edited.payload)) if a != b}
            allowed = set(range(field.offset, field.offset + 2)) | set(range(codec.CHECKSUM_OFFSET, codec.CHECKSUM_OFFSET + 4))
            self.assertLessEqual(touched, allowed)
            for key in ('amrita', 'gold'):
                balance = parser.field_map(doc)[key]
                self.assertEqual(balance.size, 8)
                self.assertFalse(balance.maxable)
                changed = parser.stage(doc, {}, key, 0)
                reduced = parser.decode(parser.serialize(doc, changed))
                self.assertEqual(balance.value(reduced.payload), 0)
                balance_touched = {offset for offset, (a, b) in enumerate(zip(doc.payload, reduced.payload)) if a != b}
                balance_allowed = set(range(balance.offset, balance.offset + balance.size)) | set(range(codec.CHECKSUM_OFFSET, codec.CHECKSUM_OFFSET + 4))
                self.assertLessEqual(balance_touched, balance_allowed)
            self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), digest)
        self.assertEqual(revisions, codec.SUPPORTED_REVISIONS)

    @unittest.skipUnless(os.environ.get('NIOH3_ENCRYPTED_COPY') and os.environ.get('NIOH3_DECRYPTED_COPY'),
                         'Private Nioh 3 encrypted/decoded USER pair is not configured.')
    def test_genuine_encrypted_edit_reparse_seed_key_and_tail_preservation(self):
        path = Path(os.environ['NIOH3_ENCRYPTED_COPY'])
        raw = path.read_bytes()
        expected = Path(os.environ['NIOH3_DECRYPTED_COPY']).read_bytes()
        doc = parser.decode(raw)
        self.assertTrue(doc.encrypted)
        self.assertEqual(doc.payload[:0x49], expected[:0x49])
        self.assertEqual(doc.payload[0x89:], expected[0x89:])
        self.assertEqual(parser.serialize(doc, {}), raw)
        field = next(field for field in parser.fields_for(doc) if field.maximum > 1)
        balance = parser.field_map(doc)['gold']
        changes = {field.id: field.maximum - 1, 'gold': 0}
        edited = parser.decode(parser.serialize(doc, changes))
        self.assertEqual(field.value(edited.payload), field.maximum - 1)
        self.assertEqual(balance.value(edited.payload), 0)
        allowed = (set(range(field.offset, field.offset + field.size))
                   | set(range(balance.offset, balance.offset + balance.size))
                   | set(range(codec.CHECKSUM_OFFSET, codec.CHECKSUM_OFFSET + 4)))
        touched = {offset for offset, (a, b) in enumerate(zip(raw, edited.raw)) if a != b}
        self.assertLessEqual(touched, allowed)
        self.assertEqual(edited.raw[:codec.BODY_START], raw[:codec.BODY_START])
        self.assertEqual(edited.raw[-8:], raw[-8:])
        self.assertEqual(edited.payload[codec.CHECKSUM_SEED_OFFSET:codec.CHECKSUM_OFFSET],
                         doc.payload[codec.CHECKSUM_SEED_OFFSET:codec.CHECKSUM_OFFSET])
        self.assertEqual(path.read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()
