"""Immutable raw Xbox 360 snapshots bound to their unchanged original CON."""
from dataclasses import dataclass, field, replace
import hashlib
import json
from pathlib import Path

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw6_xbox360.stfs_context import (
    MAX_CONTEXT_SIZE, SAVE_SIZE, OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT,
    HORSE_BASE, HORSE_STRIDE, HORSE_COUNT, qualify_payload, extract_payload,
)
from koei_editor.shared.copy_storage import atomic_new, snapshot_backup
from koei_editor.shared.save_safety import safe_path

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


@dataclass(frozen=True)
class RegionalExport:
    game_id: str
    region: str
    filename: str
    format: Format = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, 'format', Format(self.game_id))

    def _identity(self, game_id):
        if game_id is not _DEFAULT and game_id != self.game_id:
            raise SaveError(f'Choose the original {self.region} DW6 Xbox 360 conversion endpoint.')

    def decode(self, raw, game_id=_DEFAULT, source=Path('DW6.dat')):
        self._identity(game_id)
        qualify_payload(raw)
        return Document(self.format, Path(source), raw, raw)

    def context_raw(self, path):
        path = safe_path(Path(path).parent / 'ORIGINAL.CON')
        try:
            with path.open('rb') as stream:
                raw = stream.read(MAX_CONTEXT_SIZE + 1)
        except FileNotFoundError as error:
            raise SaveError('Keep an unchanged copy of the original DW6 Xbox 360 package named ORIGINAL.CON beside its extracted .dat file.') from error
        extract_payload(raw, self.game_id)
        return raw

    def read_save(self, path, game_id=_DEFAULT):
        self._identity(game_id)
        path = safe_path(path)
        if path.suffix.lower() != '.dat':
            raise SaveError(f'Open the separate extracted {self.filename} gameplay copy, with ORIGINAL.CON beside it.')
        context = self.context_raw(path)
        with path.open('rb') as stream:
            document = self.decode(stream.read(SAVE_SIZE + 1), source=path)
        if self.context_raw(path) != context:
            raise SaveError('The original Xbox 360 package changed while opening. Reopen both copied files.')
        return replace(document, context_digest=hashlib.sha256(context).hexdigest())

    def validate_document(self, document):
        if (type(document) is not Document or document.format is not self.format
                or type(document.raw) is not bytes or type(document.payload) is not bytes
                or document.raw != document.payload or not isinstance(document.source, Path)
                or type(document.context_digest) is not str):
            raise SaveError(f'A frozen {self.region} original DW6 Xbox 360 snapshot is required.')
        self.decode(document.raw)

    def serialize(self, document, changes):
        self.validate_document(document)
        if type(changes) is not dict or changes:
            raise SaveError('This Xbox 360 endpoint supports declared conversions; independent scalar edits are unavailable.')
        return document.raw

    def check_source(self, document):
        self.validate_document(document)
        context = self.context_raw(document.source)
        if not document.context_digest or hashlib.sha256(context).hexdigest() != document.context_digest:
            raise SaveError('The original Xbox 360 package changed. Reopen the copied export.')
        source = safe_path(document.source)
        with source.open('rb') as stream:
            if stream.read(SAVE_SIZE + 1) != document.raw:
                raise SaveError('The opened Xbox 360 gameplay copy changed. Reopen before backing up.')
        if self.context_raw(document.source) != context:
            raise SaveError('The original Xbox 360 package changed during source verification.')
        return source

    def backup(self, document):
        source = self.check_source(document)
        result = snapshot_backup(document.raw, source, self.game_id, source.parent / 'UniversalEditorBackups')
        metadata = {'game_id': self.game_id, 'kind': 'xbox360-export-context',
                    'context_sha256': document.context_digest, 'save_sha256': document.sha256}
        context_data = json.dumps(metadata).encode('utf-8')
        context_path = result.with_name(result.name + '.context.json')
        # Keep completed backups even if a later check fails. Another app may
        # replace any of these paths; failure must never delete its bytes.
        atomic_new(context_data, context_path)
        self.check_source(document)
        with safe_path(result).open('rb') as stream:
            if stream.read(SAVE_SIZE + 1) != document.raw:
                raise SaveError('The newly created Xbox 360 backup changed during verification.')
        with safe_path(result.with_suffix('.json')).open('rb') as stream:
            manifest_data = stream.read(4097)
        try:
            manifest = json.loads(manifest_data) if len(manifest_data) <= 4096 else None
        except (ValueError, UnicodeError) as error:
            raise SaveError('The newly created Xbox 360 backup manifest changed.') from error
        if (type(manifest) is not dict or manifest.get('game_id') != self.game_id
                or manifest.get('kind') != 'opaque-copy'
                or manifest.get('sha256') != document.sha256
                or manifest.get('size_bytes') != SAVE_SIZE):
            raise SaveError('The newly created Xbox 360 backup manifest no longer matches its snapshot.')
        with safe_path(context_path).open('rb') as stream:
            if stream.read(len(context_data) + 1) != context_data:
                raise SaveError('The newly created Xbox 360 backup context changed.')
        self.check_source(document)
        return result
