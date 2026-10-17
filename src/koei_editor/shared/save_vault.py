"""Private, bounded local save history. Never repairs or overwrites game files.

Snapshots retain exact original bytes, including qualified original companions.
SHA256 detects accidental damage; this local index is not an authenticated store
against an attacker who can rewrite both the index and its checksums. Native
qualification always uses the explicitly selected registered profile.
"""
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
from inspect import signature
import os
from pathlib import Path, PurePosixPath
import re
import stat
import uuid

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.save_safety import safe_path, reserved_windows_path
from koei_editor.shared.save_library import _identity, _handle_binding, _linked, _snapshot_digest

# Fatal Frame II remake system saves are 61,851,984 bytes. These fixed
# ceilings admit every registered native profile without caller-raised limits.
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_CONTEXT_BYTES = 2 * 1024 * 1024
MAX_BUNDLE_BYTES = 72 * 1024 * 1024
MAX_STORAGE_BYTES = 1024 * 1024 * 1024
MAX_SNAPSHOTS = 500
MAX_INDEX_BYTES = 2 * 1024 * 1024
MAX_FILES = 12
_ID = re.compile(r'[0-9a-f]{32}\Z')
_HASH = re.compile(r'[0-9a-f]{64}\Z')
_BRANCH = re.compile(r'[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}\Z')
_CONTEXT = ('PARAM.SFO', 'sce_sys/param.sfo', 'eeprom.bin',
            'factory_eeprom.bin', 'SaveMeta.xbx')


@dataclass(frozen=True)
class VaultFile:
    relative_path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class VaultSnapshot:
    id: str
    game_id: str
    filename: str
    created_utc: str
    branch: str
    label: str
    parent_id: str | None
    files: tuple[VaultFile, ...]

    @property
    def size_bytes(self):
        return sum(item.size_bytes for item in self.files)

    @property
    def sha256(self):
        return next(item.sha256 for item in self.files if item.relative_path == self.filename)


@dataclass(frozen=True)
class VaultVerification:
    snapshot_id: str
    valid: bool
    summary: str


@dataclass(frozen=True)
class VaultComparison:
    left_id: str
    right_id: str
    same_profile: bool
    identical_gameplay_bytes: bool
    identical_context_bytes: bool
    changed_files: tuple[str, ...]
    changed_field_ids: tuple[str, ...]
    changed_byte_count: int


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def _relative(value):
    if (type(value) is not str or not value or len(value) > 255
            or '\\' in value or ':' in value or reserved_windows_path(value)):
        raise SaveError('Vault file names must be ordinary portable relative paths.')
    path = PurePosixPath(value)
    if (path.is_absolute() or '..' in path.parts or path.as_posix() != value
            or len(path.parts) > 2):
        raise SaveError('Vault file names must stay inside their private bundle.')
    return value


def _branch(value):
    if type(value) is not str or _BRANCH.fullmatch(value) is None or value.endswith((' ', '.')):
        raise SaveError('Use a branch name of 1–64 ordinary letters, digits, spaces, dots, dashes or underscores.')
    return value


def _label(value):
    if type(value) is not str or len(value) > 200 or any(ord(c) < 32 for c in value):
        raise SaveError('Snapshot labels must contain at most 200 printable characters.')
    return value


