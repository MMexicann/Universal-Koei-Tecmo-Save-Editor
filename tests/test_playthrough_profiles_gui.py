"""Display-aware checks for the Smart Playthrough Profiles window."""
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.shared.playthrough_profiles_gui import PlaythroughProfilesWindow


class PlaythroughProfilesGuiLayoutTests(unittest.TestCase):
    def test_profile_window_uses_one_geometry_manager_per_tab(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')

        def destroy_root():
            try:
                root.destroy()
            except tk.TclError:
                pass

        self.addCleanup(destroy_root)
        root.withdraw()

        # Keep this check limited to widget construction and layout; no vault
        # access or background profile worker is needed to validate geometry.
        with patch.object(PlaythroughProfilesWindow, '_refresh'):
            view = PlaythroughProfilesWindow(
                root,
                vault_path='/unused-test-vault',
                palette={'background': '#ffffff', 'text': '#222222'},
            )
        self.addCleanup(view.close)
        root.update_idletasks()

        library_children = view.library_tab.winfo_children()
        self.assertTrue(library_children)
        self.assertTrue(all(child.winfo_manager() == 'grid' for child in library_children))
        output_frame = view.library_output.master.master
        self.assertIs(output_frame.master, view.library_tab)
        self.assertEqual(output_frame.winfo_manager(), 'grid')


if __name__ == '__main__':
    unittest.main()
