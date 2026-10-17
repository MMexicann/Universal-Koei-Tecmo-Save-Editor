"""DW3 targeted workflows use procedural tagged saves, never player data."""
import os
import struct
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from koei_editor.games.dw3 import bodyguard_customization as customization
from koei_editor.games.dw3 import collection_editor as collections
from koei_editor.games.dw3 import gui, officer_weapon_editor as weapons
from koei_editor.games.dw3 import save_writer as writer
from koei_editor.games.dw3.models import Change, SaveError, fields
from koei_editor.games.dw3.save_parser import parse_bytes
from koei_editor.shared.experimental_limits import experimental_limits
from tests.test_elixirs_v08 import replace_top_tag
from tests.test_elixirs_v11 import synthetic_reset_save, string, tag, typename
from tests.test_weapon_rolls import record_bytes


def weapon_record(data_id, weapon_id, skills, attr=0, *, valid=True):
    scope = typename('/Script/Refine')
    def integer(name, value):
        return tag(name, typename('IntProperty'), struct.pack('<i', value))
    def enum(name, family, value):
        return tag(name, typename('EnumProperty', typename(family, scope), typename('ByteProperty')), string(value))
    slots = []
    for skill in skills + [{'id': None, 'value': 0}] * (9 - len(skills)):
        identity = 'EEquipItemID::NUM' if skill['id'] is None else 'EEquipItemID::' + weapons.ITEMS[skill['id']]['enum']
        slots.append(enum('EquipItemID', 'EEquipItemID', identity) +
                     enum('GuardEquipItemID', 'EGuardEquipItemID', 'EGuardEquipItemID::NUM') +
                     integer('Value', skill['value']) + string('None'))
    identity = 'EWeaponID::NUM' if weapon_id is None else weapons.WEAPONS[weapon_id]['enum']
    return (integer('DataID', data_id if valid else data_id + 10) + enum('ID', 'EWeaponID', identity) +
            enum('WeaponID', 'EWeaponID', identity) + tag('Attr', typename('Int64Property'), struct.pack('<q', attr)) +
            tag('GetTime', typename('DoubleProperty'), struct.pack('<d', 123.25)) +
            tag('Skill', typename('ArrayProperty', typename('StructProperty', typename('EquipItemSaveData', scope))),
                struct.pack('<i', 9) + b''.join(slots)) + string('None'))


def weapon_document(*, source=None, target=None, invalid_last=False, unique=False):
    document = synthetic_reset_save()
    source = source if source is not None else [{'id': 0, 'value': 5}, {'id': 1, 'value': 4}, {'id': 13, 'value': 0}]
    target = target if target is not None else [{'id': 4, 'value': 1}]
    rows = [weapon_record(0, 6, source, 4), weapon_record(1, 7, target, 8),
            weapon_record(2, 6, [{'id': 3, 'value': 1}], 16, valid=not invalid_last)]
    def replace(name, struct_name, rows):
        kind = typename('ArrayProperty', typename('StructProperty', typename(struct_name, typename('/Script/Refine'))))
        return replace_top_tag(document, document.properties[name], tag(name, kind, struct.pack('<i', len(rows)) + b''.join(rows)))
    document = replace('WeaponDataArray', 'WeaponSaveData', rows)
    if unique:
        template = weapons.UNIQUES[89]
        skills = [{'id': s['item_id'] if s['item_id'] in weapons.ITEMS else None, 'value': s['value']}
                  for s in template['skill_slots']]
        document = replace('UniqueWeaponDataArray', 'WeaponSaveData',
                           [weapon_record(10000, 89, skills, template['attribute_bitmask'])])
    return document


def gallery_document(*, lazy=False):
    scope = typename('/Script/Refine')
    def struct_tag(name, kind, body):
        return tag(name, typename('StructProperty', typename(kind, scope)), body + string('None'))
    def flags(name, values):
        return tag(name, typename('ArrayProperty', typename('BoolProperty')), struct.pack('<i', len(values)) + bytes(values))
    sections = []
    for name, kind, array in [('Sound', 'OptionSound', 'bPlayBGM'), ('Edit', 'OptionEdit', 'bPlayMovie')]:
        body = b'' if lazy else flags(array, [0] * 90 + [1] + [0] * 12)
        body += flags(array + '_Old', [1, 0] * 50)
        sections.append(struct_tag(name, kind, body))
    return synthetic_reset_save(struct_tag('OptionData', 'OptionSaveData', b''.join(sections)))


