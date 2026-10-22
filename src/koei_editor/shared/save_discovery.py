"""Bounded, read-only discovery of installed games and candidate live locations.

Discovery does not open gameplay files, qualify a native save, select a parser,
import a save, or grant permission to edit a live directory. Callers must ask
users to make separate copies, including the original companion context, before
using the existing copied-save workflow. Paths are private local UI data;
``report`` deliberately excludes them and all Steam account identifiers.
"""
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import stat

from koei_editor.game_registry import GAMES
from koei_editor.games.dw3.models import SaveError
from koei_editor.resources import data_file
from koei_editor.shared.save_safety import reserved_windows_path


@dataclass(frozen=True)
class SteamMapping:
    app_id: str
    game_id: str
    evidence: str


@dataclass(frozen=True)
class NativeMapping:
    game_id: str
    base: str
    relative: str
    evidence: str


_MAX_MAPPING_BYTES = 64 * 1024
_MAX_MAPPING_RECORDS = 128


def _unique_mapping_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate discovery metadata key.')
        result[key] = value
    return result


def _mapping_path(value):
    """Require canonical portable relative paths without Windows aliases."""
    return (type(value) is str and 0 < len(value) <= 512
            and not any(part in ('', '.', '..') for part in value.split('/'))
            and not any(0xD800 <= ord(character) <= 0xDFFF for character in value)
            and '\\' not in value and ':' not in value and not reserved_windows_path(value))


def _parse_mappings(raw):
    """Validate reviewed package metadata without accessing mapped locations."""
    try:
        if type(raw) is not bytes or not 0 < len(raw) <= _MAX_MAPPING_BYTES:
            raise ValueError('Discovery metadata exceeds its fixed byte limit.')
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_mapping_object)
        if (type(value) is not dict or set(value) != {'schema_version', 'steam', 'native'}
                or type(value['schema_version']) is not int or value['schema_version'] != 1):
            raise ValueError('Unsupported discovery metadata schema.')
        registered = {game.id for game in GAMES if game.platform == 'Windows PC'}
        steam, native = [], []
        seen_apps, seen_native = set(), set()
        for name, fields in (('steam', {'app_id', 'game_id', 'evidence'}),
                             ('native', {'game_id', 'base', 'relative', 'evidence'})):
            records = value[name]
            if type(records) is not list or not 1 <= len(records) <= _MAX_MAPPING_RECORDS:
                raise ValueError('Invalid discovery metadata record limit.')
            for item in records:
                if type(item) is not dict or set(item) != fields:
                    raise ValueError('Unexpected discovery metadata fields.')
                if type(item['game_id']) is not str or item['game_id'] not in registered:
                    raise ValueError('Discovery metadata must name a registered Windows profile.')
                evidence = item['evidence']
                if (not _mapping_path(evidence) or not evidence.startswith('docs/')
                        or not evidence.endswith('.md')):
                    raise ValueError('Discovery metadata requires a relative documentation reference.')
                if name == 'steam':
                    app = item['app_id']
                    if (type(app) is not str or not re.fullmatch(r'[1-9][0-9]{0,9}', app)
                            or app in seen_apps):
                        raise ValueError('Invalid or ambiguous discovery Steam app identity.')
                    seen_apps.add(app)
                    steam.append(SteamMapping(**item))
                else:
                    if (item['base'] not in ('documents', 'local_app_data', 'roaming_app_data')
                            or not _mapping_path(item['relative'])):
                        raise ValueError('Invalid discovery native location.')
                    identity = (item['game_id'], item['base'], item['relative'].casefold())
                    if identity in seen_native:
                        raise ValueError('Duplicate discovery native location.')
                    seen_native.add(identity)
                    native.append(NativeMapping(**item))
        return tuple(steam), tuple(native)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        # Never include package metadata values in a user-facing error.
        raise SaveError('Bundled save discovery metadata is invalid or unsupported.') from None


