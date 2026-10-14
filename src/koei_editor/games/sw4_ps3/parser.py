"""Independent source-backed PS3 adapter. See docs/PS3_EXPANSION.md.

Published Apollo patch facts are reimplemented; no GPL source or player data is
included. Actual public PS3 exports were decrypted privately for qualification.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.shared.copy_storage import atomic_new, snapshot_backup, restore_snapshot
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.ps3_export import validate_optional_context


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
    kind: str = 'int'

    @property
    def experimental_maximum(self):
        return (1 << (8 * self.size)) - 1

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'big')

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from {self.minimum:,} to {self.maximum:,}.')

    def encoded(self, value):
        self.validate(value)
        return value.to_bytes(self.size, 'big')


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = True


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()

GAME_ID = 'sw4_ps3'
TITLE_IDS = ('NPUB31564',)
SAVE_SIZE = 0x64000
REVISION = bytes.fromhex('00002118')
CHECKSUM_OFFSETS = (4, 0xA8, 0xC16, 0x58532)
WEAPON_BASE, WEAPON_STRIDE, WEAPON_POOLS, WEAPON_SLOTS = 0x3882, 0x22, 60, 8
# Factual skill names/IDs in the public PS3 patch, corroborated by the PC native
# structure. PS3 progression flags remain raw inspection values, not writable.
SKILL_NAMES = (
    'Potency', 'Range', 'Courage', 'Impact', 'Fury', 'Underdog', 'Momentum',
    'Clarity', 'Verity', 'Concentration', 'Fortitude', 'Stability', 'Elasticity',
    'Bravery', 'Determination', 'Resolve', 'Nullification', 'Zeal', 'Conviction',
    'Resurrection', 'Alacrity', 'Blaze', 'Shock', 'Frost', 'Wind', 'Diamond',
    'Reaper', 'Rampage', 'Impulse', 'Awakening', 'Cavalry', 'Equestrian',
    'Connoisseur', 'Collector', 'Hoarder', 'Constitution', 'Expert', 'Endurance',
    'Paladin', 'Stimulus',
)
_fields = [Field('gold', 'Gold', 0x7842, 4, 999999)]
for i in range(8):
    _fields.append(Field(f'gem_{i}', f'Gem slot {i + 1}', 0x78BC + i, 1, 99, 'Gems', i + 1))
FORMAT = Format(GAME_ID, 'Samurai Warriors 4 (PS3, US decrypted export)',
                SAVE_SIZE, tuple(_fields),
                'Open a copied, decrypted US PS3 DATA.BIN export. Edit gold, gems '
                'then reimport and resign with Apollo. '
                'Automatic Max is unavailable for these manual controls.')


def checksums(raw):
    data = bytearray(raw)
    for offset in CHECKSUM_OFFSETS:
        data[offset:offset + 4] = b'\0' * 4
    a, b, c, d, e, f = (sum(data[x:y]) for x, y in (
        (8, 168), (172, 2284), (3098, 30934),
        (34270, 361778), (30934, 34271), (8, 30934)))
    first = ((c + a) * b + e) & 0x7FFFFFFF
    second = (a * (c + b + d)) & 0x7FFFFFFF
    third = f
    return first, second, third, (first + second + third) & 0x7FFFFFFF


def qualify(raw):
    if (type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:4] != REVISION
            or raw[0x58298:0x5829C] != b'\0' * 4):
        raise SaveError('Requires a decrypted US PS3 SW4 DATA.BIN revision 0x2118 '
                        'of 0x64000 bytes; JP layouts, PC and encrypted saves are rejected.')
    for offset, expected in zip(CHECKSUM_OFFSETS, checksums(raw)):
        if int.from_bytes(raw[offset:offset + 4], 'big') != expected:
            raise SaveError('Samurai Warriors 4 PS3 section checksum failed.')
    for i in range(55):
        if int.from_bytes(raw[0xC1A + i * 0x44:0xC1E + i * 0x44], 'big') != i:
            raise SaveError('Samurai Warriors 4 PS3 officer identities are invalid.')


def seal(payload):
    output = bytearray(payload)
    for offset, value in zip(CHECKSUM_OFFSETS, checksums(payload)):
        output[offset:offset + 4] = value.to_bytes(4, 'big')
    return bytes(output)


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select this exact PS3 decrypted-export adapter.')
    return FORMAT


def decode(raw, game_id=GAME_ID, source=Path('copy.bin')):
    get_format(game_id)
    qualify(raw)
    return Document(FORMAT, Path(source), raw, raw)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.bin':
        raise SaveError('Open a separate decrypted PS3 .bin export copy.')
    validate_optional_context(path, TITLE_IDS)
    with path.open('rb') as stream:
        return decode(stream.read(SAVE_SIZE + 1), game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format != FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload):
        raise SaveError('A frozen decrypted PS3 snapshot is required.')
    qualify(document.raw)


def fields_for(document):
    validate_document(document)
    # Proficiency levels have separate stored EXP; no write is exposed until
    # their dependency is qualified for this exact PS3 profile.
    return FORMAT.fields



def field_map(document):
    return {field.id: field for field in fields_for(document)}


def changed_payload(document, changes):
    fields = field_map(document)
    result = bytearray(document.payload)
    for key, value in changes.items():
        if key not in fields:
            raise SaveError('This field is not qualified for the opened PS3 profile.')
        field = fields[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        result[field.offset:field.offset + field.size] = field.encoded(value)
    return seal(bytes(result))


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    raw = seal(payload)
    decode(raw, GAME_ID, document.source)
    return raw


def stage(document, changes, key, value):
    changes = normalize_pending_values(document, changes, field_map(document))
    fields = field_map(document)
    if key not in fields:
        raise SaveError('This field is not qualified for the opened PS3 profile.')
    result = dict(changes)
    if type(value) is int and value == fields[key].value(document.payload):
        result.pop(key, None)
    else:
        fields[key].validate(value)
        result[key] = value
    return result


def limit_values(document, changes, keys):
    changes = normalize_pending_values(document, changes, field_map(document))
    fields = field_map(document)
    changed_payload(document, changes)
    for key in keys:
        if key not in fields:
            raise SaveError('This field is not qualified for the opened PS3 profile.')
    # Published cheat targets are manual editing bounds, not natural gameplay
    # caps. No automatic Max action is authorized by this source evidence.
    return {}


def maximums(document, changes, group=None):
    changes = normalize_pending_values(document, changes, field_map(document))
    limit_values(document, changes, [f.id for f in fields_for(document)
                                   if group is None or f.group == group])
    return dict(changes)


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def backup(document):
    validate_document(document)
    return snapshot_backup(document.raw, document.source, GAME_ID,
                           document.source.parent / 'UniversalEditorBackups')


def save_as(document, changes, destination):
    validate_document(document)
    destination = safe_path(destination)
    if destination.suffix.lower() != '.bin':
        raise SaveError('Choose a new decrypted .bin copy destination.')
    validate_optional_context(document.source, TITLE_IDS)
    validate_optional_context(destination, TITLE_IDS)
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    with safe_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened copy changed on disk. Reopen it before saving.')
    raw = serialize(document, changes)
    backup(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    validate_optional_context(safe_path(destination), TITLE_IDS)
    return restore_snapshot(backup_path, destination, GAME_ID, '.bin', SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, GAME_ID))


def record_label(slot, group='Officers'):
    return f'Officer slot {slot}' if slot else group


def field_hint(document, field):
    validate_document(document)
    return ('These quantity controls are manual; automatic Max is disabled. '
            'Unknown/higher original values remain unchanged. Export a decrypted '
            'copy with Apollo; after editing, reimport and resign it with Apollo. '
            'Encrypted console files, PARAM.PFD signing and PC saves are not handled.')

# Integrity validated by this backend, separately from sample qualification.
INTEGRITY_KIND = 'checksum'


def inspection_rows(document):
    validate_document(document)
    rows = []
    for index in range(55):
        base = 0xC1A + index * 0x44
        levels = document.payload[base + 0x2A:base + 0x2E]
        experience = [int.from_bytes(document.payload[base + 0x10 + item * 4:
                                                      base + 0x14 + item * 4], 'big')
                      for item in range(4)]
        rows.append({'group': 'Proficiency inspection', 'label': f'Officer slot {index + 1}',
                     'value': 'Stored proficiency level / EXP: '
                              + ', '.join(f'{level} / {exp:,}' for level, exp in zip(levels, experience))
                              + ' (read only)'})
    for weapon in weapon_records(document):
        if weapon['id'] == 180:
            continue
        details = []
        for skill in weapon['skills']:
            name = SKILL_NAMES[skill['id']] if skill['id'] < 40 else f"Unknown skill ID {skill['id']}"
            details.append(f"{name}: stored rank {skill['rank']}, ceiling {skill['ceiling']}, "
                           f"flags 0x{skill['flags']:02X}")
        rows.append({'group': 'Weapon inspection',
                     'label': f"Pool {weapon['pool']}, slot {weapon['slot']}: weapon ID {weapon['id']}",
                     'value': '; '.join(details) + ' (read only)'})
    return tuple(rows)


def weapon_records(document):
    """Inspect the existing source-documented PS3 arrays without importing PC data.

    Owner names, rarity fabrication and rank/reward/activation writes are not
    qualified by the patch's placeholder values. Every unknown ID/flag is kept.
    """
    validate_document(document)
    records = []
    for pool in range(WEAPON_POOLS):
        for slot in range(WEAPON_SLOTS):
            base = WEAPON_BASE + (pool * WEAPON_SLOTS + slot) * WEAPON_STRIDE
            records.append({'pool': pool + 1, 'slot': slot + 1,
                            'id': int.from_bytes(document.payload[base:base + 2], 'big'),
                            'skills': tuple({'id': document.payload[base + 10 + index],
                                             'rank': document.payload[base + 18 + index],
                                             'ceiling': document.payload[base + 2 + index],
                                             'flags': document.payload[base + 26 + index]}
                                            for index in range(8))})
    return tuple(records)
