"""User-authored optional completion notes, kept separate from save projections.

Checklist entries are manual notes only. This module does not inspect saves,
infer achievement state, or calculate a completion percentage.
"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata
import uuid

from koei_editor.shared.preferences import preference_path


MAX_BYTES = 256 * 1024
MAX_GAMES = 256
MAX_ENTRIES_PER_GAME = 128
MAX_TEXT_LENGTH = 240
_GAME_ID = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_ENTRY_ID = re.compile(r"[0-9a-f]{32}\Z")


@dataclass(frozen=True)
class ChecklistEntry:
    """A locally stored, manually tracked checklist item."""

    id: str
    text: str
    checked: bool = False


def checklist_path(settings_path=None):
    """Return the separate per-user checklist file beside editor settings."""
    base = Path(settings_path) if settings_path is not None else preference_path()
    return base.with_name("completion_checklists.json")


def _valid_game_id(game_id):
    return type(game_id) is str and _GAME_ID.fullmatch(game_id) is not None


def _valid_text(value):
    return (type(value) is str and 1 <= len(value) <= MAX_TEXT_LENGTH
            and value == value.strip()
            and not any(unicodedata.category(character).startswith("C") for character in value))


def normalize_entries(entries):
    """Validate bounded manual entries while preserving their stable IDs/order."""
    if type(entries) not in (tuple, list) or len(entries) > MAX_ENTRIES_PER_GAME:
        raise ValueError(f"A checklist can contain at most {MAX_ENTRIES_PER_GAME} entries.")
    result = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, ChecklistEntry):
            raise ValueError("Checklist entries must use the manual entry model.")
        if (type(entry.id) is not str or _ENTRY_ID.fullmatch(entry.id) is None
                or entry.id in seen or not _valid_text(entry.text)
                or type(entry.checked) is not bool):
            raise ValueError("Checklist entries must have a unique ID, short text and manual checked state.")
        seen.add(entry.id)
        result.append(entry)
    return tuple(result)


def new_entry(text):
    """Create a stable local ID for a user-authored checklist note."""
    cleaned = text.strip() if type(text) is str else text
    entry = ChecklistEntry(uuid.uuid4().hex, cleaned, False)
    return normalize_entries((entry,))[0]


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Checklist file contains a duplicate property.")
        value[key] = item
    return value


def _invalid_constant(_value):
    raise ValueError("Checklist file contains a nonfinite JSON value.")


class CompletionChecklistStore:
    """Small atomic JSON store for manual entries, independent of save files."""

    def __init__(self, path=None):
        self.path = Path(path) if path is not None else checklist_path()

    def _read(self):
        try:
            with self.path.open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
        except FileNotFoundError:
            return {}
        except OSError:
            return None
        if len(raw) > MAX_BYTES:
            return None
        try:
            value = json.loads(raw, object_pairs_hook=_unique_object,
                               parse_constant=_invalid_constant)
            if (type(value) is not dict or set(value) != {"schema", "games"}
                    or type(value["schema"]) is not int or value["schema"] != 1
                    or type(value["games"]) is not dict or len(value["games"]) > MAX_GAMES):
                return None
            result = {}
            for game_id, raw_entries in value["games"].items():
                if (not _valid_game_id(game_id) or type(raw_entries) is not list
                        or len(raw_entries) > MAX_ENTRIES_PER_GAME):
                    return None
                entries = []
                for raw_entry in raw_entries:
                    if (type(raw_entry) is not dict
                            or set(raw_entry) != {"id", "text", "checked"}):
                        return None
                    entries.append(ChecklistEntry(raw_entry["id"], raw_entry["text"],
                                                  raw_entry["checked"]))
                result[game_id] = normalize_entries(entries)
            return result
        except (ValueError, TypeError, RecursionError):
            return None

    def load(self, game_id):
        """Return one game's manual checklist; malformed storage reads as empty."""
        if not _valid_game_id(game_id):
            return ()
        value = self._read()
        return value.get(game_id, ()) if value is not None else ()

    def available(self):
        """Whether storage can be read without treating invalid data as empty."""
        return self._read() is not None

    def save(self, game_id, entries):
        """Atomically save only user text and checked state for one game ID."""
        if not _valid_game_id(game_id):
            return False
        try:
            normalized = normalize_entries(entries)
        except (ValueError, TypeError):
            return False
        games = self._read()
        if games is None:
            return False
        if normalized:
            games[game_id] = normalized
        else:
            games.pop(game_id, None)
        if len(games) > MAX_GAMES:
            return False
        data = json.dumps({
            "schema": 1,
            "games": {key: [
                {"id": entry.id, "text": entry.text, "checked": entry.checked}
                for entry in value
            ] for key, value in sorted(games.items())},
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        if len(data) > MAX_BYTES:
            return False
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="wb", dir=self.path.parent,
                                             prefix=".completion-checklist.", suffix=".tmp",
                                             delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            return True
        except (OSError, ValueError, TypeError):
            return False
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
