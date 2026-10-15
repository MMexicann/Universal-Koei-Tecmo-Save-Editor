"""Conversion-only original Japanese DW6 / Shin Sangoku Musou 5 export.

The native BLJM60041 copy qualifies the same typed roster/horse arrays as the
US release, with different file framing. It does not qualify a scalar editor,
story conversion, or a whole-file endian swap. PFD authentication is external.
"""
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
from pathlib import Path

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.ps3_copy import PS3CopyStorage
from koei_editor.shared.ps3_export import MAX_SFO_SIZE, savedata_directory
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'dw6_ps3_jp'
SAVE_SIZE = 212176
TITLE_DIRECTORY = 'BLJM60041-SAVEDATA'
OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT = 0xB18, 168, 41
HORSE_BASE, HORSE_STRIDE, HORSE_COUNT = 0x29E0, 60, 8
INTEGRITY_KIND = 'external'


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


@lru_cache(maxsize=4)
def _qualify(raw):
    if any(int.from_bytes(raw[OFFICER_BASE + i * OFFICER_STRIDE + 136:
                              OFFICER_BASE + i * OFFICER_STRIDE + 140], 'big') != i
           for i in range(OFFICER_COUNT)):
        raise SaveError('Japanese DW6 PS3 officer identities do not match the native big-endian layout.')


def decode(raw, game_id=GAME_ID, source=Path('APP.BIN')):
    if game_id != GAME_ID:
        raise SaveError('Choose the original Japanese BLJM60041 PS3 DW6 conversion endpoint.')
    if type(raw) is not bytes or len(raw) != SAVE_SIZE:
        raise SaveError('Requires a 212,176-byte PFD-decrypted Japanese BLJM60041 APP.BIN.')
    _qualify(raw)
    return Document(FORMAT, Path(source), raw, raw)


def context_raw(path):
    companion = safe_path(Path(path).parent / 'PARAM.SFO')
    try:
        with companion.open('rb') as stream:
            metadata = stream.read(MAX_SFO_SIZE + 1)
    except FileNotFoundError as error:
        raise SaveError('Keep the original BLJM60041-SAVEDATA PARAM.SFO beside the copied APP.BIN.') from error
    if savedata_directory(metadata) != TITLE_DIRECTORY:
        raise SaveError('Requires original Japanese BLJM60041-SAVEDATA metadata; other regions differ.')
    return metadata


def read_save(path, game_id=GAME_ID):
    path = safe_path(path)
    if path.suffix.lower() != '.bin':
        raise SaveError('Open a separate PFD-decrypted PS3 .bin copy.')
    metadata = context_raw(path)
    with path.open('rb') as stream:
        document = decode(stream.read(SAVE_SIZE + 1), game_id, path)
    if context_raw(path) != metadata:
        raise SaveError('The original Japanese PS3 metadata changed during opening.')
    return replace(document, context_digest=hashlib.sha256(metadata).hexdigest())


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.payload != document.raw or not isinstance(document.source, Path)
            or type(document.context_digest) is not str):
        raise SaveError('A frozen native Japanese DW6 PS3 snapshot is required.')
    decode(document.raw)


def serialize(document, changes):
    validate_document(document)
    if type(changes) is not dict or changes:
        raise SaveError('The Japanese endpoint supports roster-and-horse conversion only; scalar edits are unavailable.')
    return document.raw


_storage = PS3CopyStorage(GAME_ID, SAVE_SIZE, validate_document, context_raw, decode, read_save, serialize)
backup = _storage.backup
