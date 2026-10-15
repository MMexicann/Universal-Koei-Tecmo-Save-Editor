"""DW7 XL typed migration, dependency groups, native cipher and preservation."""
from dataclasses import replace
from functools import lru_cache
import hashlib
import itertools
import os
from pathlib import Path
import tempfile
import unittest

from koei_editor import conversion as c
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw7xl import conversion as transform
from koei_editor.games.dw7xl import dw7xl_codec as codec
from koei_editor.games.dw7xl import dw7xl_parser as pc
from koei_editor.games.dw7xl_ps3 import parser as ps3
from tests import test_ps3_expansion as ps3_context


def numeric_fields():
    """Independent serialized map used to build expected output and masks."""
    fields = [(offset, 4) for offset in range(4, 4 + 0xC98, 4)]
    fields += [(offset, 2) for offset in range(4 + 0xC98, 4 + 0xCA4, 2)]
    fields += [(offset, 4) for offset in range(4 + 0xCA4, 4 + 0xCEC, 4)]
    fields.append((4 + 0xCEC, 2))
    for kingdom in range(4):
        base = 4 + 0xCEE + kingdom * 306
        fields += [(base + offset, 2) for offset in range(0, 206, 2)]
    legend = 4 + 0x11B8
    fields += [(legend + offset, 2) for offset in range(0, 8, 2)]
    fields += [(legend + offset, 4) for offset in range(8, 0x38C, 4)]
    fields.append((legend + 0x38C, 2))
    fields += [(legend + offset, 2) for offset in range(0x3A8, 0x3BE, 2)]
    fields += [(legend + offset, 2) for offset in range(0x3FE, 0x502, 2)]
    fields += [(offset, 2) for offset in range(4 + 0x16BC, 4 + 0x1752, 2)]
    for officer in range(92):
        base = 0x2039 + officer * 128
        fields += [(base, 4), (base + 0x70, 4)]
        fields += [(base + offset, 2) for offset in range(4, 0x6E, 2)]
        fields += [(base + offset, 2) for offset in (0x74, 0x7A, 0x7C)]
    for weapon in range(1738):
        base = 0x4E39 + weapon * 20
        fields.append((base, 4))
        fields += [(base + offset, 2) for offset in range(4, 18, 2)]
    fields += [(offset, 2) for offset in range(0xD601, 0xD6D7, 2)]
    for result in range(80):
        base = 0xD6D7 + result * 20
        fields += [(base, 4), (base + 16, 4)]
        fields += [(base + offset, 2) for offset in range(4, 16, 2)]
    return tuple(fields)


def byte_spans():
    spans = [(4 + 0x11B8 + 0x3BE, 64)]
    for officer in range(92):
        base = 0x2039 + officer * 128
        spans += [(base + 0x76, 4), (base + 0x7E, 1)]
    return tuple(spans)


@lru_cache(maxsize=8)
def fixture(endpoint_id, variant=0):
    """Procedural asymmetric bytes only; never a shipped player save."""
    if endpoint_id not in (pc.GAME_ID, ps3.GAME_ID):
        raise ValueError('Choose the DW7 XL PC or PS3 fixture explicitly.')
    payload = bytearray((offset * 31 + 17 + variant * 83) % 256 for offset in range(codec.PAYLOAD_SIZE))
    order = 'little' if endpoint_id == pc.GAME_ID else 'big'
    for offset, width in numeric_fields():
        value = (offset * 271 + 0x8103 + variant * 1337) % (1 << (width * 8))
        payload[offset:offset + width] = value.to_bytes(width, order)
    payload[:4] = codec.MAGIC if endpoint_id == pc.GAME_ID else ps3.REVISION
    payload[0xDD1F] = 0
    for kingdom in range(4):
        start = 4 + 0xCEE + kingdom * 306 + 206
        payload[start:start + 100] = bytes(100)
    for start, size in ((4 + 0x11B8 + 0x38E, 26), (4 + 0x11B8 + 0x502, 2)):
        payload[start:start + size] = bytes(size)
    if endpoint_id == pc.GAME_ID:
        return codec.encode(bytes(payload), (0x19A3 + variant * 713) % 65536)
    return bytes(payload)


def write_copy(folder, endpoint_id, variant=0, directory='BLUS30873-SAVEDATA'):
    folder.mkdir()
    path = folder / ('save.dat' if endpoint_id == pc.GAME_ID else 'APP.BIN')
    path.write_bytes(fixture(endpoint_id, variant))
    if endpoint_id == ps3.GAME_ID:
        (folder / 'PARAM.SFO').write_bytes(ps3_context.PS3ContextTests.metadata(directory))
    return path


