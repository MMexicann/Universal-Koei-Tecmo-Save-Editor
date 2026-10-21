"""Observed original-PK header only; no integrity or gameplay-field claim.

Eight public complete references corroborate the exact admitted lengths. The
changing header word at +24 remains unclassified. No native write is offered.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.save_safety import safe_path

MAGIC = b'DAIKOUKAI4PKW9 1'
SIZES = frozenset((39682, 39498, 39710, 39798, 39870, 39486, 39842))
MAX_SIZE = max(SIZES)


@dataclass(frozen=True)
class Document:
    source: Path
    raw: bytes


def decode(raw, source=Path('SaveDat0.DK4')):
    if (type(raw) is not bytes or len(raw) not in SIZES or raw[:16] != MAGIC
            or struct.unpack_from('<I', raw, 20)[0] != len(raw)
            or raw[16:20] != bytes(4) or raw[28:32] != bytes(4)):
        raise SaveError('Requires an observed original Windows PK DAIKOUKAI4PKW9 1 profile; HD and foreign sizes are excluded.')
    return Document(Path(source), raw)


def read_save(path):
    path = safe_path(path)
    if path.suffix.lower() != '.dk4':
        raise SaveError('Open a separate original-PK .DK4 save copy.')
    with path.open('rb') as stream:
        return decode(stream.read(MAX_SIZE + 1), path)


def inspect(document):
    if (type(document) is not Document or not isinstance(document.source, Path)
            or decode(document.raw, document.source) != document):
        raise SaveError('Inspect a frozen original-PK framing snapshot.')
    return {'profile': 'dk4pk_pc', 'title': 'Uncharted Waters IV with Power-Up Kit',
            'platform': 'Windows PC (original PK)', 'registered_editor': False,
            'read_only': True, 'game_load_verified': False,
            'source_sha256': hashlib.sha256(document.raw).hexdigest(),
            'size_bytes': len(document.raw), 'declared_length_matches': True,
            'native_checksum_established': False,
            'uninterpreted_header_word_offset': 24,
            'record_inspection_available': False,
            'needed': 'Exact native loader/integrity meaning of header +24, complete safe resource records and controlled action/load proof. Header acceptance cannot detect every damaged body; no gameplay fields or writer are qualified.'}