def _ordinary(path, *, directory=False, missing=False, companion=False):
    path = Path(path).absolute()
    # Only an exact captured Steam owner sidecar may use this private exception.
    # Its parent still receives the complete live/cloud-folder safety policy.
    def canonical():
        if companion and path.name.casefold() == 'steam_autocloud.vdf':
            return safe_path(path.parent / '.vault-context-copy').parent / path.name
        return safe_path(path)
    canonical()  # Reject live/cloud paths before any filesystem inspection.
    lexical_parent = None
    for item in (*reversed(path.parents), path):
        try:
            info = item.lstat()
        except FileNotFoundError:
            if missing and item == path:
                info = None
                break
            raise
        if _linked(info):
            raise SaveError('Save Vault rejects symbolic links, junctions and reparse paths.')
        if item == path.parent:
            lexical_parent = info
    if info is not None:
        valid = (stat.S_ISDIR(info.st_mode) if directory else
                 stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
        if not valid:
            raise SaveError('Save Vault requires ordinary separate, unaliased files and directories.')
    # Windows short and long names can refer to the same ordinary directory.
    # Containment and future operations must use the canonical spelling, AFTER
    # checking the supplied lexical path for links/reparse points. Bind both
    # spellings to the same filesystem identity rather than trusting the string.
    resolved = canonical()
    resolved_info = None
    for item in (*reversed(resolved.parents), resolved):
        try:
            current = item.lstat()
        except FileNotFoundError:
            if info is None and item == resolved:
                break
            raise
        if _linked(current):
            raise SaveError('Save Vault rejects symbolic links, junctions and reparse paths.')
        if item == resolved.parent and info is None:
            if ((current.st_dev, current.st_ino) !=
                    (lexical_parent.st_dev, lexical_parent.st_ino)):
                raise SaveError('The canonical destination parent changed identity.')
        if item == resolved:
            resolved_info = current
    if info is None:
        if resolved_info is not None:
            raise SaveError('The destination appeared while its canonical path was checked.')
    else:
        token = (lambda value: (value.st_dev, value.st_ino)) if directory else _identity
        if resolved_info is None or token(resolved_info) != token(info):
            raise SaveError('The canonical vault path changed filesystem identity.')
    return resolved, resolved_info


def _read(path, limit, *, companion=False):
    path, before = _ordinary(path, companion=companion)
    if not 0 <= before.st_size <= limit:
        raise SaveError('A vault file exceeds its fixed size bound.')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                or _handle_binding(opened) != _handle_binding(before)):
            raise SaveError('A vault source changed before reading.')
        def bounded_read():
            blocks, length = [], 0
            while length <= limit:
                block = os.read(descriptor, min(65536, limit + 1 - length))
                if not block:
                    break
                blocks.append(block)
                length += len(block)
            return b''.join(blocks)
        raw = bounded_read()
        os.lseek(descriptor, 0, os.SEEK_SET)
        second = bounded_read()
        _, after = _ordinary(path, companion=companion)
        if (len(raw) != before.st_size or raw != second
                or _identity(os.fstat(descriptor)) != _identity(opened)
                or _identity(before) != _identity(after)):
            raise SaveError('A vault source changed during reading.')
        return raw, _identity(after)
    finally:
        os.close(descriptor)


def _new(raw, path, *, companion=False):
    path, info = _ordinary(path, missing=True, companion=companion)
    if info is not None:
        raise FileExistsError('Save Vault never overwrites an existing destination.')
    parent, parent_info = _ordinary(path.parent, directory=True)
    temporary = parent / ('.vault-' + uuid.uuid4().hex + '.tmp')
    # Temp files stay beside their destination, so the final creation is atomic.
    with temporary.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if _read(temporary, len(raw))[0] != raw:
        raise SaveError('The temporary vault copy failed integrity verification.')
    if _ordinary(parent, directory=True)[1].st_ino != parent_info.st_ino:
        raise SaveError('The destination directory changed identity.')
    if os.name == 'nt':
        os.rename(temporary, path)
    else:
        os.link(temporary, path)
        temporary.unlink()
    if _read(path, len(raw), companion=companion)[0] != raw:
        raise SaveError('The created vault copy failed integrity verification.')
    return path


def _raw(document):
    raw = getattr(document, 'raw', getattr(document, 'encrypted', None))
    if type(raw) is not bytes:
        raise SaveError('This profile does not expose an exact original byte snapshot.')
    return raw


def _context_names(path, document):
    names = set(_CONTEXT)
    # Native owner/signing contexts supply their original opaque filename.
    for attribute in ('owner', 'context'):
        context = getattr(document, attribute, None)
        basename = getattr(context, 'basename', None)
        if basename is not None:
            _relative(basename)
            if '/' in basename:
                raise SaveError('The profile companion basename is not portable.')
            names.add(basename)
    # Original spelling matters to case-sensitive hosts. Enumerate at most a
    # fixed number of neighboring entries; never scan unrelated game folders.
    count = 0
    with os.scandir(path.parent) as entries:
        for entry in entries:
            count += 1
            if count > 4096:
                raise SaveError('The copied-save directory exceeds the context scan bound.')
            if entry.name.casefold() == 'steam_autocloud.vdf':
                names.add(entry.name)
    return tuple(sorted(name for name in names if name != path.name and
                        ((path.parent / name).exists() or (path.parent / name).is_symlink())))


