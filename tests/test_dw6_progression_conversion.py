"""Semantic stage-byte checks and optional independently sourced native copies."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from koei_editor import conversion as c
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw6 import progression_conversion as progress
from tests.test_conversion import fixture, write_copy


class DW6ProgressionConversionTests(unittest.TestCase):
    def test_each_direction_preserves_typed_stage_values_flags_and_unmapped_state(self):
        routes = [route for route in c.ROUTES if route.variant == 'progress']
        self.assertEqual(len(routes), 12)
        for route in routes:
            with self.subTest(route=route.id):
                source_backend, target_backend = (c.ENDPOINTS[key].backend for key in (route.source_id, route.target_id))
                source = source_backend.decode(fixture(route.source_id))
                template = target_backend.decode(fixture(route.target_id, 1))
                raw = progress.encode(source, template)
                a, ma, source_order = progress._bases(source)
                b, mb, target_order = progress._bases(template)
                expected = bytearray(c._FAMILIES['dw6'].encode(source, template))
                for index in range(45):
                    sa, tb = a + index * 20, b + index * 20
                    for relative in (0, 4, 8):
                        value = int.from_bytes(source.raw[sa + relative:sa + relative + 4], source_order)
                        expected[tb + relative:tb + relative + 4] = value.to_bytes(4, target_order)
                    expected[tb + 12:tb + 20] = source.raw[sa + 12:sa + 20]
                expected[mb:mb + 68] = source.raw[ma:ma + 68]
                self.assertEqual(raw, bytes(expected))
                reopened = target_backend.decode(raw)
                self.assertEqual(progress.gameplay(reopened), progress.gameplay(source))
                self.assertEqual(progress.encode(reopened, source), source.raw)
                self.assertEqual(len(progress.gameplay(source)), 8336)
                start = target_backend.OFFICER_BASE
                end = target_backend.HORSE_BASE - 24 + 8 * 60
                self.assertEqual(raw[:start], template.raw[:start])
                self.assertEqual(raw[end:], template.raw[end:])

    def test_native_default_time_and_asymmetric_flags_are_not_swapped_as_words(self):
        pc, ps3 = c.ENDPOINTS['dw6'].backend, c.ENDPOINTS['dw6_ps3'].backend
        data = bytearray(fixture('dw6'))
        base = pc.OFFICER_BASE + 41 * 168
        data[base:base + 12] = (10000).to_bytes(4, 'little') + (321).to_bytes(4, 'little') + (0x4f1a0).to_bytes(4, 'little')
        data[base + 12:base + 20] = bytes((1, 7, 0x61, 0x82, 1, 0xa3, 0xb4, 0xc5))
        musou = base + 900
        data[musou:musou + 4] = bytes((1, 0, 0x69, 0x93))
        result = progress.encode(pc.decode(bytes(data)), ps3.decode(fixture('dw6_ps3', 1)))
        base = ps3.OFFICER_BASE + 41 * 168
        self.assertEqual(int.from_bytes(result[base + 8:base + 12], 'big'), 0x4f1a0)
        self.assertEqual(result[base + 12:base + 20], bytes((1, 7, 0x61, 0x82, 1, 0xa3, 0xb4, 0xc5)))
        self.assertEqual(result[base + 900:base + 904], bytes((1, 0, 0x69, 0x93)))

    def test_review_receipt_and_reverse_bind_explicit_extended_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_copy(root / 'source', 'dw6')
            template = write_copy(root / 'template', 'dw6_ps3_jp', 1)
            reviewed = c.prepare('dw6-to-dw6_ps3_jp-progress', source, template)
            self.assertEqual(reviewed.gameplay_bytes, 8336)
            self.assertIn('Musou history', reviewed.route.label)
            self.assertIn('destination gallery', reviewed.route.scope_description)
            self.assertIn('Stage review: 45', ' '.join(reviewed.notes))
            self.assertIn('Musou history review: 17', ' '.join(reviewed.notes))
            for forged in (replace(reviewed, route=c.get_route('dw6-to-dw6_ps3_jp')),
                           replace(reviewed, route=c.Route('dw6', 'dw6_ps3_jp', ['progress'])),
                           replace(reviewed, notes=('Full save including active battle',))):
                with self.assertRaises(SaveError):
                    c.export(forged, root / 'forged')
            destination, _backups, receipt = c.export(reviewed, root / 'output')
            self.assertEqual(receipt['transfer_scope'], 'roster-stages-and-musou')
            self.assertEqual(receipt['gameplay_bytes'], 8336)
            self.assertEqual(receipt['gameplay_sha256'], hashlib.sha256(progress.gameplay(reviewed.source.document)).hexdigest())
            reverse = c.prepare('dw6_ps3_jp-to-dw6-progress', destination, source)
            self.assertEqual(reverse.raw, source.read_bytes())
            basic = c.prepare('dw6-to-dw6_ps3_jp', source, template)
            self.assertEqual(basic.gameplay_bytes, 7368)
            base = c.ENDPOINTS['dw6_ps3_jp'].backend.OFFICER_BASE + 41 * 168
            self.assertEqual(basic.raw[base:base + 968], template.read_bytes()[base:base + 968])


class DW6ProgressionNativeTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('DW6_SAVE') and os.environ.get('DW6_PS3_SAVE_COPIES')
                         and os.environ.get('DW6_PS3_JP_SAVE'), 'Separate native PC/US/Japanese copies not supplied.')
    def test_all_native_progress_routes_actual_exports_semantics_and_reverses(self):
        us_copies = os.environ['DW6_PS3_SAVE_COPIES'].split(os.pathsep)
        for us_copy in us_copies:
            originals = {'dw6': Path(os.environ['DW6_SAVE']), 'dw6_ps3': Path(us_copy),
                         'dw6_ps3_jp': Path(os.environ['DW6_PS3_JP_SAVE'])}
            for route in (route for route in c.ROUTES if route.variant == 'progress'
                          and route.source_id in originals and route.target_id in originals):
                with self.subTest(route=route.id), tempfile.TemporaryDirectory() as directory:
                    root, copies = Path(directory), {}
                    for key, original in originals.items():
                        endpoint = c.ENDPOINTS[key]
                        folder = root / key
                        folder.mkdir()
                        path = folder / endpoint.filename
                        path.write_bytes(original.read_bytes())
                        if endpoint.companion:
                            (folder / endpoint.companion).write_bytes((original.parent / endpoint.companion).read_bytes())
                        copies[key] = path
                    reviewed = c.prepare(route.id, copies[route.source_id], copies[route.target_id])
                    destination, _backups, receipt = c.export(reviewed, root / 'forward')
                    reverse = c.prepare(route.target_id + '-to-' + route.source_id + '-progress', destination, copies[route.source_id])
                    restored, _backups, _receipt = c.export(reverse, root / 'reverse')
                    self.assertEqual(restored.read_bytes(), copies[route.source_id].read_bytes())
                    self.assertEqual(receipt['gameplay_bytes'], 8336)
                    self.assertFalse(receipt['game_load_verified'])
                    # Native flags are bytes on both platforms. A symmetric
                    # but wrong u32 swap would also pass a reverse roundtrip.
                    source_stages, source_musou, order = progress._bases(reviewed.source.document)
                    target_stages, target_musou, target_order = progress._bases(reviewed.template.document)
                    for index in range(45):
                        a, b = source_stages + 20 * index, target_stages + 20 * index
                        self.assertEqual(reviewed.raw[b + 12:b + 20], reviewed.source.document.raw[a + 12:a + 20])
                        for relative in (0, 4, 8):
                            self.assertEqual(int.from_bytes(reviewed.raw[b + relative:b + relative + 4], target_order),
                                             int.from_bytes(reviewed.source.document.raw[a + relative:a + relative + 4], order))
                    self.assertEqual(reviewed.raw[target_musou:target_musou + 68],
                                     reviewed.source.document.raw[source_musou:source_musou + 68])