def _load_mappings():
    try:
        # data_file uses importlib.resources for installed and frozen packages.
        # Fixed-size binary reads also bound malformed resource replacements.
        with data_file('save_discovery.json').open('rb') as stream:
            raw = stream.read(_MAX_MAPPING_BYTES + 1)
    except (OSError, ValueError):
        raise SaveError('Bundled save discovery metadata could not be read.') from None
    return _parse_mappings(raw)


# Immutable public constants retain their existing dataclass/API shape. These
# reviewed records identify candidates, never native-save support or a parser.
STEAM_MAPPINGS, NATIVE_MAPPINGS = _load_mappings()


@dataclass(frozen=True)
class DiscoveryLimits:
    max_roots: int = 16
    max_entries: int = 2000
    max_metadata_bytes: int = 2 * 1024 * 1024
    max_file_bytes: int = 256 * 1024
    max_results: int = 500

    def validate(self):
        for name, maximum in (('max_roots', 16), ('max_entries', 2000),
                              ('max_metadata_bytes', 2 * 1024 * 1024),
                              ('max_file_bytes', 256 * 1024), ('max_results', 500)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise SaveError('Discovery limits must stay within the fixed bounded range.')


@dataclass(frozen=True)
class InstalledGame:
    game_id: str
    app_id: str
    install_path: Path = field(repr=False)
    source: str = 'steam_manifest'
    confidence: str = 'installation_metadata'
    evidence: str = ''
    build_id: str | None = None
    last_updated: str | None = None


def _build_marker(value):
    """Accept only small decimal Steam build/time markers, never arbitrary VDF text."""
    return value if type(value) is str and re.fullmatch(r'[0-9]{1,20}', value) else None


def _last_updated_marker(value):
    """Accept Steam's bounded Unix-seconds marker separately from its build ID."""
    return value if type(value) is str and re.fullmatch(r'[0-9]{1,12}', value) else None


@dataclass(frozen=True)
class SaveLocation:
    game_id: str
    path: Path = field(repr=False)
    source: str = 'reviewed_native_location'
    confidence: str = 'location_candidate'
    evidence: str = ''
    live: bool = True


@dataclass(frozen=True)
class DiscoveryResult:
    installed_games: tuple[InstalledGame, ...]
    locations: tuple[SaveLocation, ...]
    issues: tuple[str, ...]
    stop_reason: str
    visited_entries: int
    metadata_bytes: int
    mapped_game_ids: tuple[str, ...]


def report(result):
    """Portable report: no paths, filenames, account IDs, or VDF values."""
    return {
        'schema': 'save-discovery-v1',
        'stop_reason': result.stop_reason,
        'visited_entries': result.visited_entries,
        'metadata_bytes': result.metadata_bytes,
        'issues': list(result.issues),
        'installed_games': [dict(game_id=item.game_id, app_id=item.app_id,
                                 source=item.source, confidence=item.confidence,
                                 build_id=item.build_id, last_updated=item.last_updated)
                            for item in result.installed_games],
        'locations': [dict(game_id=item.game_id, source=item.source,
                           confidence=item.confidence, live=item.live)
                      for item in result.locations],
        'mapped_game_ids': list(result.mapped_game_ids),
        'guidance': ('Locations are candidates, not native-save qualification. Close the game and '
                     'make separate copies with original companion context before opening. '
                     'An absent mapping does not change support for any registered profile.'),
    }


class _Stop(Exception):
    pass


class _Unsafe(Exception):
    pass


def _linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0)
                                            & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _handle_binding(info):
    # Windows path stat uses creation time for ctime, while fstat uses native
    # change time. Compare complete freshness tokens only within the same API.
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _ordinary(path, *, directory):
    # This reader deliberately does not call/relax safe_path: it examines known
    # live directory metadata but offers no gameplay-file read/write operation.
    path = Path(path).absolute()
    if '..' in path.parts:
        raise _Unsafe
    for item in (*reversed(path.parents), path):
        info = item.lstat()
        if _linked(info):
            raise _Unsafe
    info = path.lstat()
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise _Unsafe
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise _Unsafe
    return path, info


