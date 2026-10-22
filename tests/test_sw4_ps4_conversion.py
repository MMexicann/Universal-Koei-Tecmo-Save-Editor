"""Original PS4 gold transfers preserve every unrelated native PC byte.

Procedural fixtures verify software behavior, not in-game loading. Optional
private copies exercise original-context native files without publishing them.
"""
from pathlib import Path
import os
import tempfile
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.sw4dx import ps4_export as ps4
from koei_editor.games.sw4dx import samurai4dx_codec as codec
from koei_editor.games.sw4dx import samurai4dx_parser as pc
from koei_editor.games.sw4dx.ps4_conversion import TRANSFER
from koei_editor.shared.experimental_limits import experimental_limits
from tests.test_samurai4dx_format import procedural_raw, seal as seal_pc
from tests.test_sw4_ps4_source import fixture, context


class SW4PS4ConversionTests(unittest.TestCase):
    def test_exact_source_gold_and_entire_pc_remainder_are_preserved(self):
        target = pc.decode(procedural_raw())
        for gold in (0, 1, 777, 999999):
            with self.subTest(gold=gold):
                source = ps4.decode(fixture(gold=gold))
                raw = TRANSFER.encode(source, target)
                reopened = pc.decode(raw)
                self.assertEqual(pc.field_map(reopened)['gold'].value(reopened.payload), gold)
                self.assertEqual(TRANSFER.gameplay(source), gold.to_bytes(4, 'little'))
                allowed = set(range(pc.GOLD_OFFSET, pc.GOLD_OFFSET + 4))
                for offset in codec.CHECKSUM_OFFSETS:
                    allowed.update(range(offset, offset + 4))
                differences = {i for i, (a, b) in enumerate(zip(target.payload, reopened.payload)) if a != b}
                self.assertTrue(differences <= allowed)
                self.assertEqual(len(reopened.payload), len(target.payload))
                self.assertEqual(raw[:codec.PAYLOAD_OFFSET - 4], target.raw[:codec.PAYLOAD_OFFSET - 4])
                self.assertEqual(reopened.seed, target.seed)
                self.assertEqual(source.raw, fixture(gold=gold))
                self.assertEqual(target.raw, procedural_raw())
                self.assertEqual(TRANSFER.preview_notes(source, target), (f'Gold: 1,234 → {gold:,}',))

    def test_strict_changed_target_limits_and_exact_unusual_noop(self):
        target = pc.decode(procedural_raw())
        for gold in (1000000, 0xFFFFFFFF):
            with self.subTest(gold=gold):
                source = ps4.decode(fixture(gold=gold))
                with experimental_limits(True), self.assertRaises(SaveError):
                    TRANSFER.encode(source, target)
                payload = bytearray(target.payload)
                payload[pc.GOLD_OFFSET:pc.GOLD_OFFSET + 4] = gold.to_bytes(4, 'little')
                unusual = pc.decode(seal_pc(payload, seed=target.seed,
                                           header=target.raw[:codec.PAYLOAD_OFFSET - 4]))
                self.assertEqual(TRANSFER.encode(source, unusual), unusual.raw)
        same = ps4.decode(fixture(gold=1234))
        self.assertEqual(TRANSFER.encode(same, target), target.raw)

    def test_one_way_only_and_corrupted_source_are_rejected(self):
        source = ps4.decode(fixture(gold=800))
        target = pc.decode(procedural_raw())
        self.assertEqual(TRANSFER.SUPPORTED_DIRECTIONS,
                         frozenset({('sw4_ps4', 'samurai4dx')}))
        with self.assertRaises(SaveError):
            TRANSFER.encode(target, source)
        damaged = bytearray(source.raw)
        damaged[0x7842] ^= 1
        with self.assertRaises(SaveError):
            TRANSFER.encode(ps4.decode(bytes(damaged)), target)
        from koei_editor.games.sw4_ps3 import parser as ps3
        from tests.test_ps3_expansion import fixture as ps3_fixture
        with self.assertRaises(SaveError):
            TRANSFER.encode(ps3.decode(ps3_fixture(ps3)), target)

    def test_registered_plan_export_backups_and_changed_metadata(self):
        from koei_editor import conversion as c
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / 'source' / 'app.dat'
            source.parent.mkdir()
            source.write_bytes(fixture(gold=777))
            sfo = source.parent / 'sce_sys' / 'param.sfo'
            sfo.parent.mkdir()
            sfo.write_bytes(context())
            template = folder / 'template.dat'
            template.write_bytes(procedural_raw())
            route = 'sw4_ps4-to-samurai4dx-ps4-gold'
            plan = c.prepare(route, source, template)
            output, backups, receipt = c.export(plan, folder / 'converted')
            reopened = pc.read_save(output)
            self.assertEqual(pc.field_map(reopened)['gold'].value(reopened.payload), 777)
            self.assertEqual(receipt['transfer_scope'], 'sw4-ps4-gold-only')
            self.assertEqual(receipt['gameplay_bytes'], 4)
            self.assertFalse(receipt['game_load_verified'])
            self.assertEqual([backup.read_bytes() for backup in backups],
                             [source.read_bytes(), template.read_bytes()])
            self.assertEqual(source.read_bytes(), fixture(gold=777))
            self.assertEqual(template.read_bytes(), procedural_raw())
            self.assertEqual(sfo.read_bytes(), context())
            with self.assertRaises(SaveError):
                c.get_route('samurai4dx-to-sw4_ps4-ps4-gold')
            sfo.write_bytes(context() + b'\0')
            with self.assertRaises(SaveError):
                c.export(plan, folder / 'stale')
            self.assertFalse((folder / 'stale').exists())


@unittest.skipUnless(os.environ.get('SW4_PS4_US_COPY') and os.environ.get('SW4DX_SAVE_COPY'),
                     'Paired private original-context PS4 and native PC copies not supplied.')
class NativeSW4PS4ConversionTests(unittest.TestCase):
    def test_native_source_to_native_pc_retains_all_unrelated_payload(self):
        source = ps4.read_save(os.environ['SW4_PS4_US_COPY'])
        template = pc.read_save(os.environ['SW4DX_SAVE_COPY'])
        original_source, original_target = source.raw, template.raw
        gold = ps4.field_map(source)['gold'].value(source.payload)
        if gold != pc.field_map(template)['gold'].value(template.payload) and gold > 999999:
            with self.assertRaises(SaveError):
                TRANSFER.encode(source, template)
            return
        output = pc.decode(TRANSFER.encode(source, template))
        self.assertEqual(pc.field_map(output)['gold'].value(output.payload), gold)
        allowed = set(range(pc.GOLD_OFFSET, pc.GOLD_OFFSET + 4))
        for offset in codec.CHECKSUM_OFFSETS:
            allowed.update(range(offset, offset + 4))
        self.assertTrue({i for i, (a, b) in enumerate(zip(template.payload, output.payload))
                         if a != b} <= allowed)
        self.assertEqual(output.raw[:codec.PAYLOAD_OFFSET - 4], template.raw[:codec.PAYLOAD_OFFSET - 4])
        self.assertEqual(output.seed, template.seed)
        self.assertEqual(Path(os.environ['SW4_PS4_US_COPY']).read_bytes(), original_source)
        self.assertEqual(Path(os.environ['SW4DX_SAVE_COPY']).read_bytes(), original_target)
