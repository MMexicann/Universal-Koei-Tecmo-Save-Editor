"""Bounded, read-only inventory of copies for one explicitly selected profile.

No save bytes or document objects are retained in the inventory. Duplicate groups
mean identical gameplay-file bytes; they say nothing about account/context or
whole-folder equality. Opening always qualifies the selected copy again.
"""
from collections import Counter
from dataclasses import dataclass, fields, is_dataclass, replace
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat

from koei_editor.game_registry import GAMES, get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.save_safety import safe_path

LIBRARY_GAMES = tuple(game for game in GAMES if game.scalar_backend is not None)
STATUSES = ('qualified', 'rejected', 'unsafe', 'oversized', 'changed', 'unreadable')
STOP_REASONS = ('complete', 'cancelled', 'file_limit', 'entry_limit', 'byte_limit')
SUMMARIES = {
    'qualified': 'Qualified for the selected profile; rechecked before opening.',
    'rejected': 'Not qualified: foreign/damaged input, unsupported revision, or missing original context.',
    'unsafe': 'Skipped: linked, aliased, special, or protected live/cloud path.',
    'oversized': 'Skipped: gameplay file exceeds the scan size limit.',
    'changed': 'Changed during qualification; scan the copied folder again.',
    'unreadable': 'Could not read this copy or its required original context.',
}


@dataclass(frozen=True)
class ScanLimits:
    """Callers may lower, but never raise, these hard scan bounds."""
    max_files: int = 500
    max_entries: int = 5000
    max_depth: int = 3
    max_file_bytes: int = 32 * 1024 * 1024
    max_total_bytes: int = 128 * 1024 * 1024

    def validate(self):
        for name, maximum in (('max_files', 500), ('max_entries', 5000),
                ('max_depth', 3), ('max_file_bytes', 32 * 1024 * 1024),
                ('max_total_bytes', 128 * 1024 * 1024)):
            value = getattr(self, name)
            if type(value) is not int or not (0 if name == 'max_depth' else 1) <= value <= maximum:
                raise SaveError('Save Library scan limits must stay within the fixed bounded range.')


@dataclass(frozen=True)
class LibraryEntry:
    relative_path: str
    status: str
    size_bytes: int
    modified_ns: int
    sha256: str = ''
    mapped_fields: int = 0
    duplicate_group: int = 0
    # Private freshness tokens, deliberately omitted from report().
    identity: tuple = ()
    snapshot_digest: str = ''

    @property
    def summary(self):
        return SUMMARIES[self.status]


@dataclass(frozen=True)
class LibraryScan:
    game_id: str
    folder: Path
    folder_identity: tuple
    recursive: bool
    limits: ScanLimits
    entries: tuple[LibraryEntry, ...]
    visited_entries: int
    admitted_bytes: int
    excluded_directories: int
    stop_reason: str

    @property
    def qualified_count(self):
        return sum(entry.status == 'qualified' for entry in self.entries)


def adapter_for(game_id):
    game = get_game(game_id)
    if game not in LIBRARY_GAMES:
        raise SaveError('Choose a registered scalar game/platform profile for Save Library.')
    return game.get_scalar_adapter()


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _handle_binding(info):
    # On Windows, CPython's path stat/lstat preserves legacy creation-time
    # st_ctime, while fstat exposes native change time. Compare ctime only
    # within the same API, retaining volume/file identity and content metadata
    # when binding an opened handle to its checked ordinary path.
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _directory_identity(info):
    # Directory timestamps change when a new unrelated file is added. Its actual
    # identity must remain fixed, while each selected file has a full stat token.
    return (info.st_dev, info.st_ino)


def _linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0)
                                              & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))


def _checked_path(path, *, directory=False, root=None):
    original = Path(path).absolute()
    safe_path(original)
    # Reject linked ancestors too, including Windows reparse points/junctions.
    for item in (*reversed(original.parents), original):
        info = item.lstat()
        if _linked(info):
            raise SaveError('Save Library requires ordinary copies without linked paths.')
    resolved = safe_path(original)
    if root is not None and not resolved.is_relative_to(root):
        raise SaveError('A library path escaped the selected copied-save folder.')
    info = original.lstat()
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise SaveError('Choose a copied-save folder.')
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise SaveError('Save Library requires a regular, unaliased copied file.')
    return resolved, info


class _Cancelled(Exception):
    pass


def _check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise _Cancelled


