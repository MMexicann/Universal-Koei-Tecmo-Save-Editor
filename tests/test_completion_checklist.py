"""Manual completion notes remain local, bounded and separate from save data."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.shared.completion_checklist import (
    MAX_ENTRIES_PER_GAME, ChecklistEntry, CompletionChecklistStore,
    checklist_path, new_entry, normalize_entries,
)


class CompletionChecklistStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "local" / "completion_checklists.json"
        self.store = CompletionChecklistStore(self.path)

    def test_entries_are_per_game_stable_and_keep_only_manual_text_and_state(self):
        self.assertEqual(self.store.load("dw3"), ())
        first = new_entry("Clear the final chapter")
        second = ChecklistEntry(first.id, first.text, True)
        self.assertTrue(self.store.save("dw3", (second,)))
        self.assertTrue(self.store.save("dw8xl", (new_entry("Find a rare weapon"),)))
        self.assertEqual(self.store.load("dw3"), (second,))
        self.assertEqual(self.store.load("pw3"), ())
        content = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(set(content), {"schema", "games"})
        self.assertEqual(set(content["games"]["dw3"][0]), {"id", "text", "checked"})
        self.assertNotIn("save", self.path.read_text(encoding="utf-8").lower())

    def test_checklist_path_is_separate_from_editor_settings(self):
        settings = Path(self.temporary.name) / "preferences.json"
        self.assertEqual(checklist_path(settings), settings.with_name("completion_checklists.json"))
        self.assertNotEqual(checklist_path(settings), settings)

    def test_rejects_invalid_entries_and_limits_without_changing_saved_file(self):
        entry = new_entry("Optional target")
        self.assertTrue(self.store.save("dw3", (entry,)))
        original = self.path.read_bytes()
        invalid = (
            (ChecklistEntry("bad-id", "Invalid ID"),),
            (entry, ChecklistEntry(entry.id, "Duplicate ID")),
            (ChecklistEntry(new_entry("valid").id, " "),),
            (ChecklistEntry(new_entry("valid").id, "Control\ncharacter"),),
            (ChecklistEntry(new_entry("valid").id, "Invalid state", 1),),
        )
        for bad in invalid:
            with self.subTest(entries=bad):
                self.assertFalse(self.store.save("dw3", bad))
                self.assertEqual(self.path.read_bytes(), original)
        with self.assertRaises(ValueError):
            normalize_entries(tuple(new_entry(str(index)) for index in range(MAX_ENTRIES_PER_GAME + 1)))

    def test_corrupt_or_oversized_file_is_unavailable_and_never_overwritten(self):
        self.path.parent.mkdir(parents=True)
        for raw in (b"{", b'{"schema":1,"games":{},"extra":1}',
                    b" " * (256 * 1024 + 1)):
            with self.subTest(length=len(raw)):
                self.path.write_bytes(raw)
                self.assertFalse(self.store.available())
                self.assertEqual(self.store.load("dw3"), ())
                self.assertFalse(self.store.save("dw3", (new_entry("Try again"),)))
                self.assertEqual(self.path.read_bytes(), raw)

    def test_failed_replace_preserves_existing_checklist_and_cleans_temp(self):
        item = new_entry("Return to the hidden stage")
        self.assertTrue(self.store.save("dw3", (item,)))
        original = self.path.read_bytes()
        with patch("koei_editor.shared.completion_checklist.os.replace",
                   side_effect=PermissionError("Read-only settings")):
            self.assertFalse(self.store.save("dw3", (ChecklistEntry(item.id, item.text, True),)))
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob(".completion-checklist.*")), [])


if __name__ == "__main__":
    unittest.main()
