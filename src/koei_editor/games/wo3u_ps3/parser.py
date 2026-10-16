"""Independent US PS3 Ultimate resource adapter. See docs/WO3U_PS3.md.

Published Apollo patch facts are reimplemented; no GPL source or player data is
included. Actual public PS3 exports were decrypted privately for qualification.
"""
from dataclasses import dataclass
from functools import lru_cache
from collections.abc import Mapping
import hashlib
from pathlib import Path

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.shared.copy_storage import atomic_new, snapshot_backup, restore_snapshot
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.ps3_export import savedata_directory, MAX_SFO_SIZE


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
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from {self.minimum:,} to {self.maximum:,}.')

    def encoded(self, value):
        self.validate(value)
        return value.to_bytes(self.size, 'little')


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
    context_digest: str = ''

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()

GAME_ID = 'wo3u_ps3'
TITLE_IDS = ('NPUB31505-SAVEDATA',)
SAVE_SIZE = 0x2119CA
REVISION = bytes.fromhex('f1180314')
OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT = 0xECF2, 0x2B0, 145
OFFICER_MARKER = bytes.fromhex('188dd000')
WEAPON_BASE, WEAPON_STRIDE, WEAPON_COUNT = 0xC8010, 0x1C, 2320
WEAPON_MARKER = bytes.fromhex('b88bd000')
MATERIAL_SPANS = ((0xE9A8, 16), (0xE9C8, 16), (0xE9E8, 16),
                  (0xEA08, 34), (0xEA3A, 34), (0xEA6C, 34), (0xEAA8, 145))
_static = [Field('growth_points', 'Unallocated growth points', 0x1378, 4, 9999999),
           Field('gems', 'Precious stones (gems)', 0x137C, 4, 999999)]
FORMAT = Format(GAME_ID, 'Warriors Orochi 3 Ultimate (PS3, US decrypted export)',
                SAVE_SIZE, tuple(_static),
                'US NPUB31505-SAVEDATA only. Keep original PARAM.SFO alongside '
                'the copied decrypted APP.BIN. Reimport/resign with Apollo; '
                'PARAM.PFD authentication is external. Story, ownership, '
                'level/EXP and promotion rewards remain unchanged. Rich systems '
                'are inspection-only pending field-specific native/load evidence.')


def qualify(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:4] != REVISION:
        raise SaveError('Requires a decrypted US PS3 Ultimate APP.BIN revision '
                        '0x140318F1 of 0x2119CA bytes.')
    _qualify_markers(raw)


@lru_cache(maxsize=8)
def _qualify_markers(raw):
    for base, stride, count, marker in ((OFFICER_BASE - 10, OFFICER_STRIDE, 150,
            OFFICER_MARKER), (WEAPON_BASE - 4, WEAPON_STRIDE, WEAPON_COUNT,
            WEAPON_MARKER)):
        if any(raw[base + index * stride:base + index * stride + 4] != marker
               for index in range(count)):
            raise SaveError('PS3 Ultimate serialized record markers failed. '
                            'PC, base WO3 and damaged layouts are rejected.')


def _context_raw(path):
    companion = safe_path(Path(path).parent / 'PARAM.SFO')
    try:
        with companion.open('rb') as stream:
            raw = stream.read(MAX_SFO_SIZE + 1)
    except FileNotFoundError as error:
        raise SaveError('Keep the original PARAM.SFO alongside this US PS3 '
                        'decrypted export and every edited/restored destination.') from error
    if savedata_directory(raw) not in TITLE_IDS:
        raise SaveError('Only US PS3 NPUB31505-SAVEDATA Ultimate is qualified.')
    return raw


def _context(path):
    # Detect changed owner/context metadata without extracting any account field
    # or including the metadata in a backup.
    return hashlib.sha256(_context_raw(path)).hexdigest()


def _require_opened_context(document, destination=None):
    if not document.context_digest or _context(document.source) != document.context_digest:
        raise SaveError('The opened export context changed. Reopen before copying or saving.')
    if destination is not None and _context(destination) != document.context_digest:
        raise SaveError('Use the same unchanged export context for the destination.')


