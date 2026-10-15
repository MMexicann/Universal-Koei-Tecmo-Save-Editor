"""DW6 gallery bits and regional challenge words, IDs and preservation."""
from dataclasses import replace
import hashlib
import itertools
import os
from pathlib import Path
import tempfile
import unittest

from koei_editor import conversion as c
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw6 import campaign_conversion as campaigns
from koei_editor.games.dw6 import records_conversion as records
from tests.test_conversion import fixture, write_copy


# Independent locations rather than a computed fixed delta: western PS3 omits
# a block which remains in the Japanese profile after its complete horses.
LAYOUTS = {'dw6': (0xB4, 0x2BF6, 'little'),
           'dw6_ps3': (0xAC, 0x2BA8, 'big'),
           'dw6_ps3_eu': (0xAC, 0x2BA8, 'big'),
           'dw6_ps3_jp': (0xAC, 0x2BB6, 'big')}


def populated(game_id, salt):
    raw = bytearray(fixture(game_id, salt))
    gallery, challenges, endian = LAYOUTS[game_id]
    raw[gallery:gallery + 27] = bytes((index * 19 + salt * 53) % 256 for index in range(27))
    for index in range(50):
        at = challenges + index * 4
        # Exercise every u16 bit, including values outside ordinary scores.
        value = (index * 1237 + 0x8001 + salt * 3571) % 65536
        raw[at:at + 2] = value.to_bytes(2, endian)
        raw[at + 2:at + 4] = bytes(((index + salt * 31) % 256, (index * 7 + salt * 101) % 256))
    return bytes(raw)


def expected_records(source, template, converted_campaigns):
    """Independently assemble only the declared gallery and challenge changes."""
    sg, sc, se = LAYOUTS[source.format.id]
    tg, tc, te = LAYOUTS[template.format.id]
    result = bytearray(converted_campaigns)
    result[tg:tg + 26] = source.raw[sg:sg + 26]
    result[tg + 26] = (template.raw[tg + 26] & 0xFC) | (source.raw[sg + 26] & 3)
    for index in range(50):
        a, b = sc + index * 4, tc + index * 4
        score = int.from_bytes(source.raw[a:a + 2], se)
        result[b:b + 2] = score.to_bytes(2, te)
        result[b + 2:b + 4] = source.raw[a + 2:a + 4]
    return bytes(result)