def parse_vdf(text):
    """Strict bounded subset of Steam KeyValues, including old/new libraries.

    Duplicate case-insensitive keys, directives, malformed nesting and trailing
    input are rejected instead of choosing an ambiguous path or app identity.
    This parser never interprets VDF directives or expands environment values.
    """
    if not isinstance(text, str) or len(text) > 256 * 1024 or '\0' in text:
        raise ValueError('Invalid or oversized Steam metadata.')
    tokens = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if text.startswith('//', index):
            end = text.find('\n', index)
            index = len(text) if end < 0 else end + 1
            continue
        if char in '{}':
            tokens.append((char, char))
            index += 1
        elif char == '"':
            value = []
            index += 1
            while index < len(text) and text[index] != '"':
                char = text[index]
                if char == '\\' and index + 1 < len(text) and text[index + 1] in '\\"':
                    index += 1
                    char = text[index]
                value.append(char)
                index += 1
            if index >= len(text):
                raise ValueError('Unterminated Steam metadata string.')
            tokens.append(('string', ''.join(value)))
            index += 1
        else:
            raise ValueError('Unsupported Steam metadata token.')
        if len(tokens) > 20000:
            raise ValueError('Steam metadata token limit exceeded.')
    cursor = 0

    def object_value(depth=0, nested=False):
        nonlocal cursor
        if depth > 12:
            raise ValueError('Steam metadata nesting limit exceeded.')
        values = {}
        while cursor < len(tokens):
            kind, key = tokens[cursor]
            cursor += 1
            if kind == '}':
                if not nested:
                    raise ValueError('Unexpected Steam metadata brace.')
                return values
            if kind != 'string' or key.casefold() in values or cursor >= len(tokens):
                raise ValueError('Invalid or duplicate Steam metadata key.')
            kind, value = tokens[cursor]
            cursor += 1
            if kind == '{':
                value = object_value(depth + 1, True)
            elif kind != 'string':
                raise ValueError('Missing Steam metadata value.')
            values[key.casefold()] = value
        if nested:
            raise ValueError('Unclosed Steam metadata object.')
        return values
    return object_value()


