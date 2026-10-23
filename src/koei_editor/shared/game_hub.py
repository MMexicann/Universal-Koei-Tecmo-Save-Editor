"""Local notes and safe Steam actions for the installed-game hub."""
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import webbrowser

from koei_editor.shared.preferences import preference_path
from koei_editor.shared import save_discovery
from koei_editor.shared.save_discovery import STEAM_MAPPINGS

_APP_IDS = frozenset(item.app_id for item in STEAM_MAPPINGS)
_APP_ID = re.compile(r"[1-9][0-9]{0,11}\Z")
_MAX_BYTES = 128 * 1024
_MAX_NOTES = 128
MAX_NOTE_LENGTH = 500


def discover_installations(*, steam_roots=None, cancel=None):
    """Use the version tracker's install-only scanner for all Hub scans."""
    return save_discovery.discover_installed_builds(steam_roots=steam_roots, cancel=cancel)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Game Hub settings contain a duplicate property.")
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError("Game Hub settings contain a nonfinite value.")


def notes_path(preferences_path=None):
    """Return a local sidecar path without putting install paths in preferences."""
    base = Path(preferences_path) if preferences_path is not None else preference_path()
    return base.with_name(base.stem + ".game-hub.json")


class GameHubNotes:
    """Bounded local annotations keyed to reviewed Steam app IDs."""

    def __init__(self, path=None):
        self.path = Path(path) if path is not None else notes_path()

    @staticmethod
    def _validate(notes):
        if type(notes) is not dict or len(notes) > _MAX_NOTES:
            raise ValueError("Game Hub notes must be a bounded object.")
        validated = {}
        for app_id, note in notes.items():
            if (type(app_id) is not str or _APP_ID.fullmatch(app_id) is None
                    or app_id not in _APP_IDS or type(note) is not str
                    or len(note) > MAX_NOTE_LENGTH or "\0" in note):
                raise ValueError("Game Hub note has an invalid game ID or text.")
            clean = note.strip()
            if clean:
                validated[app_id] = clean
        return validated

    def load(self):
        try:
            with self.path.open("rb") as stream:
                raw = stream.read(_MAX_BYTES + 1)
            if len(raw) > _MAX_BYTES:
                return {}
            value = json.loads(raw, object_pairs_hook=_unique_object,
                               parse_constant=_invalid_constant)
            if (type(value) is not dict or set(value) != {"schema_version", "notes"}
                    or type(value["schema_version"]) is not int
                    or value["schema_version"] != 1):
                return {}
            return self._validate(value["notes"])
        except (OSError, ValueError, TypeError, RecursionError):
            return {}

    def save(self, notes):
        validated = self._validate(notes)
        data = (json.dumps({"schema_version": 1, "notes": validated},
                           ensure_ascii=True, sort_keys=True) + "\n").encode("utf-8")
        if len(data) > _MAX_BYTES:
            raise ValueError("Game Hub notes exceed the local size limit.")
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="wb", dir=self.path.parent,
                                             prefix=".game-hub.", suffix=".tmp",
                                             delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            return True
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def set_note(self, app_id, note):
        if type(app_id) is not str or app_id not in _APP_IDS:
            raise ValueError("Choose a tracked Steam game.")
        current = self.load()
        if type(note) is not str:
            raise ValueError("Installation note must be text.")
        clean = note.strip()
        if clean:
            current[app_id] = clean
        else:
            current.pop(app_id, None)
        self.save(current)
        return current.get(app_id, "")


def steam_launch_uri(app_id):
    """Build a launch URI only for a known, reviewed Steam mapping."""
    if (type(app_id) is not str or _APP_ID.fullmatch(app_id) is None
            or app_id not in _APP_IDS):
        raise ValueError("Choose a tracked Steam game.")
    return f"steam://rungameid/{app_id}"


def installation_runtime_notice(language='en'):
    """Explain host discovery without promoting Windows profiles to Linux ports."""
    if not sys.platform.startswith('linux'):
        return ''
    if str(language).lower().startswith('de'):
        return ('Linux-Steam-/Proton-Installationsmetadaten. „Windows PC“ bezeichnet das '
                'registrierte Spielstandprofil. Native Linux-Versionen, Proton-Kompatibilität '
                'und ein erfolgreicher Spielstart sind nicht verifiziert.')
    return ('Linux Steam/Proton installation metadata. Windows PC labels describe the '
            'registered save profile. Native Linux ports, Proton compatibility and successful '
            'game launches have not been verified.')


def launch_via_steam(app_id):
    """Ask the operating system to open Steam's registered game URI handler."""
    return bool(webbrowser.open(steam_launch_uri(app_id), new=0, autoraise=True))


def _ordinary_directory(path):
    candidate = Path(path).absolute()
    for item in (*reversed(candidate.parents), candidate):
        info = item.lstat()
        if (stat.S_ISLNK(info.st_mode)
                or bool(getattr(info, "st_file_attributes", 0)
                        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))):
            raise ValueError("The installation folder now contains a linked path.")
    if not stat.S_ISDIR(candidate.lstat().st_mode):
        raise ValueError("The installation folder is no longer available.")
    return candidate


def open_install_folder(path):
    """Open the verified installation directory in the system file manager."""
    directory = _ordinary_directory(path)
    if os.name == "nt":
        opener = getattr(os, "startfile", None)
        if opener is None:
            raise OSError("Windows Explorer is unavailable.")
        opener(str(directory))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(directory)], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["xdg-open", str(directory)], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True
