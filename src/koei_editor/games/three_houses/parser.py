"""Conservative Three Houses slot editor using the shared scalar contract.

No foreign implementation or extracted game catalog is included. Public source
facts and independently examined exports establish the native layouts described
in docs/THREE_HOUSES_FORMAT.md. Unknown identities, values and bytes are retained.
"""
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.three_houses import codec, names
from koei_editor.games.three_houses.equipment import ORDINARY_EQUIPMENT
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'three_houses'
TITLE = 'Fire Emblem: Three Houses'
EXTENSION = ''
SAVE_SIZE = codec.SAVE_SIZE
HEADER_SIZE = codec.HEADER_SIZE
PROFILES = codec.PROFILES
BYTEORDER = codec.BYTEORDER
INTEGRITY_KIND = 'checksum'
# Original public source Database.cs CHARACTER_USEABLE_COUNT and InitLists use
# these actual native unit IDs. Additional/DLC unit IDs need independent owner
# mapping and entitlement evidence; they are inspected but never edited here.
BASE_OWNER_IDS = frozenset(range(35))


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    size: int
    maximum: int
    group: str = 'Resources'
    slot: int = 0
    minimum: int = 0
    maxable: bool = False
    kind: str = 'integer'
    forbidden: tuple = ()
    choices: tuple = ()

    @property
    def experimental_maximum(self):
        if self.choices:
            return None
        return (1 << (self.size * 8)) - 1

    def value(self, payload):
        return codec.uint(payload, self.offset, self.size)

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from {self.minimum:,} to {self.maximum:,}.')
        if value in self.forbidden:
            raise SaveError('The native unlimited-durability sentinel cannot be granted by a numeric edit.')
        if self.choices and value not in self.choices:
            raise SaveError(f'{self.label} requires one of its qualified native choices.')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = TITLE
    size: int = SAVE_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = ('Nintendo Switch known main-campaign extracted slot/auto; native revisions 13 and 23 only. '
                 'Exact update and DLC entitlement cannot be inferred from these revision numbers. '
                 'Cindered Shadows side-story and additional/DLC character ownership are unqualified. '
                 'Open an extensionless copy with known Three Houses extraction provenance.')


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

    @property
    def profile(self):
        return PROFILES[codec.uint(self.raw, 4, 4)]


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError(f'Choose the explicit {TITLE} Nintendo Switch adapter.')
    return FORMAT


def decode(raw, game_id=GAME_ID, source=Path('slot-copy')):
    get_format(game_id)
    codec.qualify(raw)
    raw = bytes(raw)
    return Document(FORMAT, Path(source), raw, raw)


def _extension(path):
    if Path(path).suffix:
        raise SaveError('Use a separate extensionless Three Houses slot/auto export copy.')


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    _extension(path)
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes):
        raise SaveError(f'Invalid immutable {TITLE} snapshot.')
    codec.qualify(document.raw)
    if document.payload != document.raw:
        raise SaveError('The opened snapshot changed outside the edit workflow.')


def _character_rows(raw):
    profile = PROFILES[codec.uint(raw, 4, 4)]
    rows = []
    for index in range(codec.CHARACTER_COUNT):
        base = HEADER_SIZE + codec.CHARACTER_BASE + index * profile.character_stride
        rows.append({'slot': index + 1, 'index': index, 'offset': base,
            'id': codec.item_id(raw, base + 0x24), 'level': raw[base + 0x4A],
            'class': raw[base + 0x4B], 'hp': raw[base + 0x4C],
            'exp': codec.uint(raw, base + 0x2C, 2),
            'flags': codec.uint(raw, base + 0xAC, 4), 'item_count': raw[base + 0x87]})
    counts = Counter(row['id'] for row in rows if row['id'] >= 0)
    for row in rows:
        row['qualified_owner'] = (row['id'] in BASE_OWNER_IDS and counts[row['id']] == 1
            and row['level'] > 0 and row['flags'] & 3 == 3 and not row['flags'] & 8)
    return tuple(rows)


def characters(document):
    validate_document(document)
    return _character_rows(document.payload)


def items(document):
    validate_document(document)
    raw = document.payload
    rows = []
    for index in range(codec.CONVOY_COUNT):
        base = HEADER_SIZE + index * codec.ITEM_STRIDE
        identity = codec.item_id(raw, base)
        if identity != -1:
            rows.append({'owner': 'Convoy', 'slot': index + 1, 'id': identity,
                'durability': raw[base + 2], 'quantity': raw[base + 3]})
    for owner in _character_rows(raw):
        for index in range(6):
            base = owner['offset'] + index * codec.ITEM_STRIDE
            identity = codec.item_id(raw, base)
            if identity != -1:
                rows.append({'owner': f"Character slot {owner['slot']} / native ID {owner['id']}",
                    'slot': index + 1, 'id': identity, 'durability': raw[base + 2],
                    'quantity': 'Not a held quantity'})
    return tuple(rows)


