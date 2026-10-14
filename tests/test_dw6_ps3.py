"""Procedural native geometry, source/context races and optional real PS3 copies."""
from dataclasses import replace
from functools import lru_cache
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw6_ps3 import parser as p
from koei_editor.games.dw3.models import SaveError
from koei_editor.game_registry import get_game
from tests.scalar_contract import ScalarContractTests
from tests import test_ps3_expansion as ps3_context


@lru_cache(maxsize=1)
def fixture():
    raw = bytearray((i * 29 + 61) % 256 for i in range(p.SAVE_SIZE))
    for officer in range(p.OFFICER_COUNT):
        base = p.OFFICER_BASE + officer * p.OFFICER_STRIDE
        raw[base + 136:base + 140] = officer.to_bytes(4, 'big')
        for weapon in range(8):
            off = base + 8 + weapon * 16
            raw[off:off + 4] = (174).to_bytes(4, 'big')
    base = p.OFFICER_BASE + 8
    raw[base:base + 12] = (3).to_bytes(4, 'big') + (24).to_bytes(4, 'big') + (1).to_bytes(4, 'big')
    for horse in range(8):
        base = p.HORSE_BASE + horse * p.HORSE_STRIDE
        raw[base + 4:base + 8] = (60 + horse % 5).to_bytes(4, 'big')
        raw[base + 20:base + 24] = (156).to_bytes(4, 'big')
        for _key, _label, offset in p.HORSE_STATS:
            raw[base + offset:base + offset + 4] = (270).to_bytes(4, 'big')
    return bytes(raw)


def context(folder):
    (folder / 'PARAM.SFO').write_bytes(ps3_context.PS3ContextTests.metadata(p.TITLE_DIRECTORY))


