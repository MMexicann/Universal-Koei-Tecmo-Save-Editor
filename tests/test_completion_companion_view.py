"""The companion labels provider data and manual notes by their source."""

import os
import queue
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from types import SimpleNamespace

from koei_editor.shared.completion_checklist import CompletionChecklistStore, new_entry
from koei_editor.shared.completion_checklist_view import CompletionChecklistView


class _Variable:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class _Tree:
    def __init__(self):
        self.rows = {}
        self.selected = ()

    def get_children(self):
        return tuple(self.rows)

    def delete(self, item):
        self.rows.pop(item, None)

    def insert(self, _parent, _index, iid, values):
        self.rows[iid] = values

    def selection(self):
        return self.selected

    def selection_set(self, item):
        self.selected = (item,)

    def focus(self, _item):
        pass

    def exists(self, item):
        return item in self.rows

    def item(self, item, _option):
        return {"values": self.rows[item]}["values"]


class CompletionCompanionProjectionTests(unittest.TestCase):
    def setUp(self):
        self.view = SimpleNamespace(
            achievement_tree=_Tree(), achievement_status=_Variable(),
            achievement_summary=_Variable(),
            MAX_ACHIEVEMENTS=CompletionChecklistView.MAX_ACHIEVEMENTS,
            MAX_DISPLAY_TEXT=CompletionChecklistView.MAX_DISPLAY_TEXT,
        )
        self.view._display_text = CompletionChecklistView._display_text
        self.view._field = CompletionChecklistView._field
        self.view._valid_source_identity = CompletionChecklistView._valid_source_identity
        self.view._valid_retrieved_at = CompletionChecklistView._valid_retrieved_at

    def test_verified_provider_states_and_source_count_are_displayed_without_percentages(self):
        CompletionChecklistView.set_achievement_snapshot(self.view, SimpleNamespace(
            status="verified", source="Steam", retrieved_at="2026-10-22T12:00:00Z",
            note="Verified profile data.", unlocked_count=1, total_count=2,
            achievements=(
                SimpleNamespace(id="CLEAR", name="First Clear", description="Finish a stage.",
                                 state="unlocked", unlocked_at="2026-10-20T09:00:00Z"),
                SimpleNamespace(id="COLLECT", name="Collector", description="Find every item.",
                                 state="locked", unlocked_at=None),
            )))
        self.assertIn("Verified from Steam", self.view.achievement_status.get())
        self.assertIn("1 of 2 achievements unlocked", self.view.achievement_summary.get())
        self.assertNotIn("%", self.view.achievement_summary.get())
        self.assertEqual(self.view.achievement_tree.rows["achievement-0"][2], "Unlocked")
        self.assertEqual(self.view.achievement_tree.rows["achievement-1"][2], "Locked")

    def test_partial_or_unavailable_snapshot_never_displays_a_count(self):
        CompletionChecklistView.set_achievement_snapshot(self.view, {
            "status": "verified", "source": "Steam", "retrieved_at": "now",
            "unlocked_count": 1, "total_count": 2,
            "achievements": [
                {"id": "A", "name": "Known", "description": "Known state", "state": "unlocked"},
                {"id": "B", "name": "Unknown", "description": "Missing state", "state": "unavailable"},
            ],
        })
        self.assertNotIn("of 2 achievements", self.view.achievement_summary.get())
        self.assertEqual(self.view.achievement_tree.rows["achievement-1"][2], "Unavailable")
        CompletionChecklistView.set_achievement_snapshot(self.view, {
            "status": "unavailable", "source": "Steam", "note": "Profile is private.",
            "achievements": [{"id": "A", "name": "Unknown", "state": "unlocked"}],
        })
        self.assertIn("Unavailable", self.view.achievement_status.get())
        self.assertEqual(self.view.achievement_summary.get(), "Profile is private.")
        self.assertEqual(self.view.achievement_tree.rows["achievement-0"][2], "Unavailable")
        self.assertEqual(self.view.achievement_tree.rows["achievement-0"][3], "")

    def test_verified_claim_without_source_identity_and_utc_time_fails_closed(self):
        CompletionChecklistView.set_achievement_snapshot(self.view, {
            "status": "verified", "source": " \n", "retrieved_at": "yesterday",
            "unlocked_count": 1, "total_count": 1,
            "achievements": [{"id": "A", "name": "Known", "state": "unlocked"}],
        })
        self.assertIn("Unavailable", self.view.achievement_status.get())
        self.assertIn("omitted a valid identity or UTC retrieval time",
                      self.view.achievement_summary.get())
        self.assertNotIn("of 1 achievements", self.view.achievement_summary.get())
        self.assertEqual(self.view.achievement_tree.rows["achievement-0"][2], "Unavailable")

    def test_unsupported_source_stays_unavailable_and_disables_fetch(self):
        snapshot = CompletionChecklistView._initial_snapshot(None)
        CompletionChecklistView.set_achievement_snapshot(self.view, snapshot)
        self.assertEqual(CompletionChecklistView._achievement_action_state(None), "disabled")
        self.assertIn("Unavailable", self.view.achievement_status.get())
        self.assertIn("No supported achievement source", self.view.achievement_summary.get())

    def test_credentials_are_redacted_from_provider_text_and_exceptions(self):
        api_key = "super-secret-api-key"
        steam_id = "76561198000000000"
        snapshot = SimpleNamespace(
            status="verified", source="Steam", retrieved_at="now",
            note=f"Request failed for {api_key} and {steam_id}.",
            unlocked_count=None, total_count=None,
            achievements=(SimpleNamespace(
                id="A", name=f"Owner {steam_id}", description=f"Key {api_key}",
                state="unlocked", unlocked_at=None),),
        )
        display = CompletionChecklistView._display_snapshot(
            snapshot, (api_key, steam_id))
        self.assertNotIn(api_key, repr(display))
        self.assertNotIn(steam_id, repr(display))

        class FailedProvider:
            @staticmethod
            def fetch_achievements(key, profile):
                raise RuntimeError(f"URL included {key} and {profile}")

        worker = SimpleNamespace(_achievement_results=queue.SimpleQueue())
        CompletionChecklistView._fetch_achievements(
            worker, 3, FailedProvider(), api_key, steam_id)
        result = worker._achievement_results.get_nowait()
        self.assertEqual(result, (3, None, True))
        self.assertNotIn(api_key, repr(result))
        self.assertNotIn(steam_id, repr(result))

    def test_manual_rows_keep_manual_source_and_manual_state_labels(self):
        entry = new_entry("Clear the final chapter")

        class _Button:
            def __init__(self):
                self.options = {}

            def configure(self, **_kwargs):
                self.options.update(_kwargs)

        view = SimpleNamespace(
            tree=_Tree(), entries=(entry,), status=_Variable(), _storage_ok=True,
            toggle_button=_Button(), remove_button=_Button(),
        )
        view._selected_id = lambda: CompletionChecklistView._selected_id(view)
        view._selection_changed = lambda _event=None: CompletionChecklistView._selection_changed(
            view, _event)
        CompletionChecklistView._render(view)
        self.assertEqual(view.tree.rows[entry.id],
                         ("Manual", "Not checked", "Clear the final chapter"))
        self.assertEqual(view.status.get(), "1 manual entry · 0 manually checked")
        self.assertNotIn("%", view.status.get())
        view.tree.selection_set(entry.id)
        CompletionChecklistView._selection_changed(view)
        self.assertEqual(view.toggle_button.options,
                         {"state": "normal", "text": "Mark checked"})
        self.assertEqual(view.remove_button.options, {"state": "normal"})

    def test_dw3_resolves_registered_provider_and_unmapped_game_is_unavailable(self):
        from koei_editor.game_registry import get_game
        dw3 = get_game("dw3")
        if not callable(getattr(dw3, "get_achievement_source", None)):
            self.skipTest("The dependent Steam provider PR has not been merged yet.")
        source = CompletionChecklistView._get_achievement_source("dw3")
        unsupported = CompletionChecklistView._get_achievement_source("dw8xl")
        self.assertIsNotNone(source)
        self.assertEqual(CompletionChecklistView._achievement_action_state(source), "normal")
        self.assertIsNone(unsupported)
        self.assertEqual(CompletionChecklistView._achievement_action_state(unsupported), "disabled")