def _capture(path, expected, limit, cancel):
    """Streaming fingerprint: no unbounded read and no buffered file snapshot."""
    _, before = _checked_path(path)
    if _identity(before) != expected:
        raise SaveError('The selected file changed before its bounded read.')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    descriptor = os.open(path, flags)
    try:
        info = os.fstat(descriptor)
        handle_identity = _identity(info)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or _handle_binding(info) != _handle_binding(before)):
            raise SaveError('The selected file changed before its bounded read.')
        _, opened_path = _checked_path(path)
        if (_identity(opened_path) != expected
                or _handle_binding(opened_path) != _handle_binding(info)):
            raise SaveError('The selected file changed before its bounded read.')
        digest = hashlib.sha256()
        remaining = min(info.st_size, limit) + 1
        length = 0
        while remaining:
            _check_cancel(cancel)
            block = os.read(descriptor, min(65536, remaining))
            if not block:
                break
            length += len(block)
            remaining -= len(block)
            digest.update(block)
        if (length != info.st_size or length > limit
                or _identity(os.fstat(descriptor)) != handle_identity):
            raise SaveError('The selected file changed during its bounded read.')
        _, after = _checked_path(path)
        if (_identity(after) != expected
                or _handle_binding(after) != _handle_binding(info)):
            raise SaveError('The selected file changed during its bounded read.')
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def _snapshot_digest(document):
    """Hash opaque context/codec metadata without retaining or reporting it."""
    if not is_dataclass(document):
        raise SaveError('This profile does not expose a frozen scalar snapshot.')
    digest = hashlib.sha256()
    nodes = 0
    def consume(value, depth=0):
        nonlocal nodes
        nodes += 1
        if depth > 12 or nodes > 10000:
            raise SaveError('The profile snapshot exceeds bounded metadata qualification.')
        if value is None:
            digest.update(b'N;')
        elif type(value) is bytes:
            digest.update(b'B' + str(len(value)).encode() + b':')
            digest.update(value)
        elif type(value) in (str, int, bool) or isinstance(value, Path):
            raw = str(value).encode('utf-8', errors='surrogatepass')
            if len(raw) > 65536:
                raise SaveError('The profile snapshot metadata is too large.')
            digest.update(type(value).__name__.encode() + b':' + str(len(raw)).encode() + b':' + raw)
        elif is_dataclass(value):
            for field in fields(value):
                consume(field.name, depth + 1)
                consume(getattr(value, field.name), depth + 1)
        elif type(value) in (tuple, list):
            digest.update(str(len(value)).encode() + b'[')
            for item in value:
                consume(item, depth + 1)
            digest.update(b']')
        else:
            raise SaveError('The profile has unsupported snapshot metadata.')
    for field in fields(document):
        if field.name not in ('source', 'format', 'raw', 'payload'):
            consume(field.name)
            consume(getattr(document, field.name))
    return digest.hexdigest()


def _context_guard(path):
    # Shared export conventions, not game detection or a substitute for native
    # title/context validation. Do not read Steam metadata here: only its owning
    # registered backend may consume that original private sidecar.
    snapshots = []
    for relative in ('PARAM.SFO', 'sce_sys', 'sce_sys/param.sfo', 'eeprom.bin',
                     'factory_eeprom.bin', 'SaveMeta.xbx', 'steam_autocloud.vdf'):
        companion = path.parent / relative
        try:
            info = companion.lstat()
        except FileNotFoundError:
            continue
        if (_linked(info) or (relative == 'sce_sys' and not stat.S_ISDIR(info.st_mode))
                or (relative != 'sce_sys' and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1))):
            raise SaveError('Original context must remain ordinary separate, unaliased files.')
        snapshots.append((relative, _identity(info)))
    return tuple(snapshots)


def _qualify(adapter, path, info, limit, cancel):
    context = _context_guard(path)
    expected = _identity(info)
    digest = _capture(path, expected, limit, cancel)
    _check_cancel(cancel)
    document = adapter.read_save(path)
    _check_cancel(cancel)
    if (type(document.raw) is not bytes or len(document.raw) != info.st_size
            or hashlib.sha256(document.raw).hexdigest() != digest):
        raise SaveError('The selected copy changed during native qualification.')
    snapshot = _snapshot_digest(document)
    count = len(adapter.fields_for(document))
    _, after = _checked_path(path)
    if (_identity(after) != expected or _capture(path, expected, limit, cancel) != digest
            or _context_guard(path) != context):
        raise SaveError('The selected copy changed after native qualification.')
    return document, digest, snapshot, count


