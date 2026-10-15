"""Exact regional framing for independently qualified conversion-only exports."""
from dataclasses import dataclass, field, replace
from functools import lru_cache
import hashlib
from pathlib import Path

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.ps3_copy import PS3CopyStorage
from koei_editor.shared.ps3_export import MAX_SFO_SIZE, savedata_directory
from koei_editor.shared.save_safety import safe_path

OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT = 0xB18, 168, 41
HORSE_BASE, HORSE_STRIDE, HORSE_COUNT = 0x29E0, 60, 8
INTEGRITY_KIND = 'external'
_DEFAULT = object()


@dataclass(frozen=True)
class Format:
    id: str = ''


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    context_digest: str = ''

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


@lru_cache(maxsize=4)
def _qualify(raw):
    if any(int.from_bytes(raw[OFFICER_BASE + i * OFFICER_STRIDE + 136:
                              OFFICER_BASE + i * OFFICER_STRIDE + 140], 'big') != i
           for i in range(OFFICER_COUNT)):
        raise SaveError('DW6 PS3 officer identities do not match the native big-endian layout.')


@dataclass(frozen=True)
class RegionalExport:
    game_id: str
    size: int
    directory: str
    region: str
    format: Format = field(init=False)
    storage: object = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        object.__setattr__(self, 'format', Format(self.game_id))
        object.__setattr__(self, 'storage', PS3CopyStorage(
            self.game_id, self.size, self.validate_document, self.context_raw,
            self.decode, self.read_save, self.serialize))

    def _identity(self, game_id):
        if game_id is not _DEFAULT and game_id != self.game_id:
            raise SaveError(f'Choose the original {self.region} {self.directory} DW6 conversion endpoint.')

    def decode(self, raw, game_id=_DEFAULT, source=Path('APP.BIN')):
        self._identity(game_id)
        if type(raw) is not bytes or len(raw) != self.size:
            raise SaveError(f'Requires a {self.size:,}-byte PFD-decrypted {self.region} {self.directory} APP.BIN.')
        _qualify(raw)
        return Document(self.format, Path(source), raw, raw)

    def context_raw(self, path):
        companion = safe_path(Path(path).parent / 'PARAM.SFO')
        try:
            with companion.open('rb') as stream:
                metadata = stream.read(MAX_SFO_SIZE + 1)
        except FileNotFoundError as error:
            raise SaveError(f'Keep the original {self.directory} PARAM.SFO beside the copied APP.BIN.') from error
        if savedata_directory(metadata) != self.directory:
            raise SaveError(f'Requires original {self.region} {self.directory} metadata; other regions differ.')
        return metadata

    def read_save(self, path, game_id=_DEFAULT):
        self._identity(game_id)
        path = safe_path(path)
        if path.suffix.lower() != '.bin':
            raise SaveError('Open a separate PFD-decrypted PS3 .bin copy.')
        metadata = self.context_raw(path)
        with path.open('rb') as stream:
            document = self.decode(stream.read(self.size + 1), source=path)
        if self.context_raw(path) != metadata:
            raise SaveError('The original PS3 metadata changed during opening.')
        return replace(document, context_digest=hashlib.sha256(metadata).hexdigest())

    def validate_document(self, document):
        if (type(document) is not Document or document.format is not self.format
                or type(document.raw) is not bytes or type(document.payload) is not bytes
                or document.payload != document.raw or not isinstance(document.source, Path)
                or type(document.context_digest) is not str):
            raise SaveError(f'A frozen native {self.region} DW6 PS3 snapshot is required.')
        self.decode(document.raw)

    def serialize(self, document, changes):
        self.validate_document(document)
        if type(changes) is not dict or changes:
            raise SaveError('This regional endpoint supports the declared conversion routes; scalar edits are unavailable.')
        return document.raw
