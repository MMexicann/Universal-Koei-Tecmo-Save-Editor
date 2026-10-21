"""Plaintext Vita DW8 XL revision 0x131002F0 with its native byte sum.

The public platform converter and complete Vita reference establish the shared
gameplay layout. This profile edits exported MainData00.dat bytes in place; it
does not convert platforms or change console ownership metadata.
"""
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw3.game_content import DW8_ATTRIBUTE_NAMES
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.verified_editor import DW8_FIELDS, DW8_RANKED_ATTRIBUTES, Field
from koei_editor.shared.experimental_limits import experimental_enabled

GAME_ID = 'dw8xl_vita'
SAVE_SIZE, PAYLOAD_SIZE = 0xB7F45, 0xB7F44
SIGNATURE = bytes.fromhex('f002101309')
INTEGRITY_KIND = 'checksum'
WEAPON_BASE, WEAPON_STRIDE, WEAPON_COUNT = 0xE715, 0x18, 1830
BASE_FIELDS = tuple(replace(field, maxable=False) for field in DW8_FIELDS)


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Dynasty Warriors 8 Xtreme Legends Complete Edition (Vita native export)'
    size: int = SAVE_SIZE
    fields: tuple = BASE_FIELDS
    published_format: bool = True
    sample_verified: bool = False
    game_load_verified: bool = False
    note: str = ('Exported plaintext MainData00.dat, revision 0x131002F0. Gold, gems, '
                 'two materials, stored officer stats, four weapon-action aptitudes '
                 'and existing weapon attribute ranks. Max is disabled. Reimport '
                 'with your Vita save-management tool; console authentication stays external.')


FORMAT = Format()


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select the native PlayStation Vita DW8 XL profile.')
    return FORMAT


@lru_cache(maxsize=4)
def _qualify(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:5] != SIGNATURE:
        raise SaveError('Requires the 753,477-byte plaintext Vita MainData00.dat revision 0x131002F0.')
    payload = raw[:-1]
    if sum(payload) & 255 != raw[-1]:
        raise SaveError('Vita DW8 XL native gameplay checksum failed. Re-export an intact copy.')
    return payload


def decode(raw, game_id=GAME_ID, source=Path('MainData00.dat')):
    get_format(game_id)
    if type(raw) is not bytes:
        raise SaveError('An immutable exported Vita byte snapshot is required.')
    return Document(FORMAT, Path(source), raw, _qualify(raw))


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.dat':
        raise SaveError('Open a separate exported Vita .dat copy.')
    with path.open('rb') as stream:
        return decode(stream.read(SAVE_SIZE + 1), game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or not isinstance(document.source, Path)
            or _qualify(document.raw) != document.payload):
        raise SaveError('An immutable native Vita DW8 XL snapshot is required.')


@lru_cache(maxsize=4)
def common_fields(payload, experimental=False):
    """Project mapped common-core fields after an endpoint qualifies its bytes."""
    result = list(BASE_FIELDS)
    for index in range(WEAPON_COUNT):
        base = WEAPON_BASE + index * WEAPON_STRIDE
        identity = int.from_bytes(payload[base + 2:base + 4], 'little')
        if payload[base] not in (1, 3) or identity == 0xFFFF:
            continue
        for slot in range(6):
            attribute, rank = payload[base + 6 + slot], payload[base + 12 + slot]
            if attribute in DW8_RANKED_ATTRIBUTES and 1 <= rank <= (255 if experimental else 10):
                result.append(Field(f'weapon_{index}_rank_{slot}',
                                    f'{DW8_ATTRIBUTE_NAMES.get(attribute, "Attribute")} rank (ID {attribute})',
                                    base + 12 + slot, 1, 10, 'Weapon attributes', index + 1, 1, False))
    return tuple(result)


def fields_for(document):
    validate_document(document)
    return common_fields(document.payload, experimental_enabled())


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def changed_payload(document, changes):
    mapping = field_map(document)
    changes = normalize_pending_values(document, changes, mapping)
    result = bytearray(document.payload)
    for key, value in changes.items():
        field = mapping[key]
        result[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    return bytes(result)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    raw = payload + bytes((sum(payload) & 255,))
    if _qualify(raw) != payload:
        raise SaveError('The edited Vita save failed native read-back validation.')
    return raw


def stage(document, changes, key, value):
    mapping = field_map(document)
    result = normalize_pending_values(document, changes, mapping)
    if type(key) is not str or key not in mapping:
        raise SaveError('Choose a qualified Vita field.')
    proposed = dict(result)
    proposed[key] = value
    return normalize_pending_values(document, proposed, mapping)


def limit_values(document, changes, keys):
    mapping = field_map(document)
    normalize_pending_values(document, changes, mapping)
    if isinstance(keys, (str, bytes)):
        raise SaveError('Choose a sequence of verified field IDs.')
    try:
        keys = tuple(keys)
    except TypeError as error:
        raise SaveError('Choose a sequence of verified field IDs.') from error
    if any(type(key) is not str or key not in mapping for key in keys):
        raise SaveError('Choose only qualified Vita field IDs.')
    return {}


def maximums(document, changes, group=None):
    return normalize_pending_values(document, changes, field_map(document))


def review(document, changes):
    pending = normalize_pending_values(document, changes, field_map(document))
    return [(field, field.value(document.payload), pending[field.id])
            for field in fields_for(document) if field.id in pending]


def field_options(document, key):
    mapping = field_map(document)
    if type(key) is not str or key not in mapping:
        raise SaveError('Choose a qualified Vita field.')
    return tuple((value, f'{value // 25} stars') for value in (25, 50, 75, 100)) if '_compatibility_' in key else ()


def _check_source(document):
    validate_document(document)
    with safe_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened Vita copy changed on disk. Reopen it before saving.')


def backup(document):
    _check_source(document)
    return snapshot_backup(document.raw, document.source, GAME_ID,
                           document.source.parent / 'WarriorsEditorBackups')


def save_as(document, changes, destination):
    destination = safe_path(destination)
    if destination.suffix.lower() != '.dat':
        raise SaveError('Choose a new exported Vita .dat copy.')
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    _check_source(document)
    raw = serialize(document, changes)
    _check_source(document)
    backup(document)
    _check_source(document)
    atomic_new(raw, destination)
    return read_save(destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(backup_path, destination, GAME_ID, '.dat', SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, game_id))


def record_label(slot, group='Officers'):
    return f'Weapon slot {slot}' if group == 'Weapon attributes' else f'Officer slot {slot}' if slot else group


def field_hint(document, field):
    validate_document(document)
    return ('Manual native Vita field; Max is disabled because the published bounds '
            'are editing limits. Existing identities, equipment references, EXP, '
            'ownership and story are preserved. Reimport with your Vita save tool.')


def inspection_rows(document):
    validate_document(document)
    rows = []
    for index in range(WEAPON_COUNT):
        base = WEAPON_BASE + index * WEAPON_STRIDE
        identity = int.from_bytes(document.payload[base + 2:base + 4], 'little')
        if document.payload[base] not in (1, 3) or identity == 0xFFFF:
            continue
        attributes = ', '.join(
            f'{DW8_ATTRIBUTE_NAMES.get(document.payload[base + 6 + j], "Unknown")} '
            f'#{document.payload[base + 6 + j]}: {document.payload[base + 12 + j]}'
            for j in range(6))
        rows.append({'group': 'Weapons', 'label': f'Weapon slot {index + 1} — ID {identity}',
                     'value': f'Affinity byte: {document.payload[base + 4]}; {attributes}'})
    return tuple(rows)
