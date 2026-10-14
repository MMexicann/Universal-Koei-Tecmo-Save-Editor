"""Independent typed fixtures and optional native DW6 migration qualification."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor import conversion as c
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw6 import converter as transform


def fixture(endpoint_id, variant=0):
    backend = c.ENDPOINTS[endpoint_id].backend
    endian = 'little' if endpoint_id == 'dw6' else 'big'
    raw = bytearray((i * 13 + variant * 31) % 256 for i in range(backend.SAVE_SIZE))
    for officer in range(41):
        base = backend.OFFICER_BASE + officer * 168
        raw[base:base + 8] = (0x0123456789abcdef + officer + variant).to_bytes(8, endian)
        for relative in range(8, 164, 4):
            # Asymmetric full-width values catch accidental byte/halfword swaps.
            value = (0x1020304 + officer * 0x10000 + relative * 257 + variant) & 0xffffffff
            raw[base + relative:base + relative + 4] = value.to_bytes(4, endian)
        raw[base + 136:base + 140] = officer.to_bytes(4, endian)
        raw[base + 164:base + 168] = bytes((officer % 2, 0x61, 0x82, 0xa3))
    for horse in range(8):
        base = backend.HORSE_BASE - 24 + horse * 60
        for relative in range(0, 60, 4):
            value = (0x12345678 + horse * 0x10000 + relative * 0x102 + variant) & 0xffffffff
            raw[base + relative:base + relative + 4] = value.to_bytes(4, endian)
    return bytes(raw)


class DW6ConversionTests(unittest.TestCase):
    def test_each_typed_field_byte_bitset_flags_and_template_remainder(self):
        for source_id, target_id in [('dw6', 'dw6_ps3'), ('dw6_ps3', 'dw6')]:
            source_backend, target_backend = c.ENDPOINTS[source_id].backend, c.ENDPOINTS[target_id].backend
            source = source_backend.decode(fixture(source_id))
            template = target_backend.decode(fixture(target_id, 1))
            result = transform.encode(source, template)
            source_endian = 'little' if source_id == 'dw6' else 'big'
            target_endian = 'little' if target_id == 'dw6' else 'big'
            expected = bytearray(template.raw)
            for officer in range(41):
                a, b = source_backend.OFFICER_BASE + officer * 168, target_backend.OFFICER_BASE + officer * 168
                expected[b:b + 8] = int.from_bytes(source.raw[a:a + 8], source_endian).to_bytes(8, target_endian)
                expected[b + 164:b + 168] = source.raw[a + 164:a + 168]
                for relative in range(8, 164, 4):
                    value = int.from_bytes(source.raw[a + relative:a + relative + 4], source_endian)
                    expected[b + relative:b + relative + 4] = value.to_bytes(4, target_endian)
            for horse in range(8):
                a = source_backend.HORSE_BASE - 24 + horse * 60
                b = target_backend.HORSE_BASE - 24 + horse * 60
                for relative in range(0, 60, 4):
                    value = int.from_bytes(source.raw[a + relative:a + relative + 4], source_endian)
                    expected[b + relative:b + relative + 4] = value.to_bytes(4, target_endian)
            self.assertEqual(result, bytes(expected))
            actual = target_backend.decode(result)
            self.assertEqual(transform.gameplay(actual), transform.gameplay(source))
            self.assertEqual(len(transform.gameplay(source)), 41 * 168 + 8 * 60)
            self.assertEqual(transform.encode(actual, source), source.raw)
            # The first challenge bytes follow the eighth horse's stats. They
            # must remain template bytes, not a mistaken ninth horse suffix.
            end = target_backend.HORSE_BASE + 7 * 60 + 36
            self.assertEqual(result[end:end + 24], template.raw[end:end + 24])

    def test_review_cli_receipt_identify_partial_scope_and_forgery_is_refused(self):
        from tests.test_conversion import write_copy
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = write_copy(folder / 'source', 'dw6')
            template = write_copy(folder / 'template', 'dw6_ps3', 1)
            reviewed = c.prepare('dw6-to-dw6_ps3', source, template)
            self.assertEqual(reviewed.route.transfer_scope, 'roster-and-horses')
            self.assertIn('partial progress', ' '.join(reviewed.notes))
            self.assertIn('destination story', reviewed.route.scope_description)
            with self.assertRaises(SaveError):
                c.export(replace(reviewed, notes=('Everything transfers!',)), folder / 'forged')
            destination, _backups, receipt = c.export(reviewed, folder / 'output')
            self.assertEqual(receipt['transfer_scope'], 'roster-and-horses')
            self.assertFalse(receipt['game_load_verified'])
            self.assertEqual(c.ENDPOINTS['dw6_ps3'].backend.read_save(destination).raw, reviewed.raw)

    def test_source_context_changes_are_checked_for_both_directions(self):
        from tests.test_conversion import write_copy
        for source_id, target_id in [('dw6', 'dw6_ps3'), ('dw6_ps3', 'dw6')]:
            with tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                source = write_copy(folder / 'source', source_id)
                template = write_copy(folder / 'template', target_id)
                reviewed = c.prepare(source_id + '-to-' + target_id, source, template)
                ps3_path = source if source_id == 'dw6_ps3' else template
                metadata = ps3_path.parent / 'PARAM.SFO'
                metadata.write_bytes(metadata.read_bytes() + b'\0')
                with self.assertRaises(SaveError):
                    c.export(reviewed, folder / 'output')
                self.assertFalse((folder / 'output').exists())


class DW6NativeMigrationTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('DW6_SAVE') and os.environ.get('DW6_PS3_SAVE_COPIES'), 'Private native platform copies not supplied.')
    def test_native_forward_reverse_exports_preserve_all_mapped_state_and_destination_rest(self):
        sources = {'dw6': Path(os.environ['DW6_SAVE'])}
        for ps3_path in os.environ['DW6_PS3_SAVE_COPIES'].split(os.pathsep):
            sources['dw6_ps3'] = Path(ps3_path)
            for source_id, target_id in [('dw6', 'dw6_ps3'), ('dw6_ps3', 'dw6')]:
                with tempfile.TemporaryDirectory() as directory:
                    copies = {}
                    for endpoint_id, original in sources.items():
                        folder = Path(directory) / endpoint_id
                        folder.mkdir()
                        endpoint = c.ENDPOINTS[endpoint_id]
                        copy = folder / endpoint.filename
                        copy.write_bytes(original.read_bytes())
                        if endpoint.companion:
                            (folder / endpoint.companion).write_bytes((original.parent / endpoint.companion).read_bytes())
                        copies[endpoint_id] = copy
                    reviewed = c.prepare(source_id + '-to-' + target_id, copies[source_id], copies[target_id])
                    backend = c.ENDPOINTS[target_id].backend
                    spans = [(backend.OFFICER_BASE, backend.OFFICER_BASE + 41 * 168),
                             (backend.HORSE_BASE - 24, backend.HORSE_BASE - 24 + 8 * 60)]
                    cursor = 0
                    for start, end in spans:
                        self.assertEqual(reviewed.raw[cursor:start], reviewed.template.document.raw[cursor:start])
                        cursor = end
                    self.assertEqual(reviewed.raw[cursor:], reviewed.template.document.raw[cursor:])
                    destination, _backups, _receipt = c.export(reviewed, Path(directory) / 'forward')
                    reverse = c.prepare(target_id + '-to-' + source_id, destination, copies[source_id])
                    self.assertEqual(reverse.raw, copies[source_id].read_bytes())
                    # Roundtrip alone would miss a symmetrically wrong mask
                    # transformation. Compare its independently decoded value.
                    a = c.ENDPOINTS[source_id].backend.OFFICER_BASE
                    b = c.ENDPOINTS[target_id].backend.OFFICER_BASE
                    source_endian = 'little' if source_id == 'dw6' else 'big'
                    target_endian = 'little' if target_id == 'dw6' else 'big'
                    self.assertEqual(int.from_bytes(reviewed.source.document.raw[a:a + 8], source_endian),
                                     int.from_bytes(reviewed.raw[b:b + 8], target_endian))
