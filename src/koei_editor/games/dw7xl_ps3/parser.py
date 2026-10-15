"""Frozen conversion-only original DW7 XL US/European PS3 export snapshots.

The original BLUS30873/BLES01496 native containers corroborate a 470,303-byte
decrypted APP.BIN with big-endian revision 0x11080200. Their encrypted files
include one extra PFD padding byte, which is not part of this plaintext format.
The upstream anonymous 0x6EBBC-byte base-DW7 example does not qualify DW7 XL.
PFD authentication and console signing remain external; no scalar edits exist.
"""
from dataclasses import dataclass, replace
import hashlib
from pathlib import Path

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.ps3_copy import PS3CopyStorage
from koei_editor.shared.ps3_export import MAX_SFO_SIZE, savedata_directory
from koei_editor.shared.save_safety import safe_path


GAME_ID = 'dw7xl_ps3'
SAVE_SIZE = 0x72D1F
REVISION = bytes.fromhex('11080200')
TITLE_IDS = ('BLUS30873', 'BLES01496')
TITLE_DIRECTORIES = frozenset(title + '-SAVEDATA' for title in TITLE_IDS)
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


def get_format(game_id=GAME_ID):
    if type(game_id) is not str or game_id != GAME_ID:
        raise SaveError('Choose the original US/European DW7 Xtreme Legends PS3 conversion endpoint.')
    return FORMAT


def decode(raw, game_id=GAME_ID, source=Path('APP.BIN')):
    get_format(game_id)
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:4] != REVISION:
        raise SaveError('Requires the 470,303-byte PFD-decrypted DW7 Xtreme Legends '
                        'PS3 APP.BIN revision 0x11080200. Base DW7 and PC saves differ.')
    return Document(FORMAT, Path(source), raw, raw)


def context_raw(path):
    companion = safe_path(Path(path).parent / 'PARAM.SFO')
    try:
        with companion.open('rb') as stream:
            metadata = stream.read(MAX_SFO_SIZE + 1)
    except FileNotFoundError as error:
        raise SaveError('Keep the original BLUS30873-SAVEDATA or BLES01496-SAVEDATA '
                        'PARAM.SFO beside the copied DW7 XL APP.BIN.') from error
    if savedata_directory(metadata) not in TITLE_DIRECTORIES:
        raise SaveError('Requires original US BLUS30873 or European BLES01496 '
                        'DW7 Xtreme Legends metadata; base DW7 and Empires differ.')
    return metadata


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.casefold() != '.bin':
        raise SaveError('Open a separate PFD-decrypted DW7 XL PS3 .bin copy.')
    metadata = context_raw(path)
    with path.open('rb') as stream:
        document = decode(stream.read(SAVE_SIZE + 1), source=path)
    if context_raw(path) != metadata:
        raise SaveError('Original DW7 XL PS3 metadata changed while opening. Reopen the copied export.')
    return replace(document, context_digest=hashlib.sha256(metadata).hexdigest())


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload or not isinstance(document.source, Path)
            or type(document.context_digest) is not str):
        raise SaveError('A frozen original DW7 Xtreme Legends PS3 snapshot is required.')
    decode(document.raw)


def serialize(document, changes):
    validate_document(document)
    if type(changes) is not dict or changes:
        raise SaveError('This DW7 XL PS3 endpoint supplies conversion snapshots only; '
                        'independent scalar edits are unavailable.')
    return document.raw


_storage = PS3CopyStorage(GAME_ID, SAVE_SIZE, validate_document, context_raw,
                          decode, read_save, serialize)
backup = _storage.backup
