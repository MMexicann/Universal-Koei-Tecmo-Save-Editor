"""Qualified one-step PC PW4 revision-15 resource milestone.

Native serializer, profile and Beli reward mappings are described in
PIRATE_ABYSS_RESEARCH.md. Only the demonstrated ordered native layout is accepted.
Story, character growth, coin ownership/history and equipment are preserved.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import re
import struct
from types import MappingProxyType

from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.koei_codec import word_sum
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.verified_editor import Field
import koei_editor.games.pw4.pw4_candidate_codec as envelope


GAME_ID = 'pw4'
SAVE_SIZE = 0x27161C
REVISION = 15
STREAM_OFFSET = 0x618
# Ordered sizes corroborated by the native slot and executable body-size getters.
SUBTREE_SIZES = (0x290, 0x6294, 0x106DC, 0x420, 0x180, 0x1DBD0,
                 0x3880, 0x19480, 0x66880, 0x19480) + (0xA90,) * 132 + (0x100094, 0x2080)
PROFILE_HEADER = 0x6B3C
PROFILE_BODY = PROFILE_HEADER + 0x80
COIN_HEADER = 0xB8908
COIN_BODY = COIN_HEADER + 0x80
COIN_STRIDE = 0x30
COIN_ID_COUNT = 400
BATTLE_BODY_SIZE = 0x1D730
FIELD_MAP = MappingProxyType({field.id: field for field in (
    Field('beli', 'Beli', PROFILE_BODY + 4, 4, 999_999_999),
)})


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'One Piece: Pirate Warriors 4'
    size: int = SAVE_SIZE
    fields: tuple = tuple(FIELD_MAP.values())
    sample_verified: bool = True
    note: str = ('Native PC revision 15, one-step region family (WW/JP/EA). '
                 'Spendable Beli and quantities of existing obtained coin records. '
                 'Lifetime earnings, coin history/ownership, growth and story are preserved. '
                 'Native unchanged roundtrip checked; edited game loading is untested.')


FORMAT = Format()


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    seed: int

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Choose the explicit Pirate Warriors 4 PC adapter.')
    return FORMAT


def _block(payload, offset, total, own_body=None):
    checksum, size, revision = struct.unpack_from('<III', payload, offset)
    if size != total or revision != REVISION:
        raise SaveError('PW4 native serialized layout/revision is unsupported.')
    body = payload[offset + 0x80:offset + (0x80 + own_body if own_body is not None else total)]
    if checksum != (sum(body) & 0x7FFFFFFF):
        raise SaveError('PW4 native object checksum failed; corruption is not repaired.')


def _validate_payload(payload):
    # The textual slot summary is generated from the mirrored numeric summary.
    # It is a structure check, not a hardcoded player's completion values.
    prefix = payload[:96].split(b'\0', 1)[0]
    match = re.fullmatch(rb'([0-9]{3,}) ([0-9]{2,}) ([0-9]{3,}) ([0-9]{3,}) ([0-9]{3,})', prefix)
    if not match:
        raise SaveError('PW4 native PC slot summary is missing.')
    metadata = struct.unpack_from('<6I', payload, 0x600)
    if metadata[0] != 1 or metadata[1:] != tuple(int(part) for part in match.groups()):
        raise SaveError('PW4 slot summary and native metadata disagree.')
    offset = STREAM_OFFSET
    for index, size in enumerate(SUBTREE_SIZES):
        if index == 5:
            _block(payload, offset, size, BATTLE_BODY_SIZE)
            _block(payload, offset + 0x80 + BATTLE_BODY_SIZE, 0x420)
        else:
            _block(payload, offset, size)
        offset += size
    if struct.unpack_from('<I', payload, STREAM_OFFSET + 0x80)[0] != REVISION:
        raise SaveError('PW4 serialized header revision is unsupported.')


@lru_cache(maxsize=8)
def _decoded(raw):
    try:
        candidate = envelope.decode_candidate(raw, region='WW')
    except ValueError as error:
        raise SaveError(str(error)) from error
    _validate_payload(candidate.payload)
    return candidate.payload


def decode(raw, game_id=GAME_ID, source=Path('copy.dat')):
    get_format(game_id)
    if type(raw) not in (bytes, bytearray) or len(raw) != SAVE_SIZE:
        raise SaveError('PW4 accepts the mapped native PC slot size only; system saves are excluded.')
    raw = bytes(raw)
    return Document(FORMAT, Path(source), raw, _decoded(raw), struct.unpack_from('<H', raw, 2)[0])


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.dat':
        raise SaveError('Open a separate native PW4 .dat slot copy.')
    with path.open('rb') as stream:
        return decode(stream.read(SAVE_SIZE + 1), game_id, path)


def validate_document(document):
    if type(document) is not Document or document.format != FORMAT:
        raise SaveError('Invalid PW4 PC document identity.')
    if (type(document.raw) is not bytes or type(document.payload) is not bytes
            or type(document.seed) is not int):
        raise SaveError('The opened PW4 snapshot must be immutable.')
    original = decode(document.raw, GAME_ID, document.source)
    if original.payload != document.payload or original.seed != document.seed:
        raise SaveError('The opened PW4 snapshot was modified outside staging.')


def _coin_records(payload):
    records = []
    for identity in range(COIN_ID_COUNT):
        offset = COIN_BODY + identity * COIN_STRIDE
        earned, spent, quantity = struct.unpack_from('<III', payload, offset)
        flags = payload[offset + 12]
        # Reward code sets obtained bit 0 and increments the earned counter.
        # Require both; do not turn empty, stale or unknown rows into ownership.
        if earned and flags & 1:
            records.append({'id': identity, 'earned': earned, 'spent': spent,
                            'quantity': quantity, 'flags': flags})
    return tuple(records)


@lru_cache(maxsize=8)
def _field_index(payload):
    fields = dict(FIELD_MAP)
    for row in _coin_records(payload):
        identity = row['id']
        field = Field(f'coin_{identity}_quantity', 'Current quantity',
                      COIN_BODY + identity * COIN_STRIDE + 8, 4, 999,
                      'Owned coins', identity + 1)
        fields[field.id] = field
    return MappingProxyType(fields)


def field_map(document):
    validate_document(document)
    return _field_index(document.payload)


def coins(document):
    """Obtained records only; IDs are native, not guessed character/rarity names."""
    validate_document(document)
    return _coin_records(document.payload)


def record_label(slot, group):
    return f'Coin ID {slot - 1:03}' if group == 'Owned coins' and slot else group


def fields_for(document):
    return tuple(field_map(document).values())


def stage(document, changes, key, value):
    changes = normalize_pending_values(document, changes, field_map(document))
    fields = field_map(document)
    if key not in fields:
        raise SaveError('Only proven PW4 resource fields can be edited.')
    field = fields[key]
    result = dict(changes)
    if type(value) is int and value == field.value(document.payload):
        result.pop(key, None)
    else:
        field.validate(value)
        result[key] = value
    return result


def limit_values(document, changes, keys):
    changes = normalize_pending_values(document, changes, field_map(document))
    fields = field_map(document)
    result = {}
    for key in keys:
        if key not in fields:
            raise SaveError('Unknown PW4 resource field.')
        field = fields[key]
        if field.maxable and changes.get(key, field.value(document.payload)) <= field.maximum:
            result[key] = field.maximum
    return result


def maximums(document, changes, group=None):
    changes = normalize_pending_values(document, changes, field_map(document))
    keys = [field.id for field in fields_for(document) if group is None or field.group == group]
    result = dict(changes)
    for key, value in limit_values(document, changes, keys).items():
        result = stage(document, result, key, value)
    return result


def changed_payload(document, changes):
    fields = field_map(document)
    result = bytearray(document.payload)
    for key, value in changes.items():
        if key not in fields:
            raise SaveError('Unknown PW4 resource field.')
        field = fields[key]
        if type(value) is not int:
            field.validate(value)
        if value != field.value(document.payload):
            field.validate(value)
            result[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    for header, size in ((PROFILE_HEADER, SUBTREE_SIZES[2]), (COIN_HEADER, SUBTREE_SIZES[9])):
        body, end = header + 0x80, header + size
        if result[body:end] != document.payload[body:end]:
            # Recompute only a modified object's own-body checksum.
            struct.pack_into('<I', result, header, sum(result[body:end]) & 0x7FFFFFFF)
    return bytes(result)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    raw = struct.pack('<HH', word_sum(payload), document.seed) + envelope._cipher(payload, document.seed, 1)
    if decode(raw, GAME_ID, document.source).payload != payload:
        raise SaveError('Edited PW4 copy verification failed.')
    return raw


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def backup(document):
    validate_document(document)
    return snapshot_backup(document.raw, document.source, GAME_ID,
                           document.source.parent / 'WarriorsEditorBackups')


def save_as(document, changes, destination):
    destination = safe_path(destination)
    if destination.suffix.lower() != '.dat':
        raise SaveError('Choose a new .dat destination.')
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    validate_document(document)
    with safe_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened PW4 copy changed on disk; reopen it before saving.')
    encoded = serialize(document, changes)
    backup(document)
    atomic_new(encoded, destination)
    return decode(encoded, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    read_save(backup_path, game_id)
    return restore_snapshot(backup_path, destination, GAME_ID, '.dat', SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, game_id))


def field_hint(document, field):
    key = field.id if isinstance(field, Field) else field
    if key not in field_map(document):
        raise SaveError('Unknown PW4 resource field.')
    if field_map(document)[key].group == 'Owned coins':
        return ('Current quantity of an already obtained coin, 0–999. Earned/spent counters, '
                'ownership and notification flags stay unchanged. Max preserves higher quantities. '
                'Coin names and rarities are not qualified; native IDs identify these records.')
    return 'Spendable Beli only. Max preserves higher existing balances; lifetime earnings, story and growth maps stay unchanged.'


def inspection_rows(document):
    validate_document(document)
    return ({'group': 'Format', 'label': 'Native revision', 'value': REVISION},
            {'group': 'Format', 'label': 'Validated native subtrees', 'value': len(SUBTREE_SIZES)},
            {'group': 'Records', 'label': 'Lifetime Beli earned (read only)',
             'value': struct.unpack_from('<I', document.payload, PROFILE_BODY + 0x790)[0]},
            {'group': 'Records', 'label': 'Qualified obtained coin records', 'value': len(coins(document))},
            {'group': 'Progression', 'label': 'Growth / story / equipment',
             'value': 'Preserved; no completion or unlock action is implemented.'})

# Integrity validated by this backend, separately from sample qualification.
INTEGRITY_KIND = 'checksum'