def scan(game_id, folder, *, recursive=False, cancel=None, limits=None):
    """Inventory suffix-matching files using exactly one registered adapter.

    Cancel is an optional threading.Event-like object. Cancellation retains only
    entries whose complete qualification finished; it never blesses a partial read.
    Every returned result states whether a bound or cancellation ended traversal.
    """
    adapter = adapter_for(game_id)
    if type(recursive) is not bool:
        raise SaveError('Recursive scanning requires an explicit boolean choice.')
    limits = ScanLimits() if limits is None else limits
    if type(limits) is not ScanLimits:
        raise SaveError('Use fixed Save Library scan limits.')
    limits.validate()
    root, root_info = _checked_path(folder, directory=True)
    root_identity = _directory_identity(root_info)
    entries, pending, seen_directories = [], [(root, 0)], set()
    visited = admitted = excluded = 0
    reason = 'complete'
    try:
        while pending and reason == 'complete':
            _check_cancel(cancel)
            directory, depth = pending.pop()
            try:
                directory, info = _checked_path(directory, directory=True, root=root)
                key = _directory_identity(info)
                if key in seen_directories:
                    excluded += 1
                    continue
                seen_directories.add(key)
                iterator = os.scandir(directory)
            except (OSError, SaveError):
                excluded += 1
                continue
            with iterator:
                for item in iterator:
                    _check_cancel(cancel)
                    if visited >= limits.max_entries:
                        reason = 'entry_limit'
                        break
                    visited += 1
                    path = Path(item.path)
                    try:
                        item_info = item.stat(follow_symlinks=False)
                        is_directory = stat.S_ISDIR(item_info.st_mode)
                        # A linked directory is never traversed, even if its
                        # target appears to be under the root.
                        if _linked(item_info):
                            if path.suffix.lower() != adapter.extension:
                                excluded += 1
                                continue
                        elif is_directory:
                            if recursive and depth < limits.max_depth:
                                pending.append((path, depth + 1))
                            else:
                                excluded += 1
                            continue
                        if path.suffix.lower() != adapter.extension:
                            continue
                        if len(entries) >= limits.max_files:
                            reason = 'file_limit'
                            break
                        relative = path.relative_to(root).as_posix()
                        entry = LibraryEntry(relative, 'unsafe', max(0, item_info.st_size), item_info.st_mtime_ns)
                        try:
                            path, checked = _checked_path(path, root=root)
                        except (SaveError, OSError):
                            entries.append(entry)
                            continue
                        entry = replace(entry, identity=_identity(checked))
                        if checked.st_size > limits.max_file_bytes:
                            entries.append(replace(entry, status='oversized'))
                            continue
                        if admitted + checked.st_size > limits.max_total_bytes:
                            reason = 'byte_limit'
                            break
                        admitted += checked.st_size
                        try:
                            document, digest, snapshot, count = _qualify(adapter, path, checked, limits.max_file_bytes, cancel)
                            # Do not retain document/payload/account metadata.
                            del document
                            entries.append(replace(entry, status='qualified', sha256=digest,
                                                   mapped_fields=count, snapshot_digest=snapshot))
                        except _Cancelled:
                            raise
                        except OSError:
                            entries.append(replace(entry, status='unreadable'))
                        except (SaveError, ValueError, TypeError):
                            try:
                                _, current = _checked_path(path, root=root)
                                changed = _identity(current) != entry.identity
                            except (SaveError, OSError):
                                changed = True
                            entries.append(replace(entry, status='changed' if changed else 'rejected'))
                    except OSError:
                        # A disappearing directory entry is not a validated save.
                        if path.suffix.lower() == adapter.extension and len(entries) < limits.max_files:
                            entries.append(LibraryEntry(path.relative_to(root).as_posix(), 'unreadable', 0, 0))
    except _Cancelled:
        reason = 'cancelled'
    _, final_root = _checked_path(root, directory=True)
    if _directory_identity(final_root) != root_identity:
        raise SaveError('The copied-save folder changed identity. Scan it again.')
    # Only separately qualified files join a duplicate group. A rejected copy
    # with matching bytes and absent context must remain visibly rejected.
    counts = Counter((entry.size_bytes, entry.sha256) for entry in entries if entry.status == 'qualified')
    groups = {key: index + 1 for index, key in enumerate(sorted(key for key, count in counts.items() if count > 1))}
    entries = tuple(replace(entry, duplicate_group=groups.get((entry.size_bytes, entry.sha256), 0))
                    if entry.status == 'qualified' else entry for entry in entries)
    return LibraryScan(game_id, root, root_identity, recursive, limits, entries, visited, admitted, excluded, reason)


