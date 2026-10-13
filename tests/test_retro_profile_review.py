"""Independent native globals, copy boundaries and ownership review.

Generated state geometry does not claim native campaign or in-game evidence.
"""
import unittest

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.gemfire_nes import parser as gemfire_nes
from koei_editor.games.gemfire_snes import parser as gemfire_snes
from koei_editor.games.nobunaga_ambition_nes import parser as nobunaga
from tests.test_gemfire_battery import procedural_raw as gemfire_fixture
from tests.test_nobunaga_ambition_nes import procedural_raw as nobunaga_fixture


class RetroProfileReviewTests(unittest.TestCase):
    def test_snes_global_addresses_select_native_player_faction(self):
        raw = bytearray(gemfire_fixture('snes'))
        for base in (0x800, 0x1000):
            # State C004, month C007, players C028/C029. These globals do
            # not shift together with the C039/C0B1/C331 record arrays.
            raw[base + 3] = 12
            raw[base + 0x24:base + 0x26] = bytes((1, 255))
            # Contradictory former NES-like globals detect false ownership.
            raw[base + 7] = 0
            raw[base + 0x28:base + 0x2A] = bytes((0, 255))
        adapter = get_game('gemfire_snes').get_scalar_adapter()
        document = adapter.decode(raw)
        fields = adapter.field_map(document)
        self.assertEqual(len(fields), 10)
        for base in ('0800', '1000'):
            self.assertIn(f'state_{base}_province_1_gold', fields)
            self.assertNotIn(f'state_{base}_province_0_gold', fields)
        self.assertEqual(adapter.serialize(document, {}), bytes(raw))
        with self.assertRaises(SaveError):
            adapter.stage(document, {}, 'state_0800_province_0_gold', 999)

    def test_native_resource_edits_can_spell_footer_inside_existing_state(self):
        for platform in ('nes', 'snes'):
            with self.subTest(platform=platform):
                raw = bytearray(gemfire_fixture(platform))
                record = 0x800 + 0x32D
                raw[record + 11] = ord('I')  # Opaque byte must stay preserved.
                adapter = get_game('gemfire_' + platform).get_scalar_adapter()
                document = adapter.decode(raw)
                changes = {f'state_0800_province_0_{key}': value
                           for key, value in (('loyalty', 75), ('farming', 79), ('protection', 69))}
                output = adapter.serialize(document, changes)
                self.assertEqual(output[record + 8:record + 12], b'KOEI')
                reopened = adapter.decode(output)
                self.assertEqual(set(adapter.field_map(reopened)), set(adapter.field_map(document)))
                touched = {offset for offset, (before, after) in enumerate(zip(raw, output)) if before != after}
                self.assertLessEqual(touched, {record + 8, record + 9, record + 10})

    def test_generic_koei_signature_and_other_profile_geometry_do_not_qualify(self):
        raw = bytearray(8192)
        raw[0x765:0x769] = b'KOEI'
        raw[0x1FED:0x1FF2] = b'KOEI\0'
        for game_id in ('gemfire_nes', 'gemfire_snes', 'nobunaga_ambition_nes'):
            with self.subTest(game=game_id), self.assertRaises(SaveError):
                get_game(game_id).get_scalar_adapter().decode(raw)
        for backend in (gemfire_nes, gemfire_snes):
            with self.subTest(game=backend.GAME_ID), self.assertRaises(SaveError):
                backend.decode(nobunaga_fixture())
        for platform in ('nes', 'snes'):
            with self.subTest(platform=platform), self.assertRaises(SaveError):
                nobunaga.decode(gemfire_fixture(platform))

    def test_nobunaga_checksum_matches_native_low_byte_copy_counts(self):
        # Model native BRK block calls rather than the adapter's merged ranges.
        # The eight-bit $58 loop limit uses 0 for 256 bytes, 0x81EB for 0xEB.
        raw = bytes((index * 37 + 13) & 255 for index in range(8192))
        calls = [(0x6001, 255)]
        calls += [(address, 0x100) for address in range(0x6100, 0x7000, 0x100)]
        calls += [(0x7001, 255)]
        calls += [(address, 0x100) for address in range(0x7100, 0x7F00, 0x100)]
        calls += [(0x7F00, 0x81EB)]
        total, visited = 0, set()
        for address, count_word in calls:
            # The dispatcher clears accumulator bytes before every BRK call;
            # bytecode reader/writer then adds the returned unsigned sums.
            block_total = 0
            for step in range(count_word & 255 or 256):
                offset = address - 0x6000 + step
                visited.add(offset)
                block_total = (block_total + raw[offset]) & 65535
            total = (total + block_total) & 65535
        self.assertEqual(nobunaga.checksum(raw), total)
        self.assertEqual(visited, set(range(1, 0x1000)) | set(range(0x1001, 0x1FEB)))
        self.assertNotIn(0, visited)
        self.assertNotIn(0x1000, visited)
        self.assertNotIn(0x1FEB, visited)

    def test_nobunaga_conquered_and_native_rebel_ownership_stay_distinct(self):
        raw = bytearray(nobunaga_fixture())
        raw[0xE15] = 7  # Conquered fief 1 is now owned by Tokugawa.
        raw[0xE15 + 1] = 51  # Source-native uprising owner; names are unmapped.
        raw[0x1FEB:0x1FED] = nobunaga.checksum(raw).to_bytes(2, 'little')
        adapter = get_game('nobunaga_ambition_nes').get_scalar_adapter()
        document = adapter.decode(raw)
        fields = adapter.field_map(document)
        self.assertIn('Tokugawa', fields['fief_0_gold'].group)
        self.assertNotIn('fief_1_gold', fields)
        self.assertNotIn('fief_1_rice', fields)
        self.assertIn('51', str(nobunaga.province_records(document)[1]))
        output = adapter.serialize(document, {'fief_0_gold': 12})
        self.assertEqual(output[0xE15:0xE15 + 17], bytes(raw[0xE15:0xE15 + 17]))
        rebel = 0x1001 + 26
        self.assertEqual(output[rebel:rebel + 26], bytes(raw[rebel:rebel + 26]))
        self.assertEqual(adapter.serialize(document, {}), bytes(raw))


if __name__ == '__main__':
    unittest.main()
