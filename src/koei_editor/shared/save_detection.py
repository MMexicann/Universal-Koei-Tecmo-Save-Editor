"""Bounded Steam discovery and explicit import from read-only live sources.

Live paths are never passed to a game backend, save writer, or backup operation.
Only a new separate captured copy reaches native qualification. File identity
helpers and frozen snapshot/native qualification are shared with Save Library.
"""
from dataclasses import dataclass
import fnmatch
import hashlib
import os
from pathlib import Path, PureWindowsPath
import stat
import tempfile
import time
import uuid

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import save_library as library
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.save_safety import safe_path, reserved_windows_path
from koei_editor.shared.save_detection_catalog import PROFILES

MAX_FILE = 32 * 1024 * 1024
MAX_CONTEXT = 64 * 1024
MAX_METADATA = 1024 * 1024
MAX_BYTES = 128 * 1024 * 1024
MAX_ENTRIES = 5000
MAX_FILES = 256
MAX_LIBRARIES = 32
MAX_ACCOUNTS = 64


class DetectionCancelled(SaveError):
    pass


class DetectionLimit(SaveError):
    pass


@dataclass(frozen=True)
class CapturedFile:
    path: Path
    identity: tuple
    sha256: str
    size: int
    ancestors: tuple = ()


@dataclass(frozen=True)
class DetectionEntry:
    game_id: str
    app_id: int
    title: str
    status: str
    summary: str
    install_path: Path | None = None
    source: Path | None = None
    captured: tuple[CapturedFile, ...] = ()
    mapped_fields: int = 0
    revision: str = ''
    snapshot_digest: str = ''


@dataclass(frozen=True)
class DetectionScan:
    entries: tuple[DetectionEntry, ...]
    warnings: tuple[str, ...]
    stop_reason: str
    visited_entries: int
    admitted_bytes: int


class _Budget:
    def __init__(self, cancel=None):
        self.cancel, self.entries, self.bytes, self.files = cancel, 0, 0, 0
        self.started = time.monotonic()

    def check(self):
        if self.cancel is not None and self.cancel.is_set():
            raise DetectionCancelled('Detection cancelled; originals were not changed.')
        if time.monotonic() - self.started > 60:
            raise DetectionLimit('Scan time bound reached; choose a smaller Steam installation.')

    def entry(self):
        self.check()
        self.entries += 1
        if self.entries > MAX_ENTRIES:
            raise DetectionLimit('Directory entry bound reached.')

    def admit(self, size):
        self.check()
        self.bytes += size
        if self.bytes > MAX_BYTES:
            raise DetectionLimit('Scan byte bound reached.')


def checked_source(path, *, directory=False):
    """Ordinary local path check with an intentional read-only live exception.

    This does not call safe_path: that policy correctly forbids live files in
    every editing/write workflow. This helper grants no write permission.
    """
    path = Path(path)
    text = str(path)
    if ('..' in path.parts or any(ord(char) < 32 for char in text)
            or PureWindowsPath(text).drive.startswith('\\\\') or text.startswith('//')
            or (os.name == 'nt' and reserved_windows_path(path))):
        raise SaveError('Use an ordinary local Steam path without traversal or device names.')
    path = path.absolute()
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        if library._linked(info):
            raise SaveError('Linked paths and Windows reparse points are excluded.')
        if part != path and not stat.S_ISDIR(info.st_mode):
            raise SaveError('Source ancestors must remain ordinary directories.')
    info = path.lstat()
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise SaveError('Expected an ordinary local folder.')
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise SaveError('Only ordinary unlinked files may be captured.')
    return path, info


