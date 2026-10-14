"""Native Wo Long PC balances and conservative existing-stack reductions.

Full header/body integrity is required. Integer tokens alone change; unknown
JSON, owner context, identity keys and mission/reward history are preserved.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.wolong import wolong_json
from koei_editor.research.katana import katana_codec
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.verified_editor import Field
from koei_editor.shared.experimental_limits import experimental_enabled

GAME_ID, SAVE_SIZE, JSON_OFFSET = 'wolong', 5_120_272, 0x108
INTEGRITY_KIND = 'checksum'
# The authenticated PC serializer recalculates the body and header checksums.
# decode verifies both, and no other payload bytes are permitted to differ.
SERIALIZED_INTEGRITY_RANGES = ((0x3C, 0x7C),)
MANUAL_CURRENCY_LIMIT = 2_147_483_647
CURRENCY_NAMES = {'senki': 'Available Genuine Qi', 'sen': 'Copper', 'bukun': 'Accolades'}


@dataclass(frozen=True)
class JsonField(Field):
    @property
    def experimental_maximum(self):
        # JSON token length is not the native integer width. Currency members
        # are u64; ordinary item counts are u32 in the qualified serializer.
        return (1 << (64 if self.id in CURRENCY_NAMES else 32)) - 1

    def value(self, payload):
        return int(payload[self.offset:self.offset + self.size])

    def token(self, value):
        return str(value).encode('ascii')


@dataclass(frozen=True)
class JsonTextField(Field):
    kind: str = 'text'

    @property
    def experimental_maximum(self):
        return None

    def value(self, payload):
        return json.loads(payload[self.offset:self.offset + self.size].decode('utf-8'))

    def validate(self, value):
        if (type(value) is not str or not 1 <= len(value) <= self.maximum
                or any(not 32 <= ord(character) <= 126 for character in value)):
            raise SaveError(f'{self.label} requires 1..{self.maximum} printable ASCII characters.')

    def token(self, value):
        return json.dumps(value, ensure_ascii=True).encode('ascii')


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = True
    game_load_verified: bool = False


FORMAT = Format(GAME_ID, 'Wo Long: Fallen Dynasty (PC)', SAVE_SIZE, (),
                'Current native Windows PC USER revision 0x23121200. Both native '
                'checksums are verified. Available currencies use a conservative '
                'manual range, not a claimed natural cap; Max is disabled. Existing '
                'ordinary stacks use reduction limits by default while retaining at least one. '
                'Experimental numeric editing permits increases within the native '
                'integer widths, with unverified gameplay capacity. '
                'Enabled existing battle sets may receive a custom printable ASCII '
                'name of up to 16 bytes (a conservative editor limit). '
                'Equipment, skills, level, stored Qi and story are inspected without '
                'changing their identities, dependencies or history. Genuine parsing '
                'and no-op reconstruction are verified; edited game-load testing '
                'has not been performed by this project.')


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
        raise SaveError('Select the Wo Long Windows PC USER adapter.')
    return FORMAT


def _integer(obj, key, minimum=0, maximum=(1 << 64) - 1):
    value = obj.get(key)
    if type(value) is not int or not minimum <= value <= maximum:
        raise SaveError(f'Unsupported Wo Long {key} type or structural range.')
    return value


def _json(payload):
    encoded = payload[JSON_OFFSET:]
    zero = encoded.find(b'\0')
    if zero < 0 or any(encoded[zero:]):
        raise SaveError('Wo Long JSON must retain its bounded zero padding.')
    root, spans = wolong_json.parse(encoded[:zero])
    if type(root) is not dict:
        raise SaveError('Unsupported Wo Long JSON root.')
    for key in ('PlayerData', 'TempRecordData', 'UIData', 'PossessionItemData', 'MissionData'):
        if type(root.get(key)) is not dict:
            raise SaveError('Unsupported Wo Long USER serializer structure.')
    player = root['PlayerData']
    for key in (*CURRENCY_NAMES, 'senki_storage', 'new_senki_storage', 'level', 'skill_max_level'):
        _integer(player, key)
    if not 1 <= player['level'] <= 65535:
        raise SaveError('Unsupported Wo Long existing character level.')
    if (type(player.get('xing')) is not list or len(player['xing']) != 5
            or any(type(value) is not int or not 0 <= value <= 65535 for value in player['xing'])):
        raise SaveError('Unsupported Wo Long five-Virtue structure.')
    for key, count in (('possession_items', 600), ('storage_items', 2000)):
        records = root['PossessionItemData'].get(key)
        if type(records) is not list or len(records) != count:
            raise SaveError('Unqualified Wo Long inventory layout/count.')
        for wrapped in records:
            if type(wrapped) is not dict or type(wrapped.get('ItemObjectData')) is not dict:
                raise SaveError('Unsupported Wo Long item record wrapper.')
            record = wrapped['ItemObjectData']
            for name in ('key', 'key_num', 'num', 'flag', 'rarity', 'entry_number',
                         'item_level', 'weapon_skill_level', 'equipment_part'):
                _integer(record, name, maximum=0xffffffff)
            _integer(record, 'equipment_slot', -1, 65535)
    return root, spans, zero


@lru_cache(maxsize=4)
def _qualify(raw):
    if len(raw) != SAVE_SIZE or raw[:8] not in (b'WLNUSR\0\0',):
        raise SaveError('Open the qualified 5,120,272-byte Wo Long PC USER copy, not SYSTEM data.')
    try:
        native = katana_codec.decode(raw, GAME_ID)
    except (ValueError, TypeError) as error:
        raise SaveError(str(error)) from error
    if not native.integrity_verified:
        raise SaveError('Wo Long native header/body integrity must both be verified.')
    root, spans, length = _json(native.payload)
    return native.payload, root, spans, length


def decode(raw, game_id=GAME_ID, source=None):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != SAVE_SIZE:
        raise SaveError('Unsupported Wo Long native USER size/type.')
    raw = bytes(raw)
    payload = _qualify(raw)[0]
    return Document(FORMAT, Path(source) if source is not None else Path('wolong-copy.bin'), raw, payload)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.bin':
        raise SaveError('Open a separate SAVEDATA.BIN copy.')
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or not isinstance(document.source, Path)
            or _qualify(document.raw)[0] != document.payload):
        raise SaveError('An unchanged immutable Wo Long USER snapshot is required.')


def _ordinary_stack(record, experimental=False):
    # No item creation/deletion or gear quantities. Native num is retained above
    # zero; reductions need no invented per-item capacity or acquisition flags.
    return (record['key'] != 0 and record['key_num'] != 0xffffffff
            and 1 < record['num'] <= (0xffffffff if experimental else 0x7fffffff) and record['flag'] == 8
            and record['equipment_part'] == 0 and record['equipment_slot'] == -1
            and record['item_level'] == 1 and record['weapon_skill_level'] == 0)


@lru_cache(maxsize=4)
def _fields(raw, experimental=False):
    _, root, spans, _ = _qualify(raw)
    fields = []
    for key, label in CURRENCY_NAMES.items():
        start, end = spans[('PlayerData', key)]
        fields.append(JsonField(key, label, JSON_OFFSET + start, end - start,
                                MANUAL_CURRENCY_LIMIT, 'Available currencies', maxable=False))
    for group, label, slot_base in (('possession_items', 'Carried stacks', 0),
                                     ('storage_items', 'Stored stacks', 600)):
        for index, wrapped in enumerate(root['PossessionItemData'][group]):
            record = wrapped['ItemObjectData']
            if not _ordinary_stack(record, experimental):
                continue
            start, end = spans[('PossessionItemData', group, index, 'ItemObjectData', 'num')]
            fields.append(JsonField(f'{group}_{index}_num',
                                    f'Item key 0x{record["key"]:08X}: Reduce quantity',
                                    JSON_OFFSET + start, end - start, record['num'], label,
                                    slot_base + index + 1, minimum=1, maxable=False))
    names = root['UIData'].get('ui_battleset_slot_data_info')
    sets = root['PlayerData'].get('battleset_data_list')
    if type(names) is list and type(sets) is list and len(names) == len(sets) == 50:
        for index, (name_wrapper, set_wrapper) in enumerate(zip(names, sets)):
            if type(name_wrapper) is not dict or type(set_wrapper) is not dict:
                continue
            name = name_wrapper.get('UiBattleSetSlotInfo')
            battle_set = set_wrapper.get('BattleSetData')
            if (type(name) is not dict or type(name.get('str')) is not str
                    or type(battle_set) is not dict or battle_set.get('enable_flag') is not True):
                continue
            start, end = spans[('UIData', 'ui_battleset_slot_data_info', index, 'UiBattleSetSlotInfo', 'str')]
            fields.append(JsonTextField(f'battle_set_{index}_name', 'Custom name',
                                       JSON_OFFSET + start, end - start, 16,
                                       'Battle set names', index + 1, maxable=False))
    return tuple(fields)


def fields_for(document):
    validate_document(document)
    return _fields(document.raw, experimental_enabled())


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def read_back_value(document, key):
    """Read a requested field after serialization, even if it left the editor map.

    Text token lengths can move subsequent JSON fields, and reducing an ordinary
    stack to one makes it intentionally ineligible for further editing. Resolve
    the stable JSON path for verification instead of reusing stale byte offsets.
    """
    validate_document(document)
    root, _, _ = _json(document.payload)
    if key in CURRENCY_NAMES:
        return root['PlayerData'][key]
    for group in ('possession_items', 'storage_items'):
        prefix = group + '_'
        if key.startswith(prefix) and key.endswith('_num'):
            raw_index = key[len(prefix):-4]
            if raw_index.isdecimal():
                index = int(raw_index)
                records = root['PossessionItemData'][group]
                if 0 <= index < len(records):
                    return records[index]['ItemObjectData']['num']
    prefix = 'battle_set_'
    if key.startswith(prefix) and key.endswith('_name'):
        raw_index = key[len(prefix):-5]
        if raw_index.isdecimal():
            index = int(raw_index)
            names = root['UIData'].get('ui_battleset_slot_data_info')
            if type(names) is list and 0 <= index < len(names):
                return names[index]['UiBattleSetSlotInfo']['str']
    raise SaveError('The requested Wo Long field has no verified saved-copy path.')


def changed_payload(document, changes):
    mapping = field_map(document)
    if type(changes) is not dict:
        raise SaveError('Wo Long changes must be a field/value mapping.')
    replacements = []
    for key, value in changes.items():
        field = mapping.get(key)
        if (type(key) is not str or field is None
                or type(value) is not (str if getattr(field, 'kind', 'int') == 'text' else int)):
            raise SaveError('Choose a qualified currency, existing stack or battle-set name with the correct value type.')
        original = field.value(document.payload)
        if value != original:
            field.validate(value)
            replacements.append((field.offset, field.offset + field.size, field.token(value)))
    if not replacements:
        return document.payload
    length = _qualify(document.raw)[3]
    body = document.payload[JSON_OFFSET:JSON_OFFSET + length]
    for start, end, token in sorted(replacements, reverse=True):
        body = body[:start - JSON_OFFSET] + token + body[end - JSON_OFFSET:]
    if len(body) >= SAVE_SIZE - JSON_OFFSET:
        raise SaveError('Wo Long JSON edits exceed the existing native body capacity.')
    result = document.payload[:JSON_OFFSET] + body + bytes(SAVE_SIZE - JSON_OFFSET - len(body))
    _json(result)
    return result


def stage(document, changes, key, value):
    changed_payload(document, changes)
    if type(key) is not str:
        raise SaveError('Choose a mapped Wo Long field name.')
    proposed = dict(changes)
    proposed[key] = value
    changed_payload(document, proposed)
    field = field_map(document)[key]
    if value == field.value(document.payload):
        proposed.pop(key)
    return proposed


def serialize(document, changes):
    try:
        raw = katana_codec.encode(changed_payload(document, changes), document.raw, GAME_ID)
    except (ValueError, TypeError) as error:
        raise SaveError(str(error)) from error
    decode(raw)
    return raw


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    mapping = field_map(document)
    if isinstance(keys, (str, bytes)):
        raise SaveError('Choose a sequence of mapped Wo Long field names.')
    try:
        keys = tuple(keys)
    except TypeError as error:
        raise SaveError('Choose a sequence of mapped Wo Long field names.') from error
    if any(type(key) is not str or key not in mapping for key in keys):
        raise SaveError('Unknown Wo Long field selection.')
    return {}


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)


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
    if destination.suffix.lower() != '.bin':
        raise SaveError('Choose a new .bin destination.')
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    validate_document(document)
    _check_source(document)
    raw = serialize(document, changes)
    _check_source(document)
    backup(document)
    _check_source(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def _check_source(document):
    with safe_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened copy changed on disk. Reopen it before saving.')


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(backup_path, destination, GAME_ID, '.bin', SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, game_id))


def record_label(slot, group='Available currencies'):
    if group == 'Battle set names':
        return f'Battle set {slot}'
    if group == 'Carried stacks':
        return f'Carried slot {slot}'
    if group == 'Stored stacks':
        return f'Storage slot {slot - 600}'
    return group


def field_hint(document, key):
    field = field_map(document)[key if isinstance(key, str) else key.id]
    if field.group == 'Battle set names':
        return ('Rename this enabled existing battle set using 1..16 printable ASCII bytes. '
                'This is a conservative editor limit, not a recovered game maximum. '
                'The official update history warns that unsupported characters may not '
                'save. Gear, Virtues, spells and enable flags stay intact. Max is disabled; '
                'assigning the opened name restores even an unusual original unchanged.')
    if field.group == 'Available currencies':
        return ('Manual balance range 0..2,147,483,647 is a conservative editor limit, '
                'not a proven natural cap. Max is disabled. Stored Qi, lifetime/history '
                'records, level and rewards are preserved; unusual opened values can be restored unchanged.')
    return ('Default limits reduce this existing ordinary stack to 1..the opened quantity. '
            'Experimental editing permits increases up to 4,294,967,295, with '
            'unverified gameplay capacity. Deleting or creating item records is unavailable. Identity, flags, equipped '
            'references and acquisition history are preserved. Max is disabled.')


def inspection_rows(document):
    validate_document(document)
    root = _qualify(document.raw)[1]
    player = root['PlayerData']
    rows = [{'group': 'Profile', 'label': 'Native profile',
             'value': 'Windows PC USER 0x23121200; header and body checksums verified'},
            {'group': 'Profile', 'label': 'Stored Qi fields',
             'value': f'senki_storage {player["senki_storage"]:,}; new_senki_storage '
                      f'{player["new_senki_storage"]:,} (read only; semantics/history not fully mapped)'},
            {'group': 'Progression', 'label': 'Level / stored skill maximum',
             'value': f'{player["level"]} / {player["skill_max_level"]} (read only)'},
            {'group': 'Progression', 'label': 'Five Virtues (stored order)',
             'value': ', '.join(str(value) for value in player['xing']) + ' (read only)'}]
    for group in ('possession_items', 'storage_items'):
        for index, wrapped in enumerate(root['PossessionItemData'][group]):
            item = wrapped['ItemObjectData']
            if not item['key']:
                continue
            rows.append({'group': 'Inventory',
                         'label': f'{"Carried" if group == "possession_items" else "Storage"} slot {index + 1} '
                                  f'/ key 0x{item["key"]:08X}',
                         'value': f'Instance {item["key_num"]}; quantity {item["num"]:,}; '
                                  f'rarity {item["rarity"]}; stored item_level {item["item_level"]}; '
                                  f'martial-art field {item["weapon_skill_level"]}; '
                                  f'part {item["equipment_part"]}; equipment slot {item["equipment_slot"]}; '
                                  f'flags 0x{item["flag"]:X}'})
    companions = player.get('fellow_character_info')
    # Optional, unmapped serializer values remain intact. Only a qualified
    # array supplies companion inspection; null/scalar values cannot be walked.
    if type(companions) is not list:
        companions = ()
    for index, wrapped in enumerate(companions):
        if type(wrapped) is dict and type(wrapped.get('FellowCharacterInfoData')) is dict:
            info = wrapped['FellowCharacterInfoData']
            if all(type(info.get(key)) is int for key in ('fellow_character_id', 'bond_level', 'bond_point', 'flag')):
                rows.append({'group': 'Companions', 'label': f'Companion slot {index + 1} / ID {info["fellow_character_id"]}',
                             'value': f'Bond level {info["bond_level"]}; points {info["bond_point"]}; '
                                      f'flags 0x{info["flag"]:X} (read only)'})
    return tuple(rows)
