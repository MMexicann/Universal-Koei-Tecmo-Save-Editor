"""Qualified PS4 base-stat/resource transfer leaves all progression opaque.

The source code facts identify five exact u16 cells for145 playable records.
Procedural tests establish software preservation, not in-game loading.
"""
from pathlib import Path
import os
import tempfile
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.wo3u import ps4_export as ps4, wo3u_parser as pc
from koei_editor.games.wo3u.ps4_conversion import TRANSFER, STATS_TRANSFER
from koei_editor.game_registry import get_game
from koei_editor.shared.experimental_limits import experimental_limits
from tests.test_wo3u_ps4_export import fixture as resource_fixture
from tests.test_wo3u_format import procedural_raw as pc_fixture


def fixture():
    raw = bytearray(resource_fixture())
    for index, field in enumerate(ps4.STATS):
        value = 110 + index % 60 if field.id.endswith('_speed') else 200 + index % 700
        raw[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    return bytes(raw)


class WO3UPS4StatsTransferTests(unittest.TestCase):
    def test_every_source_value_and_complete_pc_remainder_are_exact(self):
        source, template = ps4.decode(fixture()), pc.decode(pc_fixture())
        raw = STATS_TRANSFER.encode(source, template)
        output = pc.decode(raw)
        allowed = {offset for field in ps4.SOURCE_FIELDS
                   for offset in range(field.offset, field.offset + field.size)}
        self.assertEqual(len(ps4.STATS), 725)
        self.assertEqual(len(ps4.SOURCE_FIELDS), 1079)
        self.assertEqual(len(allowed), 1805)
        self.assertEqual(len(STATS_TRANSFER.gameplay(source)), 1805)
        self.assertEqual(STATS_TRANSFER.gameplay(source), STATS_TRANSFER.gameplay(output))
        for offset, (before, after) in enumerate(zip(template.raw, output.raw)):
            self.assertEqual(after, source.raw[offset] if offset in allowed else before)
        # Five internal records and all saved-state snapshots remain opaque.
        self.assertEqual(output.raw[0xECE8 + 145 * 0x2B0:0x28008],
                         template.raw[0xECE8 + 145 * 0x2B0:0x28008])
        self.assertEqual(output.raw[0x28008:0xC800C], template.raw[0x28008:0xC800C])
        self.assertEqual(source.raw, fixture())
        self.assertEqual(template.raw, pc_fixture())
        self.assertEqual(TRANSFER.SUPPORTED_DIRECTIONS, STATS_TRANSFER.SUPPORTED_DIRECTIONS)
        self.assertNotEqual(TRANSFER.TRANSFER_SCOPE, STATS_TRANSFER.TRANSFER_SCOPE)

    def test_narrower_scope_never_changes_stats(self):
        source, template = ps4.decode(fixture()), pc.decode(pc_fixture())
        output = TRANSFER.encode(source, template)
        for field in ps4.STATS:
            self.assertEqual(output[field.offset:field.offset + field.size],
                             template.raw[field.offset:field.offset + field.size])
        with self.assertRaises(SaveError):
            STATS_TRANSFER.encode(template, source)

    def test_new_out_of_range_stats_rejected_even_with_experimental_policy(self):
        source, template = ps4.decode(fixture()), pc.decode(pc_fixture())
        for key, value in (('officer_0_health', 1000), ('officer_0_musou', 1000),
                           ('officer_0_attack', 1000), ('officer_0_defense', 1000),
                           ('officer_0_speed', 181), ('officer_144_speed', 65535)):
            field = ps4.field_map(source)[key]
            raw = bytearray(source.raw)
            raw[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
            with self.subTest(key=key), experimental_limits(True), self.assertRaises(SaveError):
                STATS_TRANSFER.encode(ps4.decode(bytes(raw)), template)
        self.assertEqual(template.raw, pc_fixture())

    def test_exact_unusual_opened_pc_stat_is_preserved_as_noop(self):
        source_raw = bytearray(fixture())
        field = ps4.field_map(ps4.decode(bytes(source_raw)))['officer_0_speed']
        source_raw[field.offset:field.offset + field.size] = (200).to_bytes(2, 'little')
        source = ps4.decode(bytes(source_raw))
        target_raw = bytearray(pc_fixture())
        target_raw[field.offset:field.offset + field.size] = (200).to_bytes(2, 'little')
        template = pc.decode(bytes(target_raw))
        output = pc.decode(STATS_TRANSFER.encode(source, template))
        self.assertEqual(pc.field_map(output)[field.id].value(output.payload), 200)
        self.assertEqual(output.raw[field.offset:field.offset + field.size],
                         template.raw[field.offset:field.offset + field.size])

    def test_guarded_pc_save_as_preserves_sources_and_all_unmapped_bytes(self):
        source = ps4.decode(fixture())
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            path = folder / 'SAVEDATA.BIN'
            path.write_bytes(pc_fixture())
            template = pc.read_save(path)
            changes = {key: ps4.field_map(source)[key].value(source.payload) for key in STATS_TRANSFER.keys}
            adapter = get_game('wo3u').get_scalar_adapter()
            output = adapter.save_as(template, changes, folder / 'converted.bin')
            self.assertEqual(output.raw, STATS_TRANSFER.encode(source, template))
            self.assertEqual(path.read_bytes(), template.raw)
            self.assertEqual(source.raw, fixture())
            backups = [candidate for candidate in folder.rglob('*')
                       if candidate.suffix.lower() == '.bin' and candidate not in (path, output.source)]
            self.assertTrue(backups)
            self.assertTrue(all(candidate.read_bytes() == template.raw for candidate in backups))

    @unittest.skipUnless(os.environ.get('WO3U_PS4_REFERENCE') and os.environ.get('WO3U_SAVE_COPY'),
                         'Paired private PS4 and PC native payload references not supplied.')
    def test_native_payload_reference_into_pc_template(self):
        source = ps4.decode(Path(os.environ['WO3U_PS4_REFERENCE']).read_bytes())
        template = pc.decode(Path(os.environ['WO3U_SAVE_COPY']).read_bytes())
        output = pc.decode(STATS_TRANSFER.encode(source, template))
        self.assertEqual(STATS_TRANSFER.gameplay(output), STATS_TRANSFER.gameplay(source))
        allowed = {offset for field in ps4.SOURCE_FIELDS
                   for offset in range(field.offset, field.offset + field.size)}
        changed = {i for i, (a, b) in enumerate(zip(template.raw, output.raw)) if a != b}
        self.assertLessEqual(changed, allowed)
        self.assertEqual(output.raw[0x28008:0xC800C], template.raw[0x28008:0xC800C])
