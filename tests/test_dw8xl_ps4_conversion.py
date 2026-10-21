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
from koei_editor.shared.koei_codec import byte_cipher, mix_word, word_cipher, word_sum
from tests.test_conversion import fixture, write_copy
from koei_editor.games.p5strikers_ps4.context import title_only_sfo


def alternate_pc(raw):
    """Procedural exact editor-accepted alternate header, native checksums intact."""
    backend = c.ENDPOINTS['dw8xl'].backend
    doc = backend.decode(raw, 'dw8xl')
    payload = bytes.fromhex('f027021909') + doc.payload[5:]
    inner = byte_cipher(payload, 0x13100200)
    return (struct.pack('<HH', word_sum(inner), doc.seed) + word_cipher(inner, doc.seed)
            + bytes(((sum(payload) & 255) ^ (mix_word(doc.seed) & 255),)))


class DW8PS4ConversionTests(unittest.TestCase):
    def test_alternate_pc_is_destination_only_with_original_seed_and_exact_source_core(self):
        from koei_editor.games.dw8xl import converter
        pc = c.ENDPOINTS['dw8xl'].backend
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            template = write_copy(folder / 'template', 'dw8xl', 1)
            original = alternate_pc(template.read_bytes())
            template.write_bytes(original)
            doc = pc.read_save(template, 'dw8xl')
            for index, source_id in enumerate(('dw8xl_ps4', 'dw8xl_ps3', 'dw8xl_vita')):
                source = write_copy(folder / str(index) / 'source', source_id)
                before = source.read_bytes()
                prepared = c.prepare(source_id + '-to-dw8xl', source, template)
                path, _backups, _receipt = c.export(prepared, folder / str(index) / 'output')
                reopened = pc.read_save(path, 'dw8xl')
                self.assertEqual(reopened.seed, doc.seed)
                self.assertEqual(reopened.payload, prepared.source.document.payload)
                self.assertEqual(reopened.payload[:5], p.SIGNATURE)
                self.assertEqual(c.prepare('dw8xl-to-' + source_id, path, source).raw, before)
                self.assertEqual(template.read_bytes(), original)
                self.assertEqual(source.read_bytes(), before)
                with self.assertRaisesRegex(SaveError, 'revision'):
                    c.prepare('dw8xl-to-' + source_id, template, source)
            source_doc = p.decode(fixture(p.GAME_ID))
            for bad in (replace(doc, seed=doc.seed ^ 1), replace(doc, payload=source_doc.payload),
                        replace(doc, raw=doc.raw[:-1]), replace(doc, format=replace(doc.format, size=1))):
                with self.assertRaises(SaveError):
                    converter.encode(source_doc, bad)

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
        for changes in ({'unmapped': 1}, [], None):
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
    @unittest.skipUnless(os.environ.get('DW8XL_PS4_REFERENCE') and os.environ.get('DW8XL_PC_REFERENCE'),
                         'Both public full-file references not supplied privately.')
    def test_native_ps4_to_native_alternate_pc_template_with_procedural_context(self):
        # The upstream PS4 file lacks original metadata. A generated companion
        # exercises application export plumbing; it is not original-context or
        # game-load qualification. Native source/template bytes remain exact.
        pc = c.ENDPOINTS['dw8xl'].backend
        source_raw = Path(os.environ['DW8XL_PS4_REFERENCE']).read_bytes()
        template_raw = Path(os.environ['DW8XL_PC_REFERENCE']).read_bytes()
        native_template = pc.decode(template_raw, 'dw8xl')
        self.assertEqual(native_template.payload[:5], bytes.fromhex('f027021909'))
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = write_copy(folder / 'source', p.GAME_ID)
            source.write_bytes(source_raw)
            template = write_copy(folder / 'template', 'dw8xl')
            template.write_bytes(template_raw)
            prepared = c.prepare(p.GAME_ID + '-to-dw8xl', source, template)
            output, backups, receipt = c.export(prepared, folder / 'output')
            actual = pc.read_save(output, 'dw8xl')
            self.assertEqual(actual.payload, p.decode(source_raw).payload)
            self.assertEqual(actual.seed, native_template.seed)
            self.assertEqual(c.prepare('dw8xl-to-' + p.GAME_ID, output, source).raw, source_raw)
            self.assertEqual([path.read_bytes() for path in backups], [source_raw, template_raw])
            self.assertFalse(receipt['game_load_verified'])
            self.assertEqual(source.read_bytes(), source_raw)
            self.assertEqual(template.read_bytes(), template_raw)
            damaged = bytearray(source_raw)
            damaged[-1] = 1
            source.write_bytes(damaged)
            with self.assertRaisesRegex(SaveError, 'extension'):
                c.prepare(p.GAME_ID + '-to-dw8xl', source, template)

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
