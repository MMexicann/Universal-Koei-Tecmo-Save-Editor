"""Nights of Azure 2 Switch Libra deductions with complete active block hashes.

Three public native states independently label the exact Libra scalar in their
English save previews. The original checksum is unsigned-byte FNV-1a; this is
different from FAIRY TAIL's signed-char variant. No gameplay source is copied.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import re
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'nights_azure2_switch'
EXTENSION = ''
MAX_FILE_SIZE = 91828
INTEGRITY_KIND = 'checksum'
ROOT_START = 0x540
PREVIEW_START, PREVIEW_END = 0x100, 0x500
LIBRA_OFFSET = 0xAF
BLOCK_LAYOUT = (
    (b'#EVD', 0x20001, 6325), (b'#PRD', 0x60001, None),
    (b'#QUD', 0x10001, None), (b'#PLD', 1, 199),
    (b'#LID', 0x10001, None), (b'#FAD', 0x20001, None),
    (b'#IND', 1, None), (b'#FID', 0x30001, 27778),
    (b'#NFD', 0x30001, 1047), (b'#CLD', 1, 383), (b'#EXD', 1, 198),
)
PREVIEW_PATTERN = re.compile(
    rb'Playtime: [0-9]{3,}:[0-5][0-9]:[0-5][0-9]<CR>'
    rb'(?:Playthroughs: [0-9]+<CR>)?Level: [0-9]+<CR>Blood: [0-9]+<CR>'
    rb'Libra: (?P<libra>[0-9]+)<CR>Servan Points: [0-9]+<CR>Ability Points?: [0-9]+')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Nights of Azure 2: Bride of the New Moon (original Nintendo Switch)'
    size: int = MAX_FILE_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = ('Qualified original Switch English Chapter 1/7/Clear profiles; native #USR revision 1. '
                 'Reduce existing Libra with synchronized save preview. Max disabled. '
                 'Blood, levels, checkpoint progress and all other records are preserved; '
                 'edited game loading remains untested.')


FORMAT = Format()


@dataclass(frozen=True)
class Field:
    id: str
    offset: int
    maximum: int
    label: str = 'Libra (reduce only)'
    group: str = 'Shop currency'
    slot: int = 0
    minimum: int = 0
    size: int = 4
    maxable: bool = False
    kind: str = 'int'
    experimental_maximum: None = None
    encoding: str = 'unsigned little-endian 32-bit integer'
    evidence: str = 'Three native #PLD records and matching labelled save previews; NOA2_SWITCH_FORMAT.md'

    def value(self, payload):
        return struct.unpack_from('<I', payload, self.offset)[0]

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(f'Libra requires a whole number from 0 to the opened balance ({self.maximum:,}).')


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


@dataclass(frozen=True)
class Block:
    signature: bytes
    start: int
    body_start: int
    end: int
    revision: int


@dataclass(frozen=True)
class Structure:
    root: Block
    current: tuple
    checkpoint: tuple
    preview: bytes
    libra_span: tuple


def get_format(game_id=GAME_ID):
    if type(game_id) is not str or game_id != GAME_ID:
        raise SaveError('Select the original Nintendo Switch Nights of Azure 2 profile.')
    return FORMAT


def fnv1a(data):
    """Native 32-bit FNV-1a with unsigned bytes, including high-bit bytes."""
    value = 0x811C9DC5
    for byte in data:
        value = ((value ^ byte) * 0x1000193) & 0xFFFFFFFF
    return value


def _block(raw, start, boundary):
    if start < ROOT_START or start + 20 > boundary:
        raise SaveError('Truncated Nights of Azure 2 native block header.')
    signature, header_size, size, revision, checksum = struct.unpack_from('<4sIIII', raw, start)
    end = start + 20 + size
    if header_size != 20 or size > MAX_FILE_SIZE or end > boundary:
        raise SaveError('Invalid Nights of Azure 2 native block bounds.')
    if fnv1a(raw[start + 20:end]) != checksum:
        raise SaveError('Nights of Azure 2 native block integrity failed; damaged input is not repaired.')
    return Block(signature, start, start + 20, end, revision)


def _children(raw, parent, allow_checkpoint):
    blocks = []
    cursor = parent.body_start
    for signature, revision, fixed_size in BLOCK_LAYOUT:
        child = _block(raw, cursor, parent.end)
        if (child.signature != signature or child.revision != revision
                or (fixed_size is not None and child.end - child.body_start != fixed_size)):
            raise SaveError('Unqualified Nights of Azure 2 leaf order, revision or extent.')
        blocks.append(child)
        cursor = child.end
    checkpoint = ()
    if cursor < parent.end and allow_checkpoint:
        child = _block(raw, cursor, parent.end)
        if child.signature != b'#CHD' or child.revision != 1 or child.end != parent.end:
            raise SaveError('Unqualified Nights of Azure 2 chapter checkpoint framing.')
        nested, _ = _children(raw, child, False)
        checkpoint = (child, *nested)
        cursor = child.end
    if cursor != parent.end:
        raise SaveError('Unexpected Nights of Azure 2 native child or trailing block bytes.')
    return tuple(blocks), checkpoint


@lru_cache(maxsize=4)
def _structure(raw):
    if type(raw) is not bytes or len(raw) not in (77509, 91828):
        raise SaveError('Requires a qualified complete 77,509/91,828-byte original Switch Nights of Azure 2 export.')
    caption_end = raw.find(b'\0', 0, 0x80)
    if caption_end < 0:
        raise SaveError('Unterminated Nights of Azure 2 native chapter preview.')
    caption = raw[:caption_end]
    clear = caption == b'Clear Data'
    if not clear and caption not in (
            b'Chapter 1: Ruined City in the Eternal Night',
            b'Chapter 7: The Final Dream, the Final Wish'):
        raise SaveError('Requires an independently qualified original Switch chapter preview.')
    if not raw[0x500:0x540].split(b'\0', 1)[0].startswith(b'saveload_icon_'):
        raise SaveError('Missing native Nights of Azure 2 save-preview icon identity.')
    root = _block(raw, ROOT_START, len(raw))
    if root.signature != b'#USR' or root.revision != 1:
        raise SaveError('Not the qualified original Nights of Azure 2 Switch gameplay revision.')
    current, checkpoint = _children(raw, root, True)
    if clear:
        # The game retained the previous longer slot after a shorter clear-data
        # write. It is not part of the current #USR body, and is never rewritten.
        if len(raw) != 91828 or root.end != 41351 or checkpoint:
            raise SaveError('Unqualified Nights of Azure 2 clear-data retained-tail geometry.')
    elif root.end != len(raw) or not checkpoint:
        raise SaveError('The complete Nights of Azure 2 chapter slot must include its native checkpoint.')
    preview_end = raw.find(b'\0', PREVIEW_START, PREVIEW_END)
    if preview_end < 0:
        raise SaveError('Unterminated Nights of Azure 2 resource preview.')
    preview = raw[PREVIEW_START:preview_end]
    match = PREVIEW_PATTERN.fullmatch(preview)
    if match is None:
        raise SaveError('Requires the qualified English native resource preview.')
    libra = struct.unpack_from('<I', raw, current[3].body_start + LIBRA_OFFSET)[0]
    if int(match.group('libra')) != libra:
        raise SaveError('Native Libra balance and labelled save preview disagree.')
    return Structure(root, current, checkpoint, preview, match.span('libra'))


def decode(raw, game_id=GAME_ID, source=Path('SAVE_DATA_00')):
    get_format(game_id)
    if type(raw) is not bytes or len(raw) not in (77509, 91828):
        raise SaveError('Open immutable complete native Nights of Azure 2 Switch gameplay bytes.')
    _structure(raw)
    return Document(FORMAT, Path(source), raw, raw)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or not isinstance(document.source, Path) or type(document.raw) is not bytes
            or type(document.payload) is not bytes or document.raw != document.payload):
        raise SaveError('A frozen exact-game Nights of Azure 2 snapshot is required.')
    _structure(document.raw)


def _copy_path(path):
    path = safe_path(path)
    if path.suffix:
        raise SaveError('Use a copied extensionless SAVE_DATA_00-style Switch gameplay export.')
    return path


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _copy_path(path)
    with path.open('rb') as stream:
        raw = stream.read(MAX_FILE_SIZE + 1)
    return decode(raw, game_id, path)


def field_map(document):
    validate_document(document)
    offset = _structure(document.raw).current[3].body_start + LIBRA_OFFSET
    balance = struct.unpack_from('<I', document.raw, offset)[0]
    fields = {} if balance > 0x7FFFFFFF else {'libra': Field('libra', offset, balance)}
    return MappingProxyType(fields)


def fields_for(document):
    return tuple(field_map(document).values())


def stage(document, changes, key, value):
    fields = field_map(document)
    pending = normalize_pending_values(document, changes, fields)
    if type(key) is not str or key not in fields:
        raise SaveError('Select the qualified existing Libra balance.')
    pending[key] = value
    return normalize_pending_values(document, pending, fields)


def changed_payload(document, changes):
    pending = normalize_pending_values(document, changes, field_map(document))
    if not pending:
        return document.raw
    layout = _structure(document.raw)
    field = field_map(document)['libra']
    output = bytearray(document.raw)
    struct.pack_into('<I', output, field.offset, pending['libra'])
    a, b = layout.libra_span
    preview = layout.preview[:a] + str(pending['libra']).encode('ascii') + layout.preview[b:]
    if len(preview) >= PREVIEW_END - PREVIEW_START:
        raise SaveError('Edited Libra preview exceeds its native fixed field.')
    # Preserve all bytes after the newly terminated visible preview, including
    # native stale text/padding already present after its previous terminator.
    output[PREVIEW_START:PREVIEW_START + len(preview) + 1] = preview + b'\0'
    player = layout.current[3]
    struct.pack_into('<I', output, player.start + 16, fnv1a(output[player.body_start:player.end]))
    struct.pack_into('<I', output, layout.root.start + 16,
                     fnv1a(output[layout.root.body_start:layout.root.end]))
    result = bytes(output)
    reopened = decode(result, GAME_ID, document.source)
    if field.value(reopened.payload) != pending['libra']:
        raise SaveError('Nights of Azure 2 Libra did not pass native read-back.')
    return result


def serialize(document, changes):
    return changed_payload(document, changes)


def review(document, changes):
    pending = normalize_pending_values(document, changes, field_map(document))
    return [(field, field.value(document.payload), pending[field.id])
            for field in fields_for(document) if field.id in pending]


def limit_values(document, changes, keys):
    fields = field_map(document)
    normalize_pending_values(document, changes, fields)
    if isinstance(keys, (str, bytes)):
        raise SaveError('Select qualified Libra field IDs.')
    try:
        keys = tuple(keys)
    except TypeError as error:
        raise SaveError('Select qualified Libra field IDs.') from error
    if any(type(key) is not str or key not in fields for key in keys):
        raise SaveError('Select qualified Libra field IDs.')
    return {}


def maximums(document, changes, group=None):
    return normalize_pending_values(document, changes, field_map(document))


def _validate_source(document):
    source = _copy_path(document.source)
    try:
        with source.open('rb') as stream:
            raw = stream.read(MAX_FILE_SIZE + 1)
    except OSError as error:
        raise SaveError('The opened Nights of Azure 2 copy is unavailable; reopen it.') from error
    if raw != document.raw:
        raise SaveError('The opened Nights of Azure 2 copy changed; reopen it.')
    return source


def backup(document):
    validate_document(document)
    source = _validate_source(document)
    return snapshot_backup(document.raw, source, GAME_ID,
                           safe_path(source.parent / 'WarriorsEditorBackups'))


def save_as(document, changes, destination):
    validate_document(document)
    destination = _copy_path(destination)
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    _validate_source(document)
    raw = serialize(document, changes)
    backup(document)
    _validate_source(document)
    atomic_new(raw, destination)
    result = read_save(destination)
    _validate_source(document)
    if result.raw != raw:
        raise SaveError('The saved Nights of Azure 2 output changed during read-back.')
    return result


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    backup_path, destination = _copy_path(backup_path), _copy_path(destination)
    return restore_snapshot(backup_path, destination, GAME_ID, EXTENSION, MAX_FILE_SIZE,
                            validate_raw=lambda raw: decode(raw, GAME_ID))


def inspection_rows(document):
    validate_document(document)
    layout = _structure(document.raw)
    rows = [('Native preview', part.decode('ascii')) for part in layout.preview.split(b'<CR>')]
    rows.extend((('Scope', 'Libra reductions only; growth/resources other than Libra stay read-only.'),
                 ('Chapter checkpoint', 'Preserved unchanged'),
                 ('Inactive retained tail', f'{len(document.raw) - layout.root.end:,} bytes preserved'),
                 ('Validation', 'Active native unsigned FNV-1a hashes verified; edited game loading untested.')))
    return tuple(rows)


def record_label(slot, group):
    return group


def field_hint(document, key):
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Select the qualified existing Libra balance.')
    return ('Reduce existing shop currency. The saved preview updates with it. Max and experimental '
            'increases are disabled. Blood, levels, Ability/Servan Points, items, Lilies and '
            'the chapter checkpoint are preserved. Edited game loading remains untested.')
