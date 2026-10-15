"""Musou slot word/byte semantics, scope binding and native copied exports."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from koei_editor import conversion as c
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw6 import campaign_conversion as campaigns
from tests.test_conversion import fixture, write_copy


class DW6CampaignConversionTests(unittest.TestCase):
    def test_all_directions_convert_each_word_preserve_result_bytes_and_destination_remainder(self):
        routes = [r for r in c.ROUTES if r.variant == 'campaigns']
        self.assertEqual(len(routes), 30)
        words = tuple(range(0, 20, 4)) + tuple(20 + stage * 16 + r for stage in range(6) for r in (0, 4, 8)) + (116, 120, 124, 128)
        for route in routes:
            with self.subTest(route=route.id):
                source_backend, target_backend = [c.ENDPOINTS[key].backend for key in (route.source_id, route.target_id)]
                source_order = 'little' if route.source_id == 'dw6' else 'big'
                target_order = 'little' if route.target_id == 'dw6' else 'big'
                source = source_backend.decode(fixture(route.source_id))
                template = target_backend.decode(fixture(route.target_id, 1))
                raw = campaigns.encode(source, template)
                a, b = source_backend.OFFICER_BASE - 2640, target_backend.OFFICER_BASE - 2640
                expected = bytearray(c._VARIANTS[('dw6', 'progress')].encode(source, template))
                for slot in range(20):
                    sa, tb = a + slot * 132, b + slot * 132
                    expected[tb:tb + 132] = source.raw[sa:sa + 132]
                    for relative in words:
                        value = int.from_bytes(source.raw[sa + relative:sa + relative + 4], source_order)
                        expected[tb + relative:tb + relative + 4] = value.to_bytes(4, target_order)
                    for stage in range(6):
                        relative = 20 + stage * 16 + 12
                        self.assertEqual(raw[tb + relative:tb + relative + 4], source.raw[sa + relative:sa + relative + 4])
                self.assertEqual(raw, bytes(expected))
                reopened = target_backend.decode(raw)
                self.assertEqual(campaigns.gameplay(reopened), campaigns.gameplay(source))
                self.assertEqual(campaigns.encode(reopened, source), source.raw)
                self.assertEqual(len(campaigns.gameplay(source)), 10976)
                self.assertEqual(raw[:b], template.raw[:b])
                end = target_backend.HORSE_BASE - 24 + 8 * 60
                self.assertEqual(raw[end:], template.raw[end:])

    def test_empty_source_slots_replace_destination_without_touching_other_scopes(self):
        pc, eu = c.ENDPOINTS['dw6'].backend, c.ENDPOINTS['dw6_ps3_eu'].backend
        data = bytearray(fixture('dw6'))
        base = pc.OFFICER_BASE - 2640
        record = bytearray(132)
        for stage in range(6):
            record[20 + stage * 16 + 8:20 + stage * 16 + 12] = (0x4f1a0).to_bytes(4, 'little')
        for relative, value in ((116, 17), (120, 5), (124, 0), (128, 8)):
            record[relative:relative + 4] = value.to_bytes(4, 'little')
        data[base:base + 132] = record
        source, template = pc.decode(bytes(data)), eu.decode(fixture('dw6_ps3_eu', 1))
        target_base = eu.OFFICER_BASE - 2640
        raw = campaigns.encode(source, template)
        self.assertEqual(raw[target_base:target_base + 20], bytes(20))
        self.assertEqual(int.from_bytes(raw[target_base + 116:target_base + 120], 'big'), 17)
        for variant in ('', 'progress'):
            transform = c._VARIANTS[('dw6', variant)] if variant else c._FAMILIES['dw6']
            self.assertEqual(transform.encode(source, template)[target_base:target_base + 2640],
                             template.raw[target_base:target_base + 2640])

    def test_scope_review_hash_and_receipt_include_slots_and_refuse_downgrades(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = write_copy(root / 'source', 'dw6')
            template = write_copy(root / 'template', 'dw6_ps3_eu', 1)
            reviewed = c.prepare('dw6-to-dw6_ps3_eu-campaigns', source, template)
            self.assertIn('20 Musou', reviewed.route.scope_description)
            self.assertIn('Musou slot review: 20', ' '.join(reviewed.notes))
            self.assertIn('interim', ' '.join(reviewed.notes))
            self.assertEqual(reviewed.gameplay_bytes, 10976)
            for other in ('dw6-to-dw6_ps3_eu', 'dw6-to-dw6_ps3_eu-progress'):
                with self.assertRaises(SaveError):
                    c.export(replace(reviewed, route=c.get_route(other)), root / 'forged')
            destination, _backups, receipt = c.export(reviewed, root / 'forward')
            self.assertEqual(receipt['transfer_scope'], 'roster-stages-musou-and-slots')
            self.assertEqual(receipt['gameplay_bytes'], 10976)
            self.assertEqual(receipt['gameplay_sha256'], hashlib.sha256(campaigns.gameplay(reviewed.source.document)).hexdigest())
            reverse = c.prepare('dw6_ps3_eu-to-dw6-campaigns', destination, source)
            self.assertEqual(reverse.raw, source.read_bytes())


class DW6CampaignNativeTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('DW6_SAVE') and os.environ.get('DW6_PS3_SAVE_COPIES')
                         and os.environ.get('DW6_PS3_JP_SAVE'), 'Native PC/US/Japanese references not supplied.')
    def test_each_original_region_direction_copies_native_slots_and_preserves_other_bytes(self):
        for us in os.environ['DW6_PS3_SAVE_COPIES'].split(os.pathsep):
            originals = {'dw6': Path(os.environ['DW6_SAVE']), 'dw6_ps3': Path(us),
                         'dw6_ps3_jp': Path(os.environ['DW6_PS3_JP_SAVE'])}
            for route in (r for r in c.ROUTES if r.variant == 'campaigns'
                          and r.source_id in originals and r.target_id in originals):
                with self.subTest(route=route.id), tempfile.TemporaryDirectory() as temporary:
                    root, copies = Path(temporary), {}
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
                    destination, _backups, _receipt = c.export(reviewed, root / 'forward')
                    reverse = c.prepare(route.target_id + '-to-' + route.source_id + '-campaigns',
                                        destination, copies[route.source_id])
                    restored, _backups, _receipt = c.export(reverse, root / 'reverse')
                    self.assertEqual(restored.read_bytes(), copies[route.source_id].read_bytes())
                    a, order = campaigns._base(reviewed.source.document)
                    b, target_order = campaigns._base(reviewed.template.document)
                    for slot in range(20):
                        sa, tb = a + slot * 132, b + slot * 132
                        for relative in (0, 4, 8, 12, 16, 116, 120, 124, 128):
                            self.assertEqual(int.from_bytes(reviewed.raw[tb + relative:tb + relative + 4], target_order),
                                             int.from_bytes(reviewed.source.document.raw[sa + relative:sa + relative + 4], order))
                        for stage in range(6):
                            relative = 20 + stage * 16 + 12
                            self.assertEqual(reviewed.raw[tb + relative:tb + relative + 4],
                                             reviewed.source.document.raw[sa + relative:sa + relative + 4])
                    self.assertEqual(reviewed.raw[:b], reviewed.template.document.raw[:b])
                    backend = c.ENDPOINTS[route.target_id].backend
                    end = backend.HORSE_BASE - 24 + 8 * 60
                    self.assertEqual(reviewed.raw[end:], reviewed.template.document.raw[end:])