class TargetedWeaponTests(unittest.TestCase):
    def test_layout_copy_is_surgical_and_preserves_source_flags_time_and_unrelated_records(self):
        document = weapon_document()
        original = document.encrypted
        self.assertEqual(writer.serialize(document)[0], original)
        changes = weapons.copy_bonus_changes(document, 0, [1, 2])
        raw, audit = writer.serialize(document, changes)
        result = parse_bytes(raw)
        for data_id in (1, 2):
            state = weapons.state(result, data_id)
            self.assertEqual([s for s in state['skills'] if s['id'] is not None],
                             [s for s in weapons.state(document, 0)['skills'] if s['id'] is not None])
            self.assertEqual(state['skills'][8], {'id': 13, 'value': 0})
            before = fields(document.records('WeaponDataArray')[data_id])
            after = fields(result.records('WeaponDataArray')[data_id])
            for name in ('ID', 'WeaponID', 'DataID', 'GetTime', 'Attr'):
                self.assertEqual(after[name]['value'], before[name]['value'])
        self.assertEqual(record_bytes(result, 'WeaponDataArray', 0), record_bytes(document, 'WeaponDataArray', 0))
        for name in document.properties:
            if name != 'WeaponDataArray':
                self.assertEqual(result.properties[name]['value'], document.properties[name]['value'])
        self.assertTrue(audit['unchanged_bytes_preserved'])
        self.assertEqual(writer.serialize(result)[0], raw)
        self.assertEqual(document.encrypted, original)
        self.assertEqual(writer.serialize(result, weapons.copy_bonus_changes(result, 0, [1, 2]))[0], raw)

    def test_complete_selection_refuses_view_only_duplicate_self_and_foreign_references(self):
        document = weapon_document(invalid_last=True)
        for source, targets in [(0, [1, 2]), (2, [1]), (0, []), (0, [1, 1]),
                                (0, [0]), (True, [1]), (0, [True]), (0, [-1]), (0, [10001])]:
            with self.subTest(source=source, targets=targets), self.assertRaises(SaveError):
                weapons.copy_bonus_changes(document, source, targets)
        self.assertEqual(writer.serialize(document)[0], document.encrypted)

    def test_pending_layouts_and_original_assignments_use_existing_staging_rules(self):
        document = weapon_document(source=[{'id': 0, 'value': 1}], target=[{'id': 0, 'value': 1}])
        pending_skills = weapons.original_skills(document, 1)
        pending_skills[0]['value'] = 2
        pending = [Change('weapon_roll', 1, 'Skills', pending_skills)]
        self.assertEqual(weapons.copy_bonus_changes(document, 0, [1], pending)[0].value,
                         weapons.original_skills(document, 1))
        pending_source = weapons.original_skills(document, 0)
        pending_source[0]['value'] = 3
        source_changes = [Change('weapon_roll', 0, 'Skills', pending_source)]
        copied = weapons.copy_bonus_changes(document, 0, [1], source_changes)
        reopened = parse_bytes(writer.serialize(document, source_changes + copied)[0])
        self.assertEqual(weapons.state(reopened, 1)['skills'][0]['value'], 3)

    def test_source_saved_high_and_unique_stock_exceptions_cannot_be_transferred(self):
        document = weapon_document(source=[{'id': 0, 'value': 1000}])
        self.assertTrue(weapons.state(document, 0)['editable'])
        for target in ([{'id': 4, 'value': 1}], [{'id': 0, 'value': 1}]):
            document = weapon_document(source=[{'id': 0, 'value': 1000}], target=target)
            for experimental in (False, True):
                with experimental_limits(enabled=experimental), self.assertRaises(SaveError):
                    weapons.copy_bonus_changes(document, 0, [1])
        unique = weapon_document(unique=True)
        self.assertTrue(weapons.state(unique, 10000)['editable'])
        with self.assertRaisesRegex(SaveError, 'source-only'):
            weapons.copy_bonus_changes(unique, 10000, [1])
        with self.assertRaisesRegex(SaveError, 'at least'):
            weapons.copy_bonus_changes(unique, 1, [10000])

    def test_destination_rank_and_existing_rare_requirements_are_enforced(self):
        document = weapon_document(unique=True)
        normal = [{'id': index, 'value': 1} for index in range(7)]
        kind = typename('ArrayProperty', typename('StructProperty', typename('WeaponSaveData', typename('/Script/Refine'))))
        unique = tag('UniqueWeaponDataArray', kind, struct.pack('<i', 1) + weapon_record(10000, 89, normal))
        document = replace_top_tag(document, document.properties['UniqueWeaponDataArray'], unique)
        self.assertTrue(weapons.state(document, 10000)['editable'])
        with self.assertRaisesRegex(SaveError, 'at most 6'):
            weapons.copy_bonus_changes(document, 10000, [1])
        rare_target = weapon_document(source=[{'id': 0, 'value': 1}],
                                      target=[{'id': 4, 'value': 1}, {'id': 13, 'value': 0}])
        with self.assertRaisesRegex(SaveError, 'existing rare'):
            weapons.copy_bonus_changes(rare_target, 0, [1])

    def test_copy_preserves_an_identical_high_destination_in_its_original_slot(self):
        profile = [{'id': 0, 'value': 1000}]
        document = weapon_document(source=profile, target=profile)
        changes = weapons.copy_bonus_changes(document, 0, [1])
        self.assertEqual(writer.serialize(document, changes)[0], document.encrypted)

    def test_filtered_elements_preserve_bonus_layouts_and_all_other_flag_bits(self):
        document = weapon_document(invalid_last=True)
        changes = weapons.element_changes(document, [0, 1], weapons.ELEMENTS['Lightning'])
        result = parse_bytes(writer.serialize(document, changes)[0])
        for index in (0, 1):
            self.assertEqual(weapons.original_skills(result, index), weapons.original_skills(document, index))
            before = fields(document.records('WeaponDataArray')[index])['Attr']['value']
            after = fields(result.records('WeaponDataArray')[index])['Attr']['value']
            self.assertEqual(after & ~weapons.ELEMENT_MASK, before & ~weapons.ELEMENT_MASK)
        self.assertEqual(record_bytes(result, 'WeaponDataArray', 2), record_bytes(document, 'WeaponDataArray', 2))


