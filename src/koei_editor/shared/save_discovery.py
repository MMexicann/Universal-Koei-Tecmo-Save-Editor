"""Bounded, read-only discovery of installed games and candidate live locations.

Discovery does not open gameplay files, qualify a native save, select a parser,
import a save, or grant permission to edit a live directory. Callers must ask
users to make separate copies, including the original companion context, before
using the existing copied-save workflow. Paths are private local UI data;
``report`` deliberately excludes them and all Steam account identifiers.
"""
from dataclasses import dataclass, field
import os
from pathlib import Path, PureWindowsPath
import re
import stat

from koei_editor.game_registry import GAMES
from koei_editor.games.dw3.models import SaveError


@dataclass(frozen=True)
class SteamMapping:
    app_id: str
    game_id: str
    evidence: str


# Reviewed original-PC app identities, not filename guesses or new support.
# A mapped installation still may contain a foreign/unsupported save revision.
STEAM_MAPPINGS = (
    SteamMapping('278080', 'dw8xl', 'docs/DW8_ORIGINAL_PC_SCOPE.md'),
    SteamMapping('968790', 'dw7xl', 'docs/PC_EDITOR_ATTEMPTS.md'),
    SteamMapping('322520', 'dw8e', 'docs/PC_EDITOR_ATTEMPTS.md'),
    SteamMapping('1341200', 'dw9emp', 'docs/PC_EDITOR_ATTEMPTS.md'),
    SteamMapping('331600', 'pw3', 'docs/PW3_COVERAGE.md'),
    SteamMapping('2384580', 'origins', 'docs/ORIGINS_REQUEST_STATUS.md'),
    SteamMapping('2719200', 'samurai4dx', 'docs/PC_EDITOR_ATTEMPTS.md'),
    SteamMapping('1591530', 'samurai5_pc', 'docs/PC_EDITOR_ATTEMPTS.md'),
    SteamMapping('1879330', 'wo3u', 'docs/OROCHI_RESEARCH.md'),
    SteamMapping('831560', 'wo4_pc', 'docs/PC_EDITOR_ATTEMPTS.md'),
    SteamMapping('610190', 'stars', 'docs/STARS_WO4_RESEARCH.md'),
    SteamMapping('1382330', 'p5strikers_pc', 'docs/PC_EDITOR_ATTEMPTS.md'),
    SteamMapping('3178350', 'abyss_pc', 'docs/PC_EDITOR_ATTEMPTS.md'),
    SteamMapping('527270', 'atelier_sophie', 'docs/SOPHIE_PC_FORMAT.md'),
    SteamMapping('527290', 'atelier_firis_pc', 'docs/FIRIS_PC_FORMAT.md'),
    SteamMapping('1121560', 'atelier_ryza_pc', 'docs/RYZA_PC_FORMAT.md'),
    SteamMapping('1423600', 'blue_reflection_second_light_pc', 'docs/BRSL_PC_FORMAT.md'),
    SteamMapping('348470', 'sw4ii', 'docs/SW4II_FORMAT.md'),
    SteamMapping('363150', 'rotk13_pc', 'docs/ROTK13_FORMAT.md'),
)


@dataclass(frozen=True)
class NativeMapping:
    game_id: str
    base: str
    relative: str
    evidence: str


NATIVE_MAPPINGS = (
    NativeMapping('dw4hyper', 'documents', 'KOEI/Dynasty Warriors 4 Hyper/Savedata',
                  'docs/PC_RESEARCH_RETRY.md'),
    NativeMapping('dw5special', 'documents', 'KOEI/Shin Sangokumusou 4 Special/Savedata',
                  'docs/DW5_SPECIAL.md'),
    NativeMapping('dw6', 'documents', 'KOEI/Dynasty Warriors 6/Savedata',
                  'docs/PC_RESEARCH_RETRY.md'),
    NativeMapping('dw7xl', 'documents', 'KoeiTecmo/Dynasty Warriors 7 DX/Savedata',
                  'docs/PC_RESEARCH_RETRY.md'),
    NativeMapping('dw8e', 'documents', 'KoeiTecmo/Dynasty Warriors 8 Empires/Savedata',
                  'docs/PC_RESEARCH_RETRY.md'),
    NativeMapping('dw9emp', 'documents', 'KoeiTecmo/Dynasty Warriors 9 Empires',
                  'docs/PC_RESEARCH_RETRY.md'),
    NativeMapping('sw4ii', 'documents', 'KoeiTecmo/SAMURAI WARRIORS 4-II/Savedata',
                  'docs/PC_RESEARCH_RETRY.md'),
    NativeMapping('wo3u', 'documents', 'KoeiTecmo/WARRIORS OROCHI 3 Ultimate/SAVEDATA',
                  'docs/PC_RESEARCH_RETRY.md'),
    NativeMapping('stars', 'documents', 'KoeiTecmo/WARRIORS ALL-STARS/Savedata',
                  'docs/STARS_WO4_RESEARCH.md'),
    NativeMapping('pw4', 'local_app_data', 'BANDAI NAMCO Entertainment/One Piece Pirate Warriors 4/Saved/SaveGames',
                  'docs/PC_RESEARCH_RETRY.md'),
    NativeMapping('p5strikers_pc', 'roaming_app_data', 'SEGA/Steam/P5S',
                  'docs/PC_RESEARCH_RETRY.md'),
    NativeMapping('pw3', 'documents', 'One Piece Pirate Warriors 3/SAVEDATA',
                  'docs/KOEI_FORMATS.md'),
    NativeMapping('wo1', 'documents', 'KOEI/WARRIORS OROCHI/Savedata',
                  'docs/WO1_PC_FORMAT.md'),
    NativeMapping('rotk13_pc', 'documents', 'KoeiTecmo/SAN13',
                  'docs/ROTK13_FORMAT.md'),
    NativeMapping('origins', 'local_app_data', 'KoeiTecmo/Dynasty Warriors Origins/Savedata',
                  'docs/ORIGINS_FORMAT.md'),
)


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
                                 source=item.source, confidence=item.confidence)
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

    def scan_root(self, root):
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
                    or PureWindowsPath(name).is_reserved() or any(ord(c) < 32 for c in name)):
                self.issues.add('invalid_install_directory_skipped')
                continue
            installation = self.directory(root / 'steamapps/common' / name)
            if installation is None:
                continue
            self.reserve_result()
            self.installed.append(InstalledGame(mapping.game_id, mapping.app_id, installation,
                                               evidence=mapping.evidence))
            user = root / f'steamapps/compatdata/{mapping.app_id}/pfx/drive_c' / 'users' / 'steamuser'
            self.native(user / 'Documents', user / 'AppData/Local', user / 'AppData/Roaming',
                        game_id=mapping.game_id, proton=True)
        # App-scoped remote directories are candidates even when an installation
        # was removed. Never enumerate remote contents or read Cloud metadata.
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


def discover_saves(*, steam_roots=None, home=None, documents=None, local_app_data=None,
                   roaming_app_data=None, limits=DiscoveryLimits(), cancel=None):
    """Discover metadata in fixed known locations, without modifying any files.

    Explicit ``steam_roots=()`` disables Steam discovery. Missing paths are normal.
    Additional Steam libraries are followed only from bounded libraryfolders VDF.
    Results contain private paths for a local UI; use ``report`` for export.
    """
    if type(limits) is not DiscoveryLimits:
        raise SaveError('Choose fixed bounded discovery limits.')
    limits.validate()
    home = Path.home() if home is None else Path(home)
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