class DW6RecordsConversionTests(unittest.TestCase):
    def test_every_direction_converts_only_u16_scores_and_known_gallery_bits(self):
        for source_id, target_id in itertools.permutations(LAYOUTS, 2):
            with self.subTest(source=source_id, target=target_id):
                source = c.ENDPOINTS[source_id].backend.decode(populated(source_id, 0))
                template = c.ENDPOINTS[target_id].backend.decode(populated(target_id, 1))
                raw = records.encode(source, template)
                self.assertEqual(raw, expected_records(source, template, campaigns.encode(source, template)))
                reopened = c.ENDPOINTS[target_id].backend.decode(raw)
                self.assertEqual(records.gameplay(reopened), records.gameplay(source))
                self.assertEqual(len(records.gameplay(source)), 11203)
                self.assertEqual(records.encode(reopened, source), source.raw)
                sg, sc, se = LAYOUTS[source_id]
                tg, tc, te = LAYOUTS[target_id]
                for index in range(50):
                    a, b = sc + index * 4, tc + index * 4
                    self.assertEqual(int.from_bytes(raw[b:b + 2], te), int.from_bytes(source.raw[a:a + 2], se))
                    self.assertEqual(raw[b + 2:b + 4], source.raw[a + 2:a + 4])
                self.assertEqual(raw[tg + 26] & 0xFC, template.raw[tg + 26] & 0xFC)
                self.assertEqual(raw[tc + 200:], template.raw[tc + 200:])

    def test_locked_source_replaces_availability_but_reserved_bits_do_not_change_hash(self):
        pc = c.ENDPOINTS['dw6'].backend
        eu = c.ENDPOINTS['dw6_ps3_eu'].backend
        raw = bytearray(populated('dw6', 0))
        raw[0xB4:0xCF] = bytes(27)
        source = pc.decode(bytes(raw))
        template = eu.decode(populated('dw6_ps3_eu', 1))
        converted = records.encode(source, template)
        self.assertEqual(converted[0xAC:0xC6], bytes(26))
        self.assertEqual(converted[0xC6] & 3, 0)
        self.assertEqual(converted[0xC6] & 0xFC, template.raw[0xC6] & 0xFC)
        raw[0xCE] = 0xFC
        changed_reserved = pc.decode(bytes(raw))
        self.assertEqual(records.gameplay(source), records.gameplay(changed_reserved))
        self.assertEqual(records.encode(changed_reserved, template), converted)
        self.assertIn('source availability', ' '.join(records.preview_notes(source, template)).lower())
        self.assertIn('reserved', ' '.join(records.preview_notes(source, template)))
        for variant in ('', 'progress', 'campaigns'):
            transform = c._VARIANTS[('dw6', variant)] if variant else c._FAMILIES['dw6']
            narrower = transform.encode(source, template)
            self.assertEqual(narrower[0xAC:0xC8], template.raw[0xAC:0xC8])
            self.assertEqual(narrower[0x2BA8:0x2C70], template.raw[0x2BA8:0x2C70])

    def test_review_receipt_and_scope_downgrade_bind_gallery_and_complete_boards(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = write_copy(root / 'source', 'dw6')
            template = write_copy(root / 'template', 'dw6_ps3_eu', 1)
            reviewed = c.prepare('dw6-to-dw6_ps3_eu-records', source, template)
            self.assertEqual(reviewed.gameplay_bytes, 11203)
            self.assertIn('Gallery review:', ' '.join(reviewed.notes))
            self.assertIn('Challenge review:', ' '.join(reviewed.notes))
            for suffix in ('', '-progress', '-campaigns'):
                with self.assertRaises(SaveError):
                    c.export(replace(reviewed, route=c.get_route('dw6-to-dw6_ps3_eu' + suffix)), root / 'forged')
            destination, _backups, receipt = c.export(reviewed, root / 'forward')
            self.assertEqual(receipt['transfer_scope'], records.TRANSFER_SCOPE)
            self.assertEqual(receipt['gameplay_bytes'], 11203)
            self.assertEqual(receipt['gameplay_sha256'], hashlib.sha256(records.gameplay(reviewed.source.document)).hexdigest())
            reverse = c.prepare('dw6_ps3_eu-to-dw6-records', destination, source)
            restored, _backups, _receipt = c.export(reverse, root / 'reverse')
            self.assertEqual(restored.read_bytes(), source.read_bytes())


class DW6RecordsNativeTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('DW6_SAVE') and os.environ.get('DW6_PS3_SAVE_COPIES')
                         and os.environ.get('DW6_PS3_JP_SAVE') and os.environ.get('DW6_PS3_EU_SAVE_COPIES'),
                         'Separate native PC/US/European/Japanese references not supplied.')
    def test_native_partial_gallery_and_nondefault_boards_all_directions_safe_exports(self):
        pc = Path(os.environ['DW6_SAVE'])
        jp = Path(os.environ['DW6_PS3_JP_SAVE'])
        us_copies = [Path(path) for path in os.environ['DW6_PS3_SAVE_COPIES'].split(os.pathsep)]
        eu_copies = [Path(path) for path in os.environ['DW6_PS3_EU_SAVE_COPIES'].split(os.pathsep)]
        originals = {'dw6': [pc], 'dw6_ps3': us_copies, 'dw6_ps3_jp': [jp], 'dw6_ps3_eu': eu_copies}
        initial_hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                          for paths in originals.values() for path in paths}
        partial_galleries, changed_boards = 0, 0
        default_pc_boards = pc.read_bytes()[0x2BF6:0x2CBE]
        for game_id, paths in originals.items():
            gallery, challenge, endian = LAYOUTS[game_id]
            for path in paths:
                document = c.ENDPOINTS[game_id].backend.read_save(path)
                raw = document.raw
                movies = raw[gallery + 5:gallery + 27]
                if sum(value.bit_count() for value in movies) < 170:
                    partial_galleries += 1
                musou = 0x29C4 if game_id == 'dw6' else 0x2984
                # Native movie endings are bit9+10*i; independently compare
                # their presence with each source's actual Musou clear byte.
                for officer in range(17):
                    ending_bit = 9 + 10 * officer
                    self.assertEqual(bool(movies[ending_bit // 8] & (1 << (ending_bit % 8))),
                                     bool(raw[musou + officer * 4 + 1]))
                canonical = bytearray()
                for index in range(50):
                    at = challenge + index * 4
                    canonical.extend(int.from_bytes(raw[at:at + 2], endian).to_bytes(2, 'little'))
                    canonical.extend(raw[at + 2:at + 4])
                    self.assertLessEqual(raw[at + 2], 41)
                if bytes(canonical) != default_pc_boards:
                    changed_boards += 1
        self.assertGreater(partial_galleries, 0, 'Supply the separately qualified partial European references.')
        self.assertGreater(changed_boards, 0, 'Supply independently played, nondefault challenge boards.')
        # Exercise every ordered endpoint pair and each reference in that pair,
        # rather than selecting one conveniently completed native profile.
        for source_id, target_id in itertools.permutations(originals, 2):
            for source_original, template_original in itertools.product(originals[source_id], originals[target_id]):
                with self.subTest(source=source_id, target=target_id), tempfile.TemporaryDirectory() as temporary:
                    root, copies = Path(temporary), {}
                    for name, game_id, original in (('source', source_id, source_original),
                                                     ('template', target_id, template_original)):
                        endpoint = c.ENDPOINTS[game_id]
                        folder = root / name
                        folder.mkdir()
                        path = folder / endpoint.filename
                        path.write_bytes(original.read_bytes())
                        if endpoint.companion:
                            (folder / endpoint.companion).write_bytes((original.parent / endpoint.companion).read_bytes())
                        copies[name] = path
                    reviewed = c.prepare(source_id + '-to-' + target_id + '-records', copies['source'], copies['template'])
                    self.assertEqual(reviewed.raw, expected_records(reviewed.source.document, reviewed.template.document,
                                                                   campaigns.encode(reviewed.source.document, reviewed.template.document)))
                    destination, _backups, receipt = c.export(reviewed, root / 'forward')
                    actual = c.ENDPOINTS[target_id].backend.read_save(destination)
                    self.assertEqual(records.gameplay(actual), records.gameplay(reviewed.source.document))
                    reverse = c.prepare(target_id + '-to-' + source_id + '-records', destination, copies['source'])
                    restored, _backups, _receipt = c.export(reverse, root / 'reverse')
                    self.assertEqual(restored.read_bytes(), copies['source'].read_bytes())
                    self.assertEqual(receipt['gameplay_bytes'], 11203)
                    if c.ENDPOINTS[target_id].companion:
                        self.assertEqual((destination.parent / 'PARAM.SFO').read_bytes(),
                                         (template_original.parent / 'PARAM.SFO').read_bytes())
        for path, before in initial_hashes.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)


if __name__ == '__main__':
    unittest.main()
