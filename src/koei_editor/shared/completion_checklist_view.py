"""Optional GUI for user-authored checklist entries, separate from save data."""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import queue
import threading
from datetime import datetime
import unicodedata
from urllib.parse import quote

from koei_editor.shared.completion_checklist import (
    CompletionChecklistStore, normalize_entries, new_entry,
)


class CompletionChecklistView(ttk.Frame):
    """Show an achievement snapshot and optional manual list beside the dashboard."""

    MAX_ACHIEVEMENTS = 512
    MAX_DISPLAY_TEXT = 500

    def __init__(self, master, game_id, store=None):
        super().__init__(master, padding=20)
        self.game_id = game_id
        self.store = store or CompletionChecklistStore()
        self.entries = self.store.load(game_id)
        self._storage_ok = self.store.available()
        self.item_text = tk.StringVar(self)
        self.status = tk.StringVar(self)
        self.achievement_status = tk.StringVar(self)
        self.achievement_summary = tk.StringVar(self)
        self._achievement_source = self._get_achievement_source(game_id)
        self._achievement_results = queue.SimpleQueue()
        self._achievement_revision = 0
        self._achievement_busy = False

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        ttk.Label(self, text="Completion Companion",
                  font=("TkDefaultFont", 18, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 12))
        self.tabs = ttk.Notebook(self)
        self.tabs.grid(row=1, column=0, sticky="nsew")
        self.achievement_page = ttk.Frame(self.tabs, padding=14)
        self.manual_page = ttk.Frame(self.tabs, padding=14)
        self.tabs.add(self.achievement_page, text="Platform achievements")
        self.tabs.add(self.manual_page, text="Manual checklist")
        self._build_achievements()
        self._build_manual_checklist()
        self._render()
        self.set_achievement_snapshot(self._initial_snapshot(self._achievement_source))

    @staticmethod
    def _get_achievement_source(game_id):
        try:
            from koei_editor.game_registry import get_game
            game = get_game(game_id)
            # Older editor snapshots may not yet expose an achievement source.
            # The provider accessor only imports a module; requests happen after
            # the user activates the button below.
            getter = getattr(game, "get_achievement_source", None)
            return getter() if callable(getter) else None
        except Exception:
            return None

    @staticmethod
    def _achievement_action_state(source):
        fetch = getattr(source, "fetch_achievements", None) if source is not None else None
        return "normal" if callable(fetch) else "disabled"

    @staticmethod
    def _initial_snapshot(source):
        if source is None:
            return {
                "status": "unavailable",
                "note": "No supported achievement source is available for this game/platform.",
            }
        return {
            "status": "unavailable",
            "source": "Supported platform source",
            "note": "Check the source to retrieve verified achievement states.",
        }

    def _build_manual_checklist(self):
        page = self.manual_page
        page.columnconfigure(0, weight=1)
        page.rowconfigure(2, weight=1)
        ttk.Label(page, text="Optional completion checklist",
                  font=("TkDefaultFont", 12, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            page,
            text=("Manual entries only. Verified values from the opened save stay in the "
                  "Progression Dashboard; this checklist is not read from that save."),
            style="Muted.TLabel", wraplength=940, justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 12))

        list_frame = ttk.Frame(page)
        list_frame.grid(row=2, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            list_frame, columns=("source", "state", "text"),
            show="headings", selectmode="browse", height=12,
        )
        self.tree.heading("source", text="Tracking source")
        self.tree.heading("state", text="Manual state")
        self.tree.heading("text", text="Checklist item")
        self.tree.column("source", width=140, minwidth=110, stretch=False, anchor="w")
        self.tree.column("state", width=150, minwidth=130, stretch=False, anchor="w")
        self.tree.column("text", width=650, minwidth=200, stretch=True, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<Double-1>", lambda _event: self.toggle_selected())
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)

        actions = ttk.Frame(page, padding=(0, 12, 0, 0))
        actions.grid(row=3, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        self.entry = ttk.Entry(actions, textvariable=self.item_text)
        self.entry.grid(row=0, column=0, sticky="ew")
        self.entry.bind("<Return>", lambda _event: self.add_entry())
        self.add_button = ttk.Button(actions, text="Add manual item", command=self.add_entry)
        self.add_button.grid(row=0, column=1, padx=(8, 0))
        self.toggle_button = ttk.Button(actions, text="Mark checked", command=self.toggle_selected)
        self.toggle_button.grid(row=0, column=2, padx=(8, 0))
        self.remove_button = ttk.Button(actions, text="Remove item", command=self.remove_selected)
        self.remove_button.grid(row=0, column=3, padx=(8, 0))
        ttk.Label(page, textvariable=self.status, style="Muted.TLabel").grid(
            row=4, column=0, sticky="w", pady=(8, 0))

    def _build_achievements(self):
        page = self.achievement_page
        page.columnconfigure(0, weight=1)
        page.rowconfigure(3, weight=1)
        heading = ttk.Frame(page)
        heading.grid(row=0, column=0, sticky="ew")
        heading.columnconfigure(0, weight=1)
        ttk.Label(heading, text="Verified platform achievements",
                  font=("TkDefaultFont", 12, "bold")).grid(row=0, column=0, sticky="w")
        self.achievement_action = ttk.Button(
            heading, text="Check supported source…", command=self.check_achievements,
            state=self._achievement_action_state(self._achievement_source))
        self.achievement_action.grid(row=0, column=1, sticky="e")
        ttk.Label(page, textvariable=self.achievement_status,
                  style="Muted.TLabel", wraplength=940, justify="left").grid(
            row=1, column=0, sticky="w", pady=(8, 3))
        ttk.Label(page, textvariable=self.achievement_summary,
                  style="Muted.TLabel", wraplength=940, justify="left").grid(
            row=2, column=0, sticky="w", pady=(0, 10))
        table = ttk.Frame(page)
        table.grid(row=3, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        self.achievement_tree = ttk.Treeview(
            table, columns=("id", "name", "state", "unlocked_at", "description"),
            show="headings", selectmode="browse", height=14,
        )
        for column, title, width, stretch in (
                ("id", "Achievement ID", 150, False),
                ("name", "Achievement", 220, True),
                ("state", "Platform state", 130, False),
                ("unlocked_at", "Unlocked at", 170, False),
                ("description", "Description", 300, True)):
            self.achievement_tree.heading(column, text=title)
            self.achievement_tree.column(column, width=width, minwidth=90,
                                         stretch=stretch, anchor="w")
        self.achievement_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.achievement_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.achievement_tree.configure(yscrollcommand=scrollbar.set)

    def check_achievements(self):
        """Fetch only after a click; provider network requests run off the Tk thread."""
        source = self._achievement_source
        fetch = getattr(source, "fetch_achievements", None) if source is not None else None
        if not callable(fetch) or self._achievement_busy:
            return False
        window = self.winfo_toplevel()
        api_key = simpledialog.askstring(
            "Steam Web API key", "Enter a Steam Web API key for this request.",
            parent=window, show="*",
        )
        if api_key is None:
            return False
        steam_id64 = simpledialog.askstring(
            "SteamID64", "Enter the Steam profile's 64-bit ID.", parent=window,
        )
        if steam_id64 is None:
            api_key = None
            return False
        api_key, steam_id64 = api_key.strip(), steam_id64.strip()
        if (not api_key or len(api_key) > 256 or len(steam_id64) != 17
                or not steam_id64.isascii() or not steam_id64.isdigit()):
            api_key = steam_id64 = None
            messagebox.showinfo("Achievements unavailable",
                                "Enter both values to check the supported source.", parent=window)
            return False

        self._achievement_revision += 1
        revision = self._achievement_revision
        self._achievement_busy = True
        self.achievement_action.configure(state="disabled")
        self.set_achievement_snapshot({
            "status": "unavailable", "source": "Steam",
            "note": "Checking the supported source. Credentials are used only for this request and are not saved.",
        })
        threading.Thread(target=self._fetch_achievements,
                         args=(revision, source, api_key, steam_id64),
                         daemon=True).start()
        self.after(40, self._poll_achievement_result)
        return True

    @classmethod
    def _redact_text(cls, value, secrets):
        if type(value) is not str:
            return value
        result = value
        for secret in secrets:
            if secret:
                result = result.replace(secret, "[redacted]")
                encoded = quote(secret, safe="")
                if encoded and encoded != secret:
                    result = result.replace(encoded, "[redacted]")
        return result[:cls.MAX_DISPLAY_TEXT]

    @classmethod
    def _display_snapshot(cls, snapshot, secrets):
        """Copy provider fields for display and redact transient credentials."""
        field = cls._field
        achievements = field(snapshot, "achievements", ())
        if type(achievements) not in (tuple, list):
            achievements = ()
        items = []
        for item in achievements[:cls.MAX_ACHIEVEMENTS]:
            items.append({key: cls._redact_text(field(item, key, ""), secrets)
                          for key in ("id", "name", "description", "state", "unlocked_at")})
        return {
            key: cls._redact_text(field(snapshot, key, ""), secrets)
            for key in ("status", "source", "retrieved_at", "note")
        } | {
            "unlocked_count": field(snapshot, "unlocked_count"),
            "total_count": field(snapshot, "total_count"),
            "achievements": items,
        }

    def _fetch_achievements(self, revision, source, api_key, steam_id64):
        """Worker target deliberately drops raw exception messages/credentials."""
        try:
            snapshot = source.fetch_achievements(api_key, steam_id64)
            display_snapshot = self._display_snapshot(snapshot, (api_key, steam_id64))
            self._achievement_results.put((revision, display_snapshot, False))
        except Exception:
            # HTTP exceptions can contain query parameters. Never pass them to
            # the UI or logs, since the request may include the user's key.
            self._achievement_results.put((revision, None, True))
        finally:
            api_key = None
            steam_id64 = None

    def _poll_achievement_result(self):
        try:
            if not self.winfo_exists():
                return
            revision, snapshot, failed = self._achievement_results.get_nowait()
        except queue.Empty:
            self.after(40, self._poll_achievement_result)
            return
        except tk.TclError:
            return
        if revision != self._achievement_revision:
            return
        self._achievement_busy = False
        self.achievement_action.configure(
            state=self._achievement_action_state(self._achievement_source))
        if failed or snapshot is None:
            self.set_achievement_snapshot({
                "status": "unavailable", "source": "Steam",
                "note": "The source could not verify achievement data. Check the profile and try again.",
            })
        else:
            self.set_achievement_snapshot(snapshot)

    @classmethod
    def _display_text(cls, value):
        if type(value) is not str:
            return ""
        value = " ".join(value.split())
        return value[:cls.MAX_DISPLAY_TEXT]

    @staticmethod
    def _valid_source_identity(value):
        if (type(value) is not str or not value.strip() or len(value) > 128
                or any(unicodedata.category(char).startswith("C") for char in value)):
            return None
        return " ".join(value.split())

    @staticmethod
    def _valid_retrieved_at(value):
        """Accept only canonical UTC retrieval times from the source contract."""
        if type(value) is not str or len(value) != 20 or not value.endswith("Z"):
            return None
        try:
            parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return None
        return value if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") == value else None

    @staticmethod
    def _field(value, key, default=None):
        if type(value) is dict:
            return value.get(key, default)
        return getattr(value, key, default)

    def set_achievement_snapshot(self, snapshot):
        """Render provider data; the view never performs network or save reads.

        The optional count is accepted only from the provider and displayed only
        when every listed schema achievement has a verified locked/unlocked
        state. Unknown rows remain explicitly unavailable.
        """
        for child in self.achievement_tree.get_children():
            self.achievement_tree.delete(child)
        snapshot = snapshot if snapshot is not None else {}
        achievements = self._field(snapshot, "achievements", ())
        if type(achievements) not in (list, tuple):
            achievements = ()
        achievements = achievements[:self.MAX_ACHIEVEMENTS]
        verified = self._field(snapshot, "status") == "verified"
        source = self._valid_source_identity(self._field(snapshot, "source", ""))
        retrieved = self._valid_retrieved_at(self._field(snapshot, "retrieved_at", ""))
        note = self._display_text(self._field(snapshot, "note", ""))
        claimed_verified = self._field(snapshot, "status") == "verified"
        verified = claimed_verified and source is not None and retrieved is not None
        if not verified:
            context = source or "No verified platform source"
            retrieved_text = f" · Checked {retrieved}" if retrieved else ""
            self.achievement_status.set(f"Unavailable · {context}{retrieved_text}.")
            self.achievement_summary.set("No achievement states are claimed.")
            if claimed_verified:
                self.achievement_summary.set(
                    "The source omitted a valid identity or UTC retrieval time; states remain unavailable.")
            elif note:
                self.achievement_summary.set(note)
        else:
            source_text = source or "Unknown source"
            retrieved_text = f" · Retrieved {retrieved}" if retrieved else ""
            self.achievement_status.set(f"Verified from {source_text}{retrieved_text}.")
            self.achievement_summary.set(note or "Achievement state is supplied by this platform source.")

        all_states_verified = bool(achievements)
        for index, achievement in enumerate(achievements):
            state = self._field(achievement, "state")
            if not verified or state not in ("unlocked", "locked"):
                state_text = "Unavailable"
                all_states_verified = False
            else:
                state_text = "Unlocked" if state == "unlocked" else "Locked"
            unlocked_at = (self._display_text(self._field(achievement, "unlocked_at", ""))
                           if state_text == "Unlocked" else "")
            self.achievement_tree.insert(
                "", "end", iid=f"achievement-{index}",
                values=(self._display_text(self._field(achievement, "id", "")),
                        self._display_text(self._field(achievement, "name", "")), state_text,
                        unlocked_at, self._display_text(self._field(achievement, "description", ""))),
            )
        count = self._field(snapshot, "unlocked_count")
        total = self._field(snapshot, "total_count")
        if (verified and all_states_verified and type(count) is int
                and type(total) is int and 0 <= count <= total
                and total == len(achievements)):
            self.achievement_summary.set(
                f"{count} of {total} achievements unlocked · source reported")
        elif verified and achievements:
            self.achievement_summary.set(
                f"{len(achievements)} source entries · individual states shown below")

    def _selected_id(self):
        selected = self.tree.selection()
        return selected[0] if selected else None

    def _selection_changed(self, _event=None):
        selected = self._selected_id()
        entry = next((item for item in self.entries if item.id == selected), None)
        self.toggle_button.configure(
            state="normal" if entry else "disabled",
            text=("Mark not checked" if entry and entry.checked else "Mark checked"),
        )
        self.remove_button.configure(state="normal" if entry else "disabled")

    def _render(self, selected_id=None):
        for child in self.tree.get_children():
            self.tree.delete(child)
        for entry in self.entries:
            state = "Checked" if entry.checked else "Not checked"
            self.tree.insert("", "end", iid=entry.id,
                             values=("Manual", state, entry.text))
        if selected_id and self.tree.exists(selected_id):
            self.tree.selection_set(selected_id)
            self.tree.focus(selected_id)
        checked = sum(entry.checked for entry in self.entries)
        entry_count = len(self.entries)
        entry_label = "manual entry" if entry_count == 1 else "manual entries"
        count_text = f"{entry_count} {entry_label} · {checked} manually checked"
        if not self._storage_ok:
            count_text += " · local checklist storage is unavailable or invalid"
        self.status.set(count_text)
        self._selection_changed()

    def _commit(self, entries, selected_id=None):
        try:
            validated = normalize_entries(entries)
        except (TypeError, ValueError):
            self.status.set("This checklist entry is invalid or the manual item limit was reached.")
            return False
        if not self.store.save(self.game_id, validated):
            self._storage_ok = self.store.available()
            self.status.set("The local checklist could not be saved; existing entries were kept.")
            return False
        self.entries = validated
        self._storage_ok = True
        self._render(selected_id)
        return True

    def add_entry(self):
        try:
            entry = new_entry(self.item_text.get())
        except (TypeError, ValueError):
            self.status.set("Enter a short manual checklist item first.")
            return False
        if self._commit((*self.entries, entry), entry.id):
            self.item_text.set("")
            self.entry.focus_set()
            return True
        return False

    def toggle_selected(self):
        selected = self._selected_id()
        found = False
        updated = []
        for entry in self.entries:
            if entry.id == selected:
                found = True
                updated.append(type(entry)(entry.id, entry.text, not entry.checked))
            else:
                updated.append(entry)
        return self._commit(updated, selected) if found else False

    def remove_selected(self):
        selected = self._selected_id()
        if selected is None:
            return False
        updated = tuple(entry for entry in self.entries if entry.id != selected)
        if len(updated) == len(self.entries):
            return False
        return self._commit(updated)
