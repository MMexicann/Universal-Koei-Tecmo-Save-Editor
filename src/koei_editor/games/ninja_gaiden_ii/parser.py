"""Manual essence and existing-stack reductions in the qualified NGII revision-6 story profile.

The genuine original revision-6 extracted story profile is independently
qualified. No CON/STFS signatures, Xenia identity guesses, native seeds,
ownership, weapon levels, health/Ninpo dependencies or completion bits are edited.
"""
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import re
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.games.ninja_gaiden_ii import codec
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'ninjagaiden2_x360'
SAVE_SIZE = codec.SAVE_SIZE
ESSENCE_OFFSET = 40
KARMA_OFFSET = 560
ITEM_START, ITEM_COUNT, ITEM_STRIDE = 48, 128, 4
ITEM_NAMES = MappingProxyType({
    8: 'Herb of Spiritual Life', 9: 'Grains of Spiritual Life',
    10: 'Talisman of Rebirth', 11: 'Life of the Thousand Gods',
    35: 'Incendiary Shuriken', 75: 'Life of the Gods',
    76: 'Jewel of the Demon Seal', 77: 'Spirit of the Devils',
    78: 'Devil Way Mushroom', 116: "Muramasa's Omusabi",
    148: 'Fiends Bane Bow arrows',
})


def _copy_path(path):
    """Reject native Xenia live content paths and aliases without shared branches."""
    original = Path(path).expanduser()
    resolved = safe_path(original)
    for candidate in (original, original.absolute(), resolved):
        normalized = '/' + str(candidate).lower().replace('\\', '/').lstrip('/')
        # Both older content/title and newer content/profile/title Xenia trees
        # are publicly documented. Copies must be outside either live tree.
        if re.search(r'/content/(?:[^/]+/)?544307d5(?:/|$)', normalized):
            raise SaveError('Open and save separate Ninja Gaiden II copies outside Xenia content directories.')
    return resolved


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    size: int
    maximum: int
    minimum: int = 0
    group: str = 'Resources'
    slot: int = 0
    maxable: bool = False
    kind: str = 'int'

    @property
    def experimental_maximum(self):
        return (1 << (8 * self.size)) - 1

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'big')

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires an integer from {self.minimum} to {self.maximum}.')


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = True
    game_load_verified: bool = False


FORMAT = Format(GAME_ID, 'Ninja Gaiden II (original Xbox 360/Xenia, revision-6 extracted stories)',
                SAVE_SIZE, (), 'Qualified original story profile: manual Yellow Essence and reductions '
                'of qualified existing consumable stacks. Native checksum preserved; '
                'genuine-file edits revalidate; actual edited game loading remains pending.')


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
        raise SaveError('Select original Xbox 360 Ninja Gaiden II, extracted revision-6 story profile.')
    return FORMAT


def decode(raw, game_id=GAME_ID, source=Path('ng2-story-copy.dat')):
    get_format(game_id)
    payload = codec.decode(raw)
    return Document(FORMAT, Path(source), payload, payload)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _copy_path(path)
    if path.suffix.lower() != '.dat':
        raise SaveError('Open a separate .dat raw story copy.')
    with path.open('rb') as stream:
        return decode(stream.read(SAVE_SIZE + 1), game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or not isinstance(document.source, Path)):
        raise SaveError('A frozen original Ninja Gaiden II raw story document is required.')
    if codec.decode(document.raw) != document.payload:
        raise SaveError('The opened Ninja Gaiden II snapshot changed externally.')


@lru_cache(maxsize=4)
def _fields(payload):
    fields = [Field('yellow_essence', 'Yellow Essence balance', ESSENCE_OFFSET, 4, 0xFFFFFFFF)]
    identities = [int.from_bytes(payload[ITEM_START + slot * ITEM_STRIDE:
                                        ITEM_START + slot * ITEM_STRIDE + 2], 'big')
                  for slot in range(ITEM_COUNT)]
    counts = Counter(identities)
    for slot, identity in enumerate(identities):
        at = ITEM_START + slot * ITEM_STRIDE
        quantity, variant = payload[at + 2:at + 4]
        # No creation/removal and no ownership/weapon variant changes. Ambiguous
        # duplicates or nonordinary variants stay visible but read-only.
        if identity not in ITEM_NAMES or counts[identity] != 1 or quantity <= 1 or variant != 0:
            continue
        fields.append(Field(f'item_{slot}_quantity', ITEM_NAMES[identity] + ': carried quantity',
                            at + 2, 1, quantity, minimum=1, group='Existing stacks', slot=slot + 1))
    return tuple(fields)