class _Scanner:
    def __init__(self, limits, cancel):
        self.limits = limits
        self.cancel = cancel
        self.installed = []
        self.locations = []
        self.issues = set()
        self.entries = 0
        self.bytes = 0
        self.stop_reason = 'complete'
        self.roots = []
        self.seen_roots = set()
        self.seen_locations = set()

    def check(self):
        if self.cancel is not None and self.cancel.is_set():
            self.stop('cancelled')

    def stop(self, reason):
        self.stop_reason = reason
        raise _Stop

    def directory(self, path):
        self.check()
        try:
            return _ordinary(path, directory=True)[0]
        except FileNotFoundError:
            return None
        except _Unsafe:
            self.issues.add('linked_or_nonordinary_path_skipped')
        except OSError:
            self.issues.add('unreadable_path_skipped')
        return None

    def metadata(self, path):
        self.check()
        try:
            path, before = _ordinary(path, directory=False)
            if before.st_size > self.limits.max_file_bytes:
                self.issues.add('oversized_metadata_skipped')
                return None
            if self.bytes + before.st_size > self.limits.max_metadata_bytes:
                self.stop('byte_limit')
            flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
            flags |= getattr(os, 'O_NONBLOCK', 0)
            descriptor = os.open(path, flags)
            try:
                opened = os.fstat(descriptor)
                if (_linked(opened) or not stat.S_ISREG(opened.st_mode)
                        or opened.st_nlink != 1 or _handle_binding(opened) != _handle_binding(before)):
                    raise _Unsafe
                _, checked = _ordinary(path, directory=False)
                if _identity(checked) != _identity(before):
                    raise _Unsafe
                chunks = []
                remaining = before.st_size
                while remaining:
                    self.check()
                    block = os.read(descriptor, min(65536, remaining))
                    if not block:
                        break
                    self.bytes += len(block)
                    if self.bytes > self.limits.max_metadata_bytes:
                        self.stop('byte_limit')
                    chunks.append(block)
                    remaining -= len(block)
                _, after = _ordinary(path, directory=False)
                raw = b''.join(chunks)
                if (len(raw) != before.st_size or _identity(os.fstat(descriptor)) != _identity(opened)
                        or _identity(after) != _identity(before)):
                    raise _Unsafe
            finally:
                os.close(descriptor)
            return parse_vdf(raw.decode('utf-8-sig'))
        except FileNotFoundError:
            return None
        except _Unsafe:
            self.issues.add('linked_or_changed_metadata_skipped')
        except (UnicodeError, ValueError):
            self.issues.add('malformed_metadata_skipped')
        except OSError:
            self.issues.add('unreadable_metadata_skipped')
        return None

    def children(self, path):
        path = self.directory(path)
        if path is None:
            return
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    self.check()
                    if self.entries >= self.limits.max_entries:
                        self.stop('entry_limit')
                    self.entries += 1
                    yield entry.name
        except OSError:
            self.issues.add('unreadable_directory_skipped')

    def add_root(self, path):
        self.check()
        root = self.directory(path)
        if root is None or root in self.seen_roots:
            return
        if len(self.roots) >= self.limits.max_roots:
            self.stop('root_limit')
        self.roots.append(root)
        self.seen_roots.add(root)

    def reserve_result(self):
        if len(self.installed) + len(self.locations) >= self.limits.max_results:
            self.stop('result_limit')

    def add_location(self, game_id, path, source, evidence):
        path = self.directory(path)
        key = (game_id, path)
        if path is not None and key not in self.seen_locations:
            self.reserve_result()
            self.locations.append(SaveLocation(game_id, path, source=source, evidence=evidence))
            self.seen_locations.add(key)

    def native(self, documents, local_app_data, roaming_app_data, *, game_id=None, proton=False):
        bases = dict(documents=documents, local_app_data=local_app_data,
                     roaming_app_data=roaming_app_data)
        for mapping in NATIVE_MAPPINGS:
            self.check()
            base = bases[mapping.base]
            if base is not None and (game_id is None or game_id == mapping.game_id):
                self.add_location(mapping.game_id, Path(base) / mapping.relative,
                                  'proton_reviewed_location' if proton else 'reviewed_native_location',
                                  mapping.evidence)

    def scan_root(self, root, *, include_save_locations=True, include_userdata=True):
        metadata = self.metadata(root / 'steamapps/libraryfolders.vdf')
        if metadata is None:
            # Older clients kept the same bounded KeyValues metadata here.
            metadata = self.metadata(root / 'config/libraryfolders.vdf')
        if metadata is not None:
            libraries = metadata.get('libraryfolders')
            if not isinstance(libraries, dict):
                self.issues.add('malformed_libraryfolders_skipped')
            else:
                for key, value in libraries.items():
                    self.check()
                    if not key.isascii() or not key.isdecimal():
                        continue
                    path = value.get('path') if isinstance(value, dict) else value
                    if isinstance(path, str) and path and Path(path).is_absolute():
                        self.add_root(path)
                    else:
                        self.issues.add('invalid_library_path_skipped')
        for mapping in STEAM_MAPPINGS:
            self.check()
            metadata = self.metadata(root / f'steamapps/appmanifest_{mapping.app_id}.acf')
            if metadata is None:
                continue
            app = metadata.get('appstate')
            if not isinstance(app, dict) or app.get('appid') != mapping.app_id:
                self.issues.add('manifest_identity_mismatch_skipped')
                continue
            name = app.get('installdir')
            if (not isinstance(name, str) or not name or name in ('.', '..')
                    or '/' in name or '\\' in name or ':' in name
                    or reserved_windows_path(name)):
                self.issues.add('invalid_install_directory_skipped')
                continue
            installation = self.directory(root / 'steamapps/common' / name)
            if installation is None:
                continue
            build_id = _build_marker(app.get('buildid'))
            last_updated = _last_updated_marker(app.get('lastupdated'))
            if app.get('buildid') is not None and build_id is None:
                self.issues.add('invalid_build_id_ignored')
            if app.get('lastupdated') is not None and last_updated is None:
                self.issues.add('invalid_last_updated_ignored')
            self.reserve_result()
            self.installed.append(InstalledGame(mapping.game_id, mapping.app_id, installation,
                                               evidence=mapping.evidence, build_id=build_id,
                                               last_updated=last_updated))
            user = root / f'steamapps/compatdata/{mapping.app_id}/pfx/drive_c' / 'users' / 'steamuser'
            if include_save_locations:
                self.native(user / 'Documents', user / 'AppData/Local', user / 'AppData/Roaming',
                            game_id=mapping.game_id, proton=True)
        # App-scoped remote directories are candidates even when an installation
        # was removed. Never enumerate remote contents or read Cloud metadata.
        if include_userdata:
            for account in self.children(root / 'userdata'):
                if not re.fullmatch(r'[0-9]{1,20}', account):
                    continue
                for mapping in STEAM_MAPPINGS:
                    self.add_location(mapping.game_id, root / 'userdata' / account / mapping.app_id / 'remote',
                                      'steam_userdata', mapping.evidence)


