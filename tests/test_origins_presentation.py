"""Inspector exposes mapped traits without normalizing unusual inventory data."""
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from koei_editor.games.origins import origins_parser as backend
from koei_editor.games.origins.origins_presentation import OriginsPresentation
from koei_editor.games.origins import origins_weapons as weapons
from koei_editor.games.origins.origins_game_editor import Editor
from tests.test_origins_parser import fixture
from tests.test_origins_proficiency import proficiency_fixture


class OriginsInspectionTests(unittest.TestCase):
    def test_inventory_inspection_preserves_unknown_traits_and_reserved_records(self):
        from koei_editor.games.origins import origins_codec
        raw = fixture(29)
        envelope = origins_codec.decode(raw, 'slot')
        payload = bytearray(envelope.payload)
        base = weapons.BASES[29]
        for index in range(weapons.SERIALIZED_COUNT):
            offset = base + index * weapons.RECORD_SIZE
            payload[offset:offset + 2] = b'\xff\xff'
        offset = base + 849 * weapons.RECORD_SIZE
        payload[offset:offset + 2] = (299).to_bytes(2, 'little')
        payload[offset + 2] = 120
        payload[offset + 3:offset + 15] = b'\xff\xff' * 6
        payload[offset + 15:offset + 21] = bytes((255, 2, 3, 4, 5, 6))
        reserved = base + 850 * weapons.RECORD_SIZE
        payload[reserved:reserved + 2] = b'\x00\x00'
        document = backend.decode(origins_codec.encode(bytes(payload), envelope.seed, 'slot'))
        table = OriginsPresentation(backend, 'origins').inspection_tables(document)[0]
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0][:3], (850, 299, 120))
        self.assertIn('65535', table.rows[0][3])
        self.assertEqual(table.rows[0][4], '255, 2, 3, 4, 5, 6')
        self.assertEqual(table.rows[0][5], 'Inspection only')
        self.assertEqual(backend.serialize(document, {}), document.raw)

    def test_proficiency_shows_stored_values_and_empty_art_without_level_claims(self):
        document = backend.decode(proficiency_fixture(29))
        tables = OriginsPresentation(backend, 'origins').inspection_tables(document)
        table = next(table for table in tables if table.title == 'Proficiency')
        self.assertEqual(table.columns[2], 'Stored XP')
        self.assertEqual(table.rows[2], (2, 'Sword', 1014, 40, 41, 408, 'Empty'))
        self.assertIn('before a weapon is acquired', table.note)
        self.assertNotIn('Level', table.columns)
        self.assertEqual(backend.serialize(document, {}), document.raw)
        unavailable = next(table for table in OriginsPresentation(backend, 'origins').inspection_tables(
            backend.decode(fixture(29))) if table.title == 'Proficiency')
        self.assertEqual(unavailable.rows, ())
        self.assertIn('unavailable for this copy', unavailable.note)


class OriginsProficiencyInspectorGuiTests(unittest.TestCase):
    def test_inspector_searches_family_xp_and_empty_art_without_staging_edits(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        root.withdraw()
        self.addCleanup(root.destroy)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'SLOT-copy.dat'
            original = proficiency_fixture(29)
            source.write_bytes(original)
            editor = Editor(root)
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename',
                       return_value=str(source)), patch(
                           'koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                editor.open()
                editor.show_inspector()
                errors.assert_not_called()
            dialog, = (child for child in root.winfo_children() if isinstance(child, tk.Toplevel))
            notebook, = (child for child in dialog.winfo_children() if isinstance(child, ttk.Notebook))
            tab = next(notebook.nametowidget(identity) for identity in notebook.tabs()
                       if notebook.tab(identity, 'text') == 'Proficiency')

            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)

            entry, = (child for child in descendants(tab) if isinstance(child, ttk.Entry))
            view, = (child for child in descendants(tab) if isinstance(child, ttk.Treeview))
            self.assertEqual(len(view.get_children()), 12)
            entry.insert(0, 'sWoRd 1014 empty')
            self.assertEqual(len(view.get_children()), 1)
            self.assertEqual(view.item(view.get_children()[0], 'values')[1], 'Sword')
            entry.delete(0, 'end')
            entry.insert(0, '65535')
            self.assertEqual(view.get_children(), ())
            self.assertEqual(editor.changes, {})
            self.assertFalse(any('proficiency' in identity for identity in editor.fields.get_children()))
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(backend.serialize(editor.document, {}), original)


if __name__ == '__main__':
    unittest.main()
