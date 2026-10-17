"""Bounded local library of immutable named reusable preset documents.

Each metadata file is addressed by its content digest and created atomically.
Saving/importing never replaces an existing document or stores a game save.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import compatible_presets
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.preferences import preference_path
from koei_editor.shared.save_safety import safe_path


MAX_PRESETS = 256
MAX_ENTRIES = 1024
MAX_SCAN_BYTES = 32 * 1024 * 1024
_NAME = re.compile(r'[a-f0-9]{64}\.compatible\.edits\.json\Z')


@dataclass(frozen=True)
class LibraryEntry:
    id: str
    preset: compatible_presets.CompatiblePreset
    path: Path


@dataclass(frozen=True)
class LibrarySnapshot:
    entries: tuple[LibraryEntry, ...]
    issues: tuple[str, ...] = ()
    complete: bool = True
    scanned_bytes: int = 0


@contextmanager
def _admission_lock(directory):
    """Serialize cooperating processes without deleting or writing lock bytes."""
    path = directory / '.preset-admission.lock'
    if path.is_symlink():
        raise SaveError('Linked preset-library locks are excluded.')
    flags = (os.O_RDWR | getattr(os, 'O_BINARY', 0)
             | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    try:
        descriptor = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        # Opening an existing lock without O_CREAT cannot create the target of
        # a raced dangling link on platforms without O_NOFOLLOW.
        descriptor = os.open(path, flags)
    try:
        opened, named = os.fstat(descriptor), path.lstat()
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
                or getattr(named, 'st_file_attributes', 0)
                & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
            raise SaveError('Choose an ordinary local preset-library lock file.')
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise SaveError('Another preset-library save is running. Retry after it finishes.') from error
        yield
    finally:
        # Closing releases the operating-system lock, including after a crash;
        # keeping the empty file avoids unlink/replacement races.
        os.close(descriptor)


class PresetLibrary:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else preference_path().parent / 'editing-presets'

    def _directory(self, create=False):
        original = self.directory.absolute()
        # Metadata is local to the user's configuration directory; do not follow
        # a linked final library directory to an unrelated destination.
        if original.is_symlink():
            raise SaveError('The preset library cannot be a linked directory.')
        path = safe_path(original)
        if create:
            path.mkdir(parents=True, exist_ok=True)
        if path.exists() and not path.is_dir():
            raise SaveError('The preset library location is not a directory.')
        return path

    def scan(self):
        path = self._directory()
        if not path.exists():
            return LibrarySnapshot(())
        entries, issues, complete, scanned_bytes = [], [], True, 0
        # Path.iterdir() eagerly lists the directory on supported Python versions.
        # Stream entries so the limit also bounds enumeration and its memory.
        with os.scandir(path) as children:
            for index, child_entry in enumerate(children):
                if index >= MAX_ENTRIES:
                    issues.append('The directory-entry scan limit was reached; remaining metadata was excluded.')
                    complete = False
                    break
                child = Path(child_entry.path)
                if not _NAME.fullmatch(child.name):
                    continue
                if len(entries) >= MAX_PRESETS:
                    issues.append(f'The {MAX_PRESETS}-preset scan limit was reached; remaining metadata was excluded.')
                    complete = False
                    break
                try:
                    if child.is_symlink():
                        raise SaveError('Linked preset metadata is excluded.')
                    size = child.lstat().st_size
                    if not 0 < size <= compatible_presets.MAX_BYTES:
                        raise SaveError('Preset metadata is outside its file-size bound.')
                    # Reserve the entire bounded read, including its overflow
                    # sentinel, even if parsing fails or the file changes.
                    if scanned_bytes + size + 1 > MAX_SCAN_BYTES:
                        issues.append('The total preset-byte scan limit was reached; remaining metadata was excluded.')
                        complete = False
                        break
                    scanned_bytes += size + 1
                    raw = compatible_presets.read_bytes(child, maximum=size)
                    identity = hashlib.sha256(raw).hexdigest()
                    if child.name != identity + compatible_presets.SUFFIX:
                        raise SaveError('Preset content does not match its local library identity.')
                    preset = compatible_presets.loads(raw)
                    entries.append(LibraryEntry(identity, preset, child))
                except (OSError, ValueError, SaveError):
                    issues.append(child.name + ': invalid or changed preset metadata; excluded')
        return LibrarySnapshot(tuple(sorted(entries, key=lambda entry: (entry.preset.name.casefold(), entry.id))),
                               tuple(issues), complete, scanned_bytes)

    def save(self, preset):
        raw = compatible_presets.dumps(preset)
        identity = hashlib.sha256(raw).hexdigest()
        directory = self._directory(create=True)
        path = directory / (identity + compatible_presets.SUFFIX)
        with _admission_lock(directory):
            if path.is_symlink():
                raise SaveError('A local preset identity was replaced. Existing metadata was retained.')
            if path.exists():
                if compatible_presets.read_bytes(path) != raw:
                    raise SaveError('A local preset identity was replaced. Existing metadata was retained.')
                return LibraryEntry(identity, preset, path)
            snapshot = self.scan()
            if not snapshot.complete:
                raise SaveError('The preset library scan reached a safety limit. Review its excluded metadata before adding presets.')
            if len(snapshot.entries) >= MAX_PRESETS:
                raise SaveError(f'The local library supports at most {MAX_PRESETS} presets.')
            if snapshot.scanned_bytes + len(raw) + 1 > MAX_SCAN_BYTES:
                raise SaveError('The preset library has reached its total metadata-byte limit.')
            result = atomic_new(raw, path)
            if compatible_presets.read_bytes(result) != raw:
                raise SaveError('Preset verification failed after saving. Metadata was retained; do not use it.')
        return LibraryEntry(identity, preset, result)

    def import_path(self, path):
        return self.save(compatible_presets.load(path))

    def validate_entry(self, entry):
        if (type(entry) is not LibraryEntry or type(entry.id) is not str
                or not re.fullmatch(r'[a-f0-9]{64}', entry.id)):
            raise SaveError('Select a local named editing preset.')
        path = self._directory() / (entry.id + compatible_presets.SUFFIX)
        if entry.path != path or path.is_symlink():
            raise SaveError('The selected local preset identity changed.')
        actual = compatible_presets.load(path)
        if actual != entry.preset or hashlib.sha256(compatible_presets.read_bytes(path)).hexdigest() != entry.id:
            raise SaveError('The selected local preset metadata changed. Refresh the library.')
        return actual

    def export(self, entry, destination):
        return compatible_presets.export(self.validate_entry(entry), destination)
