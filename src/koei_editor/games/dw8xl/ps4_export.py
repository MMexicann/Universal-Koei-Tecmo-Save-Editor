"""Conversion-only DW8 XL PS4 common revision with a zero extension.

No scalar editor or native gameplay checksum is claimed by this reader. Only
the published 0xD0F45-byte common-core profile is accepted; opaque nonzero PS4
extension data is refused instead of discarded.
"""
from dataclasses import dataclass, replace
import hashlib
from pathlib import Path

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw8xl_vita.parser import PAYLOAD_SIZE, SIGNATURE
from koei_editor.shared.copy_storage import snapshot_backup, atomic_new
from koei_editor.shared.ps4_export import MAX_SFO_SIZE, title_id
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'dw8xl_ps4'
SAVE_SIZE = 0xD0F45
TITLE_ID = 'CUSA00397'
INTEGRITY_KIND = 'none'


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID


FORMAT = Format()


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


def decode(raw, game_id=GAME_ID, source=Path('APP.BIN')):
    if game_id != GAME_ID:
        raise SaveError('Choose the DW8 XL CUSA00397 PS4 conversion endpoint.')
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:5] != SIGNATURE:
        raise SaveError('Requires the 855,877-byte decrypted PS4 DW8 XL revision 0x131002F0.')
    if any(raw[PAYLOAD_SIZE:]):
        raise SaveError('Nonzero PS4 extension data cannot be discarded or converted by this profile.')
    return Document(FORMAT, Path(source), raw, raw[:PAYLOAD_SIZE])


def context_raw(path):
    path = safe_path(Path(path).parent / 'sce_sys' / 'param.sfo')
    try:
        with path.open('rb') as stream:
            raw = stream.read(MAX_SFO_SIZE + 1)
    except OSError as error:
        raise SaveError('Keep original DW8 XL sce_sys/param.sfo beside the copied PS4 APP.BIN.') from error
    title_id(raw, TITLE_ID)
    return raw


def read_save(path, game_id=GAME_ID):
    path = safe_path(path)
    if path.suffix.lower() != '.bin':
        raise SaveError('Open a separate decrypted PS4 .bin copy.')
    metadata = context_raw(path)
    with path.open('rb') as stream:
        document = decode(stream.read(SAVE_SIZE + 1), game_id, path)
    if context_raw(path) != metadata:
        raise SaveError('PS4 metadata changed during opening.')
    return replace(document, context_digest=hashlib.sha256(metadata).hexdigest())


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or type(document.context_digest) is not str or not isinstance(document.source, Path)
            or decode(document.raw).payload != document.payload):
        raise SaveError('A frozen native DW8 XL PS4 snapshot is required.')


def serialize(document, changes):
    validate_document(document)
    if type(changes) is not dict or changes:
        raise SaveError('The PS4 endpoint supplies conversion only; scalar edits are unavailable.')
    return document.raw


def backup(document):
    validate_document(document)
    opened = read_save(document.source)
    if opened.raw != document.raw or opened.context_digest != document.context_digest:
        raise SaveError('The PS4 source or original metadata changed. Reopen before backing up.')
    metadata = context_raw(document.source)
    path = snapshot_backup(document.raw, document.source, GAME_ID,
                           document.source.parent / 'UniversalEditorBackups')
    companion = path.with_name(path.name + '.param.sfo')
    try:
        atomic_new(metadata, companion)
        reopened = read_save(document.source)
        if reopened.raw != document.raw or reopened.context_digest != document.context_digest:
            raise SaveError('The PS4 copy changed during backup.')
    except Exception:
        path.unlink(missing_ok=True)
        path.with_suffix('.json').unlink(missing_ok=True)
        companion.unlink(missing_ok=True)
        raise
    return path