def expected_payload(source, template):
    result = bytearray(template.payload)
    for offset, width in numeric_fields():
        value = int.from_bytes(source.payload[offset:offset + width], 'big')
        result[offset:offset + width] = value.to_bytes(width, 'little')
    for offset, size in byte_spans():
        result[offset:offset + size] = source.payload[offset:offset + size]
    return bytes(result)


class DW7XLConversionTests(unittest.TestCase):
    def test_typed_values_byte_flags_unknown_holes_and_native_seed_tail(self):
        source = ps3.decode(fixture(ps3.GAME_ID))
        template = pc.decode(fixture(pc.GAME_ID, 1))
        raw = transform.encode(source, template)
        output = pc.decode(raw)
        self.assertEqual(output.payload, expected_payload(source, template))
        self.assertEqual(output.seed, template.seed)
        self.assertEqual(output.payload[:4], codec.MAGIC)
        self.assertEqual(transform.gameplay(source), transform.gameplay(output))
        self.assertEqual(len(transform.gameplay(source)), 50138)
        # Distinct nonzero short values catch a reversible but wrong u32
        # guardian transform; all source array boundaries are checked too.
        for offset, width in numeric_fields():
            self.assertEqual(int.from_bytes(output.payload[offset:offset + width], 'little'),
                             int.from_bytes(source.payload[offset:offset + width], 'big'))
        for base, size in byte_spans():
            self.assertEqual(output.payload[base:base + size], source.payload[base:base + size])
        self.assertEqual(output.payload[0xDD1F:], template.payload[0xDD1F:])
        self.assertNotEqual(output.payload[-3:], source.payload[-3:])
        self.assertEqual(output.payload[-3:], template.payload[-3:])
        self.assertEqual(raw, codec.encode(output.payload, template.seed))

    def test_snapshot_hash_excludes_retained_padding_options_online_and_unknown_bytes(self):
        source = ps3.decode(fixture(ps3.GAME_ID))
        template = pc.decode(fixture(pc.GAME_ID, 1))
        changed = bytearray(source.raw)
        for offset in (4 + 0x1752, 0x1F7C, 0x2039 + 0x6E, 0x2039 + 0x7F,
                       0x4E39 + 18, 0xD6D7 + 1600, len(changed) - 1):
            changed[offset] ^= 0xFF
        alternate = ps3.decode(bytes(changed))
        self.assertEqual(transform.gameplay(source), transform.gameplay(alternate))
        self.assertEqual(transform.encode(source, template), transform.encode(alternate, template))
        # Source acquisition/learning states and the independent ownership
        # states must participate in the same canonical review.
        for offset in (4 + 0xC98, 4 + 0x11B8 + 0x3BE, 0x4E39 + 4,
                       4 + 0x16BC + 0x32, 0xD641 + 0x32, 0x2039 + 0x76):
            changed = bytearray(source.raw)
            changed[offset] ^= 1
            self.assertNotEqual(transform.gameplay(source), transform.gameplay(ps3.decode(bytes(changed))))

    def test_nonzero_unknown_progress_extensions_rejected_for_source_and_pc_template(self):
        source = ps3.decode(fixture(ps3.GAME_ID))
        template = pc.decode(fixture(pc.GAME_ID, 1))
        ranges = [(4 + 0xCEE + index * 306 + 206, 100) for index in range(4)]
        ranges += [(4 + 0x11B8 + 0x38E, 26), (4 + 0x11B8 + 0x502, 2)]
        output = pc.decode(transform.encode(source, template))
        for start, size in ranges:
            self.assertEqual(output.payload[start:start + size], template.payload[start:start + size])
            for offset in (start, start + size - 1):
                raw = bytearray(source.raw)
                raw[offset] = 1
                with self.subTest(offset=offset), self.assertRaisesRegex(SaveError, 'unqualified'):
                    transform.encode(ps3.decode(bytes(raw)), template)
                payload = bytearray(template.payload)
                payload[offset] = 1
                unknown_template = pc.decode(codec.encode(bytes(payload), template.seed))
                with self.subTest(template_offset=offset), self.assertRaisesRegex(SaveError, 'unqualified'):
                    transform.encode(source, unknown_template)

    def test_semantically_identical_state_is_exact_pc_noop_with_nonzero_uncovered_tail(self):
        template = pc.decode(fixture(pc.GAME_ID, 1))
        raw = bytearray(template.payload)
        raw[:4] = ps3.REVISION
        for offset, width in numeric_fields():
            raw[offset:offset + width] = int.from_bytes(template.payload[offset:offset + width], 'little').to_bytes(width, 'big')
        for kingdom in range(4):
            start = 4 + 0xCEE + kingdom * 306 + 206
            raw[start:start + 100] = bytes(100)
        for start, size in ((4 + 0x11B8 + 0x38E, 26), (4 + 0x11B8 + 0x502, 2)):
            raw[start:start + size] = bytes(size)
        self.assertNotEqual(template.payload[-1], 0)
        source = ps3.decode(bytes(raw))
        self.assertEqual(transform.gameplay(source), transform.gameplay(template))
        self.assertEqual(transform.encode(source, template), template.raw)

    def test_acquisition_learning_and_distinct_primary_mirror_state_move_together(self):
        raw = bytearray(fixture(ps3.GAME_ID))
        legend = 4 + 0x11B8
        raw[legend + 0x3BE:legend + 0x3FE] = bytes(index % 3 for index in range(64))
        for index in range(5):
            reference, meter = index * 137, index * 199
            raw[legend + 0x3A8 + index * 2:legend + 0x3AA + index * 2] = reference.to_bytes(2, 'big')
            raw[legend + 0x3B2 + index * 2:legend + 0x3B4 + index * 2] = meter.to_bytes(2, 'big')
            at = 0x4E39 + reference * 20
            raw[at + 4:at + 6] = (5 if index % 2 else 1).to_bytes(2, 'big')
            raw[at + 6:at + 8] = meter.to_bytes(2, 'big')
        raw[4 + 0xC98:4 + 0xCA4] = bytes([0xFF] * 12)
        primary, mirror = 4 + 0x16BC + 0x32, 0xD641 + 0x32
        raw[primary:primary + 2] = bytes.fromhex('1a2b')
        raw[mirror:mirror + 2] = bytes.fromhex('3c4d')
        source = ps3.decode(bytes(raw))
        output = pc.decode(transform.encode(source, pc.decode(fixture(pc.GAME_ID, 1))))
        self.assertEqual(output.payload[legend + 0x3BE:legend + 0x3FE], bytes(index % 3 for index in range(64)))
        self.assertEqual(int.from_bytes(output.payload[primary:primary + 2], 'little'), 0x1A2B)
        self.assertEqual(int.from_bytes(output.payload[mirror:mirror + 2], 'little'), 0x3C4D)
        for index in range(5):
            reference, meter = index * 137, index * 199
            at = 0x4E39 + reference * 20
            self.assertEqual(int.from_bytes(output.payload[legend + 0x3A8 + index * 2:legend + 0x3AA + index * 2], 'little'), reference)
            self.assertEqual(int.from_bytes(output.payload[legend + 0x3B2 + index * 2:legend + 0x3B4 + index * 2], 'little'), meter)
            self.assertEqual(int.from_bytes(output.payload[at + 4:at + 6], 'little'), 5 if index % 2 else 1)
            self.assertEqual(int.from_bytes(output.payload[at + 6:at + 8], 'little'), meter)
        self.assertEqual(output.payload[4 + 0xC98:4 + 0xCA4], bytes([0xFF] * 12))

    def test_suspended_and_unknown_battle_states_rejected_for_either_input(self):
        for endpoint_id, flag in itertools.product((pc.GAME_ID, ps3.GAME_ID), (1, 2, 255)):
            backend = pc if endpoint_id == pc.GAME_ID else ps3
            data = backend.decode(fixture(endpoint_id))
            payload = bytearray(data.payload)
            payload[0xDD1F] = flag
            raw = codec.encode(bytes(payload), data.seed) if endpoint_id == pc.GAME_ID else bytes(payload)
            invalid = backend.decode(raw)
            source, template = ps3.decode(fixture(ps3.GAME_ID)), pc.decode(fixture(pc.GAME_ID, 1))
            with self.subTest(endpoint=endpoint_id, flag=flag), self.assertRaisesRegex(SaveError, 'suspended'):
                transform.encode(invalid if endpoint_id == ps3.GAME_ID else source,
                                 invalid if endpoint_id == pc.GAME_ID else template)

    def test_wrong_direction_and_forged_frozen_snapshots_fail_closed(self):
        source, template = ps3.decode(fixture(ps3.GAME_ID)), pc.decode(fixture(pc.GAME_ID, 1))
        for wrong in ((template, source), (template, template), (source, source)):
            with self.assertRaises(SaveError):
                transform.encode(*wrong)
        for forged in (replace(source, payload=bytearray(source.payload)),
                       replace(source, raw=source.raw[:-1]),
                       replace(source, format=ps3.Format()),
                       replace(template, seed=template.seed ^ 1)):
            with self.assertRaises(SaveError):
                transform.gameplay(forged)

    def test_review_receipt_and_actual_export_retain_pc_context_and_source_files(self):
        for directory in ('BLUS30873-SAVEDATA', 'BLES01496-SAVEDATA'):
            with self.subTest(region=directory), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = write_copy(root / 'source', ps3.GAME_ID, directory=directory)
                template = write_copy(root / 'template', pc.GAME_ID, 1)
                initial = source.read_bytes(), template.read_bytes()
                reviewed = c.prepare('dw7xl_ps3-to-dw7xl', source, template)
                self.assertEqual(reviewed.raw, transform.encode(reviewed.source.document, reviewed.template.document))
                self.assertIn('92', ' '.join(reviewed.notes))
                self.assertIn('1,738', ' '.join(reviewed.notes))
                destination, backups, receipt = c.export(reviewed, root / 'output')
                self.assertEqual(destination.read_bytes(), reviewed.raw)
                self.assertEqual(pc.read_save(destination).payload,
                                 expected_payload(reviewed.source.document, reviewed.template.document))
                self.assertTrue(backups)
                self.assertEqual(receipt['transfer_scope'], transform.TRANSFER_SCOPE)
                self.assertEqual(receipt['gameplay_sha256'], hashlib.sha256(transform.gameplay(reviewed.source.document)).hexdigest())
                self.assertFalse(receipt['game_load_verified'])
                self.assertEqual(source.read_bytes(), initial[0])
                self.assertEqual(template.read_bytes(), initial[1])
                self.assertFalse((destination.parent / 'PARAM.SFO').exists())
                with self.assertRaises(SaveError):
                    c.get_route('dw7xl-to-dw7xl_ps3')