class DW6PS3ContractTests(ScalarContractTests, unittest.TestCase):
    game_id = p.GAME_ID

    def fixture_bytes(self):
        return fixture()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.game = get_game(self.game_id)
        self.adapter = self.game.get_scalar_adapter()
        self.raw = fixture()
        self.source = self.folder / 'APP.BIN'
        self.source.write_bytes(self.raw)
        context(self.folder)
        self.document = self.adapter.read_save(self.source)

    def test_big_endian_surgical_writes_all_fields_and_protected_adjacent_word(self):
        fields = p.fields_for(self.document)
        self.assertEqual(len(fields), 34)
        for field in fields:
            value = 3 if field.id.endswith('_element') else 1
            raw = p.serialize(self.document, {field.id: value})
            self.assertEqual(raw[:field.offset], self.raw[:field.offset])
            self.assertEqual(raw[field.offset + field.size:], self.raw[field.offset + field.size:])
            self.assertEqual(raw[field.offset:field.offset + field.size], value.to_bytes(field.size, 'big'))
            self.assertEqual(field.value(p.decode(raw).payload), value)
        adjacent = p.HORSE_BASE + 20
        self.assertEqual(p.serialize(self.document, {'horse_0_speed': 500})[adjacent:adjacent + 4], self.raw[adjacent:adjacent + 4])

    def test_unknown_empty_records_are_not_writable_and_max_is_disabled(self):
        raw = bytearray(self.raw)
        raw[p.HORSE_BASE + 4:p.HORSE_BASE + 8] = (99).to_bytes(4, 'big')
        doc = p.decode(bytes(raw))
        self.assertNotIn('horse_0_speed', p.field_map(doc))
        self.assertNotIn('officer_0_weapon_1_element', p.field_map(doc))
        self.assertEqual(p.maximums(doc, {}), {})
        self.assertEqual(p.limit_values(doc, {}, tuple(p.field_map(doc))), {})
        for bad in (True, -1, 4, '1'):
            with self.assertRaises(SaveError): p.stage(doc, {}, 'officer_0_weapon_0_element', bad)

    def test_higher_originals_unstage_and_experimental_encoding_limits(self):
        from koei_editor.shared.experimental_limits import experimental_limits
        raw = bytearray(self.raw)
        off = p.HORSE_BASE + 16
        raw[off:off + 4] = (999).to_bytes(4, 'big')
        doc = p.decode(bytes(raw))
        self.assertEqual(p.stage(doc, {'horse_0_speed': 100}, 'horse_0_speed', 999), {})
        self.assertEqual(p.serialize(doc, {}), bytes(raw))
        with self.assertRaises(SaveError): p.serialize(doc, {'horse_0_speed': 501})
        with experimental_limits(True):
            result = p.serialize(doc, {'horse_0_speed': 0xFFFFFFFF})
            self.assertEqual(result[off:off + 4], b'\xff' * 4)
            with self.assertRaises(SaveError): p.serialize(doc, {'horse_0_speed': 0x100000000})
            with self.assertRaises(SaveError): p.serialize(doc, {'officer_0_weapon_0_element': 4})

    def test_foreign_revision_endianness_context_and_mutable_snapshot_rejected(self):
        for raw in (self.raw[:-1], self.raw + b'\0', bytearray(self.raw), bytes(p.SAVE_SIZE)):
            with self.assertRaises(SaveError): p.decode(raw)
        raw = bytearray(self.raw)
        off = p.OFFICER_BASE + p.OFFICER_STRIDE + 136
        raw[off:off + 4] = (1).to_bytes(4, 'little')
        with self.assertRaises(SaveError): p.decode(bytes(raw))
        with self.assertRaises(SaveError): p.fields_for(replace(self.document, payload=bytearray(self.raw)))
        (self.folder / 'PARAM.SFO').write_bytes(ps3_context.PS3ContextTests.metadata('BLJM60041-SAVEDATA'))
        with self.assertRaises(SaveError): p.read_save(self.source)

    def test_metadata_and_source_races_are_checked_after_backup(self):
        original = p._storage.backup
        def racing(document):
            result = original(document)
            (self.folder / 'PARAM.SFO').write_bytes((self.folder / 'PARAM.SFO').read_bytes() + b'\0')
            return result
        with patch.object(p._storage, 'backup', side_effect=racing), self.assertRaises(SaveError):
            self.adapter.save_as(self.document, {'horse_0_speed': 500}, self.folder / 'output.bin')
        self.assertFalse((self.folder / 'output.bin').exists())

    def test_restore_rejects_forged_native_bytes_even_with_updated_manifest(self):
        snapshot = p.backup(self.document)
        raw = bytearray(snapshot.read_bytes())
        raw[p.OFFICER_BASE + 136:p.OFFICER_BASE + 140] = (99).to_bytes(4, 'big')
        snapshot.write_bytes(raw)
        import hashlib
        manifest_path = snapshot.with_suffix('.json')
        manifest = json.loads(manifest_path.read_text())
        manifest['sha256'] = hashlib.sha256(raw).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(SaveError): p.restore(snapshot, self.folder / 'restore.bin')
        self.assertFalse((self.folder / 'restore.bin').exists())

    def test_copied_cli_selftest_preserves_original_context(self):
        from koei_editor.shared.verified_self_test import run
        report = run(p.GAME_ID, self.source, self.folder / 'selftest')
        self.assertTrue(report['success'])
        self.assertEqual((self.folder / 'selftest' / 'PARAM.SFO').read_bytes(), (self.folder / 'PARAM.SFO').read_bytes())


class DW6PS3NativeTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('DW6_PS3_SAVE_COPIES'), 'Separate private US PS3 exports not supplied.')
    def test_native_copies_every_field_surgical_roundtrip_and_safe_output(self):
        for source in os.environ['DW6_PS3_SAVE_COPIES'].split(os.pathsep):
            with self.subTest(copy=Path(source).name), tempfile.TemporaryDirectory() as directory:
                doc = p.read_save(source)
                self.assertEqual(p.serialize(doc, {}), doc.raw)
                for field in p.fields_for(doc):
                    value = 3 if field.id.endswith('_element') else min(499, field.value(doc.payload))
                    edited = p.serialize(doc, {field.id: value})
                    self.assertEqual(edited[:field.offset], doc.raw[:field.offset])
                    self.assertEqual(edited[field.offset + field.size:], doc.raw[field.offset + field.size:])
                destination = Path(directory) / 'APP.BIN'
                p.prepare_copy_context(doc, destination.parent)
                actual = get_game(p.GAME_ID).get_scalar_adapter().save_as(doc, {'horse_0_speed': 499}, destination)
                self.assertEqual(p.field_map(doc)['horse_0_speed'].value(actual.payload), 499)