def fields_for(document):
    validate_document(document)
    return _fields(document.payload)


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def changed_payload(document, changes):
    if not isinstance(changes, Mapping):
        raise SaveError('Pending Ninja Gaiden II changes must be a field/value mapping.')
    mapping = field_map(document)
    result = bytearray(document.payload)
    changed = False
    for key, value in changes.items():
        if type(key) is not str or key not in mapping:
            raise SaveError('Only qualified existing Ninja Gaiden II fields are writable.')
        field = mapping[key]
        field.validate(value)
        if value == field.value(document.payload):
            continue
        result[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'big')
        changed = True
    return codec.rebuild(result) if changed else document.payload


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if decode(payload, GAME_ID, document.source).payload != payload:
        raise SaveError('The edited Ninja Gaiden II raw story copy did not revalidate.')
    return payload


def stage(document, changes, key, value):
    changed_payload(document, changes)
    mapping = field_map(document)
    if type(key) is not str or key not in mapping:
        raise SaveError('The requested Ninja Gaiden II field is not editable.')
    field = mapping[key]
    field.validate(value)
    result = dict(changes)
    if value == field.value(document.payload):
        result.pop(key, None)
    else:
        result[key] = value
    return result


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    mapping = field_map(document)
    if isinstance(keys, (str, bytes)):
        raise SaveError('Choose a sequence of mapped Ninja Gaiden II field names.')
    try:
        keys = tuple(keys)
    except TypeError as error:
        raise SaveError('Choose a sequence of mapped Ninja Gaiden II field names.') from error
    for key in keys:
        if type(key) is not str or key not in mapping:
            raise SaveError('The requested Ninja Gaiden II field is not editable.')
    return {}  # Natural caps and grant/reward boundaries have not been proved.


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def backup(document):
    validate_document(document)
    source = _copy_path(document.source)
    folder = _copy_path(source.parent / 'UniversalEditorBackups')
    return snapshot_backup(document.raw, source, GAME_ID, folder)


def save_as(document, changes, destination):
    validate_document(document)
    destination = _copy_path(destination)
    if destination.suffix.lower() != '.dat':
        raise SaveError('Choose a new .dat raw story destination.')
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    _check_source(document)
    raw = serialize(document, changes)
    _check_source(document)
    backup(document)
    _check_source(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def _check_source(document):
    with _copy_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened Ninja Gaiden II copy changed on disk. Reopen it before saving.')


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(_copy_path(backup_path), _copy_path(destination), GAME_ID, '.dat', SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, GAME_ID))


def record_label(slot, group='Resources'):
    return f'Inventory slot {slot}' if group == 'Existing stacks' else group


def field_hint(document, field):
    key = field.id if isinstance(field, Field) else field
    if type(key) is not str or key not in field_map(document):
        raise SaveError('The requested Ninja Gaiden II field is not editable.')
    if key == 'yellow_essence':
        return ('Manual native balance. The 32-bit input range is a storage range, not a proven '
                'natural gameplay cap. Max leaves it unchanged. Karma, health, Ninpo and completion remain separate.')
    return ('Reduce this existing stack to 1..the opened quantity. Item identity and variant are preserved. '
            'Creation, removal and increases remain unavailable until capacities and reward dependencies are proved.')


def inspection_records(document):
    validate_document(document)
    payload = document.payload
    mapping = field_map(document)
    rows = []
    for slot in range(ITEM_COUNT):
        at = ITEM_START + slot * ITEM_STRIDE
        record = payload[at:at + ITEM_STRIDE]
        if record == b'\0\0\0\0':
            continue
        identity = int.from_bytes(record[:2], 'big')
        rows.append((slot + 1, identity, ITEM_NAMES.get(identity, f'Unknown ID {identity}'),
                     record[2], record[3], 'reduce only' if f'item_{slot}_quantity' in mapping else 'read only'))
    scalars = (('Yellow Essence balance', int.from_bytes(payload[ESSENCE_OFFSET:ESSENCE_OFFSET + 4], 'big')),
               ('Karma / historical score (read only)', int.from_bytes(payload[KARMA_OFFSET:KARMA_OFFSET + 4], 'big')))
    return tuple(rows), scalars


INTEGRITY_KIND = 'checksum'