def capture_ordinary(path, limit, budget=None, expected=None):
    """Read bounded bytes; bind path and handle without cross-API ctime equality."""
    if type(limit) is not int or not 0 < limit <= MAX_FILE:
        raise SaveError('Invalid bounded capture size.')
    budget = budget or _Budget()
    budget.check()
    path, before = checked_source(path)
    ancestors = tuple((str(parent), library._directory_identity(parent.lstat())) for parent in path.parents)
    token = library._identity(before)
    if expected is not None and token != expected.identity:
        raise SaveError('Source changed since discovery. Scan again.')
    if expected is not None and ancestors != expected.ancestors:
        raise SaveError('Source folder identity changed since discovery.')
    if before.st_size > limit:
        raise SaveError('Source exceeds the bounded read limit.')
    budget.admit(before.st_size)
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        handle_token = library._identity(opened)
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                or library._handle_binding(opened) != library._handle_binding(before)):
            raise SaveError('Source changed before capture.')
        _, rebound = checked_source(path)
        if library._identity(rebound) != token:
            raise SaveError('Source changed before capture.')
        output = bytearray()
        while len(output) <= before.st_size:
            budget.check()
            block = os.read(descriptor, min(65536, before.st_size + 1 - len(output)))
            if not block:
                break
            output.extend(block)
        if len(output) != before.st_size or library._identity(os.fstat(descriptor)) != handle_token:
            raise SaveError('Source changed during capture.')
        _, after = checked_source(path)
        if library._identity(after) != token or library._handle_binding(after) != library._handle_binding(opened):
            raise SaveError('Source path changed during capture.')
        if ancestors != tuple((str(parent), library._directory_identity(parent.lstat())) for parent in path.parents):
            raise SaveError('Source folder identity changed during capture.')
        raw = bytes(output)
        digest = hashlib.sha256(raw).hexdigest()
        if expected is not None and digest != expected.sha256:
            raise SaveError('Source bytes changed since discovery. Scan again.')
        return raw, CapturedFile(path, token, digest, len(raw), ancestors)
    finally:
        os.close(descriptor)


def parse_vdf(raw):
    """Strict bounded quoted KeyValues subset used by Steam installation files."""
    if not isinstance(raw, bytes) or len(raw) > MAX_METADATA:
        raise SaveError('Steam metadata exceeds its bound.')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeError as error:
        raise SaveError('Steam metadata is not supported UTF-8.') from error
    tokens, index = [], 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
        elif text.startswith('//', index):
            end = text.find('\n', index)
            index = len(text) if end < 0 else end + 1
        elif char in '{}':
            tokens.append(char)
            index += 1
        elif char == '"':
            index += 1
            value = []
            while index < len(text) and text[index] != '"':
                if text[index] == '\\' and index + 1 < len(text) and text[index + 1] in ('\\', '"'):
                    index += 1
                value.append(text[index])
                index += 1
            if index >= len(text):
                raise SaveError('Unterminated Steam metadata string.')
            item = ''.join(value)
            if len(item) > 8192 or '\0' in item:
                raise SaveError('Steam metadata value is invalid.')
            tokens.append(('text', item))
            index += 1
        else:
            raise SaveError('Unsupported Steam metadata syntax.')
        if len(tokens) > 50000:
            raise SaveError('Steam metadata token bound reached.')
    position = 0
    def object_value(depth=0, nested=False):
        nonlocal position
        if depth > 8:
            raise SaveError('Steam metadata nesting bound reached.')
        result = {}
        while position < len(tokens):
            key = tokens[position]
            if key == '}':
                if not nested:
                    raise SaveError('Unexpected Steam metadata brace.')
                position += 1
                return result
            if not isinstance(key, tuple):
                raise SaveError('Steam metadata requires quoted keys.')
            position += 1
            if position >= len(tokens):
                raise SaveError('Steam metadata value is missing.')
            item = tokens[position]
            position += 1
            name = key[1].casefold()
            if name in result:
                raise SaveError('Ambiguous duplicate Steam metadata key.')
            if item == '{':
                result[name] = object_value(depth + 1, True)
            elif isinstance(item, tuple):
                result[name] = item[1]
            else:
                raise SaveError('Invalid Steam metadata value.')
        if nested:
            raise SaveError('Unclosed Steam metadata object.')
        return result
    return object_value()


def _metadata(path, budget):
    raw, _ = capture_ordinary(path, MAX_METADATA, budget)
    return parse_vdf(raw)


def default_steam_roots():
    paths = []
    if os.name == 'nt':
        import winreg
        for hive, name, value in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'),
                (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath')):
            try:
                with winreg.OpenKey(hive, name, 0, winreg.KEY_READ) as key:
                    text, kind = winreg.QueryValueEx(key, value)
                    if kind in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) and isinstance(text, str):
                        paths.append(Path(os.path.expandvars(text)))
            except OSError:
                pass
        for variable in ('ProgramFiles(x86)', 'ProgramFiles'):
            if os.environ.get(variable):
                paths.append(Path(os.environ[variable]) / 'Steam')
    else:
        paths.extend((Path.home() / '.local/share/Steam', Path.home() / '.steam/steam'))
    return tuple(dict.fromkeys(paths))