def _profile_path(game_id, path):
    """Reuse the selected backend's established read-only destination policy.

    Several adapters add installed-game/emulator-folder checks beyond safe_path.
    Apply those BEFORE creating any destination, preserving their exact policy.
    Only their existing single-path guard convention is accepted; never guess a
    different call signature or try another game's backend.
    """
    game = get_game(game_id)
    safe_path(path)
    if game.scalar_backend:
        backend = game.get_scalar_adapter().backend
        guard = getattr(backend, '_copy_path', None) or getattr(backend, '_path', None)
        if guard is not None:
            try:
                signature(guard).bind(path)
            except (ValueError, TypeError) as error:
                raise SaveError('This profile needs an explicit single-path destination safety hook.') from error
            checked = guard(path)
            if Path(checked) != Path(path).resolve():
                raise SaveError('The native path guard returned a different destination.')


def _fidelity(document):
    if getattr(document, 'format', None) is not None:
        return _snapshot_digest(document)
    plaintext = getattr(document, 'plaintext', None)
    if type(plaintext) is bytes:
        return _digest(plaintext)
    raise SaveError('This profile lacks comparable original native snapshot metadata.')


def _qualify(game_id, path, expected):
    # Registry read_save binds the exact selected scalar or bespoke DW3 parser.
    document = get_game(game_id).read_save(path)
    if _raw(document) != expected:
        raise SaveError('The selected profile read different bytes during native qualification.')
    return document


