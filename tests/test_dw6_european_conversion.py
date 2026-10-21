"""European native framing, exact metadata boundaries and copied migrations."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from koei_editor import conversion as c
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw6 import converter, progression_conversion, campaign_conversion, records_conversion
from koei_editor.games.dw6_ps3 import european_export as eu, japanese_export as jp
from tests.test_conversion import fixture, write_copy
from tests import test_ps3_expansion as ps3_context


class EuropeanDW6ConversionTests(unittest.TestCase):
    def test_exact_format_size_order_and_frozen_regional_identity(self):
        raw = fixture(eu.GAME_ID)
        document = eu.decode(raw)
        self.assertEqual(eu.serialize(document, {}), raw)
        for invalid in (raw[:-1], raw + b'\0', bytes(eu.SAVE_SIZE), bytearray(raw)):
            with self.assertRaises(SaveError):
                eu.decode(invalid)
        for wrong_id in (None, 'dw6', 'dw6_ps3', jp.GAME_ID, 'dw6_empires'):
            with self.assertRaises(SaveError):
                eu.decode(raw, wrong_id)
        changed = bytearray(raw)
        offset = eu.OFFICER_BASE + eu.OFFICER_STRIDE + 136
        changed[offset:offset + 4] = (1).to_bytes(4, 'little')
        with self.assertRaises(SaveError):
            eu.decode(bytes(changed))
        for forged in (replace(document, format=eu.Format(eu.GAME_ID)),
                       replace(document, format=jp.FORMAT),
                       replace(document, raw=bytearray(raw)),
                       replace(document, payload=bytearray(raw)),
                       replace(document, payload=raw[:-1])):
            with self.assertRaises(SaveError):
                converter.gameplay(forged)
        with self.assertRaises(SaveError):
            eu.serialize(document, {'stage_0_available': 1})
        # Equal US/EU file sizes do not make frozen snapshots interchangeable.
        with self.assertRaises(SaveError):
            eu.validate_document(c.ENDPOINTS['dw6_ps3'].backend.decode(fixture('dw6_ps3')))

    def test_original_european_context_is_required_despite_shared_us_size(self):
        for directory in ('BLUS30110-SAVEDATA', 'BLJM60041-SAVEDATA', 'BLES00540-SAVEDATA', None, 'oversized'):
            with self.subTest(directory=directory), tempfile.TemporaryDirectory() as temporary:
                path = write_copy(Path(temporary) / 'copy', eu.GAME_ID)
                metadata = path.parent / 'PARAM.SFO'
                if directory is None:
                    metadata.unlink()
                elif directory == 'oversized':
                    metadata.write_bytes(metadata.read_bytes() + bytes(4097))
                else:
                    metadata.write_bytes(ps3_context.PS3ContextTests.metadata(directory))
                with self.assertRaises(SaveError):
                    eu.read_save(path)

    def test_all_european_routes_have_distinct_scopes_and_actual_export_receipts(self):
        routes = [route for route in c.ROUTES if eu.GAME_ID in (route.source_id, route.target_id)]
        self.assertEqual(len(routes), 40)
        self.assertEqual(len(c.ROUTES), 145)
        self.assertEqual(len(set(route.label for route in c.ROUTES)), 145)
        for route in routes:
            with self.subTest(route=route.id), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = write_copy(root / 'source', route.source_id)
                template = write_copy(root / 'template', route.target_id, 1)
                original, original_template = source.read_bytes(), template.read_bytes()
                reviewed = c.prepare(route.id, source, template)
                destination, _backups, receipt = c.export(reviewed, root / 'forward')
                expected_size = {'': 7368, 'progress': 8336, 'campaigns': 10976, 'records': 11203}[route.variant]
                self.assertEqual(receipt['gameplay_bytes'], expected_size)
                self.assertEqual(receipt['transfer_scope'], route.transfer_scope)
                self.assertFalse(receipt['game_load_verified'])
                suffix = '-' + route.variant if route.variant else ''
                reverse = c.prepare(route.target_id + '-to-' + route.source_id + suffix, destination, source)
                self.assertEqual(reverse.raw, original)
                self.assertEqual(source.read_bytes(), original)
                self.assertEqual(template.read_bytes(), original_template)
                endpoint = c.ENDPOINTS[route.target_id]
                if endpoint.companion:
                    self.assertEqual((destination.parent / endpoint.companion).read_bytes(),
                                     (template.parent / endpoint.companion).read_bytes())


class EuropeanDW6NativeTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('DW6_PS3_EU_SAVE_COPIES') and os.environ.get('DW6_SAVE')
                         and os.environ.get('DW6_PS3_SAVE_COPIES') and os.environ.get('DW6_PS3_JP_SAVE'),
                         'Separate native PC/US/European/Japanese references not supplied.')
    def test_each_native_european_reference_all_routes_readback_values_and_untouched_remainder(self):
        for european in os.environ['DW6_PS3_EU_SAVE_COPIES'].split(os.pathsep):
            originals = {'dw6': Path(os.environ['DW6_SAVE']),
                         'dw6_ps3': Path(os.environ['DW6_PS3_SAVE_COPIES'].split(os.pathsep)[0]),
                         jp.GAME_ID: Path(os.environ['DW6_PS3_JP_SAVE']), eu.GAME_ID: Path(european)}
            for route in (r for r in c.ROUTES if eu.GAME_ID in (r.source_id, r.target_id)
                          and r.source_id in originals and r.target_id in originals):
                with self.subTest(reference=Path(european).parent.name, route=route.id), tempfile.TemporaryDirectory() as temporary:
                    root, copies = Path(temporary), {}
                    hashes = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in originals.items()}
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
                    suffix = '-' + route.variant if route.variant else ''
                    reverse = c.prepare(route.target_id + '-to-' + route.source_id + suffix,
                                        destination, copies[route.source_id])
                    restored, _backups, _receipt = c.export(reverse, root / 'reverse')
                    self.assertEqual(restored.read_bytes(), copies[route.source_id].read_bytes())
                    backend = c.ENDPOINTS[route.target_id].backend
                    start, end = backend.OFFICER_BASE, backend.HORSE_BASE - 24 + 8 * 60
                    if route.variant in ('campaigns', 'records'):
                        start -= 20 * 132
                    allowed = [(start, end)]
                    if route.variant == 'records':
                        gallery, challenges = {'dw6': (0xB4, 0x2BF6), 'dw6_ps3': (0xAC, 0x2BA8),
                                               'dw6_ps3_eu': (0xAC, 0x2BA8), 'dw6_ps3_jp': (0xAC, 0x2BB6)}[route.target_id]
                        allowed.extend(((gallery, gallery + 27), (challenges, challenges + 200)))
                        self.assertEqual(reviewed.raw[gallery + 26] & 0xFC,
                                         reviewed.template.document.raw[gallery + 26] & 0xFC)
                    expected = bytearray(reviewed.template.document.raw)
                    for left, right in allowed:
                        expected[left:right] = reviewed.raw[left:right]
                    self.assertEqual(reviewed.raw, bytes(expected))
                    transform = {'': converter, 'progress': progression_conversion, 'campaigns': campaign_conversion,
                                 'records': records_conversion}[route.variant]
                    actual = backend.read_save(destination)
                    self.assertEqual(transform.gameplay(actual), transform.gameplay(reviewed.source.document))
                    # Independent values catch reversible but wrong word/byte swaps.
                    a = c.ENDPOINTS[route.source_id].backend.OFFICER_BASE
                    order = 'little' if route.source_id == 'dw6' else 'big'
                    target_order = 'little' if route.target_id == 'dw6' else 'big'
                    for i in range(41):
                        sa, tb = a + i * 168, backend.OFFICER_BASE + i * 168
                        self.assertEqual(int.from_bytes(actual.raw[tb:tb + 8], target_order),
                                         int.from_bytes(reviewed.source.document.raw[sa:sa + 8], order))
                        self.assertEqual(actual.raw[tb + 164:tb + 168], reviewed.source.document.raw[sa + 164:sa + 168])
                    self.assertEqual(receipt['gameplay_bytes'], {'': 7368, 'progress': 8336, 'campaigns': 10976,
                                                               'records': 11203}[route.variant])
                    for key, original in originals.items():
                        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), hashes[key])