def default_documents_roots():
    if os.name == 'nt':
        import ctypes
        buffer = ctypes.create_unicode_buffer(32768)
        # CSIDL_PERSONAL respects the user's redirected Documents folder.
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0 and buffer.value:
            return (Path(buffer.value),)
    return (Path.home() / 'Documents',)


def _directories(path, budget):
    checked_source(path, directory=True)
    with os.scandir(path) as entries:
        for entry in entries:
            budget.entry()
            yield Path(entry.path)


def _walk_files(folder, patterns, depth, budget):
    try:
        children = _directories(folder, budget)
        for path in children:
            try:
                _, info = checked_source(path)
            except SaveError:
                try:
                    checked_source(path, directory=True)
                except (OSError, SaveError):
                    continue
                if depth:
                    yield from _walk_files(path, patterns, depth - 1, budget)
                continue
            if any(fnmatch.fnmatchcase(path.name.casefold(), pattern.casefold()) for pattern in patterns):
                budget.files += 1
                if budget.files > MAX_FILES:
                    raise DetectionLimit('Candidate file bound reached.')
                yield path
    except FileNotFoundError:
        return


def _library_paths(roots, budget, warnings):
    libraries = []
    for root in roots:
        try:
            root, _ = checked_source(root, directory=True)
            if root not in libraries:
                libraries.append(root)
            if len(libraries) > MAX_LIBRARIES:
                raise DetectionLimit('Steam library bound reached.')
            metadata = root / 'steamapps/libraryfolders.vdf'
            if not metadata.exists():
                metadata = root / 'config/libraryfolders.vdf'
            if not metadata.exists():
                continue
            value = _metadata(metadata, budget).get('libraryfolders')
            if not isinstance(value, dict):
                raise SaveError('Steam library metadata has no supported libraryfolders object.')
            for key, row in value.items():
                if not key.isdecimal():
                    continue
                text = row.get('path') if isinstance(row, dict) else row
                if not isinstance(text, str) or not Path(text).is_absolute():
                    raise SaveError('Steam library paths must be absolute local paths.')
                path, _ = checked_source(text, directory=True)
                if path not in libraries:
                    libraries.append(path)
                if len(libraries) > MAX_LIBRARIES:
                    raise DetectionLimit('Steam library bound reached.')
        except (OSError, SaveError) as error:
            if isinstance(error, (DetectionCancelled, DetectionLimit)):
                raise
            warnings.append('A Steam root or library metadata file was unavailable or unsafe.')
    return tuple(dict.fromkeys(libraries))


def _source_bundle(profile, path, budget, expected=()):
    expected_by_name = {item.path.name: item for item in expected}
    raw, main = capture_ordinary(path, MAX_FILE, budget, expected_by_name.get(path.name))
    bundle = [(raw, main)]
    context_entries = tuple(_directories(path.parent, budget)) if profile.context else ()
    for name in profile.context:
        if '/' in name or '\\' in name or name in ('.', '..'):
            raise SaveError('Invalid registered context basename.')
        if len([item for item in context_entries if item.name.casefold() == name.casefold()]) != 1:
            raise SaveError('Required original context is missing or ambiguous.')
        data, captured = capture_ordinary(path.parent / name, MAX_CONTEXT, budget, expected_by_name.get(name))
        bundle.append((data, captured))
    if expected and tuple(item.path for _, item in bundle) != tuple(item.path for item in expected):
        raise SaveError('Source context differs from discovery.')
    return tuple(bundle)


def _qualify_bundle(profile, bundle, budget):
    adapter = library.adapter_for(profile.game_id)
    with tempfile.TemporaryDirectory(prefix='KoeiSaveDetection-') as temporary:
        folder = safe_path(temporary)
        _publish_bundle(profile, bundle, folder, budget)
        copied = folder / bundle[0][1].path.name
        _, info = library._checked_path(copied)
        document, digest, _, count = library._qualify(adapter, copied, info, MAX_FILE, budget.cancel)
        if (adapter.serialize(document, {}) != bundle[0][0]
                or adapter.backend.serialize(document, {}) != bundle[0][0]):
            raise SaveError('Captured save failed exact unchanged native roundtrip.')
        budget.check()
        # Owner-dependent snapshots include the temporary companion's path and
        # inode. Those correctly change between safe captures. Bind native
        # payload bytes and exact opaque context digests instead; every capture
        # still receives the owning backend's complete context qualification.
        snapshot = _bundle_digest(document, bundle)
        revision = getattr(document, 'revision', None)
        return count, snapshot, str(revision) if type(revision) in (int, str) else 'Native profile qualified'