def _require_opened_source(document):
    validate_document(document)
    _require_opened_context(document)
    with safe_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened copy changed on disk. Reopen it before saving or backing up.')


def prepare_copy_context(document, output_dir):
    """Keep opaque source metadata private beside shared self-test copies."""
    _require_opened_source(document)
    raw = _context_raw(document.source)
    if not document.context_digest or hashlib.sha256(raw).hexdigest() != document.context_digest:
        raise SaveError('The opened export context changed. Reopen before copying.')
    destination = safe_path(Path(output_dir) / 'PARAM.SFO')
    _require_opened_context(document)
    atomic_new(raw, destination)
    _require_opened_source(document)
    with destination.open('rb') as stream:
        if stream.read(MAX_SFO_SIZE + 1) != raw:
            raise SaveError('The prepared original export context changed during actual read-back.')


def seal(payload):
    # Firsthand PS3 direct-hex-edit evidence qualifies the two resource writes.
    # No game-internal checksum rewrite is evidenced for these fields. This is
    # not a global claim that no other gameplay region has native integrity.
    # PFD authentication/re-encryption remains external.
    return payload


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select this exact PS3 decrypted-export adapter.')
    return FORMAT


def decode(raw, game_id=GAME_ID, source=Path('copy.bin')):
    get_format(game_id)
    if type(raw) is not bytes:
        raise SaveError('A frozen decrypted PS3 byte snapshot is required.')
    qualify(raw)
    return Document(FORMAT, Path(source), raw, raw)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.bin':
        raise SaveError('Open a separate decrypted PS3 .bin export copy.')
    digest = _context(path)
    with path.open('rb') as stream:
        document = decode(stream.read(SAVE_SIZE + 1), game_id, path)
    if _context(path) != digest:
        raise SaveError('The export context changed while opening the copy. Reopen it.')
    return Document(FORMAT, path, document.raw, document.payload, digest)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload):
        raise SaveError('A frozen decrypted PS3 snapshot is required.')
    if type(document.context_digest) is not str:
        raise SaveError('Invalid PS3 export context snapshot.')
    qualify(document.raw)


def fields_for(document):
    validate_document(document)
    return FORMAT.fields

def field_map(document):
    return {field.id: field for field in fields_for(document)}


