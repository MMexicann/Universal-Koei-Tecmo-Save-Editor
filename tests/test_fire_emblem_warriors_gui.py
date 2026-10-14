"""Real Tk on procedural or optional private player-export copies; no console test."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from koei_editor.games.fire_emblem_warriors import parser as fe
from koei_editor.games.fire_emblem_warriors.editor import Editor
from tests.test_fire_emblem_warriors import procedural_fe
from tests.test_hyrule_gui import GuiWorkflow


class FireEmblemGuiTests(GuiWorkflow, unittest.TestCase):
    backend = fe
    editor_type = Editor
    fixture = staticmethod(procedural_fe)
    group, search, field, value = 'Weapon stars', 'Brave Sword', 'weapon_1_stars', 5

    def test_max_visible_restores_unusual_opened_stars_after_pending_reduction(self):
        editor = self.editor
        editor.group.set('Weapon stars')
        editor.search.set('slot 3')
        editor.refresh()
        self.assertEqual(editor.fields.get_children(), ('weapon_3_stars',))
        editor.fields.selection_set('weapon_3_stars')
        editor.value.set('2')
        editor.apply_selected()
        self.assertEqual(editor.changes, {'weapon_3_stars': 2})
        editor.max_visible()
        self.assertEqual(editor.changes, {})
        self.assertFalse(self.errors)
        self.assertEqual(fe.serialize(editor.document, editor.changes), self.raw)

    def test_seal_decrease_excluded_from_max_and_extensionless_dialog(self):
        e = self.editor
        e.group.set('Ordinary seal KOs')
        e.search.set('Critical')
        e.refresh()
        self.assertEqual(e.fields.get_children(), ('weapon_1_seal_1_kos',))
        e.max_visible()
        self.assertEqual(e.changes, {})
        e.fields.selection_set('weapon_1_seal_1_kos')
        e.value.set('0')
        e.apply_selected()
        self.assertEqual(e.changes, {'weapon_1_seal_1_kos': 0})
        calls = []
        with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename',
                   side_effect=lambda **kwargs: calls.append(kwargs) or ''): e.save_as()
        self.assertEqual(calls[0]['initialfile'], 'copy-edited')
        self.assertEqual(calls[0]['defaultextension'], '')
        titles = [t.title for t in e.presentation.inspection_tables(e.document)]
        self.assertIn('Weapon attributes', titles)


@unittest.skipUnless(os.environ.get('FE_WARRIORS_SAVE_COPY'), 'No private genuine modified player export')
class FireEmblemGenuineGuiTests(GuiWorkflow, unittest.TestCase):
    backend = fe
    editor_type = Editor
    fixture = staticmethod(lambda: Path(os.environ['FE_WARRIORS_SAVE_COPY']).read_bytes())
    group, search, field, value = 'Ordinary materials', 'Rowan', 'material_64568', 998