class SaveVault:
    """An explicit private vault directory, with serialized cross-process access.

    A busy lock fails clearly instead of guessing that another process is dead.
    A process interrupted during a write can leave unindexed objects or a lock;
    these are never silently deleted or used for restoration. Keep this local
    store private: original companions can contain account/signing context.
    """
    def __init__(self, root):
        self.root, info = _ordinary(root, directory=True)
        self._root_identity = (info.st_dev, info.st_ino)
        self.objects, info = _ordinary(self.root / 'objects', directory=True)
        self._objects_identity = (info.st_dev, info.st_ino)
        with self._locked():
            self._load()

    @classmethod
    def create(cls, root):
        root, info = _ordinary(root, missing=True, directory=True)
        if info is not None:
            raise FileExistsError('Choose a new private Save Vault folder.')
        _ordinary(root.parent, directory=True)
        root.mkdir(mode=0o700)
        (root / 'objects').mkdir(mode=0o700)
        payload = {'schema_version': 1, 'snapshots': [], 'branches': {}}
        _new(_json({'payload': payload, 'sha256': _digest(_json(payload))}), root / 'index.json')
        return cls(root)

    def _check_roots(self):
        for path, expected in ((self.root, self._root_identity),
                               (self.objects, self._objects_identity)):
            _, info = _ordinary(path, directory=True)
            if (info.st_dev, info.st_ino) != expected:
                raise SaveError('The Save Vault directory changed identity; reopen it.')

    @contextmanager
    def _locked(self):
        self._check_roots()
        lock = self.root / '.lock'
        try:
            lock.mkdir(mode=0o700)
        except FileExistsError:
            raise SaveError('Save Vault is busy or has an interrupted operation lock; no files were changed.') from None
        _, info = _ordinary(lock, directory=True)
        identity = (info.st_dev, info.st_ino)
        try:
            self._check_roots()
            yield
            self._check_roots()
        finally:
            # Never remove a replacement lock or someone else's contents.
            try:
                _, current = _ordinary(lock, directory=True)
                if (current.st_dev, current.st_ino) == identity:
                    lock.rmdir()
            except (OSError, SaveError):
                pass

    def _load(self):
        raw, token = _read(self.root / 'index.json', MAX_INDEX_BYTES)
        try:
            envelope = json.loads(raw)
            if (type(envelope) is not dict or set(envelope) != {'payload', 'sha256'}
                    or envelope['sha256'] != _digest(_json(envelope['payload']))):
                raise ValueError
            payload = envelope['payload']
            if (type(payload) is not dict or set(payload) != {'schema_version', 'snapshots', 'branches'}
                    or type(payload['schema_version']) is not int or payload['schema_version'] != 1
                    or type(payload['snapshots']) is not list or len(payload['snapshots']) > MAX_SNAPSHOTS
                    or type(payload['branches']) is not dict or len(payload['branches']) > MAX_SNAPSHOTS):
                raise ValueError
            snapshots = []
            for item in payload['snapshots']:
                if type(item) is not dict or set(item) != set(VaultSnapshot.__dataclass_fields__):
                    raise ValueError
                item = dict(item)
                if type(item['files']) is not list or not 1 <= len(item['files']) <= MAX_FILES:
                    raise ValueError
                files = []
                for entry in item['files']:
                    if type(entry) is not dict or set(entry) != set(VaultFile.__dataclass_fields__):
                        raise ValueError
                    record = VaultFile(**entry)
                    _relative(record.relative_path)
                    if (type(record.sha256) is not str or not _HASH.fullmatch(record.sha256)
                            or type(record.size_bytes) is not int or not 0 <= record.size_bytes <= MAX_FILE_BYTES):
                        raise ValueError
                    files.append(record)
                item['files'] = tuple(files)
                snapshot = VaultSnapshot(**item)
                if (type(snapshot.id) is not str or not _ID.fullmatch(snapshot.id)
                        or type(snapshot.game_id) is not str or len(snapshot.game_id) > 100
                        or type(snapshot.created_utc) is not str or len(snapshot.created_utc) > 40
                        or snapshot.parent_id is not None and
                        (type(snapshot.parent_id) is not str or not _ID.fullmatch(snapshot.parent_id))):
                    raise ValueError
                _relative(snapshot.filename)
                _branch(snapshot.branch)
                _label(snapshot.label)
                game = get_game(snapshot.game_id)
                names = [entry.relative_path.casefold() for entry in files]
                if any(entry.relative_path != snapshot.filename and entry.size_bytes > MAX_CONTEXT_BYTES for entry in files):
                    raise ValueError
                if (len(set(names)) != len(names) or snapshot.filename not in [f.relative_path for f in files]
                        or '/' in snapshot.filename or Path(snapshot.filename).suffix.lower() != game.extension
                        or snapshot.size_bytes > MAX_BUNDLE_BYTES):
                    raise ValueError
                snapshots.append(snapshot)
            by_id = {snapshot.id: snapshot for snapshot in snapshots}
            if len(by_id) != len(snapshots) or sum(s.size_bytes for s in snapshots) > MAX_STORAGE_BYTES:
                raise ValueError
            for snapshot in snapshots:
                seen, node = set(), snapshot
                while node.parent_id is not None:
                    if node.id in seen or node.parent_id not in by_id:
                        raise ValueError
                    seen.add(node.id)
                    node = by_id[node.parent_id]
                    if node.game_id != snapshot.game_id:
                        raise ValueError
            for name, head in payload['branches'].items():
                _branch(name)
                if type(head) is not str or head not in by_id:
                    raise ValueError
            self._index_token, self._index_raw = token, raw
            return snapshots, dict(payload['branches'])
        except (ValueError, TypeError, KeyError, RecursionError) as error:
            raise SaveError('The Save Vault index is damaged or has invalid bounded metadata.') from error

    def _save(self, snapshots, branches):
        current, token = _read(self.root / 'index.json', MAX_INDEX_BYTES)
        if token != self._index_token or current != self._index_raw:
            raise SaveError('The Save Vault index changed during this operation.')
        payload = {'schema_version': 1, 'snapshots': [asdict(s) for s in snapshots], 'branches': branches}
        raw = _json({'payload': payload, 'sha256': _digest(_json(payload))})
        if len(raw) > MAX_INDEX_BYTES:
            raise SaveError('The Save Vault index reached its metadata bound.')
        temporary = self.root / ('.index-' + uuid.uuid4().hex + '.tmp')
        _new(raw, temporary)
        self._check_roots()
        if _read(self.root / 'index.json', MAX_INDEX_BYTES) != (current, token):
            raise SaveError('The Save Vault index changed before committing.')
        os.replace(temporary, self.root / 'index.json')
        if _read(self.root / 'index.json', MAX_INDEX_BYTES)[0] != raw:
            raise SaveError('The committed Save Vault index failed verification.')

    @staticmethod
    def _find(snapshots, snapshot_id):
        if type(snapshot_id) is not str or not _ID.fullmatch(snapshot_id):
            raise SaveError('Choose a valid Save Vault snapshot identifier.')
        for snapshot in snapshots:
            if snapshot.id == snapshot_id:
                return snapshot
        raise SaveError('The requested Save Vault snapshot does not exist.')

    def list_snapshots(self, *, game_id=None, branch=None):
        with self._locked():
            snapshots, branches = self._load()
            if game_id is not None:
                get_game(game_id)
            if branch is not None:
                _branch(branch)
                if branch not in branches:
                    raise SaveError('The requested vault branch does not exist.')
                ancestors, head = set(), branches[branch]
                while head is not None:
                    ancestors.add(head)
                    head = self._find(snapshots, head).parent_id
                snapshots = [s for s in snapshots if s.id in ancestors]
            return tuple(s for s in snapshots if game_id is None or s.game_id == game_id)

    def list_branches(self):
        with self._locked():
            _, branches = self._load()
            return dict(branches)

    def branch(self, name, from_snapshot):
        name = _branch(name)
        with self._locked():
            snapshots, branches = self._load()
            self._find(snapshots, from_snapshot)
            if name in branches:
                raise SaveError('The vault branch already exists.')
            if len(branches) >= MAX_SNAPSHOTS:
                raise SaveError('The vault reached its branch limit.')
            branches[name] = from_snapshot
            self._save(snapshots, branches)

    def _bundle(self, snapshot):
        directory, directory_info = _ordinary(self.objects / snapshot.id, directory=True)
        bundle = {}
        for record in snapshot.files:
            limit = MAX_FILE_BYTES if record.relative_path == snapshot.filename else MAX_CONTEXT_BYTES
            raw, _ = _read(directory / record.relative_path, limit, companion=True)
            if len(raw) != record.size_bytes or _digest(raw) != record.sha256:
                raise SaveError('Snapshot file checksum or size does not match its index.')
            bundle[record.relative_path] = raw
        self._check_bundle_entries(directory, bundle)
        document = _qualify(snapshot.game_id, directory / snapshot.filename, bundle[snapshot.filename])
        # Native readers can consume opaque context. Compare their fresh reads
        # against exactly the immutable bytes admitted above, including sidecars.
        for name, raw in bundle.items():
            if _read(directory / name, MAX_FILE_BYTES, companion=True)[0] != raw:
                raise SaveError('Snapshot context changed during native qualification.')
        reread = _qualify(snapshot.game_id, directory / snapshot.filename, bundle[snapshot.filename])
        if _fidelity(reread) != _fidelity(document):
            raise SaveError('Snapshot native context changed during qualification.')
        for name, raw in bundle.items():
            if _read(directory / name, MAX_FILE_BYTES, companion=True)[0] != raw:
                raise SaveError('Snapshot bytes changed after native qualification.')
        self._check_bundle_entries(directory, bundle)
        final_info = _ordinary(directory, directory=True)[1]
        if (final_info.st_dev, final_info.st_ino) != (directory_info.st_dev, directory_info.st_ino):
            raise SaveError('The snapshot directory changed identity.')
        return bundle, reread

    @staticmethod
    def _check_bundle_entries(directory, bundle):
        expected = set(bundle)
        actual = set()
        with os.scandir(directory) as entries:
            for item in entries:
                if len(actual) > MAX_FILES:
                    raise SaveError('A snapshot contains too many storage entries.')
                if item.name == 'sce_sys':
                    subdir, _ = _ordinary(Path(item.path), directory=True)
                    with os.scandir(subdir) as children:
                        for child in children:
                            actual.add('sce_sys/' + child.name)
                            if len(actual) > MAX_FILES:
                                raise SaveError('A snapshot contains too many storage entries.')
                else:
                    actual.add(item.name)
        if actual != expected:
            raise SaveError('The snapshot contains unindexed or missing storage files.')

    @staticmethod
    def _materialize(bundle, directory):
        for name, raw in bundle.items():
            target = directory / name
            if '/' in name:
                if not target.parent.exists():
                    target.parent.mkdir(mode=0o700)
                _ordinary(target.parent, directory=True)
            _new(raw, target, companion=True)

    def snapshot(self, game_id, source, *, branch='main', label='', parent_id=None):
        branch, label = _branch(branch), _label(label)
        get_game(game_id)
        source, source_info = _ordinary(source)
        _relative(source.name)
        source_parent = _ordinary(source.parent, directory=True)[1]
        if source.is_relative_to(self.root):
            raise SaveError('Snapshot an independent save copy outside the vault.')
        with self._locked():
            snapshots, branches = self._load()
            if len(snapshots) >= MAX_SNAPSHOTS:
                raise SaveError('The vault reached its snapshot limit.')
            if branch not in branches and len(branches) >= MAX_SNAPSHOTS:
                raise SaveError('The vault reached its branch limit.')
            if parent_id is None:
                parent_id = branches.get(branch)
            if parent_id is not None and self._find(snapshots, parent_id).game_id != game_id:
                raise SaveError('Use a separate branch for this game/platform profile.')
            raw, token = _read(source, MAX_FILE_BYTES)
            if token != _identity(source_info):
                raise SaveError('The source copy changed before snapshot capture.')
            # Reject linked/oversized conventional context before native readers
            # can follow it. The backend owns any additional profile-specific context.
            for name in _context_names(source, None):
                _read(source.parent / name, MAX_CONTEXT_BYTES, companion=True)
            document = _qualify(game_id, source, raw)
            fidelity = _fidelity(document)
            names = _context_names(source, document)
            if len(names) + 1 > MAX_FILES:
                raise SaveError('The original context exceeds the companion file bound.')
            bundle, tokens = {source.name: raw}, {source.name: token}
            for name in names:
                _relative(name)
                data, context_token = _read(source.parent / name, MAX_CONTEXT_BYTES, companion=True)
                bundle[name], tokens[name] = data, context_token
            if sum(map(len, bundle.values())) > MAX_BUNDLE_BYTES:
                raise SaveError('The save and original context exceed the snapshot size bound.')
            if sum(s.size_bytes for s in snapshots) + sum(map(len, bundle.values())) > MAX_STORAGE_BYTES:
                raise SaveError('The vault reached its bounded storage capacity.')
            # Qualify the source again AFTER capturing companions, avoiding a
            # switch to a different still-valid original account/title sidecar.
            reread = _qualify(game_id, source, raw)
            if _fidelity(reread) != fidelity:
                raise SaveError('The original native context changed during snapshot capture.')
            for name, expected in bundle.items():
                data, current = _read(source.parent / name, MAX_FILE_BYTES, companion=True)
                if data != expected or current != tokens[name]:
                    raise SaveError('The source or its original companion context changed during capture.')
            if _context_names(source, document) != names:
                raise SaveError('The original companion set changed during capture.')
            snapshot_id = uuid.uuid4().hex
            record = VaultSnapshot(snapshot_id, game_id, source.name,
                                   datetime.now(timezone.utc).isoformat(), branch, label, parent_id,
                                   tuple(VaultFile(name, _digest(data), len(data)) for name, data in sorted(bundle.items())))
            # Include abandoned, unindexed storage in the capacity calculation.
            total, count = 0, 0
            with os.scandir(self.objects) as entries:
                for item in entries:
                    count += 1
                    if count > MAX_SNAPSHOTS or not _ID.fullmatch(item.name):
                        raise SaveError('The vault object directory is full or contains invalid storage.')
                    _ordinary(item.path, directory=True)
                    # Every admitted object has fixed per-file bounds; counting
                    # unindexed directories conservatively avoids unbounded walks.
                    if item.name not in {s.id for s in snapshots}:
                        total += MAX_BUNDLE_BYTES
            if count >= MAX_SNAPSHOTS:
                raise SaveError('The vault object directory reached its fixed entry limit.')
            if total + sum(s.size_bytes for s in snapshots) + record.size_bytes > MAX_STORAGE_BYTES:
                raise SaveError('Unindexed vault objects consume the remaining storage capacity.')
            directory = self.objects / snapshot_id
            _profile_path(game_id, directory / source.name)
            directory.mkdir(mode=0o700)
            self._materialize(bundle, directory)
            self._bundle(record)  # Exact restored-byte native qualification before acceptance.
            for name, expected in bundle.items():
                data, current = _read(source.parent / name, MAX_FILE_BYTES, companion=True)
                if data != expected or current != tokens[name]:
                    raise SaveError('The source changed before the snapshot was committed.')
            if _context_names(source, document) != names:
                raise SaveError('The original companion set changed before committing the snapshot.')
            final_parent = _ordinary(source.parent, directory=True)[1]
            if (final_parent.st_dev, final_parent.st_ino) != (source_parent.st_dev, source_parent.st_ino):
                raise SaveError('The original copied-save directory changed identity.')
            snapshots.append(record)
            branches[branch] = record.id
            self._save(snapshots, branches)
            return record

    def verify(self, snapshot_id=None):
        with self._locked():
            snapshots, _ = self._load()
            if snapshot_id is not None:
                snapshots = [self._find(snapshots, snapshot_id)]
            results = []
            for snapshot in snapshots:
                try:
                    self._bundle(snapshot)
                    result = VaultVerification(snapshot.id, True, 'SHA256, exact original context and selected native profile verified; in-game loading is not established.')
                except (OSError, ValueError, TypeError):
                    # Never expose parser exceptions containing owner/path data.
                    result = VaultVerification(snapshot.id, False, 'Snapshot integrity or selected native profile/context validation failed. Restore is blocked.')
                results.append(result)
            return tuple(results)

    def restore(self, snapshot_id, destination):
        """Restore exact bytes into a NEW dedicated directory; return save path.

        The directory must not exist. Companion names and gameplay filename are
        retained. A failed write may leave a private incomplete directory; it is
        never overwritten or silently deleted, and failure never reports success.
        """
        destination, info = _ordinary(destination, directory=True, missing=True)
        if info is not None:
            raise FileExistsError('Restore requires a new dedicated destination directory.')
        if destination.is_relative_to(self.root):
            raise SaveError('Restore to a separate copied-save folder outside the vault.')
        with self._locked():
            snapshots, _ = self._load()
            snapshot = self._find(snapshots, snapshot_id)
            bundle, _ = self._bundle(snapshot)
            _profile_path(snapshot.game_id, destination / snapshot.filename)
            destination.mkdir(mode=0o700)
            self._materialize(bundle, destination)
            path = destination / snapshot.filename
            _qualify(snapshot.game_id, path, bundle[snapshot.filename])
            for name, raw in bundle.items():
                if _read(destination / name, MAX_FILE_BYTES, companion=True)[0] != raw:
                    raise SaveError('The restored copy changed during native read-back.')
            self._check_bundle_entries(destination, bundle)
            return path

    def relabel(self, snapshot_id, label):
        label = _label(label)
        from dataclasses import replace
        with self._locked():
            snapshots, branches = self._load()
            snapshot = self._find(snapshots, snapshot_id)
            updated = replace(snapshot, label=label)
            self._save([updated if s.id == snapshot_id else s for s in snapshots], branches)
            return updated

    def delete(self, snapshot_id):
        """Remove a leaf history entry; retain its immutable files for recovery.

        Deletion only removes this index reference and updates branch heads.
        Files deliberately remain private, unindexed objects: destructive disk
        cleanup requires a separate explicit operation and never follows aliases.
        """
        with self._locked():
            snapshots, branches = self._load()
            snapshot = self._find(snapshots, snapshot_id)
            if any(s.parent_id == snapshot_id for s in snapshots):
                raise SaveError('Remove descendant snapshots before deleting this history entry.')
            branches = {name: snapshot.parent_id if head == snapshot_id else head
                        for name, head in branches.items() if head != snapshot_id or snapshot.parent_id is not None}
            self._save([s for s in snapshots if s.id != snapshot_id], branches)

    def compare(self, left_id, right_id):
        with self._locked():
            snapshots, _ = self._load()
            left, right = self._find(snapshots, left_id), self._find(snapshots, right_id)
            first, first_doc = self._bundle(left)
            second, second_doc = self._bundle(right)
            left_raw, right_raw = first[left.filename], second[right.filename]
            left_context = {name: raw for name, raw in first.items() if name != left.filename}
            right_context = {name: raw for name, raw in second.items() if name != right.filename}
            changes = tuple(sorted(name for name in first.keys() | second.keys() if first.get(name) != second.get(name)))
            field_ids = ()
            same_profile = left.game_id == right.game_id
            game = get_game(left.game_id)
            if same_profile and game.scalar_backend:
                adapter = game.get_scalar_adapter()
                left_fields = {f.id: f.value(first_doc.payload) for f in adapter.fields_for(first_doc)}
                right_fields = {f.id: f.value(second_doc.payload) for f in adapter.fields_for(second_doc)}
                field_ids = tuple(sorted(key for key in left_fields.keys() | right_fields.keys()
                                         if left_fields.get(key) != right_fields.get(key)))
            changed_bytes = sum(a != b for a, b in zip(left_raw, right_raw)) + abs(len(left_raw) - len(right_raw))
            return VaultComparison(left_id, right_id, same_profile, left_raw == right_raw,
                                   left_context == right_context, changes, field_ids, changed_bytes)