def _bundle_digest(document, bundle):
    if type(document.payload) is not bytes:
        raise SaveError('Native qualification did not return an immutable payload.')
    digest = hashlib.sha256(document.payload)
    for _, captured in bundle:
        digest.update(captured.path.name.encode('utf-8'))
        digest.update(captured.sha256.encode('ascii'))
    return digest.hexdigest()


def _publish_bundle(profile, bundle, folder, budget):
    """Publish only registered opaque sidecars beside captured gameplay.

    The ordinary editor policy continues to reject Steam metadata paths. The
    exception is restricted to the owning profile's reviewed companion basename
    inside a newly created separate directory; contents are not interpreted here.
    """
    for index, (raw, captured) in enumerate(bundle):
        budget.check()
        library._checked_path(folder, directory=True)
        destination = folder / captured.path.name
        if index == 0:
            atomic_new(raw, destination)
            continue
        if (captured.path.name not in profile.context or captured.path.name != 'steam_autocloud.vdf'
                or len(raw) > MAX_CONTEXT):
            raise SaveError('Unregistered opaque context cannot be copied.')
        # Creating the sidecar does not authorize editing or replacing it. All
        # later qualification is delegated to the original owning backend.
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        descriptor = os.open(destination, flags, 0o600)
        try:
            offset = 0
            while offset < len(raw):
                budget.check()
                wrote = os.write(descriptor, raw[offset:offset + 65536])
                if wrote <= 0:
                    raise SaveError('Could not create the opaque context copy.')
                offset += wrote
            os.fsync(descriptor)
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != len(raw):
                raise SaveError('The opaque context destination changed during creation.')
        finally:
            os.close(descriptor)
        actual, _ = capture_ordinary(destination, MAX_CONTEXT, budget)
        if actual != raw:
            raise SaveError('The actual opaque context copy failed read-back.')


def discover(steam_roots=None, documents_roots=None, cancel=None):
    """Return bounded evidence statuses, retaining fingerprints rather than save bytes."""
    budget, entries, warnings = _Budget(cancel), [], []
    roots = tuple(default_steam_roots() if steam_roots is None else steam_roots)
    documents = tuple(default_documents_roots() if documents_roots is None else documents_roots)
    stop = 'complete'
    try:
        if len(roots) > MAX_LIBRARIES or len(documents) > 8:
            raise DetectionLimit('Root count bound reached.')
        libraries = _library_paths(roots, budget, warnings)
        for profile in PROFILES:
            budget.check()
            game = get_game(profile.game_id)
            installs = []
            for folder in libraries:
                manifest = folder / 'steamapps' / f'appmanifest_{profile.app_id}.acf'
                try:
                    state = _metadata(manifest, budget).get('appstate')
                    if (not isinstance(state, dict) or state.get('appid') != str(profile.app_id)
                            or not isinstance(state.get('installdir'), str)):
                        raise SaveError('App manifest does not identify the registered Steam app.')
                    component = state['installdir']
                    if (component in ('', '.', '..') or any(c in component for c in '/\\:')
                            or reserved_windows_path(component)):
                        raise SaveError('Unsafe Steam installation directory.')
                    install, _ = checked_source(folder / 'steamapps/common' / component, directory=True)
                    installs.append(install)
                except FileNotFoundError:
                    continue
                except (OSError, SaveError) as error:
                    if isinstance(error, (DetectionCancelled, DetectionLimit)):
                        raise
                    warnings.append(f'Steam app {profile.app_id}: manifest or installation was not qualified.')
            if not installs:
                continue
            if len(set(installs)) != 1:
                entries.append(DetectionEntry(game.id, profile.app_id, game.title, 'ambiguous',
                    'Multiple installations were found. Select one Steam library and scan again.'))
                continue
            install = installs[0]
            candidates = []
            if profile.documents_folder:
                for folder in documents:
                    candidates.extend(_walk_files(Path(folder).joinpath(*profile.documents_folder), profile.filenames,
                                                  profile.depth, budget))
            # Steam's documented Remote Storage location is app-scoped. No
            # remotecache/account metadata is parsed or rewritten.
            for root in roots:
                try:
                    accounts = 0
                    for account in _directories(Path(root) / 'userdata', budget):
                        if not account.name.isdecimal():
                            continue
                        accounts += 1
                        if accounts > MAX_ACCOUNTS:
                            raise DetectionLimit('Steam account folder bound reached.')
                        candidates.extend(_walk_files(account / str(profile.app_id) / 'remote',
                                                      profile.filenames, 3, budget))
                except FileNotFoundError:
                    pass
            unique = tuple(dict.fromkeys(candidates))
            if not unique:
                entries.append(DetectionEntry(game.id, profile.app_id, game.title, 'no_saves',
                    'Installed; no matching files in the enabled public location hints.' +
                    (' Documents location is not enabled because its public references conflict.' if game.id == 'origins' else ''), install))
            for path in unique:
                budget.check()
                try:
                    bundle = _source_bundle(profile, path, budget)
                    count, snapshot, revision = _qualify_bundle(profile, bundle, budget)
                    # Re-read source after parsing the safe copy; owner context
                    # must remain byte-exact and bound to its original identity.
                    _source_bundle(profile, path, budget, tuple(item for _, item in bundle))
                    entries.append(DetectionEntry(game.id, profile.app_id, game.title, 'qualified',
                        'Captured copy passed native validation and exact no-edit roundtrip; import rechecks original bytes.',
                        install, path, tuple(item for _, item in bundle), count, revision, snapshot))
                except (OSError, SaveError) as error:
                    if isinstance(error, (DetectionCancelled, DetectionLimit)):
                        raise
                    entries.append(DetectionEntry(game.id, profile.app_id, game.title, 'rejected',
                        'Not qualified for this app/profile: unsafe or changing source, unsupported revision, damaged input, or missing original context.',
                        install, path))
    except DetectionCancelled:
        stop = 'cancelled'
    except DetectionLimit as error:
        stop = 'limit'
        warnings.append(str(error))
    except (OSError, SaveError):
        stop = 'incomplete'
        warnings.append('A source folder was unavailable, unsafe, or changed while scanning.')
    return DetectionScan(tuple(entries), tuple(warnings), stop, budget.entries, budget.bytes)