class DW7XLNativeConversionTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('DW7XL_PC_SAVE_COPIES') and os.environ.get('DW7XL_PS3_SAVE_COPIES'),
                         'Separate native DW7 XL PS3 and Definitive Edition PC copies not supplied.')
    def test_every_native_ps3_context_and_pc_progress_state_typed_exports_and_original_preservation(self):
        pc_copies = [Path(path) for path in os.environ['DW7XL_PC_SAVE_COPIES'].split(os.pathsep)]
        ps3_copies = [Path(path) for path in os.environ['DW7XL_PS3_SAVE_COPIES'].split(os.pathsep)]
        initial = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in pc_copies + ps3_copies}
        for original_source, original_template in itertools.product(ps3_copies, pc_copies):
            with self.subTest(source=original_source.parent.name, template=original_template.parent.name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source_dir, target_dir = root / 'source', root / 'template'
                source_dir.mkdir()
                target_dir.mkdir()
                source, template = source_dir / 'APP.BIN', target_dir / 'save.dat'
                source.write_bytes(original_source.read_bytes())
                metadata = (original_source.parent / 'PARAM.SFO').read_bytes()
                (source_dir / 'PARAM.SFO').write_bytes(metadata)
                template.write_bytes(original_template.read_bytes())
                reviewed = c.prepare('dw7xl_ps3-to-dw7xl', source, template)
                destination, _backups, receipt = c.export(reviewed, root / 'output')
                reopened = pc.read_save(destination)
                self.assertEqual(reopened.payload, expected_payload(reviewed.source.document, reviewed.template.document))
                self.assertEqual(reopened.seed, reviewed.template.document.seed)
                self.assertEqual(reopened.payload[0xDD1F:], reviewed.template.document.payload[0xDD1F:])
                self.assertEqual(transform.gameplay(reopened), transform.gameplay(reviewed.source.document))
                self.assertEqual(receipt['gameplay_bytes'], len(transform.gameplay(reviewed.source.document)))
                self.assertFalse(receipt['game_load_verified'])
                self.assertEqual((source_dir / 'PARAM.SFO').read_bytes(), metadata)
        for path, checksum in initial.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), checksum)


if __name__ == '__main__':
    unittest.main()