@unittest.skipUnless(os.name == "nt" or os.environ.get("DISPLAY"),
                     "A graphical display is required.")
class CompletionCompanionViewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = tk.Tk()
        self.root.geometry("1100x700")
        self.addCleanup(self.root.destroy)
        self.store = CompletionChecklistStore(
            Path(self.temporary.name) / "completion_checklists.json")
        self.view = CompletionChecklistView(self.root, "dw3", self.store)
        self.view.pack(fill="both", expand=True)
        self.root.update()

    def test_achievement_status_is_unavailable_until_a_provider_snapshot_arrives(self):
        self.assertIn("Unavailable", self.view.achievement_status.get())
        self.assertEqual(self.view.achievement_summary.get(),
                         "Check the source to retrieve verified achievement states.")
        self.assertEqual(str(self.view.achievement_action.cget("state")), "normal")
        self.assertFalse(self.view._achievement_busy)
        self.assertEqual(self.view.achievement_tree.get_children(), ())

    def test_manual_checklist_add_toggle_and_remove_are_persisted_as_manual(self):
        self.view.item_text.set("Clear the final chapter")
        self.assertTrue(self.view.add_entry())
        self.root.update()
        entry_id = self.view.tree.get_children()[0]
        self.assertEqual(self.view.tree.item(entry_id, "values"),
                         ("Manual", "Not checked", "Clear the final chapter"))
        self.assertEqual(self.view.status.get(), "1 manual entry · 0 manually checked")
        self.view.tree.selection_set(entry_id)
        self.assertTrue(self.view.toggle_selected())
        self.assertEqual(self.store.load("dw3")[0].checked, True)
        self.assertEqual(self.view.tree.item(entry_id, "values")[1], "Checked")
        self.view.tree.selection_set(entry_id)
        self.assertTrue(self.view.remove_selected())
        self.assertEqual(self.store.load("dw3"), ())


    def test_supported_fetch_requires_a_click_runs_in_background_and_redacts_credentials(self):
        import threading
        import time
        from unittest.mock import patch

        api_key, steam_id = "a" * 32, "76561198000000000"
        calls = []
        ui_thread = threading.get_ident()

        def fetch(key, profile):
            calls.append((key, profile, threading.get_ident()))
            return {
                "status": "verified", "source": "Steam Web API",
                "retrieved_at": "2026-10-22T12:00:00Z",
                "achievements": [{"id": "CLEAR", "name": f"Profile {profile}",
                                  "description": f"Request key {key}", "state": "locked"}],
            }

        self.view._achievement_source = SimpleNamespace(fetch_achievements=fetch)
        self.root.update()
        self.assertEqual(calls, [])
        with patch("koei_editor.shared.completion_checklist_view.simpledialog.askstring",
                   side_effect=(api_key, steam_id)):
            self.view.achievement_action.invoke()
        deadline = time.monotonic() + 3
        while self.view._achievement_busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.005)
        self.assertFalse(self.view._achievement_busy, "The asynchronous result was not delivered.")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][:2], (api_key, steam_id))
        self.assertNotEqual(calls[0][2], ui_thread)
        self.assertIn("Verified from Steam Web API", self.view.achievement_status.get())
        rows = tuple(self.view.achievement_tree.item(iid, "values")
                     for iid in self.view.achievement_tree.get_children())
        self.assertEqual(rows[0][2], "Locked")
        self.assertIn("[redacted]", rows[0][1])
        self.assertIn("[redacted]", rows[0][4])
        self.assertNotIn(api_key, repr(rows))
        self.assertNotIn(steam_id, repr(rows))
        self.assertEqual(self.view.entries, ())
        self.assertFalse(self.store.path.exists())

    def test_cancelled_credentials_do_not_start_a_request_or_write_checklist_data(self):
        from unittest.mock import Mock, patch
        fetch = Mock()
        self.view._achievement_source = SimpleNamespace(fetch_achievements=fetch)
        with patch("koei_editor.shared.completion_checklist_view.simpledialog.askstring",
                   side_effect=("a" * 32, None)):
            self.assertFalse(self.view.check_achievements())
        self.assertFalse(self.view._achievement_busy)
        fetch.assert_not_called()
        self.assertFalse(self.store.path.exists())


    def test_closing_a_companion_cancels_polling_without_targeting_deleted_widgets(self):
        import threading
        import time
        from unittest.mock import patch

        release = threading.Event()
        finished = threading.Event()
        self.addCleanup(release.set)
        self.root.tk.eval(
            'set ::completion_background_errors {}; '
            'proc bgerror {msg} {lappend ::completion_background_errors $msg}')

        def fetch(_key, _profile):
            try:
                release.wait(2)
                return {"status": "unavailable"}
            finally:
                finished.set()

        self.view._achievement_source = SimpleNamespace(fetch_achievements=fetch)
        with patch("koei_editor.shared.completion_checklist_view.simpledialog.askstring",
                   side_effect=("a" * 32, "76561198000000000")):
            self.assertTrue(self.view.check_achievements())
        self.view.destroy()
        release.set()
        self.assertTrue(finished.wait(1))
        deadline = time.monotonic() + 0.12
        while time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.005)
        self.assertEqual(self.root.tk.call("set", "::completion_background_errors"), "")
        self.assertFalse(self.store.path.exists())


if __name__ == "__main__":
    unittest.main()