def import_copy(entry, destination_folder, cancel=None):
    """Explicitly create a new guarded import; never modify or clean up originals."""
    if not isinstance(entry, DetectionEntry) or entry.status != 'qualified' or not entry.captured or entry.source is None:
        raise SaveError('Choose a qualified discovery result.')
    profiles = [profile for profile in PROFILES if profile.game_id == entry.game_id and profile.app_id == entry.app_id]
    if len(profiles) != 1:
        raise SaveError('Discovery result has no unambiguous registered Steam profile.')
    profile = profiles[0]
    budget = _Budget(cancel)
    parent, _ = library._checked_path(destination_folder, directory=True)
    # Prevent importing into the live source tree even if a new title's location
    # has not yet been added to the global editor path deny-list.
    for captured in entry.captured:
        if parent.is_relative_to(captured.path.parent):
            raise SaveError('Choose a separate destination outside the original save folder.')
    bundle = _source_bundle(profile, entry.source, budget, entry.captured)
    count, snapshot, revision = _qualify_bundle(profile, bundle, budget)
    if (count, snapshot, revision) != (entry.mapped_fields, entry.snapshot_digest, entry.revision):
        raise SaveError('Native qualification changed since discovery. Scan again.')
    budget.check()
    folder = parent / f'KoeiImported-{entry.game_id}-{uuid.uuid4().hex}'
    folder.mkdir()
    library._checked_path(folder, directory=True, root=parent)
    # Partial/new files are deliberately retained on any failure. Deleting a
    # concurrently replaced destination could destroy someone else's bytes.
    _publish_bundle(profile, bundle, folder, budget)
    copied = folder / entry.source.name
    adapter = library.adapter_for(entry.game_id)
    _, info = library._checked_path(copied, root=folder)
    document, _, _, actual_count = library._qualify(adapter, copied, info, MAX_FILE, cancel)
    actual_snapshot = _bundle_digest(document, bundle)
    if ((actual_snapshot, actual_count) != (entry.snapshot_digest, entry.mapped_fields)
            or adapter.serialize(document, {}) != bundle[0][0]
            or adapter.backend.serialize(document, {}) != bundle[0][0]):
        raise SaveError('Actual imported file failed native read-back verification; the new files were retained.')
    for raw, captured in bundle:
        actual, _ = capture_ordinary(folder / captured.path.name, MAX_FILE, budget)
        if actual != raw:
            raise SaveError('Actual imported bytes changed during validation; files were retained.')
    _source_bundle(profile, entry.source, budget, entry.captured)
    library._checked_path(folder, directory=True, root=parent)
    budget.check()
    return copied
