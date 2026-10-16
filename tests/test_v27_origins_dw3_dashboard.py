"""Game-specific dashboards preserve native values and limit percentage claims."""
from dataclasses import replace
import struct
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.games.dw3 import gui, progression_editor, save_writer
from koei_editor.games.dw3.models import Change, SaveError
from koei_editor.games.dw3.progression_dashboard import dashboard as dw3_dashboard
from koei_editor.games.dw3.save_parser import parse_bytes
from koei_editor.games.origins import origins_codec, origins_parser
from koei_editor.games.origins.origins_dashboard import dashboard as origins_dashboard
from koei_editor.games.origins.origins_presentation import OriginsPresentation
from koei_editor.games.origins.origins_progression import BATTLE_HISTORY_IDS, HISTORY_BASES, PEACE_BASES, BOND_BASES
from tests.test_elixirs_v11 import synthetic_reset_save
from tests.test_experimental_dw3_core import equipment_document, numeric_document
from tests.test_origins_parser import fixture
from tests.test_origins_proficiency import proficiency_fixture


def sections(dashboard):
    return {section.id: section for section in dashboard.sections}


def metrics(card):
    return {metric.id: metric for metric in card.metrics}


def changed_origins(document, offset, value):
    payload = bytearray(document.payload)
    payload[offset:offset + len(value)] = value
    return origins_parser.decode(origins_codec.encode(bytes(payload), document.seed, 'slot'))


class OriginsDashboardTests(unittest.TestCase):
    def test_native_revision_resource_scope_and_proficiency_without_level_inference(self):
        for revision in (16, 17, 29):
            with self.subTest(revision=revision):
                document = origins_parser.decode(proficiency_fixture(revision))
                before = (document.raw, document.payload)
                result = OriginsPresentation(origins_parser, 'origins').dashboard(document)
                views = sections(result)
                resources = metrics(views['resources'].cards[0])
                self.assertEqual(resources['gold'].value, '3456')
                self.assertIsNone(resources['gold'].fraction)
                self.assertEqual('dlc_skill_points' in resources, revision == 29)
                sword = next(card for card in views['proficiency'].cards if card.title == 'Sword')
                values = metrics(sword)
                self.assertEqual(values['stored-xp'].value, '1014')
                self.assertIsNone(values['stored-xp'].fraction)
                self.assertIsNone(values['stored-xp'].field_id)
                self.assertEqual(values['art-3'].value, 'Empty')
                self.assertFalse(any('level' in metric.label.lower() for metric in sword.metrics))
                self.assertEqual((document.raw, document.payload), before)
                self.assertEqual(origins_parser.serialize(document, {}), document.raw)
                writable = origins_parser.field_map(document)
                for section in result.sections:
                    for card in section.cards:
                        for metric in card.metrics:
                            if metric.field_id is not None:
                                self.assertIn(metric.field_id, writable)

    def test_verified_peace_and_mapped_history_denominators_keep_story_separate(self):
        document = origins_parser.decode(proficiency_fixture(29))
        document = changed_origins(document, PEACE_BASES[29], struct.pack('<H', 2500))
        document = changed_origins(document, BOND_BASES[29], bytes((4, 0, 3, 0, 0)))
        for index in BATTLE_HISTORY_IDS:
            document = changed_origins(document, HISTORY_BASES[29] + index, bytes((int(index < 3),)))
        views = sections(origins_dashboard(origins_parser, document))
        peace = metrics(next(card for card in views['completion'].cards if card.id == 'peace'))
        self.assertEqual(peace['peace_0'].fraction, .25)
        bond = metrics(next(card for card in views['characters'].cards if card.id == 'bond-0'))
        self.assertEqual(bond['bond_0_level'].fraction, .8)
        self.assertIsNone(bond['bond_0_training'].fraction)
        history = next(card for card in views['completion'].cards if card.id == 'battle-history')
        self.assertEqual(metrics(history)['mapped-clears'].total, len(BATTLE_HISTORY_IDS))
        self.assertEqual(metrics(history)['mapped-clears'].current, 3)
        self.assertIn('do not establish campaign', history.subtitle)
        self.assertIn('No overall completion', views['completion'].note)

    def test_unknown_proficiency_is_unavailable_and_unusual_values_not_normalized(self):
        document = origins_parser.decode(fixture(29, gold=0xffffffff))
        result = sections(origins_dashboard(origins_parser, document))
        self.assertFalse(result['proficiency'].cards)
        self.assertIn('unavailable', result['proficiency'].note)
        gold = metrics(result['resources'].cards[0])['gold']
        self.assertEqual(gold.value, str(0xffffffff))
        self.assertIsNone(gold.fraction)
        self.assertEqual(origins_parser.serialize(document, {}), document.raw)
        with self.assertRaises(SaveError):
            origins_dashboard(origins_parser, replace(document, revision=17))