class TargetedCollectionTests(unittest.TestCase):
    def test_selected_entries_preserve_acknowledgements_and_unshown_tail(self):
        document = gallery_document()
        changes = collections.unlock_entry_changes(document, 'music', [0, 41])
        changes += collections.unlock_entry_changes(document, 'movies', [1, 49])
        result = parse_bytes(writer.serialize(document, changes)[0])
        for gallery in ('music', 'movies'):
            spec = collections.DATA[gallery]
            _, before_props, before, saved = collections._array(document, spec)
            _, after_props, after, actual = collections._array(result, spec)
            expected = list(saved)
            for change in changes:
                if change.field == spec['field']:
                    expected[change.index] = True
            self.assertEqual(actual, expected)
            self.assertEqual(after['data_size'], before['data_size'])
            self.assertEqual(next(p for p in before_props if p['name'] == spec['array'] + '_Old')['value'],
                             next(p for p in after_props if p['name'] == spec['array'] + '_Old')['value'])
        self.assertEqual(writer.serialize(result, changes)[0], result.encrypted)

    def test_selected_lazy_entries_insert_only_requested_flags_with_native_default_count(self):
        document = gallery_document(lazy=True)
        changes = collections.unlock_entry_changes(document, 'music', [41])
        changes += collections.unlock_entry_changes(document, 'movies', [49])
        result = parse_bytes(writer.serialize(document, changes)[0])
        for gallery, index in [('music', 41), ('movies', 49)]:
            values = collections._array(result, collections.DATA[gallery])[3]
            self.assertEqual(len(values), 100)
            self.assertEqual([i for i, value in enumerate(values) if value], [index])
        self.assertEqual(writer.serialize(result)[0], result.encrypted)

    def test_selection_refuses_reserved_title_loop_duplicates_and_bad_types(self):
        document = gallery_document()
        for gallery, indices in [('music', [42]), ('movies', [50]), ('movies', [51]),
                                 ('music', [0, 99]), ('movies', [1, 1]), ('music', []),
                                 ('movies', [True]), ('music', [1.0]), ('other', [1]), ([], [1])]:
            with self.subTest(gallery=gallery, indices=indices), self.assertRaises(SaveError):
                collections.unlock_entry_changes(document, gallery, indices)

    def test_documented_appearance_selector_keeps_prior_selector_compatible(self):
        self.assertEqual(customization.customization_unlock_changes('appearance', 3),
                         [Change('guard_customization', 3, 'AppearanceUnlocked', True)])
        self.assertEqual(customization.customization_unlock_changes('appearance'),
                         customization.customization_unlock_changes('koei_editor.shared.appearance'))


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'Tk requires a display.')
class TargetedWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.editor = gui.Editor(self.root, persist_preferences=False)

    def tearDown(self):
        self.root.destroy()

    def load(self, document):
        self.editor.document = document
        self.editor.set_loaded(True)
        self.editor.refresh()

    def test_copy_layout_review_undo_and_actual_safe_copy_workflow(self):
        document = weapon_document()
        self.load(document)
        editor = self.editor
        editor.weapons.selection_set('WeaponDataArray:1')
        editor.select_weapon()
        source = next(label for label, data_id in editor.weapon_bonus_sources.items() if data_id == 0)
        editor.weapon_bonus_source.set(source)
        editor.copy_weapon_bonuses()
        self.assertEqual(set(editor.changes), {('weapon_roll', 1, 'Skills')})
        self.assertEqual(editor.review_change(editor.changes[('weapon_roll', 1, 'Skills')])[1], 'Copy bonuses')
        editor.review()
        with tempfile.TemporaryDirectory() as folder:
            output, _ = writer.write_save(document, Path(folder) / 'edited.sav', list(editor.changes.values()))
            copied = parse_bytes(output.read_bytes())
            self.assertEqual(weapons.state(copied, 1)['skills'][8]['id'], 13)
            backup = writer.backup_save(document, Path(folder) / 'backups')
            restored = writer.restore_backup(backup, Path(folder) / 'restored.sav')
            self.assertEqual(restored.read_bytes(), document.encrypted)
        editor.undo()
        self.assertEqual(editor.changes, {})

    def test_visible_element_action_respects_search_scope_and_preserves_view_only_copy(self):
        self.load(weapon_document(invalid_last=True))
        editor = self.editor
        editor.weapon_filter.set('Long Spear')
        self.assertEqual(set(editor.weapon_rows), {'WeaponDataArray:1'})
        editor.weapon_element.set('Fire')
        editor.apply_visible_weapon_elements()
        self.assertEqual(set(editor.changes), {('weapon_element', 1, 'Elements')})
        editor.undo()
        editor.weapon_filter.set('Spear')
        editor.weapon_element.set('Lightning')
        editor.apply_visible_weapon_elements()
        self.assertEqual(set(editor.changes), {('weapon_element', 0, 'Elements')})

    def test_selected_gallery_entries_remain_selected_after_staging_and_undo(self):
        self.load(gallery_document())
        editor = self.editor
        editor.collection_tree.selection_set(('music:41', 'movies:49'))
        editor.unlock_selected_collections()
        self.assertEqual(set(editor.changes), {('collection', 41, 'Music'), ('collection', 49, 'Movie')})
        self.assertEqual(set(editor.collection_tree.selection()), {'music:41', 'movies:49'})
        self.assertTrue(all(editor.collection_tree.item(key, 'values')[2] == 'Yes'
                            for key in editor.collection_tree.selection()))
        editor.undo()
        self.assertEqual(editor.changes, {})
        self.assertEqual(set(editor.collection_tree.selection()), {'music:41', 'movies:49'})
        editor.collection_filter.set('41')
        self.assertNotIn('movies:49', editor.collection_tree.get_children())

    def test_invalid_destination_profile_is_rejected_without_losing_pending_edits(self):
        self.load(weapon_document(unique=True))
        editor = self.editor
        editor.stage_many([Change('officer', 0, 'Attack', 100)])
        before = dict(editor.changes)
        editor.weapons.selection_set('WeaponDataArray:1')
        editor.select_weapon()
        editor.weapon_bonus_source.set(next(label for label, data_id in editor.weapon_bonus_sources.items() if data_id == 10000))
        with patch.object(gui.messagebox, 'showerror') as error:
            editor.copy_weapon_bonuses()
        error.assert_called_once()
        self.assertEqual(editor.changes, before)


if __name__ == '__main__':
    unittest.main()
