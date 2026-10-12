"""Independent battery-SRAM writer from the documented native NES routines.

This is a 28-team SRAM profile, not a ROM editor or emulator-state editor.
See docs/TECMO_SUPER_BOWL_NES_FORMAT.md for integrity and source evidence.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'tecmo_super_bowl_nes'
SIZE = MAX_FILE_SIZE = 8192
INTEGRITY_KIND = 'checksum'
# The native season checksum is updated when a valid play/condition/control
# field changes. It is verified during decode and is the only permitted
# serializer difference beyond the requested bytes.
SERIALIZED_INTEGRITY_RANGES = ((0x6BE, 0x6C0),)
POSITIONS = ('QB1', 'QB2', 'RB1', 'RB2', 'RB3', 'RB4', 'WR1', 'WR2', 'WR3',
             'WR4', 'TE1', 'TE2', 'C', 'LG', 'RG', 'LT', 'RT', 'RE', 'NT', 'LE',
             'ROLB', 'RILB', 'LILB', 'LOLB', 'RCB', 'LCB', 'FS', 'SS', 'K', 'P')
CONDITIONS = ('Bad', 'Average', 'Good', 'Excellent')
CONTROLS = ('Manual (MAN)', 'Coach (COA)', 'Computer (COM)', 'Skip (SKP)')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Tecmo Super Bowl (NES, compatible 28-team battery SRAM)'
    note: str = ('Raw 8 KiB battery SRAM, not a ROM or emulator state. Team control, '
                 'player condition and per-slot playbook choices. Injuries, starters, '
                 'season results and roster abilities are preserved. Close the emulator '
                 'before exporting and importing a separate battery-save copy.')
    size: int = SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    published_format: bool = True


FORMAT = Format()


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    shift: int
    bits: int
    maximum: int
    group: str
    slot: int
    minimum: int = 0
    size: int = 1
    maxable: bool = False
    kind: str = 'int'

    def value(self, payload):
        return (payload[self.offset] >> self.shift) & ((1 << self.bits) - 1)

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(f'{self.label} requires a whole number from 0 to {self.maximum}.')


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def team_base(index):
    # The native pointer table skips a 260-byte buffer after team 9.
    if type(index) is not int or not 0 <= index < 28:
        raise SaveError('Unknown Tecmo Super Bowl team record.')
    return 0x7AE + index * 208 + (260 if index >= 9 else 0)


def checksum(raw):
    return (0x3412 + sum(raw[0x6C0:0xEFE]) + sum(raw[0x1002:0x1F72])) & 0xFFFF


@lru_cache(maxsize=4)
def qualify(raw):
    if len(raw) != SIZE or raw[0x6B7:0x6BE] != b'AKIHIKO':
        raise SaveError('Requires the compatible 8,192-byte 28-team Tecmo Super Bowl battery save.')
    if int.from_bytes(raw[0x6BE:0x6C0], 'little') != checksum(raw):
        raise SaveError('Tecmo Super Bowl native season checksum failed; damaged saves are not repaired.')


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select the Tecmo Super Bowl NES battery-save profile.')
    return FORMAT


def decode(raw, game_id=GAME_ID, source=Path('copy.sav')):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != SIZE:
        raise SaveError('Open a raw 8 KiB battery save, not a ROM or emulator state.')
    raw = bytes(raw)
    qualify(raw)
    return Document(FORMAT, Path(source), raw, raw)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.payload != document.raw):
        raise SaveError('The opened Tecmo Super Bowl snapshot was changed outside staging.')
    qualify(document.raw)


def _suffix(path):
    if path.suffix.lower() != '.sav':
        raise SaveError('Use a separate raw battery-save copy with the .sav extension.')
    return path.suffix.lower()


def read_save(path, game_id=GAME_ID):
    path = safe_path(path)
    _suffix(path)
    with path.open('rb') as stream:
        raw = stream.read(SIZE + 1)
    return decode(raw, game_id, path)


@lru_cache(maxsize=4)
def _fields(raw):
    result = {}
    for team in range(28):
        base, slot = team_base(team), team + 1
        group = f'Team {slot:02}'
        field = Field(f'team_{team}_control', 'Season control', 0x69B + team,
                      0, 2, 3, group + ' · Control', slot)
        result[field.id] = field
        for player, position in enumerate(POSITIONS):
            if player < 12 and injury_status(raw, base, player):
                # Native weekly condition updates force injured skill players to
                # Average. Preserve these dependent records, including unusual
                # opened conditions, rather than manufacture a better condition.
                continue
            field = Field(f'team_{team}_condition_{player}', position + ' condition',
                          base + 0xC8 + player // 4, 6 - 2 * (player % 4), 2, 3,
                          group + ' · Conditions', slot, maxable=True)
            result[field.id] = field
        for play in range(8):
            role = 'Run' if play < 4 else 'Pass'
            shift = 4 if play % 2 == 0 else 0
            if ((raw[base + 0xBD + play // 2] >> shift) & 15) > 7:
                # The native loader adds the full nibble to the slot's base ID.
                # Unknown choices cannot safely be presented as ordinary plays.
                continue
            field = Field(f'team_{team}_play_{play}', f'{role} slot {play % 4 + 1} choice',
                          base + 0xBD + play // 2, shift, 4, 7,
                          group + ' · Playbook', slot)
            result[field.id] = field
    return MappingProxyType(result)


def field_map(document):
    validate_document(document)
    return _fields(document.payload)


def fields_for(document):
    return tuple(field_map(document).values())


def changed_payload(document, changes):
    fields = field_map(document)
    if not isinstance(changes, Mapping):
        raise SaveError('Edits require a field/value mapping.')
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('Unknown Tecmo Super Bowl field.')
        field = fields[key]
        field.validate(value)
        mask = ((1 << field.bits) - 1) << field.shift
        output[field.offset] = (output[field.offset] & ~mask) | (value << field.shift)
    return bytes(output)


def stage(document, changes, key, value):
    changed_payload(document, changes)
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Unknown Tecmo Super Bowl field.')
    field = field_map(document)[key]
    field.validate(value)
    result = dict(changes)
    if value == field.value(document.payload):
        result.pop(key, None)
    else:
        result[key] = value
    return result


def serialize(document, changes):
    raw = changed_payload(document, changes)
    if raw == document.raw:
        return document.raw
    output = bytearray(raw)
    output[0x6BE:0x6C0] = checksum(output).to_bytes(2, 'little')
    return decode(output).raw


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def field_options(document, key):
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Unknown Tecmo Super Bowl field.')
    if '_condition_' in key:
        return tuple(enumerate(CONDITIONS))
    if key.endswith('_control'):
        return tuple(enumerate(CONTROLS))
    play = int(key.rsplit('_', 1)[1])
    return tuple((choice, f'Choice {choice + 1} (play ID {play * 8 + choice})')
                 for choice in range(8))


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    result = {}
    for key in keys:
        if type(key) is not str or key not in field_map(document):
            raise SaveError('Unknown Tecmo Super Bowl field.')
        field = field_map(document)[key]
        if field.maxable:
            result[key] = max(field.value(document.payload), changes.get(key, 0), field.maximum)
    return result


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    result = dict(changes)
    for field in fields_for(document):
        if field.maxable and (group is None or field.group == group):
            result = stage(document, result, field.id, field.maximum)
    return result


def _validate_source(document):
    source = safe_path(document.source)
    try:
        with source.open('rb') as stream:
            current = stream.read(SIZE + 1)
    except OSError as error:
        raise SaveError('The opened battery-save copy is unavailable; reopen it.') from error
    if current != document.raw:
        raise SaveError('The opened battery-save copy changed on disk; reopen it.')
    return source


def backup(document):
    validate_document(document)
    source = _validate_source(document)
    return snapshot_backup(document.raw, source, GAME_ID,
                           safe_path(source.parent / 'WarriorsEditorBackups'))


def save_as(document, changes, destination):
    validate_document(document)
    destination = safe_path(destination)
    _suffix(destination)
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    _validate_source(document)
    raw = serialize(document, changes)
    backup(document)
    _validate_source(document)
    atomic_new(raw, destination)
    return decode(raw, source=destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    backup_path, destination = safe_path(backup_path), safe_path(destination)
    suffix = _suffix(backup_path)
    if _suffix(destination) != suffix:
        raise SaveError('Restore with the same battery-save extension as the backup.')
    return restore_snapshot(backup_path, destination, GAME_ID, suffix, SIZE,
                            validate_raw=lambda raw: decode(raw))


def inspection_rows(document):
    validate_document(document)
    result = []
    for team in range(28):
        base = team_base(team)
        raw = document.payload
        result.append((f'Team {team + 1:02}', *raw[base + 0xB2:base + 0xB5],
                       raw[base + 0xBD:base + 0xC1].hex(' '),
                       raw[base + 0xC1:base + 0xC5].hex(' '),
                       raw[base + 0xC5:base + 0xC8].hex(' '),
                       raw[base + 0xC8:base + 0xD0].hex(' ')))
    return tuple(result)


def injury_status(raw, base, player):
    if player >= 12:
        return 0
    return (raw[base + 0xC5 + player // 4] >> (6 - 2 * (player % 4))) & 3


def player_records(document):
    validate_document(document)
    result = []
    injury_names = ('Healthy', 'Probable', 'Questionable', 'Doubtful')
    for team in range(28):
        base = team_base(team)
        for player, position in enumerate(POSITIONS):
            condition = (document.payload[base + 0xC8 + player // 4] >> (6 - 2 * (player % 4))) & 3
            injury = injury_status(document.payload, base, player)
            result.append((f'Team {team + 1:02}', position, CONDITIONS[condition],
                           injury_names[injury] if player < 12 else 'No injury record',
                           'Read only: injured' if injury else 'Editable'))
    return tuple(result)


def record_label(slot, group):
    return f'Team {slot:02}'


def field_hint(document, key):
    field_options(document, key)
    if '_condition_' in key:
        return 'Only healthy player conditions are editable. Condition changes temporary ability modifiers; injuries and base ROM abilities stay intact.'
    if '_play_' in key:
        return 'Each of the four run and four pass slots has its own eight choices. Select a choice within this slot.'
    return 'MAN controls play; COA calls plays; COM watches computer play; SKP simulates games. Season results stay intact.'