class DW3DashboardTests(unittest.TestCase):
    def test_existing_owned_equipment_and_reference_do_not_create_collection_ownership(self):
        document = equipment_document()
        before = document.encrypted, document.plaintext
        result = sections(dw3_dashboard(document))
        self.assertEqual(len(result['equipment'].cards), 1)
        weapon = result['equipment'].cards[0]
        self.assertIn('Owned regular copy', weapon.subtitle)
        self.assertIn('equipped-weapon', metrics(result['characters'].cards[0]))
        self.assertFalse(any(card.id.startswith('collection-') for card in result['completion'].cards))
        self.assertIn('no overall', result['completion'].note)
        self.assertEqual((document.encrypted, document.plaintext), before)
        self.assertEqual(save_writer.serialize(document)[0], document.encrypted)

    def test_opened_higher_merit_stays_visible_without_clamped_progress_or_level(self):
        document = numeric_document(merit=0x7fffffff, elixirs=0x7fffffff)
        result = sections(dw3_dashboard(document))
        merit = metrics(result['characters'].cards[0])['SPoint']
        self.assertEqual(merit.value, str(0x7fffffff))
        self.assertIsNone(merit.fraction)
        self.assertIn('not inferred', merit.note)
        self.assertEqual(metrics(result['resources'].cards[0])['elixirs'].value, str(0x7fffffff))
        self.assertIsNone(metrics(result['resources'].cards[0])['elixirs'].fraction)

    def test_actual_serialized_story_clear_changes_dashboard_but_not_original(self):
        original = synthetic_reset_save()
        original_view = sections(dw3_dashboard(original))
        route = next(card for card in original_view['completion'].cards if card.id == 'route-0')
        self.assertEqual(metrics(route)['cleared'].value, 'Not cleared')
        modified, _ = save_writer.serialize(original, progression_editor.musou_clear_changes(original, 0))
        changed = sections(dw3_dashboard(parse_bytes(modified)))
        changed_route = next(card for card in changed['completion'].cards if card.id == 'route-0')
        self.assertEqual(metrics(changed_route)['cleared'].value, 'Cleared')
        self.assertEqual(metrics(changed_route)['route-progress'].fraction, 1)
        self.assertEqual(metrics(original_view['resources'].cards[0])['elixirs'].value, '0')
        self.assertEqual(metrics(changed['resources'].cards[0])['elixirs'].value, '3')


class DW3DashboardGuiTests(unittest.TestCase):
    def test_navigation_theme_and_refresh_leave_pending_changes_and_original_intact(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        root.withdraw()
        self.addCleanup(root.destroy)
        editor = gui.Editor(root, persist_preferences=False)
        editor.document = numeric_document(merit=1, elixirs=3)
        original = editor.document.encrypted
        editor.set_loaded(True)
        editor.refresh()
        self.assertTrue(editor.stage_many([Change('officer', 0, 'SPoint', 8)]))
        before = dict(editor.changes), list(editor.history)
        editor.officer_filter.set('no matching officer')
        editor.refresh_officers()
        editor.navigate_dashboard('officer:0:SPoint')
        self.assertEqual(editor.notebook.select(), str(editor.tabs['Officers']))
        self.assertEqual(editor.officers.selection(), ('0',))
        self.assertEqual(editor.inputs['SPoint'].get(), '8')
        editor.theme_dashboard('Dark')
        editor.theme_dashboard('Light')
        editor.navigate_dashboard('progression:0:HuanglongElixirs')
        self.assertEqual(editor.notebook.select(), str(editor.tabs['Unlocks']))
        editor.navigate_dashboard('not-a-field')
        selected_tab = editor.notebook.select()
        self.assertFalse(editor.navigate_dashboard('story:999:MusouCleared'))
        self.assertEqual(editor.notebook.select(), selected_tab)
        self.assertTrue(editor.navigate_dashboard('story:0:MusouCleared'))
        self.assertEqual(editor.story_officer_choices[editor.story_officer.get()], 0)
        self.assertEqual((editor.changes, editor.history), before)
        self.assertEqual(editor.document.encrypted, original)
        self.assertEqual(save_writer.serialize(editor.document)[0], original)
        # A display-only mapping failure does not poison the editable document.
        editor._dashboard_document = None
        with patch('koei_editor.games.dw3.progression_dashboard.dashboard', side_effect=ValueError('unavailable')):
            editor.refresh_dashboard()
        self.assertIn('unavailable', editor.dashboard_view.dashboard.note)
        self.assertEqual((editor.changes, editor.history), before)
        editor.set_loaded(False)
        self.assertEqual(editor.dashboard_view.dashboard.sections, ())
        editor.set_loaded(True)
        self.assertTrue(editor.dashboard_view.dashboard.sections)
        editor.document = None
        editor.refresh()
        self.assertEqual(editor.dashboard_view.dashboard.sections, ())
        # A filtered-out weapon remains a valid navigation target.
        editor.document = equipment_document()
        editor.set_loaded(True)
        editor.refresh()
        editor.weapon_filter.set('no matching weapon')
        editor.refresh_weapons()
        self.assertFalse(editor.weapon_rows)
        self.assertTrue(editor.navigate_dashboard('weapon:0:Skills'))
        self.assertEqual(editor.notebook.select(), str(editor.tabs['Weapons']))
        self.assertEqual(editor.weapons.selection(), ('WeaponDataArray:0',))


if __name__ == '__main__':
    unittest.main()
