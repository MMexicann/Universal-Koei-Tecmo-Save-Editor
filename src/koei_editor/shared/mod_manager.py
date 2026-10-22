"""Safe, profile-based deployment for the verified Nioh 2 PC mod folder method.

This module deliberately supports one game installation method: Nioh 2 PC's
``Mods`` directory used by Nioh 2 Mod Enabler. It never installs a loader or
writes files beside the game executable. Managed packages are isolated in
subfolders, and the loader's documented `` DISABLED`` folder suffix is used
for enable/disable operations.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from functools import wraps
import hashlib
import json
import math
import os
import queue
import re
import shutil
import stat
import tempfile
import threading
import uuid
import zipfile
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Protocol
from urllib.parse import urlsplit


GAME_ID = "nioh2_pc"
GAME_EXE = "nioh2.exe"
LOADER_FILE = "d3d11.dll"
MODS_DIR = "Mods"
DISABLED_SUFFIX = " DISABLED"
SUPPORTED_ASSET_EXTENSIONS = frozenset({".fmt", ".vb", ".ib", ".dds"})
SUPPORTED_MOD_EXTENSIONS = SUPPORTED_ASSET_EXTENSIONS | {".ini"}
_MAX_ARCHIVE_FILES = 20_000
_MAX_ARCHIVE_FILE_BYTES = 512 * 1024 * 1024
_MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024
_MAX_NEXUS_DOWNLOAD_BYTES = _MAX_ARCHIVE_BYTES
_MAX_NEXUS_QUEUE_SIZE = 3
_NEXUS_NUMERIC_ID_RE = re.compile(r"^[0-9]{1,20}$")
_MAX_METADATA_BYTES = 1024 * 1024
_MAX_STATE_BYTES = 16 * 1024 * 1024
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,47}$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_TRANSACTION_STAGE_RE = re.compile(r"^\.ktmm-transaction-[0-9a-f]{32}$")
_REMOVAL_BACKUP_RE = re.compile(r"^\.ktmm-remove-[0-9a-f]{32}-([a-z0-9][a-z0-9._-]{1,47})$")
_WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


class ModManagerError(Exception):
    """Base class for safe mod-manager failures shown in the UI."""


class PackageError(ModManagerError):
    """A package does not match the verified Nioh 2 mod layout."""


class InstallationError(ModManagerError):
    """The selected install or loader does not match the supported method."""


class SafetyError(ModManagerError):
    """An unsafe path, collision, or external modification was detected."""


class ProfileError(ModManagerError):
    """A requested profile is invalid or has unresolved requirements."""


@dataclass(frozen=True)
class ModFile:
    path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class ModRecord:
    id: str
    name: str
    version: str
    dependencies: tuple[str, ...]
    conflicts: tuple[str, ...]
    files: tuple[ModFile, ...]
    content_sha256: str
    installed: bool
    enabled: bool


@dataclass(frozen=True)
class ProfileRecord:
    id: str
    name: str
    enabled_mods: tuple[str, ...]


@dataclass(frozen=True)
class NexusDownloadResult:
    """Safe completion state for a manager-owned Nexus import job.

    The result deliberately contains no request object, downloader, credential,
    signed URL, temporary path, or exception text.
    """

    status: str
    message: str
    mod_id: str | None = None
    retry_after_seconds: int | None = None


class NexusDownloadRequestLike(Protocol):
    """Structural browser request; the manager does not import Nexus API code."""

    provider: str
    game_id: str
    game_domain: str
    game_scoped_mod_id: str
    mod_id: str
    file_id: str
    file_name: str
    file_version_id: str
    game_scoped_file_version_id: str
    mod_page_url: str


class NexusArchiveDownloader(Protocol):
    """Narrow in-memory capability that streams an authorized ZIP to a path."""

    def download_archive(self, request: NexusDownloadRequestLike, destination: Path) -> int:
        ...


@dataclass(frozen=True)
class _NexusDownloadJob:
    request: NexusDownloadRequestLike
    downloader: NexusArchiveDownloader


def _library_locked(method):
    """Serialize library reads/removals with asynchronous package imports."""
    @wraps(method)
    def locked(self, *args, **kwargs):
        with self._library_lock:
            return method(self, *args, **kwargs)
    return locked


def default_state_dir() -> Path:
    """Return a per-user application-data location for manager state."""
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "Universal Koei Tecmo Save Editor" / "Mod Manager"
    state_home = os.environ.get("XDG_STATE_HOME")
    if state_home:
        return Path(state_home) / "universal-koei-tecmo-save-editor" / "mod-manager"
    return Path.home() / ".local" / "state" / "universal-koei-tecmo-save-editor" / "mod-manager"


def _safe_relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise PackageError("Package paths must be nonempty relative paths using forward slashes.")
    if value.startswith("/"):
        raise PackageError(f"Absolute or empty package path is unsupported: {value!r}.")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise PackageError(f"Unsafe package path: {value!r}.")
    for part in parts:
        if ":" in part or any(ch in part for ch in '<>"|?*'):
            raise PackageError(f"Unsafe package path: {value!r}.")
        if part.endswith((".", " ")) or part.split(".", 1)[0].casefold() in _WINDOWS_RESERVED:
            raise PackageError(f"Windows cannot safely represent package path: {value!r}.")
    return PurePosixPath(*parts)


def _slug(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"[^a-z0-9._-]+", "-", value).strip(".-_")
    value = re.sub(r"[-_.]{2,}", "-", value)
    value = value[:48].strip(".-_") or "nioh-mod"
    return value if len(value) >= 2 else value + "-mod"


def _digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_root(path: str | os.PathLike[str]) -> Path:
    candidate = Path(path).expanduser()
    try:
        root = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise InstallationError(f"The selected game folder cannot be resolved: {exc}") from exc
    if not root.is_dir():
        raise InstallationError("Select the folder that directly contains nioh2.exe.")
    executable = root / GAME_EXE
    if executable.is_symlink() or not executable.is_file():
        raise InstallationError("The selected folder must directly contain nioh2.exe.")
    return root


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    except Exception:
        try:
            temp.unlink()
        except OSError:
            pass
        raise


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if path.stat().st_size > _MAX_STATE_BYTES:
            raise SafetyError(f"Manager state is unexpectedly large: {path.name}.")
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object)
    except FileNotFoundError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise SafetyError(f"Cannot read manager state {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise SafetyError(f"Manager state {path.name} has an invalid structure.")
    return value


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON property: {key!r}.")
        value[key] = item
    return value


def _iter_tree(root: Path) -> tuple[dict[str, tuple[str, int]], set[str]]:
    """Hash regular files and record all directories; reject links and special files."""
    if root.is_symlink() or not root.is_dir():
        raise SafetyError(f"Managed folder is missing or is not a real directory: {root.name}.")
    files: dict[str, tuple[str, int]] = {}
    directories: set[str] = set()
    seen_paths: set[str] = set()
    for current, names, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        names.sort(key=str.casefold)
        filenames.sort(key=str.casefold)
        for name in names:
            child = current_path / name
            if child.is_symlink() or _is_reparse_point(child):
                raise SafetyError(f"A link or reparse point was found in a managed folder: {child.name}.")
            if not child.is_dir():
                raise SafetyError(f"A non-directory entry was found in a managed folder: {child.name}.")
            key = child.relative_to(root).as_posix().casefold()
            if key in seen_paths:
                raise SafetyError(f"A case-insensitive path collision was found in {root.name}.")
            seen_paths.add(key)
            directories.add(key)
        for name in filenames:
            child = current_path / name
            if child.is_symlink() or _is_reparse_point(child) or not child.is_file():
                raise SafetyError(f"A link or special file was found in a managed folder: {child.name}.")
            relative = child.relative_to(root).as_posix()
            key = relative.casefold()
            if key in seen_paths:
                raise SafetyError(f"A case-insensitive path collision was found in {root.name}.")
            seen_paths.add(key)
            files[key] = (_file_digest(child), child.stat().st_size)
    return files, directories


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _expected_dirs(files: Iterable[ModFile]) -> set[str]:
    result: set[str] = set()
    for item in files:
        parent = PurePosixPath(item.path).parent
        while parent != PurePosixPath("."):
            result.add(parent.as_posix().casefold())
            parent = parent.parent
    return result


def _file_map(files: Iterable[ModFile]) -> dict[str, tuple[str, int]]:
    return {item.path.casefold(): (item.sha256, item.size) for item in files}


def _verify_tree(path: Path, files: Iterable[ModFile], *, allow_subset: bool = False) -> bool:
    files = tuple(files)
    actual, actual_dirs = _iter_tree(path)
    expected = _file_map(files)
    expected_dirs = _expected_dirs(files)
    if allow_subset:
        return (set(actual) <= set(expected)
                and all(expected[key] == value for key, value in actual.items())
                and actual_dirs <= expected_dirs)
    return actual == expected and actual_dirs == expected_dirs


def _normal_id(value: Any, *, label: str = "mod id") -> str:
    if not isinstance(value, str):
        raise PackageError(f"The {label} must be text.")
    normalized = value.strip().casefold()
    if not _ID_RE.fullmatch(normalized) or "disabled" in normalized:
        raise PackageError(f"The {label} must contain 2–48 safe lowercase letters, digits, dots, dashes or underscores, and cannot contain 'disabled'.")
    return normalized


def _metadata_value(value: Any, fallback_name: str, fallback_id: str) -> tuple[str, str, str, tuple[str, ...], tuple[str, ...]]:
    if value is None:
        return _normal_id(fallback_id), fallback_name, "unknown", (), ()
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise PackageError("koei-mod.json must be an object with schema_version 1.")
    if value.get("game_id") != GAME_ID:
        raise PackageError(f"koei-mod.json must declare game_id {GAME_ID!r}.")
    mod_id = _normal_id(value.get("id"))
    name = value.get("name")
    version = value.get("version", "unknown")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
        raise PackageError("koei-mod.json name must contain 1–120 characters.")
    if not isinstance(version, str) or not version.strip() or len(version.strip()) > 80:
        raise PackageError("koei-mod.json version must contain 1–80 characters.")
    dependencies = value.get("dependencies", [])
    conflicts = value.get("conflicts", [])
    if not isinstance(dependencies, list) or not isinstance(conflicts, list):
        raise PackageError("koei-mod.json dependencies and conflicts must be lists of mod ids.")
    dependencies = tuple(sorted({_normal_id(item, label="dependency id") for item in dependencies}))
    conflicts = tuple(sorted({_normal_id(item, label="conflict id") for item in conflicts}))
    if mod_id in dependencies or mod_id in conflicts:
        raise PackageError("A mod cannot depend on or conflict with itself.")
    if set(dependencies) & set(conflicts):
        raise PackageError("A mod cannot both depend on and conflict with the same mod.")
    return mod_id, name.strip(), version.strip(), dependencies, conflicts


class ModManager:
    """Manage validated Nioh 2 PC loose-file mods and per-install profiles."""

    def __init__(self, state_dir: str | os.PathLike[str] | None = None,
                 game_root: str | os.PathLike[str] | None = None) -> None:
        self.state_dir = Path(state_dir or default_state_dir()).expanduser().resolve()
        self.packages_dir = self.state_dir / "packages"
        self.installations_dir = self.state_dir / "installations"
        self.index_path = self.state_dir / "library.json"
        self.index: dict[str, Any] = {"schema_version": 1, "mods": {}}
        self._library_lock = threading.RLock()
        self._nexus_jobs: queue.Queue[_NexusDownloadJob] = queue.Queue(maxsize=_MAX_NEXUS_QUEUE_SIZE)
        self._nexus_results: queue.Queue[NexusDownloadResult] = queue.Queue()
        self._nexus_worker_lock = threading.Lock()
        self._nexus_worker: threading.Thread | None = None
        self.installation: dict[str, Any] | None = None
        self.install_key: str | None = None
        self.install_state_dir: Path | None = None
        self.journal_path: Path | None = None
        self.current_game_root: Path | None = None
        self._load_index()
        if game_root is not None:
            self.set_game_root(game_root)

    def _load_index(self) -> None:
        if self.index_path.is_symlink() or _is_reparse_point(self.index_path):
            raise SafetyError("The mod library index must be a regular manager-owned file.")
        try:
            value = _read_json(self.index_path)
        except FileNotFoundError:
            return
        if value.get("schema_version") != 1 or not isinstance(value.get("mods"), dict):
            raise SafetyError("The mod library index has an unsupported format.")
        for mod_id, record in value["mods"].items():
            if _normal_id(mod_id) != mod_id or not isinstance(record, dict):
                raise SafetyError("The mod library index contains an invalid entry.")
            self._validate_record(record, mod_id)
        self.index = value

    def _save_index(self) -> None:
        _atomic_json(self.index_path, self.index)

    def _validate_record(self, record: dict[str, Any], mod_id: str) -> None:
        try:
            if record.get("id") != mod_id or not isinstance(record.get("name"), str):
                raise ValueError("identity")
            files = record.get("files")
            if not isinstance(files, list) or not files:
                raise ValueError("files")
            seen: set[str] = set()
            for item in files:
                rel = _safe_relative_path(item["path"]).as_posix()
                if rel.casefold() in seen or not _HASH_RE.fullmatch(item["sha256"]):
                    raise ValueError("file map")
                if not isinstance(item["size"], int) or item["size"] < 0:
                    raise ValueError("file size")
                if Path(rel).suffix.casefold() not in SUPPORTED_MOD_EXTENSIONS:
                    raise ValueError("file extension")
                seen.add(rel.casefold())
            if not _HASH_RE.fullmatch(record.get("content_sha256", "")):
                raise ValueError("content hash")
            _metadata_value({
                "schema_version": 1,
                "game_id": GAME_ID,
                "id": mod_id,
                "name": record.get("name"),
                "version": record.get("version", "unknown"),
                "dependencies": record.get("dependencies", []),
                "conflicts": record.get("conflicts", []),
            }, record.get("name", ""), mod_id)
        except (KeyError, TypeError, ValueError, PackageError) as exc:
            raise SafetyError(f"The mod library record for {mod_id!r} is invalid.") from exc

    def set_game_root(self, path: str | os.PathLike[str]) -> Path:
        root = _canonical_root(path)
        key_material = os.path.normcase(str(root)).casefold().encode("utf-8", "strict")
        key = hashlib.sha256(key_material).hexdigest()
        directory = self.installations_dir / key
        state_path = directory / "state.json"
        journal_path = directory / "transaction.json"
        if (directory.is_symlink() or _is_reparse_point(directory)
                or self.installations_dir.is_symlink() or _is_reparse_point(self.installations_dir)
                or state_path.is_symlink() or _is_reparse_point(state_path)
                or journal_path.is_symlink() or _is_reparse_point(journal_path)):
            raise SafetyError("The saved installation state contains a link or reparse point.")
        try:
            state = _read_json(state_path)
        except FileNotFoundError:
            state = self._new_installation(root)
        else:
            stored_root = state.get("game_root")
            if (state.get("schema_version") != 1 or state.get("game_id") != GAME_ID
                    or not isinstance(stored_root, str) or Path(stored_root).resolve() != root
                    or not isinstance(state.get("installed"), dict)
                    or not isinstance(state.get("profiles"), list)):
                raise SafetyError("The saved installation profile does not match this Nioh 2 folder.")
            self._validate_installation_state(state)
        previous = (self.install_key, self.install_state_dir, self.journal_path,
                    self.current_game_root, self.installation)
        self.install_key = key
        self.install_state_dir = directory
        self.journal_path = journal_path
        self.current_game_root = root
        self.installation = state
        try:
            if journal_path.exists():
                self._recover_transaction()
            elif not state_path.exists():
                self._save_installation()
        except Exception:
            (self.install_key, self.install_state_dir, self.journal_path,
             self.current_game_root, self.installation) = previous
            raise
        return root

    def has_pending_transaction_for(self, path: str | os.PathLike[str]) -> bool:
        """Return whether a root has a journal or unsafe saved-state path."""
        try:
            root = _canonical_root(path)
        except InstallationError:
            return False
        key_material = os.path.normcase(str(root)).casefold().encode("utf-8", "strict")
        key = hashlib.sha256(key_material).hexdigest()
        directory = self.installations_dir / key
        journal = directory / "transaction.json"
        state = directory / "state.json"
        if (self.installations_dir.is_symlink() or _is_reparse_point(self.installations_dir)
                or directory.is_symlink() or _is_reparse_point(directory)
                or state.is_symlink() or _is_reparse_point(state)
                or journal.is_symlink() or _is_reparse_point(journal)):
            return True
        return journal.exists()

    @staticmethod
    def _new_installation(root: Path) -> dict[str, Any]:
        profile_id = "default"
        return {
            "schema_version": 1,
            "game_id": GAME_ID,
            "game_root": str(root),
            "mods_dir_created": False,
            "active_profile_id": profile_id,
            "profiles": [{"id": profile_id, "name": "Default", "enabled_mods": []}],
            "installed": {},
        }

    def _validate_installation_state(self, state: dict[str, Any]) -> None:
        if (state.get("schema_version") != 1 or state.get("game_id") != GAME_ID
                or not isinstance(state.get("mods_dir_created"), bool)
                or not isinstance(state.get("installed"), dict)
                or not isinstance(state.get("profiles"), list)):
            raise SafetyError("The saved Nioh 2 installation state is invalid.")
        profiles = state["profiles"]
        if not profiles:
            raise SafetyError("At least one mod profile must exist.")
        profile_ids: set[str] = set()
        profile_names: set[str] = set()
        for profile in profiles:
            if not isinstance(profile, dict):
                raise SafetyError("The saved mod profiles are invalid.")
            profile_id = profile.get("id")
            name = profile.get("name")
            enabled = profile.get("enabled_mods")
            if (not isinstance(profile_id, str) or not _ID_RE.fullmatch(profile_id)
                    or not isinstance(name, str) or not name.strip()
                    or not isinstance(enabled, list)
                    or any(not isinstance(mod_id, str) for mod_id in enabled)
                    or len(set(enabled)) != len(enabled)):
                raise SafetyError("The saved mod profiles are invalid.")
            if profile_id in profile_ids or name.strip().casefold() in profile_names:
                raise SafetyError("The saved mod profiles contain duplicate identities.")
            profile_ids.add(profile_id)
            profile_names.add(name.strip().casefold())
            for mod_id in enabled:
                if mod_id not in self.index["mods"]:
                    raise SafetyError(f"Profile {name!r} refers to an unknown mod {mod_id!r}.")
        if state.get("active_profile_id") not in profile_ids:
            raise SafetyError("The active mod profile is missing.")
        for mod_id, enabled in state["installed"].items():
            if (not isinstance(mod_id, str) or mod_id not in self.index["mods"]
                    or not isinstance(enabled, bool)):
                raise SafetyError("The installed mod list is invalid.")
        for profile in profiles:
            for mod_id in profile["enabled_mods"]:
                if mod_id not in self.index["mods"]:
                    raise SafetyError(f"Profile {profile['name']!r} refers to an unknown mod {mod_id!r}.")

    def _save_installation(self) -> None:
        if self.installation is None or self.install_state_dir is None:
            raise InstallationError("Choose a Nioh 2 installation first.")
        _atomic_json(self.install_state_dir / "state.json", self.installation)

    def _require_installation(self) -> dict[str, Any]:
        if self.installation is None or self.current_game_root is None:
            raise InstallationError("Choose a Nioh 2 PC game folder first.")
        return self.installation

    def _require_loader(self, confirmed: bool) -> tuple[Path, Path]:
        state = self._require_installation()
        root = _canonical_root(state["game_root"])
        loader = root / LOADER_FILE
        if loader.is_symlink() or _is_reparse_point(loader) or not loader.is_file():
            raise InstallationError(
                "This manager requires an existing compatible Nioh 2 Mod Enabler d3d11.dll beside nioh2.exe. "
                "It will not install or replace loader files."
            )
        if not confirmed:
            raise InstallationError(
                "Confirm that the existing d3d11.dll is the Nioh 2 Mod Enabler before changing the Mods folder."
            )
        return root, self._mods_path(root)

    def import_archive(self, archive_path: str | os.PathLike[str]) -> ModRecord:
        self._ensure_no_pending_library_transactions()
        source = Path(archive_path).expanduser()
        if source.suffix.casefold() != ".zip":
            raise PackageError("Only ZIP packages are imported directly. Extract 7z packages with a trusted archive tool, then use a ZIP wrapper.")
        if source.is_symlink() or not source.is_file():
            raise PackageError("Select a regular ZIP file.")
        try:
            archive = zipfile.ZipFile(source, "r")
        except (OSError, zipfile.BadZipFile) as exc:
            raise PackageError(f"Cannot open ZIP package: {exc}") from exc
        with archive:
            if len(archive.infolist()) > _MAX_ARCHIVE_FILES:
                raise PackageError("The ZIP package contains too many entries.")
            entries: dict[str, zipfile.ZipInfo] = {}
            total_size = 0
            metadata_info = None
            fomod = False
            for info in archive.infolist():
                if info.is_dir():
                    raw_dir = info.filename[:-1] if info.filename.endswith("/") else info.filename
                    if raw_dir:
                        _safe_relative_path(raw_dir)
                    continue
                rel = _safe_relative_path(info.filename)
                mode = info.external_attr >> 16
                file_type = stat.S_IFMT(mode)
                if stat.S_ISLNK(mode) or file_type not in (0, stat.S_IFREG):
                    raise PackageError(f"Links and special files are unsupported: {info.filename!r}.")
                key = rel.as_posix().casefold()
                if key in entries:
                    raise PackageError(f"The ZIP contains duplicate paths that differ only by case: {info.filename!r}.")
                if info.file_size < 0 or info.file_size > _MAX_ARCHIVE_FILE_BYTES:
                    raise PackageError(f"The ZIP entry is too large: {info.filename!r}.")
                total_size += info.file_size
                if total_size > _MAX_ARCHIVE_BYTES:
                    raise PackageError("The ZIP package exceeds the 1 GiB extracted-size limit.")
                entries[key] = info
                if rel.name.casefold() == "moduleconfig.xml" and any(part.casefold() == "fomod" for part in rel.parts[:-1]):
                    fomod = True
                if rel.as_posix().casefold() == "koei-mod.json":
                    if metadata_info is not None:
                        raise PackageError("The ZIP contains more than one koei-mod.json manifest.")
                    metadata_info = info
            if fomod:
                raise PackageError("FOMOD installer packages require an interactive installer and are not supported.")
            data_entries = []
            ignored_docs = {"readme.md", "readme.txt", "changelog.md", "license", "license.txt", "license.md"}
            for info in entries.values():
                rel = PurePosixPath(info.filename)
                if rel.as_posix().casefold() == "koei-mod.json":
                    continue
                if rel.name.casefold() in ignored_docs or rel.name.casefold().startswith("license."):
                    continue
                if rel.name.casefold() == LOADER_FILE:
                    raise PackageError("Loader DLL packages are not supported; the manager does not write to the game root.")
                extension = Path(rel.name).suffix.casefold()
                if extension not in SUPPORTED_MOD_EXTENSIONS:
                    raise PackageError(
                        f"Unsupported package file {rel.as_posix()!r}. Nioh 2 support is limited to .ini, .fmt, .vb, .ib and .dds files."
                    )
                data_entries.append((rel, info, extension))
            ini_entries = [item for item in data_entries if item[2] == ".ini"]
            assets = [item for item in data_entries if item[2] in SUPPORTED_ASSET_EXTENSIONS]
            if len(ini_entries) != 1 or not assets:
                raise PackageError("A Nioh 2 mod must contain exactly one .ini file and at least one .fmt, .vb, .ib or .dds asset.")
            mod_root = ini_entries[0][0].parent
            payload: list[tuple[PurePosixPath, zipfile.ZipInfo]] = []
            for rel, info, _extension in data_entries:
                try:
                    installed_rel = rel.relative_to(mod_root) if mod_root != PurePosixPath(".") else rel
                except ValueError as exc:
                    raise PackageError("All Nioh 2 mod files must be inside the folder containing the .ini marker.") from exc
                if not installed_rel.parts:
                    raise PackageError("The .ini marker cannot be installed as an empty path.")
                payload.append((installed_rel, info))
            metadata = None
            if metadata_info is not None:
                if metadata_info.file_size > _MAX_METADATA_BYTES:
                    raise PackageError("koei-mod.json is too large.")
                try:
                    metadata = json.loads(archive.read(metadata_info).decode("utf-8"),
                                          object_pairs_hook=_unique_json_object)
                except (UnicodeError, ValueError, OSError, RuntimeError) as exc:
                    raise PackageError(f"Cannot read koei-mod.json: {exc}") from exc
            fallback_name = source.stem.strip() or "Nioh 2 mod"
            fallback_id = _slug(fallback_name)
            mod_id, name, version, dependencies, conflicts = _metadata_value(
                metadata, fallback_name, fallback_id
            )
            return self._store_package(archive, payload, mod_id, name, version, dependencies, conflicts)

    def _store_package(self, archive: zipfile.ZipFile,
                       payload: list[tuple[PurePosixPath, zipfile.ZipInfo]],
                       mod_id: str, name: str, version: str,
                       dependencies: tuple[str, ...], conflicts: tuple[str, ...]) -> ModRecord:
        if self.packages_dir.is_symlink() or _is_reparse_point(self.packages_dir):
            raise SafetyError("The package library path is a link or reparse point.")
        self.packages_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = self.packages_dir / f".import-{uuid.uuid4().hex}"
        payload_dir = temp_dir / "payload"
        payload_dir.mkdir(parents=True)
        try:
            total = 0
            for relative, info in payload:
                relative = _safe_relative_path(relative.as_posix())
                destination = payload_dir.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                size = 0
                with archive.open(info, "r") as source, destination.open("xb") as output:
                    while True:
                        block = source.read(1024 * 1024)
                        if not block:
                            break
                        size += len(block)
                        total += len(block)
                        if size > _MAX_ARCHIVE_FILE_BYTES or total > _MAX_ARCHIVE_BYTES:
                            raise PackageError("The expanded mod exceeds the safe import size limit.")
                        digest.update(block)
                        output.write(block)
                    output.flush()
                    os.fsync(output.fileno())
                if size != info.file_size:
                    raise PackageError(f"ZIP entry size changed while reading: {info.filename!r}.")
            files, _dirs = _iter_tree(payload_dir)
            mod_files = []
            for current, _dirs, filenames in os.walk(payload_dir):
                for filename in filenames:
                    path = Path(current) / filename
                    relative = path.relative_to(payload_dir).as_posix()
                    digest, size = files[relative.casefold()]
                    mod_files.append(ModFile(relative, digest, size))
            mod_files.sort(key=lambda item: item.path.casefold())
            content_digest = self._content_digest(mod_files)
            with self._library_lock:
                existing = self.index["mods"].get(mod_id)
                if existing is not None:
                    if existing.get("content_sha256") == content_digest:
                        shutil.rmtree(temp_dir)
                        return self._record(mod_id)
                    raise PackageError(f"Mod id {mod_id!r} already exists with different package contents.")
                final_dir = self.packages_dir / mod_id
                if final_dir.exists():
                    raise SafetyError(f"The package storage path for {mod_id!r} already exists without a library record.")
                os.replace(temp_dir, final_dir)
                record = {
                    "id": mod_id,
                    "name": name,
                    "version": version,
                    "dependencies": list(dependencies),
                    "conflicts": list(conflicts),
                    "files": [item.__dict__ for item in mod_files],
                    "content_sha256": content_digest,
                }
                self.index["mods"][mod_id] = record
                try:
                    self._save_index()
                except Exception:
                    self.index["mods"].pop(mod_id, None)
                    shutil.rmtree(final_dir, ignore_errors=True)
                    raise
                return self._record(mod_id)
        except Exception:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    @staticmethod
    def _content_digest(files: Iterable[ModFile]) -> str:
        digest = hashlib.sha256()
        for item in sorted(files, key=lambda entry: entry.path.casefold()):
            digest.update(item.path.casefold().encode("utf-8"))
            digest.update(b"\0")
            digest.update(item.sha256.encode("ascii"))
            digest.update(b"\0")
            digest.update(str(item.size).encode("ascii"))
            digest.update(b"\n")
        return digest.hexdigest()

    @_library_locked
    def _record(self, mod_id: str) -> ModRecord:
        record = self.index["mods"][mod_id]
        installed = bool(self.installation and mod_id in self.installation["installed"])
        enabled = False
        if self.installation:
            active = self._profile(self.installation["active_profile_id"])
            enabled = mod_id in active["enabled_mods"]
        return ModRecord(
            mod_id, record["name"], record["version"], tuple(record["dependencies"]),
            tuple(record["conflicts"]), tuple(ModFile(**item) for item in record["files"]),
            record["content_sha256"], installed, enabled,
        )

    def mods(self) -> tuple[ModRecord, ...]:
        with self._library_lock:
            return tuple(self._record(mod_id) for mod_id in sorted(self.index["mods"]))

    @property
    def nexus_downloads_pending(self) -> bool:
        """Whether an accepted Nexus job is queued or currently being handled."""
        with self._nexus_worker_lock:
            return (not self._nexus_jobs.empty()
                    or bool(self._nexus_worker and self._nexus_worker.is_alive()))

    def enqueue_nexus_download(
        self,
        request: NexusDownloadRequestLike,
        downloader: NexusArchiveDownloader,
    ) -> bool:
        """Accept a selected Nioh 2 Nexus ZIP for asynchronous library import.

        ``downloader`` is a same-process capability supplied by the Nexus
        browser. It resolves authorization and streams bytes to a manager-owned
        temporary ZIP; this service never accepts API keys or resolved URLs.
        The return value is immediate and true only if the bounded work queue
        accepted the request.
        """
        if not self._is_supported_nexus_request(request):
            return False
        try:
            download_archive = getattr(downloader, "download_archive", None)
        except Exception:
            return False
        if not callable(download_archive):
            return False
        with self._nexus_worker_lock:
            # Reject a full queue before starting a thread. For a new worker,
            # start while holding this lock and enqueue before it can complete
            # its empty-queue/shutdown handshake.
            if self._nexus_jobs.full():
                return False
            if self._nexus_worker is None or not self._nexus_worker.is_alive():
                worker = threading.Thread(
                    target=self._drain_nexus_jobs,
                    name="koei-nexus-import",
                    daemon=True,
                )
                self._nexus_worker = worker
                try:
                    worker.start()
                except Exception:
                    # Leave any older accepted work in the queue untouched.
                    self._nexus_worker = None
                    return False
            try:
                self._nexus_jobs.put_nowait(_NexusDownloadJob(request, downloader))
            except queue.Full:
                return False
        return True

    @staticmethod
    def _is_supported_nexus_request(request) -> bool:
        """Fail closed on the cross-component request's public metadata."""
        fields = (
            "provider", "game_id", "game_domain", "game_scoped_mod_id", "mod_id",
            "file_id", "file_name", "file_version_id", "game_scoped_file_version_id",
            "mod_page_url",
        )
        values = {}
        try:
            for name in fields:
                value = getattr(request, name)
                if not isinstance(value, str) or not value or len(value) > 2048:
                    return False
                if any(ord(char) < 32 or ord(char) == 127 for char in value):
                    return False
                values[name] = value
        except Exception:
            return False
        filename = values["file_name"]
        try:
            page = urlsplit(values["mod_page_url"])
        except ValueError:
            return False
        return (
            values["provider"] == "nexus"
            and values["game_id"] == GAME_ID
            and values["game_domain"] == "nioh2"
            and bool(_NEXUS_NUMERIC_ID_RE.fullmatch(values["game_scoped_mod_id"]))
            and bool(_NEXUS_NUMERIC_ID_RE.fullmatch(values["mod_id"]))
            and bool(_NEXUS_NUMERIC_ID_RE.fullmatch(values["game_scoped_file_version_id"]))
            and ModManager._is_safe_nexus_opaque_id(values["file_id"])
            and ModManager._is_safe_nexus_opaque_id(values["file_version_id"])
            and ModManager._is_safe_nexus_opaque_id(values["file_name"], max_length=256)
            and page.scheme == "https"
            and page.hostname == "www.nexusmods.com"
            and page.netloc == "www.nexusmods.com"
            and page.username is None
            and page.password is None
            and not page.query
            and not page.fragment
            and page.path == f"/nioh2/mods/{values['game_scoped_mod_id']}"
            and len(filename) <= 256
            and filename not in (".", "..")
            and "/" not in filename
            and "\\" not in filename
        )

    @staticmethod
    def _is_safe_nexus_opaque_id(value: str, *, max_length: int = 512) -> bool:
        if (not value or len(value) > max_length or value in (".", "..")
                or "/" in value or "\\" in value
                or any(ord(char) < 0x20 or ord(char) == 0x7f for char in value)):
            return False
        try:
            value.encode("utf-8", "strict")
        except UnicodeEncodeError:
            return False
        return True

    def _drain_nexus_jobs(self) -> None:
        while True:
            try:
                job = self._nexus_jobs.get_nowait()
            except queue.Empty:
                with self._nexus_worker_lock:
                    if self._nexus_jobs.empty():
                        self._nexus_worker = None
                        return
                continue
            try:
                result = self._run_nexus_job(job)
                self._nexus_results.put(result)
            finally:
                self._nexus_jobs.task_done()

    def _run_nexus_job(self, job: _NexusDownloadJob) -> NexusDownloadResult:
        """Download and validate one archive without installing it."""
        try:
            if not self._is_supported_nexus_request(job.request):
                return NexusDownloadResult(
                    "download_failed",
                    "The selected Nexus request is no longer supported by this manager.",
                )
            self.state_dir.mkdir(parents=True, exist_ok=True)
            if self.state_dir.is_symlink() or _is_reparse_point(self.state_dir):
                raise SafetyError("The manager state directory is not a regular directory.")
            with tempfile.TemporaryDirectory(prefix=".nexus-", dir=self.state_dir) as temporary:
                destination = Path(temporary) / self._nexus_temp_archive_name(job.request)
                try:
                    job.downloader.download_archive(job.request, destination)
                except Exception as error:
                    return self._nexus_download_error_result(error)
                if (destination.is_symlink() or _is_reparse_point(destination)
                        or not destination.is_file()):
                    return NexusDownloadResult(
                        "download_failed",
                        "Nexus did not produce a regular ZIP archive.",
                    )
                try:
                    size = destination.stat().st_size
                except OSError:
                    return NexusDownloadResult(
                        "download_failed",
                        "Nexus did not produce a readable ZIP archive.",
                    )
                if size > _MAX_NEXUS_DOWNLOAD_BYTES:
                    return NexusDownloadResult(
                        "download_failed",
                        "The Nexus archive exceeds the manager's 1 GiB download limit.",
                    )
                try:
                    mod = self.import_archive(destination)
                except PackageError:
                    return NexusDownloadResult(
                        "package_rejected",
                        "The downloaded ZIP did not pass Nioh 2 package validation.",
                    )
                except Exception:
                    return NexusDownloadResult(
                        "manager_error",
                        "The manager could not add the downloaded package to its library.",
                    )
                return NexusDownloadResult(
                    "imported",
                    "Added the validated package to the mod library. Review it before enabling or installing.",
                    mod.id,
                )
        except Exception:
            return NexusDownloadResult(
                "manager_error",
                "The manager could not prepare a temporary download location.",
            )

    @staticmethod
    def _nexus_download_error_result(error: Exception) -> NexusDownloadResult:
        try:
            status = getattr(error, "status", None)
        except Exception:
            status = None
        if status == 429:
            try:
                retry_header = getattr(error, "retry_after", None)
            except Exception:
                retry_header = None
            retry_after = ModManager._parse_retry_after(retry_header)
            if retry_after is None:
                message = "Nexus rate limit reached. Wait before trying again."
            else:
                message = f"Nexus rate limit reached. Wait at least {retry_after} seconds before retrying."
            return NexusDownloadResult("rate_limited", message, retry_after_seconds=retry_after)
        return NexusDownloadResult(
            "download_failed",
            "Nexus could not provide this archive. Check your Nexus access and try again.",
        )

    @staticmethod
    def _parse_retry_after(value) -> int | None:
        """Parse a bounded RFC Retry-After value without echoing its raw text."""
        if not isinstance(value, str) or not value or len(value) > 128:
            return None
        if any(ord(char) < 0x20 or ord(char) == 0x7f for char in value):
            return None
        text = value.strip()
        if text.isascii() and text.isdigit():
            seconds = int(text)
            return seconds if 0 < seconds <= 7 * 24 * 60 * 60 else None
        try:
            retry_at = parsedate_to_datetime(text)
            if retry_at.tzinfo is None:
                return None
            seconds = math.ceil((retry_at.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None
        return seconds if 0 < seconds <= 7 * 24 * 60 * 60 else None

    @staticmethod
    def _nexus_temp_archive_name(request) -> str:
        """Make a safe, recognizable temporary ZIP name without using raw input."""
        filename = getattr(request, "file_name")
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(filename).stem).strip(".-_")
        if len(stem) < 2 or "disabled" in stem.casefold():
            stem = "Nexus-Mod"
        if stem.split(".", 1)[0].casefold() in _WINDOWS_RESERVED:
            stem = "Nexus-" + stem
        identity = "\0".join((
            getattr(request, "game_scoped_mod_id"),
            getattr(request, "file_id"),
            getattr(request, "file_version_id"),
        ))
        suffix = hashlib.sha256(identity.encode("utf-8", "strict")).hexdigest()[:8]
        return f"{stem[:36]}-{suffix}.zip"

    def poll_nexus_download_results(self, *, limit: int = 20) -> tuple[NexusDownloadResult, ...]:
        """Return completed Nexus imports without blocking the UI thread."""
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("The Nexus result limit must be between 1 and 100.")
        results = []
        for _ in range(limit):
            try:
                results.append(self._nexus_results.get_nowait())
            except queue.Empty:
                break
        return tuple(results)

    def profiles(self) -> tuple[ProfileRecord, ...]:
        if self.installation is None:
            return ()
        return tuple(ProfileRecord(item["id"], item["name"], tuple(sorted(item["enabled_mods"])))
                     for item in self.installation["profiles"])

    @property
    def active_profile_id(self) -> str | None:
        return self.installation.get("active_profile_id") if self.installation else None

    @property
    def has_pending_transaction(self) -> bool:
        path = self.journal_path
        return bool(path and (path.exists() or path.is_symlink() or _is_reparse_point(path)))

    def recover_pending_transaction(self) -> None:
        """Recover the selected installation's journal before refreshing state."""
        if self.has_pending_transaction:
            self._recover_transaction()

    def _ensure_transaction_recovered(self) -> None:
        """Recover the selected install before any operation reads or changes its state."""
        self.recover_pending_transaction()

    def _ensure_no_pending_library_transactions(self) -> None:
        """Protect global library changes from journals belonging to any install."""
        self._ensure_transaction_recovered()
        directory = self.installations_dir
        if directory.is_symlink() or _is_reparse_point(directory):
            raise SafetyError("The saved installation directory is a link or reparse point.")
        if not directory.exists():
            return
        if not directory.is_dir():
            raise SafetyError("The saved installation path is not a directory.")
        for child in directory.iterdir():
            if child.is_symlink() or _is_reparse_point(child):
                raise SafetyError("A saved installation path is a link or reparse point.")
            if not child.is_dir():
                continue
            pending = child / "transaction.json"
            if pending.is_symlink() or _is_reparse_point(pending):
                raise SafetyError("A saved installation transaction journal is a link or reparse point.")
            if pending.exists() and pending != self.journal_path:
                raise InstallationError(
                    "A pending transaction exists for another registered game folder. Select that folder and "
                    "recover it before changing the shared mod library."
                )

    def _profile(self, profile_id: str) -> dict[str, Any]:
        state = self._require_installation()
        for profile in state["profiles"]:
            if profile["id"] == profile_id:
                return profile
        raise ProfileError(f"Mod profile {profile_id!r} does not exist.")

    @staticmethod
    def _profile_name(value: str) -> str:
        name = value.strip() if isinstance(value, str) else ""
        if not name or len(name) > 80 or any(ord(char) < 32 for char in name):
            raise ProfileError("Profile names must contain 1–80 printable characters.")
        return name

    def create_profile(self, name: str, copy_from: str | None = None) -> ProfileRecord:
        self._ensure_transaction_recovered()
        state = self._require_installation()
        name = self._profile_name(name)
        if any(item["name"].casefold() == name.casefold() for item in state["profiles"]):
            raise ProfileError("A profile with that name already exists.")
        enabled: list[str] = []
        if copy_from is not None:
            enabled = list(self._profile(copy_from)["enabled_mods"])
        profile_id = f"profile-{uuid.uuid4().hex[:12]}"
        state["profiles"].append({"id": profile_id, "name": name, "enabled_mods": enabled})
        try:
            self._save_installation()
        except Exception:
            state["profiles"] = [item for item in state["profiles"] if item["id"] != profile_id]
            raise
        return ProfileRecord(profile_id, name, tuple(sorted(enabled)))

    def rename_profile(self, profile_id: str, name: str) -> None:
        self._ensure_transaction_recovered()
        state = self._require_installation()
        name = self._profile_name(name)
        if any(item["id"] != profile_id and item["name"].casefold() == name.casefold()
               for item in state["profiles"]):
            raise ProfileError("A profile with that name already exists.")
        profile = self._profile(profile_id)
        old_name = profile["name"]
        profile["name"] = name
        try:
            self._save_installation()
        except Exception:
            profile["name"] = old_name
            raise

    def delete_profile(self, profile_id: str) -> None:
        self._ensure_transaction_recovered()
        state = self._require_installation()
        if len(state["profiles"]) < 2:
            raise ProfileError("Keep at least one profile.")
        if state["active_profile_id"] == profile_id:
            raise ProfileError("Apply another profile before deleting the active profile.")
        self._profile(profile_id)
        old_profiles = state["profiles"]
        state["profiles"] = [item for item in old_profiles if item["id"] != profile_id]
        try:
            self._save_installation()
        except Exception:
            state["profiles"] = old_profiles
            raise

    def set_profile_mod_enabled(self, profile_id: str, mod_id: str, enabled: bool) -> None:
        self._ensure_transaction_recovered()
        if mod_id not in self.index["mods"]:
            raise ProfileError(f"Mod {mod_id!r} is not in the library.")
        state = self._require_installation()
        profile = self._profile(profile_id)
        selected = set(profile["enabled_mods"])
        if enabled:
            selected.add(mod_id)
        else:
            selected.discard(mod_id)
        previous = profile["enabled_mods"]
        profile["enabled_mods"] = sorted(selected)
        issues = self.profile_issues(profile_id)
        if issues:
            profile["enabled_mods"] = previous
            raise ProfileError("Cannot enable this mod: " + "; ".join(issues))
        try:
            self._save_installation()
        except Exception:
            profile["enabled_mods"] = previous
            raise

    @_library_locked
    def profile_issues(self, profile_id: str) -> tuple[str, ...]:
        profile = self._profile(profile_id)
        selected = set(profile["enabled_mods"])
        issues: list[str] = []
        for mod_id in sorted(selected):
            record = self.index["mods"].get(mod_id)
            if record is None:
                issues.append(f"Profile refers to missing mod {mod_id!r}.")
                continue
            for dependency in record["dependencies"]:
                if dependency not in selected:
                    issues.append(f"{record['name']} requires {dependency} to be enabled in this profile.")
            for conflict in record["conflicts"]:
                if conflict in selected:
                    issues.append(f"{record['name']} conflicts with {self.index['mods'].get(conflict, {}).get('name', conflict)}.")
        selected_records = [(mod_id, self.index["mods"].get(mod_id)) for mod_id in sorted(selected)]
        seen_assets: dict[str, tuple[str, str]] = {}
        for mod_id, record in selected_records:
            if record is None:
                continue
            for item in record["files"]:
                if Path(item["path"]).suffix.casefold() not in SUPPORTED_ASSET_EXTENSIONS:
                    continue
                asset_key = item["path"].casefold()
                previous = seen_assets.get(asset_key)
                if previous and previous[1] != item["sha256"]:
                    other_id, _other_hash = previous
                    issues.append(
                        f"Possible asset path conflict: {Path(item['path']).as_posix()} is changed by "
                        f"{self.index['mods'][other_id]['name']} and {record['name']}; the loader has no verified load-order control."
                    )
                elif previous is None:
                    seen_assets[asset_key] = (mod_id, item["sha256"])
        return tuple(dict.fromkeys(issues))

    def _package_path(self, mod_id: str) -> Path:
        if mod_id not in self.index["mods"]:
            raise ModManagerError(f"Mod {mod_id!r} is not in the library.")
        if self.packages_dir.is_symlink() or _is_reparse_point(self.packages_dir):
            raise SafetyError("The package library path is a link or reparse point.")
        package_dir = self.packages_dir / mod_id
        if package_dir.is_symlink() or _is_reparse_point(package_dir):
            raise SafetyError(f"The stored package for {mod_id!r} is linked outside manager storage.")
        payload = package_dir / "payload"
        if payload.is_symlink() or _is_reparse_point(payload):
            raise SafetyError(f"The stored package payload for {mod_id!r} is linked outside manager storage.")
        return payload

    def _verify_package(self, mod_id: str) -> None:
        record = self.index["mods"][mod_id]
        package = self._package_path(mod_id)
        try:
            valid = _verify_tree(package, (ModFile(**item) for item in record["files"]))
        except (OSError, SafetyError) as exc:
            raise SafetyError(f"The stored package for {record['name']} is missing or unsafe: {exc}") from exc
        if not valid:
            raise SafetyError(f"The stored package for {record['name']} changed after import; refusing to install it.")

    def _target_name(self, mod_id: str, enabled: bool) -> str:
        return mod_id if enabled else mod_id + DISABLED_SUFFIX

    def _game_relative(self, value: str) -> Path:
        relative = _safe_relative_path(value).as_posix()
        root = self.current_game_root
        if root is None:
            raise InstallationError("Choose a Nioh 2 PC game folder first.")
        target = root.joinpath(*PurePosixPath(relative).parts)
        resolved = target.resolve(strict=False)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise SafetyError("A managed path resolves outside the selected game folder.") from exc
        cursor = root
        for part in PurePosixPath(relative).parts:
            cursor = cursor / part
            if cursor.is_symlink() or _is_reparse_point(cursor):
                raise SafetyError(f"A link or reparse point blocks managed path {relative!r}.")
        return target

    def _mods_path(self, root: Path) -> Path:
        mods = root / MODS_DIR
        if mods.is_symlink() or _is_reparse_point(mods):
            raise SafetyError("The game's Mods path must be a real directory, not a link or file.")
        if mods.exists() and not mods.is_dir():
            raise SafetyError("The game's Mods path must be a real directory, not a link or file.")
        return mods

    def install_mod(self, mod_id: str, *, loader_confirmed: bool = False) -> None:
        self._ensure_transaction_recovered()
        state = self._require_installation()
        root, mods = self._require_loader(loader_confirmed)
        if mod_id not in self.index["mods"]:
            raise ModManagerError(f"Mod {mod_id!r} is not in the library.")
        if mod_id in state["installed"]:
            raise InstallationError("This mod is already installed in the selected game folder.")
        if mod_id in self._profile(state["active_profile_id"])["enabled_mods"]:
            raise ProfileError("This mod is enabled in the active profile. Apply that profile to install and enable it.")
        self._verify_package(mod_id)
        destination = self._target_name(mod_id, enabled=False)
        if mods.exists() and self._casefold_child(mods, destination) is not None:
            raise SafetyError(f"The target Mods folder already contains {destination!r}; no files were changed.")
        new_state = copy.deepcopy(state)
        new_state["installed"][mod_id] = False
        self._run_transaction(
            state, new_state,
            installs=[{"mod_id": mod_id, "destination": f"{MODS_DIR}/{destination}"}],
            create_mods=not mods.exists(),
        )

    def uninstall_mod(self, mod_id: str, *, loader_confirmed: bool = False) -> None:
        self._ensure_transaction_recovered()
        state = self._require_installation()
        root, mods = self._require_loader(loader_confirmed)
        if mod_id not in state["installed"]:
            raise InstallationError("This mod is not installed in the selected game folder.")
        if (state["installed"][mod_id]
                or mod_id in self._profile(state["active_profile_id"])["enabled_mods"]):
            raise ProfileError("Disable this mod in the active profile and apply that profile before uninstalling it.")
        self._verify_managed_directory(mod_id, enabled=False)
        source = f"{MODS_DIR}/{self._target_name(mod_id, enabled=False)}"
        backup = f".ktmm-remove-{uuid.uuid4().hex}-{mod_id}"
        new_state = copy.deepcopy(state)
        new_state["installed"].pop(mod_id)
        self._run_transaction(
            state, new_state,
            moves=[{"source": source, "destination": backup, "mod_id": mod_id}],
            cleanup=[backup],
        )
        if new_state.get("mods_dir_created") and mods.exists():
            try:
                mods.rmdir()
                new_state["mods_dir_created"] = False
                self.installation = new_state
                self._save_installation()
            except OSError:
                pass

    @_library_locked
    def remove_mod(self, mod_id: str) -> None:
        self._ensure_no_pending_library_transactions()
        if mod_id not in self.index["mods"]:
            raise ModManagerError(f"Mod {mod_id!r} is not in the library.")
        for path in self.installations_dir.glob("*/state.json"):
            data = _read_json(path)
            if path.is_symlink() or not isinstance(data.get("installed"), dict):
                raise SafetyError(f"Cannot safely inspect another Nioh 2 installation state: {path.name}.")
            if mod_id in data.get("installed", {}):
                raise InstallationError("Uninstall this mod from every registered game folder before removing it from the library.")
            profiles = data.get("profiles")
            if not isinstance(profiles, list):
                raise SafetyError(f"Cannot safely inspect mod profiles in {path.name}.")
            for profile in profiles:
                if not isinstance(profile, dict) or not isinstance(profile.get("enabled_mods"), list):
                    raise SafetyError(f"Cannot safely inspect mod profiles in {path.name}.")
                if mod_id in profile["enabled_mods"]:
                    raise ProfileError(f"Remove {mod_id!r} from every registered profile before deleting it from the library.")
        self._verify_package(mod_id)
        package_dir = self.packages_dir / mod_id
        quarantine = self.packages_dir / f".remove-{mod_id}-{uuid.uuid4().hex}"
        os.replace(package_dir, quarantine)
        record = self.index["mods"].pop(mod_id)
        try:
            self._save_index()
        except Exception:
            self.index["mods"][mod_id] = record
            os.replace(quarantine, package_dir)
            raise
        shutil.rmtree(quarantine)

    def apply_profile(self, profile_id: str, *, loader_confirmed: bool = False) -> tuple[str, ...]:
        self._ensure_transaction_recovered()
        state = self._require_installation()
        root, mods_path = self._require_loader(loader_confirmed)
        profile = self._profile(profile_id)
        issues = self.profile_issues(profile_id)
        if issues:
            raise ProfileError("Resolve the profile issues before applying it: " + "; ".join(issues))
        desired_enabled = set(profile["enabled_mods"])
        old_installed = dict(state["installed"])
        new_state = copy.deepcopy(state)
        installs: list[dict[str, str]] = []
        moves: list[dict[str, str]] = []
        statuses: list[str] = []
        for mod_id, was_enabled in sorted(old_installed.items()):
            self._verify_managed_directory(mod_id, enabled=was_enabled)
            should_enable = mod_id in desired_enabled
            old_name = self._target_name(mod_id, enabled=was_enabled)
            new_name = self._target_name(mod_id, enabled=should_enable)
            if old_name != new_name:
                if self._casefold_child(mods_path, new_name) is not None:
                    raise SafetyError(f"The destination folder {new_name!r} already exists; no folders were renamed.")
                moves.append({"source": f"{MODS_DIR}/{old_name}",
                              "destination": f"{MODS_DIR}/{new_name}", "mod_id": mod_id})
                statuses.append(f"{'Enabled' if should_enable else 'Disabled'} {self.index['mods'][mod_id]['name']}.")
            new_state["installed"][mod_id] = should_enable
        for mod_id in sorted(desired_enabled - set(old_installed)):
            self._verify_package(mod_id)
            destination = self._target_name(mod_id, enabled=True)
            if self._casefold_child(mods_path, destination) is not None:
                raise SafetyError(f"The target Mods folder already contains {destination!r}; no files were changed.")
            installs.append({"mod_id": mod_id, "destination": f"{MODS_DIR}/{destination}"})
            new_state["installed"][mod_id] = True
            statuses.append(f"Installed and enabled {self.index['mods'][mod_id]['name']}.")
        for mod_id in sorted(set(old_installed) - desired_enabled):
            if old_installed[mod_id]:
                statuses.append(f"Disabled {self.index['mods'][mod_id]['name']}.")
        new_state["active_profile_id"] = profile_id
        self._run_transaction(state, new_state, moves=moves, installs=installs,
                              create_mods=bool(installs) and not mods_path.exists())
        return tuple(statuses or [f"Applied profile {profile['name']} with no file changes."])

    def _verify_managed_directory(self, mod_id: str, *, enabled: bool) -> Path:
        record = self.index["mods"].get(mod_id)
        if record is None:
            raise SafetyError(f"The installed mod {mod_id!r} is not in the library.")
        root = self.current_game_root
        if root is None:
            raise InstallationError("Choose a Nioh 2 PC game folder first.")
        mods = self._mods_path(root)
        folder = mods / self._target_name(mod_id, enabled)
        try:
            if not _verify_tree(folder, (ModFile(**item) for item in record["files"])):
                raise SafetyError(f"Managed mod folder {folder.name!r} was changed outside this manager; refusing to overwrite or remove it.")
        except OSError as exc:
            raise SafetyError(f"Managed mod folder {folder.name!r} cannot be checked: {exc}") from exc
        return folder

    @staticmethod
    def _casefold_child(parent: Path, name: str) -> Path | None:
        if not parent.exists():
            return None
        wanted = name.casefold()
        matches = [parent / child for child in os.listdir(parent) if child.casefold() == wanted]
        if len(matches) > 1:
            raise SafetyError(f"The Mods folder contains multiple case-insensitive matches for {name!r}.")
        return matches[0] if matches else None

    def _run_transaction(self, old_state: dict[str, Any], new_state: dict[str, Any], *,
                         moves: list[dict[str, str]] | None = None,
                         installs: list[dict[str, str]] | None = None,
                         cleanup: list[str] | None = None,
                         create_mods: bool = False) -> None:
        self._require_installation()
        root = self.current_game_root
        journal_path = self.journal_path
        assert root is not None and journal_path is not None
        if journal_path.is_symlink() or _is_reparse_point(journal_path):
            raise SafetyError("The transaction journal is a link or reparse point.")
        if journal_path.exists():
            self._recover_transaction()
            raise InstallationError(
                "A previous mod operation was recovered. Refresh the manager, review the selected profile, and retry."
            )
        moves = list(moves or [])
        installs = list(installs or [])
        cleanup = list(cleanup or [])
        stage_name = f".ktmm-transaction-{uuid.uuid4().hex}"
        stage_path = root / stage_name
        if stage_path.exists():
            raise SafetyError("A transaction staging path unexpectedly exists.")
        journal = {
            "schema_version": 1,
            "committed": False,
            "old_state": copy.deepcopy(old_state),
            "new_state": copy.deepcopy(new_state),
            "moves": moves,
            "installs": installs,
            "cleanup": cleanup,
            "stage": stage_name,
            "create_mods": create_mods,
            "mods_created": False,
        }
        self._validate_transaction_journal(journal)
        stage_path.mkdir()
        try:
            _atomic_json(journal_path, journal)
        except Exception:
            stage_path.rmdir()
            raise
        try:
            mods_path = self._mods_path(root)
            if create_mods and not mods_path.exists():
                mods_path.mkdir()
                journal["mods_created"] = True
                new_state["mods_dir_created"] = True
                journal["new_state"] = copy.deepcopy(new_state)
                _atomic_json(journal_path, journal)
            for item in installs:
                mod_id = item["mod_id"]
                package = self._package_path(mod_id)
                self._verify_package(mod_id)
                staged = stage_path / mod_id
                shutil.copytree(package, staged, symlinks=False)
                record = self.index["mods"][mod_id]
                if not _verify_tree(staged, (ModFile(**entry) for entry in record["files"])):
                    raise SafetyError(f"Staged package for {record['name']} did not pass hash verification.")
            for item in moves:
                source = self._game_relative(item["source"])
                destination = self._game_relative(item["destination"])
                if not source.exists() or destination.exists():
                    raise SafetyError("A transaction path changed before it could be renamed.")
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source, destination)
            for item in installs:
                source = stage_path / item["mod_id"]
                destination = self._game_relative(item["destination"])
                if destination.exists():
                    raise SafetyError(f"The transaction destination {destination.name!r} appeared during install.")
                os.replace(source, destination)
            self.installation = new_state
            self._save_installation()
            journal["committed"] = True
            journal["new_state"] = copy.deepcopy(new_state)
            _atomic_json(journal_path, journal)
        except Exception:
            self._rollback_transaction(journal)
            raise
        # Once the committed journal is durable, cleanup must roll forward.
        # Rolling back after deleting an uninstall backup could lose the only
        # remaining copy of the managed directory.
        self._finish_committed_transaction(journal)

    def _validate_transaction_journal(self, journal: dict[str, Any]) -> None:
        if (journal.get("schema_version") != 1
                or not isinstance(journal.get("committed"), bool)
                or not isinstance(journal.get("create_mods"), bool)
                or not isinstance(journal.get("mods_created"), bool)
                or not isinstance(journal.get("old_state"), dict)
                or not isinstance(journal.get("new_state"), dict)
                or not isinstance(journal.get("moves"), list)
                or not isinstance(journal.get("installs"), list)
                or not isinstance(journal.get("cleanup"), list)
                or not isinstance(journal.get("stage"), str)
                or not _TRANSACTION_STAGE_RE.fullmatch(journal["stage"])
                or len(journal["moves"]) > _MAX_ARCHIVE_FILES
                or len(journal["installs"]) > _MAX_ARCHIVE_FILES
                or len(journal["cleanup"]) > _MAX_ARCHIVE_FILES):
            raise SafetyError("An incomplete transaction has an unsupported journal format.")
        root = self.current_game_root
        if root is None:
            raise InstallationError("Choose a Nioh 2 PC game folder first.")
        for value in (journal["old_state"], journal["new_state"]):
            game_root = value.get("game_root")
            if (not isinstance(game_root, str) or Path(game_root).resolve() != root):
                raise SafetyError("A transaction journal belongs to a different game folder.")
            self._validate_installation_state(value)

        old_state = journal["old_state"]
        new_state = journal["new_state"]
        removal_backups: set[str] = set()
        for item in journal["moves"]:
            if (not isinstance(item, dict) or set(item) != {"source", "destination", "mod_id"}
                    or not isinstance(item["mod_id"], str)
                    or item["mod_id"] not in self.index["mods"]):
                raise SafetyError("A transaction journal contains an invalid folder rename.")
            mod_id = item["mod_id"]
            source = _safe_relative_path(item["source"]).as_posix()
            destination = _safe_relative_path(item["destination"]).as_posix()
            old_enabled = old_state["installed"].get(mod_id)
            new_enabled = new_state["installed"].get(mod_id)
            if old_enabled is None:
                raise SafetyError("A transaction journal renames a mod that was not installed.")
            expected_source = f"{MODS_DIR}/{self._target_name(mod_id, old_enabled)}"
            if source != expected_source:
                raise SafetyError("A transaction journal rename source is outside the expected mod folder.")
            if new_enabled is not None:
                expected_destination = f"{MODS_DIR}/{self._target_name(mod_id, new_enabled)}"
                if destination != expected_destination or old_enabled == new_enabled:
                    raise SafetyError("A transaction journal rename does not match its profile state.")
            else:
                match = _REMOVAL_BACKUP_RE.fullmatch(destination)
                if (new_state["installed"].get(mod_id) is not None or not match
                        or match.group(1) != mod_id):
                    raise SafetyError("A transaction journal removal destination is invalid.")
                removal_backups.add(destination)

        for item in journal["installs"]:
            if (not isinstance(item, dict) or set(item) != {"mod_id", "destination"}
                    or not isinstance(item["mod_id"], str)
                    or item["mod_id"] not in self.index["mods"]):
                raise SafetyError("A transaction journal contains an invalid package install.")
            mod_id = item["mod_id"]
            destination = _safe_relative_path(item["destination"]).as_posix()
            enabled = new_state["installed"].get(mod_id)
            if (mod_id in old_state["installed"] or enabled is None
                    or destination != f"{MODS_DIR}/{self._target_name(mod_id, enabled)}"):
                raise SafetyError("A transaction journal install does not match its profile state.")

        if (any(not isinstance(item, str) for item in journal["cleanup"])
                or len(set(journal["cleanup"])) != len(journal["cleanup"])
                or any(item not in removal_backups for item in journal["cleanup"])):
            raise SafetyError("A transaction journal cleanup path is not a managed removal backup.")
        if journal["create_mods"] and old_state.get("mods_dir_created"):
            raise SafetyError("A transaction journal has an invalid Mods-folder ownership flag.")
        if journal["mods_created"] and not journal["create_mods"]:
            raise SafetyError("A transaction journal has an invalid Mods-folder creation record.")
        if journal["mods_created"] and not new_state.get("mods_dir_created"):
            raise SafetyError("A transaction journal does not record ownership of its new Mods folder.")

    def _finish_committed_transaction(self, journal: dict[str, Any]) -> None:
        self._validate_transaction_journal(journal)
        if not journal["committed"]:
            raise SafetyError("Cannot finish cleanup for an uncommitted transaction.")
        root = self.current_game_root
        if root is None:
            raise InstallationError("Choose a Nioh 2 PC game folder first.")
        for relative in journal.get("cleanup", []):
            path = self._game_relative(relative)
            if path.exists():
                mod_id = next((item["mod_id"] for item in journal.get("moves", [])
                               if item["destination"] == relative), None)
                if mod_id is None or not _verify_tree(path, (ModFile(**entry)
                                                              for entry in self.index["mods"][mod_id]["files"])):
                    raise SafetyError(f"Cannot safely remove transaction backup {path.name!r}.")
                shutil.rmtree(path)
        stage = root / journal["stage"]
        if stage.exists():
            self._clean_transaction_stage(stage, journal, committed=True)
        if self.journal_path and self.journal_path.exists():
            self.journal_path.unlink()

    def _clean_transaction_stage(self, stage: Path, journal: dict[str, Any], *, committed: bool) -> None:
        if stage.is_symlink() or _is_reparse_point(stage) or not stage.is_dir():
            raise SafetyError("The transaction staging path was replaced by a link or non-directory.")
        entries = list(stage.iterdir())
        if committed:
            if entries:
                raise SafetyError("A committed transaction has unexpected files in its staging directory.")
            stage.rmdir()
            return
        expected = {item["mod_id"] for item in journal["installs"]}
        seen: set[str] = set()
        for child in entries:
            if (child.name.casefold() not in expected or child.name.casefold() in seen
                    or child.is_symlink() or _is_reparse_point(child) or not child.is_dir()):
                raise SafetyError(f"Unexpected content blocks transaction-stage cleanup: {child.name!r}.")
            seen.add(child.name.casefold())
            mod_id = child.name.casefold()
            record = self.index.get("mods", {}).get(mod_id)
            if (record is None or not _verify_tree(
                    child, (ModFile(**entry) for entry in record["files"]), allow_subset=True)):
                raise SafetyError(f"Cannot verify staged package content for {mod_id!r}; recovery stopped.")
        for child in entries:
            shutil.rmtree(child)
        stage.rmdir()

    def _rollback_transaction(self, journal: dict[str, Any]) -> None:
        self._validate_transaction_journal(journal)
        if journal["committed"]:
            raise SafetyError("A committed transaction must be recovered by rolling forward.")
        root = self.current_game_root
        if root is None:
            raise InstallationError("Choose a Nioh 2 PC game folder first.")
        errors: list[str] = []
        try:
            for item in reversed(journal.get("moves", [])):
                source = self._game_relative(item["source"])
                destination = self._game_relative(item["destination"])
                if destination.exists() and not source.exists():
                    mod_id = item["mod_id"]
                    record = self.index["mods"].get(mod_id)
                    if record is None or not _verify_tree(destination, (ModFile(**entry) for entry in record["files"])):
                        raise SafetyError(f"Cannot restore renamed folder {destination.name!r}; its bytes changed.")
                    os.replace(destination, source)
                elif destination.exists() and source.exists():
                    raise SafetyError(f"Both transaction paths exist for {item['mod_id']!r}; neither was changed.")
                elif not destination.exists() and not source.exists():
                    raise SafetyError(f"Neither transaction path exists for {item['mod_id']!r}; recovery stopped.")
                else:
                    mod_id = item["mod_id"]
                    record = self.index["mods"].get(mod_id)
                    if record is None or not _verify_tree(source, (ModFile(**entry) for entry in record["files"])):
                        raise SafetyError(f"Cannot verify unchanged mod folder {source.name!r}; recovery stopped.")
            for item in reversed(journal.get("installs", [])):
                destination = self._game_relative(item["destination"])
                if destination.exists():
                    record = self.index["mods"].get(item["mod_id"])
                    if record is None or not _verify_tree(destination, (ModFile(**entry) for entry in record["files"])):
                        raise SafetyError(f"Cannot remove transaction install {destination.name!r}; its bytes changed.")
                    shutil.rmtree(destination)
            stage = root / journal["stage"]
            if stage.exists():
                self._clean_transaction_stage(stage, journal, committed=False)
            old_state = journal["old_state"]
            mods = root / MODS_DIR
            if (journal["mods_created"]
                    and mods.exists() and not any(mods.iterdir())):
                mods.rmdir()
            self.installation = old_state
            self._save_installation()
            if self.journal_path and self.journal_path.exists():
                self.journal_path.unlink()
        except Exception as exc:
            errors.append(str(exc))
        if errors:
            raise SafetyError("Transaction rollback needs attention: " + "; ".join(errors))

    def _recover_transaction(self) -> None:
        if self.journal_path is None:
            return
        if self.journal_path.is_symlink() or _is_reparse_point(self.journal_path):
            raise SafetyError("The transaction journal is a link or reparse point.")
        journal = _read_json(self.journal_path)
        self._validate_transaction_journal(journal)
        if journal["committed"]:
            self.installation = journal["new_state"]
            self._save_installation()
            self._finish_committed_transaction(journal)
        else:
            self._rollback_transaction(journal)
