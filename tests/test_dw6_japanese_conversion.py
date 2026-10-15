"""Japanese native framing, region boundaries and copied conversion safety."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor import conversion as c
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw6_ps3 import japanese_export as jp
from koei_editor.games.dw6 import converter
from tests.test_conversion import fixture, write_copy
from tests import test_ps3_expansion as ps3_context


class JapaneseDW6ConversionTests(unittest.TestCase):
    def test_regional_identity_endianness_length_and_frozen_snapshot_boundaries(self):
        raw = fixture(jp.GAME_ID)
        document = jp.decode(raw)
        self.assertEqual(jp.serialize(document, {}), raw)
        for foreign in (raw[:-1], raw + bytes(64), bytes(jp.SAVE_SIZE), bytearray(raw)):
            with self.assertRaises(SaveError):
                jp.decode(foreign)
        for wrong_id in ('dw6', 'dw6_ps3', 'dw6_special'):
            with self.assertRaises(SaveError):
                jp.decode(raw, wrong_id)
        changed = bytearray(raw)
        offset = jp.OFFICER_BASE + jp.OFFICER_STRIDE + 136
        changed[offset:offset + 4] = (1).to_bytes(4, 'little')
        with self.assertRaises(SaveError):
            jp.decode(bytes(changed))
        for forged in (replace(document, payload=bytearray(raw)),
                       replace(document, raw=bytearray(raw)),
                       replace(document, format=jp.Format()),
                       replace(document, payload=raw[:-1])):
            with self.assertRaises(SaveError):
                converter.gameplay(forged)
        with self.assertRaises(SaveError):
            jp.serialize(document, {'horse_0_speed': 500})

    def test_all_added_directions_preserve_typed_values_unknowns_and_template_remainder(self):
        for other in ('dw6', 'dw6_ps3'):
            for source_id, target_id in ((jp.GAME_ID, other), (other, jp.GAME_ID)):
                with self.subTest(route=(source_id, target_id)):
                    source_backend = c.ENDPOINTS[source_id].backend
                    target_backend = c.ENDPOINTS[target_id].backend
                    source = source_backend.decode(fixture(source_id))
                    template = target_backend.decode(fixture(target_id, 1))
                    raw = converter.encode(source, template)
                    reopened = target_backend.decode(raw)
                    self.assertEqual(converter.gameplay(reopened), converter.gameplay(source))
                    self.assertEqual(converter.encode(reopened, source), source.raw)
                    spans = ((target_backend.OFFICER_BASE, target_backend.OFFICER_BASE + 41 * 168),
                             (target_backend.HORSE_BASE - 24, target_backend.HORSE_BASE - 24 + 8 * 60))
                    cursor = 0
                    for start, end in spans:
                        self.assertEqual(raw[cursor:start], template.raw[cursor:start])
                        cursor = end
                    self.assertEqual(raw[cursor:], template.raw[cursor:])
                    a, b = source_backend.OFFICER_BASE, target_backend.OFFICER_BASE
                    source_order = 'little' if source_id == 'dw6' else 'big'
                    target_order = 'little' if target_id == 'dw6' else 'big'
                    self.assertEqual(int.from_bytes(source.raw[a:a + 8], source_order),
                                     int.from_bytes(raw[b:b + 8], target_order))
                    self.assertEqual(raw[b + 164:b + 168], source.raw[a + 164:a + 168])

    def test_original_context_required_and_backup_source_and_metadata_races_refused(self):
        for action in ('wrong-region', 'oversized', 'source-race', 'metadata-race'):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = write_copy(root / 'source', jp.GAME_ID)
                template = write_copy(root / 'template', 'dw6')
                metadata = source.parent / 'PARAM.SFO'
                if action == 'wrong-region':
                    metadata.write_bytes(ps3_context.PS3ContextTests.metadata('BLUS30110-SAVEDATA'))
                elif action == 'oversized':
                    metadata.write_bytes(metadata.read_bytes() + bytes(4097))
                if action in ('wrong-region', 'oversized'):
                    with self.assertRaises(SaveError):
                        c.prepare(jp.GAME_ID + '-to-dw6', source, template)
                    continue
                reviewed = c.prepare(jp.GAME_ID + '-to-dw6', source, template)
                original = jp._storage.backup
                def racing(document):
                    result = original(document)
                    path = source if action == 'source-race' else metadata
                    path.write_bytes(path.read_bytes() + b'\0')
                    return result
                with patch.object(jp, 'backup', side_effect=racing), self.assertRaises(SaveError):
                    c.export(reviewed, root / 'output')
                self.assertFalse((root / 'output').exists())


class JapaneseDW6NativeTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('DW6_PS3_JP_SAVE') and os.environ.get('DW6_SAVE')
                         and os.environ.get('DW6_PS3_SAVE_COPIES'), 'Private native PC/US/Japanese copies not supplied.')
    def test_native_japanese_all_four_exported_paths_and_byte_exact_reverses(self):
        originals = {jp.GAME_ID: Path(os.environ['DW6_PS3_JP_SAVE']),
                     'dw6': Path(os.environ['DW6_SAVE']),
                     'dw6_ps3': Path(os.environ['DW6_PS3_SAVE_COPIES'].split(os.pathsep)[0])}
        for other in ('dw6', 'dw6_ps3'):
            for source_id, target_id in ((jp.GAME_ID, other), (other, jp.GAME_ID)):
                with self.subTest(route=(source_id, target_id)), tempfile.TemporaryDirectory() as directory:
                    root, copies = Path(directory), {}
                    for endpoint_id, original in originals.items():
                        endpoint = c.ENDPOINTS[endpoint_id]
                        folder = root / endpoint_id
                        folder.mkdir()
                        path = folder / endpoint.filename
                        path.write_bytes(original.read_bytes())
                        if endpoint.companion:
                            (folder / endpoint.companion).write_bytes((original.parent / endpoint.companion).read_bytes())
                        copies[endpoint_id] = path
                    reviewed = c.prepare(source_id + '-to-' + target_id, copies[source_id], copies[target_id])
                    destination, _backups, receipt = c.export(reviewed, root / 'output')
                    self.assertEqual(receipt['transfer_scope'], 'roster-and-horses')
                    self.assertFalse(receipt['game_load_verified'])
                    reverse = c.prepare(target_id + '-to-' + source_id, destination, copies[source_id])
                    self.assertEqual(reverse.raw, copies[source_id].read_bytes())
                    self.assertEqual(len(reviewed.raw), c.ENDPOINTS[target_id].backend.SAVE_SIZE)