@lru_cache(maxsize=4)
def _field_index(raw):
    profile = PROFILES[codec.uint(raw, 4, 4)]
    gold = HEADER_SIZE + profile.player_offset + 0x1074
    fields = [Field('gold', 'Gold (decrease only)', gold, 4, codec.uint(raw, gold, 4))]
    name_offset = HEADER_SIZE + names.OFFSETS[profile.revision]
    protagonists = [row for row in _character_rows(raw) if row['id'] in (0, 1)]
    if (len(protagonists) == 1 and protagonists[0]['qualified_owner']
            and names.framed_name(raw[name_offset:name_offset + names.SIZE]) is not None):
        fields.append(names.NameField(name_offset))
    for index in range(codec.CONVOY_COUNT):
        base = HEADER_SIZE + index * codec.ITEM_STRIDE
        if codec.item_id(raw, base) not in ORDINARY_EQUIPMENT or raw[base + 3] == 0:
            continue
        identity = codec.item_id(raw, base)
        label = f'Convoy slot {index + 1} / {ORDINARY_EQUIPMENT[identity]} / ID {identity}'
        if raw[base + 2] != 100:
            fields.append(Field(f'convoy:{index}:durability', label + ' durability (decrease only)',
                base + 2, 1, raw[base + 2], 'Convoy', index + 1, forbidden=(100,)))
        fields.append(Field(f'convoy:{index}:quantity', label + ' quantity (decrease only)',
            base + 3, 1, raw[base + 3], 'Convoy', index + 1, minimum=1))
    for owner in _character_rows(raw):
        if not owner['qualified_owner']:
            continue
        base = owner['offset']
        # Motivation is a standalone instruction budget, not proficiency EXP.
        # Native Byleth profiles 0/1 cannot receive ordinary instruction.
        if owner['id'] not in (0, 1) and raw[base + 0xC4] in (0, 25, 50, 75, 100):
            fields.append(Field(f"character:{owner['index']}:motivation",
                f"Character slot {owner['slot']} / ID {owner['id']} motivation",
                base + 0xC4, 1, 100, 'Motivation', owner['slot'],
                choices=(0, 25, 50, 75, 100)))
        equipped = tuple(raw[base + 0x7F:base + 0x84])
        occupied = tuple(identity for identity in equipped if identity != 240)
        # Preserve unrecognized/default/duplicate loadouts. An original equipped
        # identity must also be learned; pending edits never grant ownership.
        if (occupied and not owner['flags'] & (1 << 18)
                and len(set(occupied)) == len(occupied) and all(identity < 240
                and raw[base + 0x61 + identity // 8] & (1 << (identity % 8))
                for identity in occupied)):
            choices = tuple(sorted(set(occupied))) + (240,)
            for slot in range(5):
                fields.append(Field(f"character:{owner['index']}:ability:{slot}",
                    f"Character slot {owner['slot']} / ID {owner['id']}, ability slot {slot + 1}",
                    base + 0x7F + slot, 1, 240, 'Existing ability loadout',
                    owner['slot'], choices=choices))
        for index in range(6):
            base = owner['offset'] + index * codec.ITEM_STRIDE
            identity = codec.item_id(raw, base)
            if identity not in ORDINARY_EQUIPMENT or raw[base + 2] == 100:
                continue
            fields.append(Field(f"character:{owner['index']}:item:{index}:durability",
                f"Character slot {owner['slot']} / ID {owner['id']}, item slot {index + 1} / {ORDINARY_EQUIPMENT[identity]} / ID {identity} durability (decrease only)",
                base + 2, 1, raw[base + 2], 'Held equipment', owner['slot'], forbidden=(100,)))
    return MappingProxyType({field.id: field for field in fields})


def field_map(document):
    validate_document(document)
    return _field_index(document.payload)


def fields_for(document):
    return tuple(field_map(document).values())


def changed_payload(document, changes):
    if type(changes) is not dict:
        raise SaveError('Pending changes must be a dictionary.')
    fields = field_map(document)
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('This field or existing owner is not qualified for edits.')
        field = fields[key]
        # Assigning unusual opened values always preserves/unstages the original.
        original = field.value(document.payload)
        if type(value) is type(original) and value == original:
            continue
        field.validate(value)
        if field.kind == 'text':
            field.write(output, value, document.payload)
        else:
            output[field.offset:field.offset + field.size] = value.to_bytes(field.size, BYTEORDER)
    # Validate the final staged loadout, including edits already pending. Empty
    # slots can repeat, but a standard ability cannot occupy two slots.
    for owner in _character_rows(document.payload):
        prefix = f"character:{owner['index']}:ability:"
        if not any(key.startswith(prefix) for key in changes):
            continue
        base = owner['offset'] + 0x7F
        occupied = [identity for identity in output[base:base + 5] if identity != 240]
        if len(occupied) != len(set(occupied)):
            raise SaveError('An ability may occupy only one equipped slot per character.')
    return codec.encode(bytes(output), document.raw)


def serialize(document, changes):
    result = changed_payload(document, changes)
    if decode(result, GAME_ID, document.source).payload != result:
        raise SaveError('Edited Three Houses export failed read-back validation.')
    return result


def stage(document, changes, key, value):
    changed_payload(document, changes)
    fields = field_map(document)
    if type(key) is not str or key not in fields:
        raise SaveError('This field or existing owner is not qualified for edits.')
    result = dict(changes)
    original = fields[key].value(document.payload)
    if type(value) is type(original) and value == original:
        result.pop(key, None)
    else:
        fields[key].validate(value)
        result[key] = value
    changed_payload(document, result)
    return result


def field_options(document, key):
    field = field_map(document).get(key)
    if field is None:
        raise SaveError('This original record is not qualified for edits.')
    if field.group == 'Motivation':
        return tuple((value, f'{value} motivation ({value // 25} instruction attempts)')
                     for value in field.choices)
    if field.group == 'Existing ability loadout':
        owner = next(row for row in _character_rows(document.payload) if row['slot'] == field.slot)
        opened = document.payload[owner['offset'] + 0x7F:owner['offset'] + 0x84]
        return tuple((value, 'Empty' if value == 240 else f'Ability from opened slot {opened.index(value) + 1}')
                     for value in field.choices)
    return ()


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    fields = field_map(document)
    if type(keys) not in (list, tuple, set, frozenset):
        raise SaveError('Select a collection of qualified field identifiers.')
    for key in keys:
        if type(key) is not str or key not in fields:
            raise SaveError('This field is not qualified for edits.')
    return {}  # No source-backed natural gameplay caps are asserted.


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def backup(document):
    validate_document(document)
    source = safe_path(document.source)
    return snapshot_backup(document.raw, source, GAME_ID, source.parent / 'WarriorsEditorBackups')


def save_as(document, changes, destination):
    destination = safe_path(destination)
    _extension(destination)
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    validate_document(document)
    with safe_path(document.source).open('rb') as stream:
        current = stream.read(SAVE_SIZE + 1)
    if current != document.raw:
        raise SaveError('The opened copy changed on disk. Reopen it before saving.')
    result = serialize(document, changes)
    backup(document)
    atomic_new(result, destination)
    return decode(result, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(safe_path(backup_path), safe_path(destination), GAME_ID,
        EXTENSION, SAVE_SIZE, validate_raw=lambda raw: decode(raw, game_id))


def record_label(slot, group='Resources'):
    return f'{group} record {slot}' if slot else group


def field_hint(document, key):
    field = field_map(document).get(key)
    if field is None:
        raise SaveError('This original record is not qualified for edits.')
    if field.kind == 'text':
        return ('Rename the existing protagonist using 1–8 printable ASCII characters. This is a conservative '
                'editor input limit, not a recovered natural name limit. Original UTF-8 names and both native '
                'closing controls are preserved on no-op. Recruitment, gender, appearance and system-file previews '
                'are separate; only this gameplay slot is edited. No Max.')
    if field.group == 'Motivation':
        return ('Instruction motivation in steps of 25, from 0 to 100. Only original unique living '
                'joined base units other than Byleth qualify. No instruction is performed: '
                'proficiency, budding talents, support points, professor EXP and lesson activity remain unchanged. No Max.')
    if field.group == 'Existing ability loadout':
        return ('Select an ability already equipped and learned in this opened character, or Empty. '
                'Clear its old slot before moving it; duplicate equipped abilities are rejected. '
                'The original learned bitmap, class, personal/class abilities and all reward flags remain unchanged. No Max.')
    return ('Decrease this opened balance/value only; no natural Max is asserted. '
            'Existing identity, record count, ownership and equipped references are preserved. '
            'Equipment writes require a reviewed ordinary weapon ID; held writes additionally '
            'require a unique living available/joined base-unit owner ID 0–34. '
            'Durability 100 is the native unlimited sentinel and remains read only. '
            'Held-item amount bytes are not quantities. Recruitment, progression, rewards and DLC entitlement are separate.')


def inspection_rows(document):
    validate_document(document)
    profile = document.profile
    raw = document.payload
    return ({'group': 'Native profile', 'label': 'Save-format revision', 'value': profile.revision},
        {'group': 'Native profile', 'label': 'Game update / DLC entitlement', 'value': 'Not encoded by this revision marker'},
        {'group': 'Native profile', 'label': 'Qualified context', 'value': 'Known main-campaign exports; side story and DLC/additional owners unqualified'},
        {'group': 'Resources', 'label': 'Gold', 'value': codec.uint(raw, HEADER_SIZE + profile.player_offset + 0x1074, 4)},
        {'group': 'Resources', 'label': 'Renown (read only)', 'value': codec.uint(raw, HEADER_SIZE + profile.activities_offset + 0xC, 4)},
        {'group': 'Progression', 'label': 'Professor experience (read only)', 'value': codec.uint(raw, HEADER_SIZE + profile.activities_offset + 0x12, 2)})
