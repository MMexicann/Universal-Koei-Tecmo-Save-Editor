"""Procedural semantic transfer, native dependencies and stale preview checks."""
from pathlib import Path
import struct
import tempfile
import unittest

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.gundam1_ps3 import parser as gundam
from koei_editor.games.pokemon_conquest_ds import parser as conquest
from koei_editor.games.wo3u import wo3u_equipment as mounts
from koei_editor.shared import save_transfer
from tests.test_gundam1_ps3 import fixture as gundam_fixture, metadata
from tests.test_origins_parser import fixture as origins_fixture
from tests.test_pokemon_conquest_ds import fixture as conquest_fixture
from tests.test_wo3u_mounts import mount_raw


class SaveTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def copies(self, game, source, target):
        self.adapter = get_game(game).get_scalar_adapter()
        extension = self.adapter.extension
        paths = [self.folder / ('source' + extension), self.folder / ('target' + extension)]
        for path, raw in zip(paths, (source, target)):
            path.write_bytes(raw)
        return tuple(self.adapter.read_save(path) for path in paths)

    def test_resources_select_individually_keep_other_edits_and_preserve_copies(self):
        source, target = self.copies('origins', origins_fixture(gold=1234, skill_points=50), origins_fixture())
        plan = save_transfer.prepare(self.adapter, source, target, {'skill_points': 70}, ('gold',))
        self.assertEqual(dict(plan.result), {'gold': 1234, 'skill_points': 70})
        self.assertEqual([row.field.id for row in plan.rows], ['gold', 'skill_points'])
        self.assertEqual(save_transfer.confirm(plan, self.adapter, target, {'skill_points': 70}), dict(plan.result))
        self.assertEqual(source.source.read_bytes(), source.raw)
        self.assertEqual(target.source.read_bytes(), target.raw)

    def test_native_revision_mismatch_rejected_and_no_fallback(self):
        source, target = self.copies('origins', origins_fixture(revision=29), origins_fixture(revision=17))
        with self.assertRaisesRegex(SaveError, 'different qualified native revisions'):
            save_transfer.catalogue(self.adapter, source, target)

    def test_selection_unknown_empty_duplicates_bool_and_same_path_fail_closed(self):
        source, target = self.copies('origins', origins_fixture(gold=30), origins_fixture())
        for selection in ((), ('unknown',), ('gold', 'gold'), (True,), 'gold'):
            with self.subTest(selection=selection), self.assertRaises(SaveError):
                save_transfer.prepare(self.adapter, source, target, {}, selection)
        with self.assertRaisesRegex(SaveError, 'two separate'):
            save_transfer.catalogue(self.adapter, source, source)

    def test_stale_pending_source_target_and_forged_plan_rejected(self):
        source, target = self.copies('origins', origins_fixture(gold=30), origins_fixture())
        plan = save_transfer.prepare(self.adapter, source, target, {}, ('gold',))
        with self.assertRaisesRegex(SaveError, 'Pending edits changed'):
            save_transfer.confirm(plan, self.adapter, target, {'skill_points': 1})
        with self.assertRaises(SaveError):
            save_transfer.confirm(None, self.adapter, target, {})
        for document in (source, target):
            document.source.write_bytes(origins_fixture(gold=99))
            with self.assertRaises(SaveError):
                save_transfer.confirm(plan, self.adapter, target, {})
            document.source.write_bytes(document.raw)

    def test_resource_transfer_to_opened_value_unstages_existing_edit(self):
        source, target = self.copies('origins', origins_fixture(), origins_fixture())
        plan = save_transfer.prepare(self.adapter, source, target, {'gold': 1}, ('gold',))
        self.assertEqual(plan.result, ())
        self.assertEqual(plan.rows[0].after, 3456)

    def gallery_raw(self, order=(0, 56, 199), values=(1, 8, 17, 3)):
        raw = bytearray(conquest_fixture(counts=(3, 3)))
        for bank, base in enumerate(conquest.GALLERY_OFFSETS, 1):
            for slot, species in enumerate(order):
                offset = base + 24 + conquest.WARRIOR_BYTES + slot * 12
                struct.pack_into('<I', raw, offset, species)
                for value, (delta, shift, _label) in zip(values, conquest.IV_LAYOUT):
                    word = struct.unpack_from('<I', raw, offset + delta)[0]
                    struct.pack_into('<I', raw, offset + delta, (word & ~(31 << shift)) | value << shift)
            length = struct.unpack_from('<I', raw, base + 4)[0] >> 9
            struct.pack_into('<I', raw, base, sum(raw[base + 24:base + 24 + length]))
        return bytes(raw)

    def test_gallery_matches_species_across_reordered_records_preserves_banks_and_unknown_bits(self):
        source, target = self.copies('pokemon_conquest_ds', self.gallery_raw(values=(4, 11, 24, 7)),
                                      self.gallery_raw(order=(199, 0, 56)))
        key = 'bank_1_pokemon_2_iv_4'  # Eevee moved from source record 1 to destination 2.
        plan = save_transfer.prepare(self.adapter, source, target, {}, (key,))
        choice = next(choice for choice in plan.catalogue.choices if choice.id == key)
        self.assertEqual(choice.source_field.id, 'bank_1_pokemon_1_iv_4')
        result = self.adapter.serialize(target, dict(plan.result))
        field = self.adapter.field_map(target)[key]
        self.assertEqual(field.value(result), 7)
        touched = {i for i, (a, b) in enumerate(zip(result, target.raw)) if a != b}
        allowed = set(range(field.offset, field.offset + 4)) | set(range(conquest.GALLERY_OFFSETS[0], conquest.GALLERY_OFFSETS[0] + 4))
        self.assertLessEqual(touched, allowed)
        self.assertEqual(result[conquest.GALLERY_OFFSETS[1]:], target.raw[conquest.GALLERY_OFFSETS[1]:])

    def test_gallery_duplicate_in_either_save_is_ambiguous_only_in_that_bank(self):
        for source_raw, target_raw in ((self.gallery_raw(order=(0, 0, 199)), self.gallery_raw()),
                                       (self.gallery_raw(), self.gallery_raw(order=(0, 0, 199)))):
            source, target = self.copies('pokemon_conquest_ds', source_raw, target_raw)
            available = save_transfer.catalogue(self.adapter, source, target)
            self.assertTrue(any('duplicate species' in item.reason for item in available.exclusions))
            self.assertFalse(any(choice.identity[3] == 0 for choice in available.choices))
            self.assertTrue(any(choice.identity[3] == 199 for choice in available.choices))

    def test_gallery_missing_species_does_not_match_same_slot_or_other_bank(self):
        source, target = self.copies('pokemon_conquest_ds', self.gallery_raw(order=(1, 56, 199)), self.gallery_raw())
        with self.assertRaisesRegex(SaveError, 'excluded'):
            save_transfer.prepare(self.adapter, source, target, {}, ('bank_1_pokemon_1_iv_1',))

    def gundam_raw(self, selected=(0, 1, 2, 3), learned=0xFF):
        raw = bytearray(gundam_fixture())
        for _key, _name, base in gundam.PILOTS:
            raw[base + 23:base + 29] = bytes((*selected, 4, 5))
            raw[base + 29:base + 34] = bytes((learned, 0, 0, 0, 0))
        return gundam.seal(bytes(raw))

    def gundam_copies(self, source=None, target=None):
        (self.folder / 'PARAM.SFO').write_bytes(metadata())
        return self.copies('gundam1_ps3', source or self.gundam_raw(), target or self.gundam_raw())

    def test_pilot_learning_is_additive_and_equipped_references_require_original_learning(self):
        source, target = self.gundam_copies(self.gundam_raw(selected=(6, 1, 2, 3)), self.gundam_raw(learned=0x3F))
        available = save_transfer.catalogue(self.adapter, source, target)
        self.assertIn('amuro_skill_6', {choice.id for choice in available.choices})
        self.assertNotIn('amuro_equipped_0', {choice.id for choice in available.choices})
        plan = save_transfer.prepare(self.adapter, source, target, {}, ('amuro_skill_6',))
        self.assertEqual(dict(plan.result), {'amuro_skill_6': 1})
        with self.assertRaises(SaveError):
            save_transfer.prepare(self.adapter, source, target, {}, ('amuro_skill_6', 'amuro_equipped_0'))
        reverse = save_transfer.catalogue(self.adapter, target, source)
        self.assertNotIn('amuro_skill_6', {choice.id for choice in reverse.choices})
        self.assertTrue(any('cannot be removed' in item.reason for item in reverse.exclusions))

    def test_full_equipped_swap_uses_complete_native_batch_lone_duplicate_rejected(self):
        source, target = self.gundam_copies(self.gundam_raw(selected=(1, 0, 2, 3)))
        with self.assertRaisesRegex(SaveError, 'distinct'):
            save_transfer.prepare(self.adapter, source, target, {}, ('amuro_equipped_0',))
        plan = save_transfer.prepare(self.adapter, source, target, {}, ('amuro_equipped_0', 'amuro_equipped_1'))
        self.assertEqual(dict(plan.result), {'amuro_equipped_0': 1, 'amuro_equipped_1': 0})
        self.assertEqual(self.adapter.serialize(target, dict(plan.result))[0x188 + 23:0x188 + 27], bytes((1, 0, 2, 3)))

    def test_pilot_companion_changed_after_preview_and_wrong_region_reject(self):
        source, target = self.gundam_copies(self.gundam_raw(selected=(6, 1, 2, 3)))
        plan = save_transfer.prepare(self.adapter, source, target, {}, ('amuro_equipped_0',))
        (self.folder / 'PARAM.SFO').write_bytes(metadata('BLES00147-00'))
        with self.assertRaises(SaveError):
            save_transfer.confirm(plan, self.adapter, target, {})

    def test_mount_transfers_reference_only_preserves_ownership_rank_and_other_loadout(self):
        raw = bytearray(mount_raw())
        raw[mounts.MOUNT_LOADOUT_OFFSETS[0]] = 3
        source, target = self.copies('wo3u', bytes(raw), mount_raw())
        plan = save_transfer.prepare(self.adapter, source, target, {}, ('mount_loadout_0',))
        result = self.adapter.serialize(target, dict(plan.result))
        self.assertEqual({i for i, pair in enumerate(zip(result, target.raw)) if pair[0] != pair[1]},
                         {mounts.MOUNT_LOADOUT_OFFSETS[0]})

    def test_mount_unowned_or_unusual_destination_rank_is_excluded(self):
        raw = bytearray(mount_raw())
        raw[mounts.MOUNT_LOADOUT_OFFSETS[0]] = 3
        for missing in ('ownership', 'rank'):
            target_raw = bytearray(mount_raw())
            if missing == 'rank':
                position = mounts.ITEM_RANK_OFFSET + 31 * 2
                target_raw[position:position + 2] = (2).to_bytes(2, 'little')
            else:
                position = mounts.ITEM_OWNERSHIP_OFFSET
                mask = int.from_bytes(target_raw[position:position + 8], 'little') & ~(1 << 31)
                target_raw[position:position + 8] = mask.to_bytes(8, 'little')
            source, target = self.copies('wo3u', bytes(raw), bytes(target_raw))
            with self.assertRaisesRegex(SaveError, 'excluded'):
                save_transfer.prepare(self.adapter, source, target, {}, ('mount_loadout_0',))


if __name__ == '__main__':
    unittest.main()
