"""Private local, copy-only save history with immutable content and catalogs.

The catalog contains labels and opaque hashes, never source paths or decoded
account metadata. Qualification and context copying stay in the selected game
adapter. No vault operation edits a player's original or an existing output.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import uuid

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import save_library, save_comparison
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.save_safety import safe_path, reserved_windows_path

MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_CONTEXT_BYTES = 2 * 1024 * 1024
MAX_INDEX_BYTES = 4 * 1024 * 1024
MAX_SNAPSHOTS = 5000
MAX_REVISIONS = 10000
MAX_CATALOG_BYTES = 128 * 1024 * 1024
MAX_CONTEXT_FILES = 8
_HASH = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'[0-9a-f]{32}\Z')


def default_root():
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')
    return base / 'UniversalKoeiTecmoSaveEditor' / 'SaveVault'


def _label(value):
    if (type(value) is not str or not value.strip() or len(value) > 120
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise SaveError('Use a nonempty label of at most 120 characters without control characters.')
    return value.strip()


def _relative(value):
    if type(value) is not str:
        raise SaveError('Invalid private snapshot filename.')
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or len(path.parts) > 2 or '..' in path.parts
            or '.' in path.parts or '\\' in value or ':' in value
            or path.as_posix() != value or reserved_windows_path(value)):
        raise SaveError('Invalid private snapshot filename.')
    return path


def _ordinary(path, *, directory=False):
    """Check ordinary ancestors, including the special opaque Steam sidecar."""
    path = Path(path).absolute()
    # The generic policy rightly refuses Steam cloud metadata as a game input.
    # Only private, opaque backend-produced sidecars use this narrow exception.
    safe_path(path.parent)
    if path.name.casefold() != 'steam_autocloud.vdf':
        safe_path(path)
    for item in (*reversed(path.parents), path):
        info = item.lstat()
        if save_library._linked(info):
            raise SaveError('Save Vault requires ordinary paths without links or reparse points.')
    info = path.lstat()
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise SaveError('Save Vault requires an ordinary directory.')
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise SaveError('Save Vault requires an ordinary unaliased file.')
    return path, info


def _read(path, limit):
    path, before = _ordinary(path)
    token = save_library._identity(before)
    if before.st_size > limit:
        raise SaveError('Save Vault file exceeds its bounded size.')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0)
                 | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    try:
        opened = os.fstat(fd)
        handle_token = save_library._identity(opened)
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                or save_library._handle_binding(opened) != save_library._handle_binding(before)):
            raise SaveError('Save Vault file changed before reading.')
        chunks, remaining = [], limit + 1
        while remaining:
            part = os.read(fd, min(65536, remaining))
            if not part:
                break
            chunks.append(part)
            remaining -= len(part)
        raw = b''.join(chunks)
        _, after = _ordinary(path)
        if (len(raw) != before.st_size or len(raw) > limit
                or save_library._identity(after) != token
                or save_library._identity(os.fstat(fd)) != handle_token):
            raise SaveError('Save Vault file changed during reading.')
        return raw
    finally:
        os.close(fd)


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _source_context_hashes(source):
    """Bind complete known opaque originals independently of native metadata.

    Windows path ctime can be creation time. Exact bytes remain authoritative
    even when a same-size replacement restores its original mtime.
    """
    hashes, total = {}, 0
    for relative, _ in save_library._context_guard(source):
        if relative == 'sce_sys':
            continue
        raw = _read(source.parent.joinpath(*relative.split('/')), MAX_CONTEXT_BYTES)
        total += len(raw)
        if total > MAX_CONTEXT_BYTES:
            raise SaveError('Original opaque context exceeds the total vault byte bound.')
        hashes[relative] = _digest(raw)
    return hashes


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate catalog key.')
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid number')))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise SaveError('Save Vault catalog is damaged.') from error


def _new(raw, path):
    """Publish an ordinary new file and validate actual bytes without rollback."""
    path = Path(path)
    parent, parent_info = _ordinary(path.parent, directory=True)
    parent_identity = save_library._directory_identity(parent_info)
    if path.name.casefold() == 'steam_autocloud.vdf':
        # atomic_new's general policy excludes cloud metadata; this exact private
        # companion is already opaque bytes supplied by the qualified backend.
        temp = path.parent / ('.opaque-' + uuid.uuid4().hex)
        atomic_new(raw, temp)
        if os.name == 'nt':
            os.rename(temp, path)
        else:
            os.link(temp, path)
            temp.unlink()
    else:
        atomic_new(raw, path)
    if _read(path, len(raw)) != raw:
        raise SaveError('A completed Save Vault output changed during verification; it was retained.')
    if save_library._directory_identity(_ordinary(parent, directory=True)[1]) != parent_identity:
        raise SaveError('Output directory changed; completed Save Vault files were retained.')
    return path


class Vault:
    def __init__(self, root=None):
        original = Path(default_root() if root is None else root).absolute()
        safe_path(original)
        # Reject linked existing ancestors before mkdir resolves anything.
        for item in (*reversed(original.parents), original):
            if item.exists() or item.is_symlink():
                if save_library._linked(item.lstat()):
                    raise SaveError('Choose a local vault without linked ancestors.')
        original.mkdir(parents=True, exist_ok=True)
        self.root, info = _ordinary(original, directory=True)
        self._root_identity = save_library._directory_identity(info)
        self._directories = {}
        for name in ('blobs', 'catalog', 'copies'):
            path = self.root / name
            path.mkdir(exist_ok=True)
            self._directories[name] = save_library._directory_identity(_ordinary(path, directory=True)[1])

    def _guard(self):
        _, info = _ordinary(self.root, directory=True)
        if save_library._directory_identity(info) != self._root_identity:
            raise SaveError('Save Vault directory changed identity.')
        for name in ('blobs', 'catalog', 'copies'):
            if save_library._directory_identity(_ordinary(self.root / name, directory=True)[1]) != self._directories[name]:
                raise SaveError('A Save Vault storage directory changed identity.')

    @contextmanager
    def _writer(self):
        self._guard()
        lock = self.root / '.writer-lock'
        try:
            lock.mkdir()
        except FileExistsError as error:
            raise SaveError('Save Vault is busy or has an interrupted writer lock. Close other vault writers before recovery.') from error
        _, info = _ordinary(lock, directory=True)
        identity = save_library._directory_identity(info)
        try:
            yield
        finally:
            # Never delete a foreign replacement, or a lock with unknown files.
            try:
                _, current = _ordinary(lock, directory=True)
                if save_library._directory_identity(current) == identity:
                    lock.rmdir()
            except OSError:
                pass

    def _catalog(self):
        self._guard()
        names, total = [], 0
        with os.scandir(self.root / 'catalog') as entries:
            for entry in entries:
                if len(names) >= MAX_REVISIONS:
                    raise SaveError('Save Vault catalog revision limit reached.')
                if not re.fullmatch(r'[0-9]{8}\.json', entry.name):
                    raise SaveError('Save Vault catalog contains an unexpected entry.')
                info = entry.stat(follow_symlinks=False)
                total += info.st_size
                if total > MAX_CATALOG_BYTES:
                    raise SaveError('Save Vault catalog exceeds its total bounded size.')
                names.append(entry.name)
        names.sort()
        if names != [f'{index:08}.json' for index in range(1, len(names) + 1)]:
            raise SaveError('Save Vault catalog history has a missing revision.')
        if not names:
            return {'schema': 1, 'revision': 0, 'previous': '', 'collections': [], 'snapshots': []}, ''
        previous_digest = ''
        raw = None
        for ordinal, name in enumerate(names, 1):
            raw = _read(self.root / 'catalog' / name, MAX_INDEX_BYTES)
            header = _json(raw)
            if (type(header) is not dict or type(header.get('revision')) is not int
                    or header['revision'] != ordinal or header.get('previous') != previous_digest):
                raise SaveError('Save Vault immutable catalog hash chain is damaged.')
            previous_digest = _digest(raw)
        index = _json(raw)
        try:
            self._validate(index)
        except (TypeError, KeyError, ValueError) as error:
            raise SaveError('Save Vault catalog metadata is invalid.') from error
        if index['revision'] != len(names):
            raise SaveError('Save Vault catalog revision does not match its immutable filename.')
        self._guard()
        return index, _digest(raw)

    def _validate(self, index):
        if (type(index) is not dict or set(index) != {'schema', 'revision', 'previous', 'collections', 'snapshots'}
                or type(index['schema']) is not int or index['schema'] != 1
                or type(index['revision']) is not int or not 1 <= index['revision'] <= MAX_REVISIONS
                or type(index['previous']) is not str
                or (index['previous'] and not _HASH.fullmatch(index['previous']))
                or type(index['collections']) is not list or len(index['collections']) > 500
                or type(index['snapshots']) is not list or len(index['snapshots']) > MAX_SNAPSHOTS):
            raise SaveError('Save Vault catalog shape or bounds are invalid.')
        collections = set()
        for label in index['collections']:
            if _label(label) != label or label in collections:
                raise SaveError('Save Vault collections must be unique labels.')
            collections.add(label)
        seen = {}
        for row in index['snapshots']:
            if (type(row) is not dict or set(row) != {'id', 'game_id', 'label', 'collection', 'branch',
                    'parent', 'created_utc', 'filename', 'blob', 'size', 'context'}
                    or type(row['id']) is not str or not _ID.fullmatch(row['id']) or row['id'] in seen
                    or row['collection'] not in collections or type(row['created_utc']) is not str
                    or len(row['created_utc']) > 40 or type(row['size']) is not int
                    or not 0 < row['size'] <= MAX_FILE_BYTES
                    or type(row['blob']) is not str or not _HASH.fullmatch(row['blob'])
                    or type(row['context']) is not dict or len(row['context']) > MAX_CONTEXT_FILES):
                raise SaveError('Save Vault snapshot metadata is invalid.')
            _label(row['label']); _label(row['branch'])
            adapter = save_library.adapter_for(row['game_id'])
            relative = _relative(row['filename'])
            if len(relative.parts) != 1 or Path(row['filename']).suffix.lower() != adapter.extension:
                raise SaveError('Save Vault snapshot filename does not match its selected profile.')
            for name, digest in row['context'].items():
                _relative(name)
                if (name == row['filename'] or type(digest) is not str or not _HASH.fullmatch(digest)):
                    raise SaveError('Save Vault opaque companion metadata is invalid.')
            parent = row['parent']
            if parent is not None and (parent not in seen or seen[parent]['game_id'] != row['game_id']
                    or seen[parent]['collection'] != row['collection']):
                raise SaveError('Save Vault parent history is missing, cyclic or belongs to another profile/collection.')
            seen[row['id']] = row

    def _commit(self, index, previous):
        self._guard()
        latest, digest = self._catalog()
        if digest != previous or latest['revision'] != index['revision']:
            raise SaveError('Save Vault catalog changed during this operation; completed copies were retained.')
        index = {**index, 'revision': index['revision'] + 1, 'previous': previous}
        self._validate(index)
        raw = (json.dumps(index, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
        if len(raw) > MAX_INDEX_BYTES:
            raise SaveError('Save Vault bounded catalog is full; completed copies were retained.')
        total = len(raw)
        for revision in range(1, index['revision']):
            _, info = _ordinary(self.root / 'catalog' / f'{revision:08}.json')
            total += info.st_size
        if total > MAX_CATALOG_BYTES:
            raise SaveError('Save Vault total catalog bound reached; completed copies were retained.')
        _new(raw, self.root / 'catalog' / f'{index["revision"]:08}.json')
        self._guard()
        committed, digest = self._catalog()
        if digest != _digest(raw) or committed != index:
            raise SaveError('Save Vault catalog changed after commit; completed copies were retained.')

    def collections(self):
        return tuple(self._catalog()[0]['collections'])

    def create_collection(self, label):
        label = _label(label)
        with self._writer():
            index, digest = self._catalog()
            if label in index['collections']:
                raise SaveError('That collection already exists.')
            index['collections'].append(label)
            self._commit(index, digest)
        return label

    def snapshots(self, *, query='', collection=None, game_id=None, branch=None):
        tokens = str(query).casefold().split()
        rows = self._catalog()[0]['snapshots']
        return tuple(dict(row, context=dict(row['context'])) for row in reversed(rows)
            if (collection is None or row['collection'] == collection)
            and (game_id is None or row['game_id'] == game_id)
            and (branch is None or row['branch'] == branch)
            and all(token in ' '.join((row['label'], row['collection'], row['branch'], row['game_id'])).casefold()
                    for token in tokens))

    def _row(self, snapshot_id):
        return next((row for row in self._catalog()[0]['snapshots'] if row['id'] == snapshot_id), None)

    def _require(self, snapshot_id):
        row = self._row(snapshot_id)
        if row is None:
            raise SaveError('Choose an existing Save Vault snapshot.')
        return row

    def _blob(self, raw):
        digest = _digest(raw)
        path = self.root / 'blobs' / digest
        if path.exists() or path.is_symlink():
            if _read(path, max(MAX_FILE_BYTES, MAX_CONTEXT_BYTES)) != raw:
                raise SaveError('Save Vault content-addressed blob is damaged.')
        else:
            _new(raw, path)
        return digest

    def import_copy(self, game_id, path, label, *, collection='Backups', branch='main', parent_id=None):
        label, collection, branch = _label(label), _label(collection), _label(branch)
        adapter = save_library.adapter_for(game_id)
        source, info = save_library._checked_path(path)
        source_context_guard = save_library._context_guard(source)
        source_context_hashes = _source_context_hashes(source)
        original, _, _, _ = save_library._qualify(adapter, source, info, MAX_FILE_BYTES, None)
        if Path(source).suffix.lower() != adapter.extension:
            raise SaveError('The source filename does not match the selected game/platform.')
        _relative(source.name)
        with self._writer():
            index, previous = self._catalog()
            if parent_id is not None:
                parent = next((row for row in index['snapshots'] if row['id'] == parent_id), None)
                if parent is None or parent['game_id'] != game_id or parent['collection'] != collection:
                    raise SaveError('Choose a parent from the same game/platform and collection.')
            identity = uuid.uuid4().hex
            stage = self.root / 'copies' / identity
            stage.mkdir()
            context_hook = getattr(adapter.backend, 'prepare_copy_context', None)
            if context_hook is not None:
                context_hook(original, stage)
            staged = _new(original.raw, stage / source.name)
            prepare = getattr(adapter.backend, 'prepare_self_test_copy', None)
            if prepare is not None:
                if context_hook is None:
                    # Older read-only title-context adapters create minimal SFO
                    # in self-tests. Vault preserves the exact original instead;
                    # the owning hook then validates the existing companion.
                    for relative in ('PARAM.SFO', 'sce_sys/param.sfo'):
                        companion = source.parent.joinpath(*relative.split('/'))
                        if companion.exists() or companion.is_symlink():
                            raw = _read(companion, MAX_CONTEXT_BYTES)
                            target = stage.joinpath(*relative.split('/'))
                            if target.parent != stage:
                                target.parent.mkdir(exist_ok=True)
                            _new(raw, target)
                prepare(original, staged)
            context_state = self._context_state(stage, source.name)
            for relative, _ in context_state:
                if not relative.endswith('/'):
                    components = _relative(relative).parts
                    if _read(stage.joinpath(*components), MAX_CONTEXT_BYTES) != _read(source.parent.joinpath(*components), MAX_CONTEXT_BYTES):
                        raise SaveError('Vault requires exact original opaque context; synthesized companions are not imported.')
            stored = adapter.read_save(staged)
            if stored.raw != original.raw or stored.payload != original.payload:
                raise SaveError('Save Vault copied input does not match its qualified original.')
            context = self._capture_context(stage, source.name)
            if prepare is not None:
                prepare(original, staged)
            if adapter.read_save(staged) != stored or self._context_state(stage, source.name) != context_state:
                raise SaveError('Copied original context changed while importing into Save Vault.')
            # Requalify the same source after context copying and native readback.
            current, _, _, _ = save_library._qualify(adapter, source, info, MAX_FILE_BYTES, None)
            if (current != original or save_library._context_guard(source) != source_context_guard
                    or _source_context_hashes(source) != source_context_hashes):
                raise SaveError('The copied input or original context changed during import.')
            row = {'id': identity, 'game_id': game_id, 'label': label, 'collection': collection,
                   'branch': branch, 'parent': parent_id,
                   'created_utc': datetime.now(timezone.utc).isoformat(), 'filename': source.name,
                   'blob': self._blob(original.raw), 'size': len(original.raw), 'context': context}
            if collection not in index['collections']:
                index['collections'].append(collection)
            index['snapshots'].append(row)
            self._commit(index, previous)
        self.verify(identity)
        return dict(row, context=dict(context))

    def _capture_context(self, directory, gameplay):
        context, total = {}, 0
        def visit(folder, depth):
            nonlocal total
            _ordinary(folder, directory=True)
            with os.scandir(folder) as entries:
                for item in entries:
                    relative = Path(item.path).relative_to(directory).as_posix()
                    if relative == gameplay:
                        continue
                    _relative(relative)
                    if len(context) >= MAX_CONTEXT_FILES:
                        raise SaveError('Backend copied context exceeds the vault file bound.')
                    info = item.stat(follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode) and depth == 0 and not save_library._linked(info):
                        visit(Path(item.path), depth + 1)
                    else:
                        raw = _read(item.path, MAX_CONTEXT_BYTES)
                        total += len(raw)
                        if total > MAX_CONTEXT_BYTES:
                            raise SaveError('Backend copied opaque context exceeds its byte bound.')
                        context[relative] = self._blob(raw)
        visit(directory, 0)
        return context

    def _context_state(self, directory, gameplay):
        """Bound every backend-produced companion across native qualification."""
        states = []
        visited = 0
        def visit(folder, depth):
            nonlocal visited
            _ordinary(folder, directory=True)
            with os.scandir(folder) as entries:
                for entry in entries:
                    visited += 1
                    if visited > 24:
                        raise SaveError('Copied context contains too many directory entries.')
                    relative = Path(entry.path).relative_to(directory).as_posix()
                    if relative == gameplay:
                        continue
                    _relative(relative)
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode) and depth == 0 and not save_library._linked(info):
                        states.append((relative + '/', save_library._directory_identity(info)))
                        visit(Path(entry.path), 1)
                    else:
                        _, checked = _ordinary(entry.path)
                        states.append((relative, save_library._identity(checked)))
            if len(states) > MAX_CONTEXT_FILES + 1:
                raise SaveError('Copied context exceeds the file bound.')
        visit(directory, 0)
        return tuple(sorted(states))

    def _verify_context(self, row, directory):
        state = self._context_state(directory, row['filename'])
        names = {name for name, _ in state if not name.endswith('/')}
        if names != set(row['context']):
            raise SaveError('Save Vault copied companion inventory changed.')
        total = 0
        for relative, digest in row['context'].items():
            expected = _read(self.root / 'blobs' / digest, MAX_CONTEXT_BYTES)
            total += len(expected)
            if total > MAX_CONTEXT_BYTES:
                raise SaveError('Save Vault opaque companion bytes exceed the total bound.')
            actual = _read(directory.joinpath(*_relative(relative).parts), MAX_CONTEXT_BYTES)
            if _digest(expected) != digest or expected != actual:
                raise SaveError('Save Vault original opaque context is damaged or changed.')
        if state != self._context_state(directory, row['filename']):
            raise SaveError('Save Vault original context changed during verification.')
        return state

    def _materialize(self, row, directory):
        _ordinary(directory, directory=True)
        if any(directory.iterdir()):
            raise SaveError('Save Vault export requires a brand-new empty output directory.')
        context_bytes = 0
        for relative, digest in row['context'].items():
            raw = _read(self.root / 'blobs' / digest, MAX_CONTEXT_BYTES)
            context_bytes += len(raw)
            if context_bytes > MAX_CONTEXT_BYTES:
                raise SaveError('Save Vault opaque companion bytes exceed the total bound.')
            if _digest(raw) != digest:
                raise SaveError('Save Vault opaque companion hash does not match.')
            path = directory.joinpath(*_relative(relative).parts)
            if path.parent != directory:
                path.parent.mkdir(exist_ok=True)
                _ordinary(path.parent, directory=True)
            _new(raw, path)
        raw = _read(self.root / 'blobs' / row['blob'], MAX_FILE_BYTES)
        if _digest(raw) != row['blob'] or len(raw) != row['size']:
            raise SaveError('Save Vault gameplay hash or size does not match.')
        return _new(raw, directory / row['filename'])

    def verify(self, snapshot_id):
        self._guard()
        row = self._require(snapshot_id)
        adapter = save_library.adapter_for(row['game_id'])
        # Stored working copies are rechecked against immutable content blobs;
        # no repair is attempted when either representation was changed.
        directory = self.root / 'copies' / row['id']
        directory_identity = save_library._directory_identity(_ordinary(directory, directory=True)[1])
        path, info = save_library._checked_path(directory / row['filename'])
        expected = _read(self.root / 'blobs' / row['blob'], MAX_FILE_BYTES)
        if _digest(expected) != row['blob'] or len(expected) != row['size']:
            raise SaveError('Save Vault gameplay blob is damaged.')
        context_state = self._verify_context(row, directory)
        document, _, _, _ = save_library._qualify(adapter, path, info, MAX_FILE_BYTES, None)
        if document.raw != expected:
            raise SaveError('Save Vault snapshot copy does not match its immutable content.')
        if context_state != self._verify_context(row, directory):
            raise SaveError('Save Vault context changed across native qualification.')
        if save_library._directory_identity(_ordinary(directory, directory=True)[1]) != directory_identity:
            raise SaveError('Save Vault snapshot directory changed identity.')
        self._guard()
        return document

    def compare(self, left_id, right_id):
        left, right = self._require(left_id), self._require(right_id)
        if left['game_id'] != right['game_id']:
            raise SaveError('Compare two snapshots from the same game/platform.')
        result = save_comparison.compare_documents(left['game_id'], self.verify(left_id), self.verify(right_id))
        self.verify(left_id); self.verify(right_id)
        return result

    def history(self, snapshot_id):
        rows = {row['id']: row for row in self._catalog()[0]['snapshots']}
        if snapshot_id not in rows:
            raise SaveError('Choose an existing Save Vault snapshot.')
        chain = []
        while snapshot_id is not None:
            row = rows[snapshot_id]
            chain.append(dict(row, context=dict(row['context'])))
            snapshot_id = row['parent']
        return tuple(chain)

    def export(self, snapshot_id, new_directory):
        row = self._require(snapshot_id)
        self.verify(snapshot_id)
        original = Path(new_directory).absolute()
        safe_path(original)
        if original.is_relative_to(self.root):
            raise SaveError('Export to a separate new folder outside the vault storage.')
        # Check every existing ancestor before creating a new leaf directory.
        parent, _ = _ordinary(original.parent, directory=True)
        identity = save_library._directory_identity(parent.lstat())
        if original.exists() or original.is_symlink():
            raise FileExistsError('Choose a new directory; existing output is never replaced.')
        original.mkdir()
        leaf_identity = save_library._directory_identity(_ordinary(original, directory=True)[1])
        path = self._materialize(row, original)
        context_state = self._verify_context(row, original)
        adapter = save_library.adapter_for(row['game_id'])
        actual, _, _, _ = save_library._qualify(adapter, path, path.lstat(), MAX_FILE_BYTES, None)
        if actual.sha256 != row['blob']:
            raise SaveError('Save Vault output changed during native read-back; completed files were retained.')
        if context_state != self._verify_context(row, original):
            raise SaveError('Export context changed across native qualification; completed outputs were retained.')
        self.verify(snapshot_id)
        if save_library._directory_identity(_ordinary(parent, directory=True)[1]) != identity:
            raise SaveError('The export parent directory changed identity; completed outputs were retained.')
        if save_library._directory_identity(_ordinary(original, directory=True)[1]) != leaf_identity:
            raise SaveError('The export directory changed identity; completed outputs were retained.')
        return path

    restore = export

    def capture_editor_backup(self, game_id, editor, *, event='opened'):
        document = getattr(editor, 'document', None)
        if document is None:
            raise SaveError('Open a qualified copied save before capturing its original snapshot.')
        labels = {'opened': 'Opened save copy', 'saved': 'Saved copy',
                  'backup': 'Validated source snapshot'}
        if event not in labels:
            raise SaveError('Choose a supported automatic capture event.')
        adapter = save_library.adapter_for(game_id)
        current = adapter.read_save(document.source)
        if current != document:
            raise SaveError('The editor original changed; reopen before automatic vault capture.')
        rows = self.snapshots(collection='Automatic backups', game_id=game_id, branch='main')
        return self.import_copy(game_id, document.source, labels[event],
            collection='Automatic backups', branch='main', parent_id=rows[0]['id'] if rows else None)


def capture_editor_backup(game_id, editor, root=None, *, event='opened'):
    return Vault(root).capture_editor_backup(game_id, editor, event=event)