def changed_payload(document, changes):
    fields = field_map(document)
    if not isinstance(changes, Mapping):
        raise SaveError('Pending PS3 changes must be a field/value mapping.')
    result = bytearray(document.payload)
    for key, value in changes.items():
        if key not in fields:
            raise SaveError('This field is not qualified for the opened PS3 profile.')
        field = fields[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        result[field.offset:field.offset + field.size] = field.encoded(value)
    return bytes(result)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    raw = seal(payload)
    decode(raw, GAME_ID, document.source)
    return raw


def stage(document, changes, key, value):
    changed_payload(document, changes)
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
    fields = field_map(document)
    changed_payload(document, changes)
    for key in keys:
        if key not in fields:
            raise SaveError('This field is not qualified for the opened PS3 profile.')
    # Published cheat targets are manual editing bounds, not natural gameplay
    # caps. No automatic Max action is authorized by this source evidence.
    return {}


def maximums(document, changes, group=None):
    limit_values(document, changes, [f.id for f in fields_for(document)
                                   if group is None or f.group == group])
    return dict(changes)


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def backup(document):
    _require_opened_source(document)
    result = snapshot_backup(document.raw, document.source, GAME_ID,
                             document.source.parent / 'UniversalEditorBackups')
    # Retain a completed backup if the source/context changed during creation.
    _require_opened_source(document)
    return result


def save_as(document, changes, destination):
    validate_document(document)
    destination = safe_path(destination)
    if destination.suffix.lower() != '.bin':
        raise SaveError('Choose a new decrypted .bin copy destination.')
    _require_opened_context(document, destination)
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    _require_opened_source(document)
    raw = serialize(document, changes)
    backup(document)
    _require_opened_context(document, destination)
    _require_opened_source(document)
    atomic_new(raw, destination)
    reopened = read_save(destination)
    _require_opened_source(document)
    _require_opened_context(document, destination)
    if reopened.raw != raw or reopened.context_digest != document.context_digest:
        raise SaveError('The saved PS3 copy or export context changed during actual read-back.')
    return reopened


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    destination = safe_path(destination)
    digest = _context(destination)
    validated = []
    def validate_restore(raw):
        decode(raw, GAME_ID)
        if _context(destination) != digest:
            raise SaveError('The destination export context changed during restore.')
        validated.append(raw)
    result = restore_snapshot(backup_path, destination, GAME_ID, '.bin', SAVE_SIZE,
                              validate_raw=validate_restore)
    reopened = read_save(result)
    if (not validated or reopened.raw != validated[-1]
            or reopened.context_digest != digest or _context(result) != digest):
        raise SaveError('The restored PS3 copy or export context changed during actual read-back.')
    return result


def record_label(slot, group='Officers'):
    if group == 'Weapons' and slot:
        return f'Weapon record {slot}'
    return f'Officer slot {slot}' if slot else group


def field_hint(document, field):
    validate_document(document)
    return ('Only this balance changes; no EXP allocation, levels or rewards. '
            'Manual source-backed editing bound; automatic Max is disabled. '
            'Unknown/higher original values remain unchanged. Export a decrypted '
            'copy with Apollo; after editing, reimport and resign it with Apollo. '
            'Encrypted console files, PARAM.PFD signing and PC saves are not handled.')


# Console encryption/PFD authentication remains external to this file.
INTEGRITY_KIND = 'external'


def inspection_rows(document):
    validate_document(document)
    rows = []
    for index in range(150):
        base = OFFICER_BASE + index * OFFICER_STRIDE
        rows.append({'group': 'Progression',
                     'label': f'Officer slot {index + 1}' if index < 145 else f'Internal record {index + 1}',
                     'value': f'Life {int.from_bytes(document.payload[base:base + 2], "little")}; '
                              f'Musou {int.from_bytes(document.payload[base + 2:base + 4], "little")}; '
                              f'attack {int.from_bytes(document.payload[base + 4:base + 6], "little")}; '
                              f'defense {int.from_bytes(document.payload[base + 6:base + 8], "little")}; '
                              f'speed {int.from_bytes(document.payload[base + 8:base + 10], "little")}; '
                              f'stored level {document.payload[base + 17] + 1}; '
                              f'EXP {int.from_bytes(document.payload[base + 26:base + 30], "little")}; '
                              f'promotion count {document.payload[base + 62]}; '
                              f'equipment slots {document.payload[base + 44]} (read only)'})
    for index in range(WEAPON_COUNT):
        base = WEAPON_BASE + index * WEAPON_STRIDE
        identity = int.from_bytes(document.payload[base:base + 2], 'little')
        if identity == 65535:
            continue
        attributes = ', '.join(f'ID {attribute}: {document.payload[base + 12 + slot]}'
                               for slot, attribute in enumerate(document.payload[base + 4:base + 12])
                               if attribute != 255)
        rows.append({'group': 'Weapons', 'label': record_label(index + 1, 'Weapons'),
                     'value': f'Existing ID {identity}; slots {document.payload[base + 2]}; '
                              f'reinforcement {document.payload[base + 3]}; attributes {attributes or "none"}'})
    for index in range(58):
        rows.append({'group': 'Attribute orbs', 'label': f'Orb record {index + 1}',
                     'value': f'{document.payload[0xE944 + index]} (read only; name unqualified)'})
    for family, (base, count) in enumerate(MATERIAL_SPANS):
        for index in range(count):
            rows.append({'group': 'Crafting materials',
                         'label': f'Family {family + 1}, record {index + 1}',
                         'value': f'{document.payload[base + index]} (read only; name unqualified)'})
    rows.extend(({'group': 'Other resources', 'label': 'Crystal byte',
                  'value': f'{document.payload[0xD5DC]} (read only)'},
                 {'group': 'Other resources', 'label': 'Lottery-ticket byte',
                  'value': f'{document.payload[0xB0F1]} (read only)'}))
    return tuple(rows)