def _windows_roots():
    paths = []
    for variable in ('PROGRAMFILES(X86)', 'PROGRAMFILES', 'LOCALAPPDATA'):
        if os.environ.get(variable):
            paths.append(Path(os.environ[variable]) / 'Steam')
    # Read only the Steam installation keys. Never inspect account/login data.
    try:
        import winreg
        for hive, key, value in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'),
                                 (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath')):
            try:
                with winreg.OpenKey(hive, key, 0, winreg.KEY_READ) as handle:
                    path, kind = winreg.QueryValueEx(handle, value)
                if kind == winreg.REG_SZ and isinstance(path, str) and path:
                    paths.append(Path(path))
            except OSError:
                pass
    except ImportError:
        pass
    return paths


def _default_roots(home):
    paths = [home / '.local/share/Steam', home / '.steam/steam', home / '.steam/root']
    if os.name == 'nt':
        paths.extend(_windows_roots())
    return paths


def _windows_documents():
    """Resolve the current user's redirected Documents folder without writes."""
    import ctypes
    class GUID(ctypes.Structure):
        _fields_ = [('data1', ctypes.c_uint32), ('data2', ctypes.c_uint16),
                    ('data3', ctypes.c_uint16), ('data4', ctypes.c_ubyte * 8)]
    # FOLDERID_Documents: FDD39AD0-238F-46AF-ADB4-6C85480369C7.
    folder_id = GUID.from_buffer_copy(bytes.fromhex('d09ad3fd8f23af46adb46c85480369c7'))
    allocated = ctypes.c_void_p()
    try:
        shell = ctypes.WinDLL('shell32', use_last_error=True)
        ole = ctypes.WinDLL('ole32', use_last_error=True)
        resolve = shell.SHGetKnownFolderPath
        resolve.argtypes = (ctypes.POINTER(GUID), ctypes.c_uint32,
                            ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
        resolve.restype = ctypes.c_int32
        free = ole.CoTaskMemFree
        free.argtypes = (ctypes.c_void_p,)
        free.restype = None
        try:
            if resolve(ctypes.byref(folder_id), 0, None, ctypes.byref(allocated)) != 0:
                return None
            if allocated.value:
                value = ctypes.wstring_at(allocated)
                if value and Path(value).is_absolute():
                    return Path(value)
        finally:
            if allocated.value:
                free(allocated)
    except (AttributeError, OSError, ValueError):
        pass
    return None


def discover_saves(*, steam_roots=None, home=None, documents=None, local_app_data=None,
                   roaming_app_data=None, limits=DiscoveryLimits(), cancel=None):
    """Discover metadata in fixed known locations, without modifying any files.

    Explicit ``steam_roots=()`` disables Steam discovery. Missing paths are normal.
    Additional Steam libraries are followed only from bounded libraryfolders VDF.
    Windows defaults use the current user's Documents known folder; explicit
    ``home`` or ``documents`` overrides retain their supplied location.
    Results contain private paths for a local UI; use ``report`` for export.
    """
    if type(limits) is not DiscoveryLimits:
        raise SaveError('Choose fixed bounded discovery limits.')
    limits.validate()
    default_home = home is None
    home = Path.home() if default_home else Path(home)
    known_documents = documents is None and default_home and os.name == 'nt'
    documents = home / 'Documents' if documents is None else Path(documents)
    if local_app_data is None:
        local_app_data = Path(os.environ['LOCALAPPDATA']) if os.name == 'nt' and os.environ.get('LOCALAPPDATA') else home / 'AppData/Local'
    if roaming_app_data is None:
        roaming_app_data = Path(os.environ['APPDATA']) if os.name == 'nt' and os.environ.get('APPDATA') else home / 'AppData/Roaming'
    scanner = _Scanner(limits, cancel)
    registered = {game.id for game in GAMES}
    mapped = tuple(sorted({item.game_id for item in (*STEAM_MAPPINGS, *NATIVE_MAPPINGS)} & registered))
    # Every mapping is tied to a current registration; never create new support.
    if any(item.game_id not in registered for item in (*STEAM_MAPPINGS, *NATIVE_MAPPINGS)):
        raise SaveError('A discovery mapping is not a registered game/platform.')
    try:
        scanner.check()
        if known_documents:
            documents = _windows_documents() or documents
        scanner.native(documents, local_app_data, roaming_app_data)
        roots = _default_roots(home) if steam_roots is None else steam_roots
        for index, root in enumerate(roots):
            scanner.check()
            # Bound caller iterables too, including nonexistent/repeated roots.
            if index >= limits.max_roots:
                scanner.stop('root_limit')
            scanner.add_root(root)
        index = 0
        while index < len(scanner.roots):
            scanner.scan_root(scanner.roots[index])
            index += 1
    except _Stop:
        pass
    return DiscoveryResult(tuple(scanner.installed), tuple(scanner.locations), tuple(sorted(scanner.issues)),
                           scanner.stop_reason, scanner.entries, scanner.bytes, mapped)


def discover_installed_builds(*, steam_roots=None, home=None, limits=DiscoveryLimits(), cancel=None):
    """Read only mapped Steam installation manifests for installed-build tracking.

    Unlike ``discover_saves``, this path never checks Documents, native save
    locations, Proton save folders, or Steam ``userdata``. It reads bounded
    library/manifests metadata and verifies that the mapped installation folder
    is an ordinary directory. The returned paths are local in-memory values;
    portable callers should use ``report`` which excludes them.
    """
    if type(limits) is not DiscoveryLimits:
        raise SaveError('Choose fixed bounded discovery limits.')
    limits.validate()
    home = Path.home() if home is None else Path(home)
    scanner = _Scanner(limits, cancel)
    registered = {game.id for game in GAMES}
    mapped = tuple(sorted({item.game_id for item in STEAM_MAPPINGS} & registered))
    if any(item.game_id not in registered for item in STEAM_MAPPINGS):
        raise SaveError('A Steam discovery mapping is not a registered game/platform.')
    try:
        scanner.check()
        roots = _default_roots(home) if steam_roots is None else steam_roots
        for index, root in enumerate(roots):
            scanner.check()
            if index >= limits.max_roots:
                scanner.stop('root_limit')
            scanner.add_root(root)
        index = 0
        while index < len(scanner.roots):
            scanner.scan_root(scanner.roots[index], include_save_locations=False,
                              include_userdata=False)
            index += 1
    except _Stop:
        pass
    return DiscoveryResult(tuple(scanner.installed), (), tuple(sorted(scanner.issues)),
                           scanner.stop_reason, scanner.entries, scanner.bytes, mapped)
