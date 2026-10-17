"""Bounded local library of immutable named reusable preset documents.

Each metadata file is addressed by its content digest and created atomically.
Saving/importing never replaces an existing document or stores a game save.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import compatible_presets
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.preferences import preference_path
from koei_editor.shared.save_safety import safe_path


MAX_PRESETS = 256
MAX_ENTRIES = 1024
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
        entries, issues = [], []
        for index, child in enumerate(path.iterdir()):
            if index >= MAX_ENTRIES:
                raise SaveError('The preset library has too many directory entries to scan safely.')
            if not _NAME.fullmatch(child.name):
                continue
            if len(entries) >= MAX_PRESETS:
                raise SaveError(f'The local library supports at most {MAX_PRESETS} presets.')
            try:
                if child.is_symlink():
                    raise SaveError('Linked preset metadata is excluded.')
                raw = compatible_presets.read_bytes(child)
                identity = hashlib.sha256(raw).hexdigest()
                if child.name != identity + compatible_presets.SUFFIX:
                    raise SaveError('Preset content does not match its local library identity.')
                preset = compatible_presets.loads(raw)
                entries.append(LibraryEntry(identity, preset, child))
            except (OSError, ValueError, SaveError):
                issues.append(child.name + ': invalid or changed preset metadata; excluded')
        return LibrarySnapshot(tuple(sorted(entries, key=lambda entry: (entry.preset.name.casefold(), entry.id))),
                               tuple(issues))

    def save(self, preset):
        raw = compatible_presets.dumps(preset)
        identity = hashlib.sha256(raw).hexdigest()
        path = self._directory(create=True) / (identity + compatible_presets.SUFFIX)
        if path.is_symlink():
            raise SaveError('A local preset identity was replaced. Existing metadata was retained.')
        if path.exists():
            if compatible_presets.read_bytes(path) != raw:
                raise SaveError('A local preset identity was replaced. Existing metadata was retained.')
            return LibraryEntry(identity, preset, path)
        if len(self.scan().entries) >= MAX_PRESETS:
            raise SaveError(f'The local library supports at most {MAX_PRESETS} presets.')
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
