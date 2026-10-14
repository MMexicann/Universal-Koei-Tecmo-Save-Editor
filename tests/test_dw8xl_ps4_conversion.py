"""PS4 extension/context bounds and native common-core reverse preservation."""
from dataclasses import replace
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from koei_editor import conversion as c
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw8xl import ps4_export as p
from koei_editor.shared.ps4_export import title_id
from tests.test_conversion import fixture, write_copy
from koei_editor.games.p5strikers_ps4.context import title_only_sfo


class DW8PS4ConversionTests(unittest.TestCase):
    def test_noop_and_zero_extension_are_exact(self):
        raw = fixture(p.GAME_ID)
        doc = p.decode(raw)
        self.assertEqual(p.serialize(doc, {}), raw)
        self.assertEqual(len(doc.payload), 0xB7F44)
        for offset in (0xB7F44, 0xB7F45, len(raw) - 1):
            damaged = bytearray(raw)
            damaged[offset] = 1
            with self.assertRaisesRegex(SaveError, 'extension'): p.decode(bytes(damaged))
        for candidate in (raw[:-1], raw + b'\0', bytes(len(raw)), bytearray(raw)):
            with self.assertRaises(SaveError): p.decode(candidate)
        for changes in ({'gold': 1}, [], None):
            with self.assertRaises(SaveError): p.serialize(doc, changes)
        for candidate in (replace(doc, payload=b''), replace(doc, format=replace(p.FORMAT)),
                          replace(doc, raw=bytearray(raw)), replace(doc, payload=bytearray(doc.payload)), None):
            with self.assertRaises(SaveError): p.validate_document(candidate)

    def test_sfo_bounds_duplicate_wrong_title_and_malformed_values(self):
        valid = title_only_sfo().replace(b'CUSA19640', b'CUSA00397')
        self.assertEqual(title_id(valid, p.TITLE_ID), p.TITLE_ID)
        for bad in (b'', valid[:-1], valid + bytes(4096), title_only_sfo(), bytearray(valid)):
            with self.assertRaises(SaveError): title_id(bad, p.TITLE_ID)
        for offset, value in ((4, 0), (8, 0), (12, 0), (16, 129), (24, 99), (28, 0xffffffff), (32, 0xffffffff)):
            raw = bytearray(valid)
            struct.pack_into('<I', raw, offset, value)
            with self.assertRaises(SaveError): title_id(bytes(raw), p.TITLE_ID)
        raw = bytearray(valid)
        raw[0] ^= 1
        with self.assertRaises(SaveError): title_id(bytes(raw), p.TITLE_ID)
        # Two valid title entries must still fail, even with identical values.
        _magic, _version, keys, data, _count = struct.unpack_from('<5I', valid)
        duplicate = (struct.pack('<5I', 0x46535000, 0x101, keys + 16, data + 16, 2)
                     + valid[20:36] * 2 + valid[36:])
        with self.assertRaises(SaveError): title_id(duplicate, p.TITLE_ID)

    def test_backup_binds_complete_metadata_and_rechecks_races(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_copy(Path(directory) / 'source', p.GAME_ID)
            doc = p.read_save(path)
            backup = p.backup(doc)
            self.assertEqual(backup.read_bytes(), doc.raw)
            self.assertEqual(backup.with_name(backup.name + '.param.sfo').read_bytes(), p.context_raw(path))
            original = p.snapshot_backup
            def racing(*args, **kwargs):
                result = original(*args, **kwargs)
                companion = path.parent / 'sce_sys' / 'param.sfo'
                companion.write_bytes(companion.read_bytes() + b'\0')
                return result
            with patch.object(p, 'snapshot_backup', side_effect=racing), self.assertRaises(SaveError): p.backup(doc)

    def test_all_six_ps4_routes_reject_extension_loss_and_preserve_template_context(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = write_copy(folder / 'source', p.GAME_ID)
            for index, target in enumerate(('dw8xl', 'dw8xl_ps3', 'dw8xl_vita')):
                template = write_copy(folder / str(index), target, 1)
                forward = c.prepare(p.GAME_ID + '-to-' + target, source, template)
                path, _backups, _receipt = c.export(forward, folder / ('out' + str(index)))
                reverse = c.prepare(target + '-to-' + p.GAME_ID, path, source)
                self.assertEqual(reverse.raw, source.read_bytes())
            damaged = bytearray(source.read_bytes())
            damaged[-1] = 1
            source.write_bytes(damaged)
            with self.assertRaisesRegex(SaveError, 'extension'):
                c.prepare(p.GAME_ID + '-to-dw8xl_vita', source, template)


class DW8PS4ReferenceTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('DW8XL_PS4_REFERENCE'), 'Public full-file reference not supplied privately.')
    def test_public_full_file_reference_core_forward_reverse(self):
        reference = p.decode(Path(os.environ['DW8XL_PS4_REFERENCE']).read_bytes())
        from koei_editor.games.dw8xl import converter
        for target in ('dw8xl', 'dw8xl_ps3', 'dw8xl_vita'):
            backend = c.ENDPOINTS[target].backend
            template = backend.decode(fixture(target), target)
            raw = converter.encode(reference, template)
            actual = backend.decode(raw, target)
            self.assertEqual(actual.payload, reference.payload)
            self.assertEqual(converter.encode(actual, reference), reference.raw)