def _validate_scan(result):
    if (type(result) is not LibraryScan or type(result.entries) is not tuple
            or type(result.limits) is not ScanLimits or type(result.recursive) is not bool
            or result.stop_reason not in STOP_REASONS
            or any(type(getattr(result, key)) is not int or getattr(result, key) < 0
                   for key in ('visited_entries', 'admitted_bytes', 'excluded_directories'))):
        raise SaveError('A frozen Save Library inventory is required.')
    result.limits.validate()
    if (len(result.entries) > result.limits.max_files or result.visited_entries > result.limits.max_entries
            or result.admitted_bytes > result.limits.max_total_bytes):
        raise SaveError('The inventory exceeds its fixed scan bounds.')
    for entry in result.entries:
        if (type(entry) is not LibraryEntry or type(entry.relative_path) is not str
                or entry.status not in STATUSES or not entry.relative_path
                or any(type(getattr(entry, key)) is not int or getattr(entry, key) < 0
                       for key in ('size_bytes', 'mapped_fields', 'duplicate_group'))):
            raise SaveError('The library contains an invalid result entry.')
    return adapter_for(result.game_id)


def requalify(result, entry, *, cancel=None):
    """Return a freshly read document only if this scanned source stayed fixed.

    The caller must open its source with the normal editor read path as well;
    library qualification never substitutes for the editor's own source checks.
    """
    adapter = _validate_scan(result)
    if type(entry) is not LibraryEntry or entry not in result.entries or entry.status != 'qualified':
        raise SaveError('Choose a qualified copied-save entry.')
    relative = PurePosixPath(entry.relative_path)
    if (relative.is_absolute() or '..' in relative.parts or '\\' in entry.relative_path
            or ':' in entry.relative_path or relative.as_posix() != entry.relative_path):
        raise SaveError('The selected entry is not an ordinary relative copied-save path.')
    root, root_info = _checked_path(result.folder, directory=True)
    if _directory_identity(root_info) != result.folder_identity:
        raise SaveError('The copied-save folder changed identity. Scan it again.')
    path, info = _checked_path(root.joinpath(*relative.parts), root=root)
    if _identity(info) != entry.identity:
        raise SaveError('This copy changed since the scan. Scan the copied folder again.')
    document, digest, snapshot, count = _qualify(adapter, path, info, result.limits.max_file_bytes, cancel)
    if digest != entry.sha256 or snapshot != entry.snapshot_digest or count != entry.mapped_fields:
        raise SaveError('This save or its original context changed. Scan the copied folder again.')
    # A folder replacement can retain the very same save/context file inodes
    # after they are moved into a new directory. File freshness alone cannot
    # establish that the selected copied-save folder stayed the same.
    _, final_root = _checked_path(root, directory=True)
    if _directory_identity(final_root) != result.folder_identity:
        raise SaveError('The copied-save folder changed identity. Scan it again.')
    return document


def report(result):
    """Privacy-preserving summary: no paths, names, hashes or owner metadata.

    This describes a historical scan, not fresh qualification for opening/editing.
    """
    _validate_scan(result)
    game = get_game(result.game_id)
    counts = Counter(entry.status for entry in result.entries)
    duplicate_counts = Counter(entry.duplicate_group for entry in result.entries if entry.duplicate_group)
    return {'schema_version': 1, 'game_id': result.game_id, 'title': game.title,
            'platform': game.platform, 'read_only': True, 'historical_scan': True,
            'recursive': result.recursive, 'stop_reason': result.stop_reason,
            'candidate_files': len(result.entries), 'visited_directory_entries': result.visited_entries,
            'admitted_gameplay_bytes': result.admitted_bytes, 'excluded_directories': result.excluded_directories,
            'statuses': {status: counts[status] for status in STATUSES},
            'identical_gameplay_file_groups': len(duplicate_counts),
            'files_in_identical_gameplay_groups': sum(duplicate_counts.values()),
            'notes': ['Duplicate groups compare qualified gameplay-file bytes only; folder/account-context equality is not established.',
                      'Qualification is specific to the selected profile. It does not verify in-game loading.',
                      'Open a selected copy through the normal editor; a scan is not authorization to skip revalidation.']}
