"""Copy-only Origins Steam slot editor, qualified against native serialization.

Only independently mapped fields are writable. See ORIGINS_FORMAT.md for native
revision lengths, serializer offsets, limits and the intentionally unknown data.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

import koei_editor.games.origins.origins_codec as codec
from koei_editor.games.origins.origins_progression import progression_specs
from koei_editor.games.origins.origins_weapons import weapon_specs, weapon_inspection_rows, weapon_hint, validate_weapon_changes
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.experimental_limits import within_numeric_limits, experimental_enabled


GAME_ID = 'origins'
MAX_FILE_SIZE = codec.SLOT_FILE_SIZE
REVISION_LENGTHS = MappingProxyType({16: 0x214ed, 17: 0x214ee, 29: 0x22b5d})


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
    maxable: bool = True

    @property
    def experimental_maximum(self):
        """Largest representable numeric value; protected choices stay bounded."""
        if self.id.startswith('battle_history_'):
            return None
        return (1 << (8 * self.size)) - 1

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    def validate(self, value):
        if not within_numeric_limits(value, self.minimum, self.maximum,
                                     storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from '
                            f'{self.minimum:,} to {self.maximum:,}.')


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = True


FORMAT = Format(GAME_ID, 'Dynasty Warriors: Origins (Steam PC)', MAX_FILE_SIZE,
                (Field('gold', 'Gold', 0x69b, 4, 999999),
                 Field('skill_points', 'Skill Points', 0xa87, 2, 999),
                 Field('dlc_skill_points', 'DLC Skill Points', 0x21f1a, 2, 999)),
                'Native Steam slot revisions 16, 17 and 29. Gold: 0–999,999; '
                'unspent Skill Points: 0–999 per pool (DLC pool in revision 29). '
                'Existing bond levels, provincial peace and qualified weapon '
                'upgrades are editable. Other progression and USER.dat are preserved.')


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    seed: int
    revision: int

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('This adapter handles Dynasty Warriors: Origins Steam PC slots only.')
    return FORMAT


def _qualify(payload):
    # These lengths were calculated from all 72 native serializers and their
    # configuration counts, independently of the copied saves. An envelope
    # checksum alone cannot identify the title or supported schema revision.
    if len(payload) != MAX_FILE_SIZE - codec.HEADER_SIZE:
        raise SaveError('Origins requires a complete SLOT save; USER.dat is system data.')
    length, revision = struct.unpack_from('<II', payload, 0x660)
    if revision not in REVISION_LENGTHS:
        raise SaveError(f'Unsupported Origins slot revision {revision}; no changes were made.')
    if length != REVISION_LENGTHS[revision]:
        raise SaveError('Origins serialized length does not match the native revision layout.')
    return revision


@lru_cache(maxsize=3)
def _snapshot(raw):
    try:
        envelope = codec.decode(raw, 'slot')
    except codec.SaveFormatError as error:
        raise SaveError(f'Origins save integrity check failed: {error}') from error
    return envelope.payload, envelope.seed, _qualify(envelope.payload)


def decode(raw, game_id=GAME_ID, source=Path('copy.dat')):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != MAX_FILE_SIZE:
        raise SaveError('Open a copied Origins SLOT0000–SLOT0008.dat save, not USER.dat.')
    raw = bytes(raw)
    payload, seed, revision = _snapshot(raw)
    return Document(FORMAT, Path(source), raw, payload, seed, revision)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.casefold() != '.dat':
        raise SaveError('Choose a separate Origins .dat slot copy.')
    with path.open('rb') as stream:
        raw = stream.read(MAX_FILE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if not isinstance(document, Document) or document.format != FORMAT:
        raise SaveError('Unregistered Origins save document.')
    if (type(document.raw) is not bytes or type(document.payload) is not bytes or
            type(document.seed) is not int or type(document.revision) is not int):
        raise SaveError('The Origins snapshot requires immutable bytes and native integer metadata.')
    payload, seed, revision = _snapshot(document.raw)
    if (document.payload, document.seed, document.revision) != (payload, seed, revision):
        raise SaveError('The Origins snapshot changed outside the edit workflow.')


def _fields(payload, revision):
    return _fields_cached(payload, revision, experimental_enabled())


@lru_cache(maxsize=3)
def _fields_cached(payload, revision, _experimental):
    resources = FORMAT.fields if revision == 29 else FORMAT.fields[:2]
    return resources + tuple(Field(**spec) for spec in progression_specs(payload, revision)) + tuple(
        Field(**spec) for spec in weapon_specs(payload, revision))


def fields_for(document):
    # The cached native snapshot keeps repeated GUI staging inexpensive while
    # preventing forged revision metadata from exposing absent DLC fields.
    validate_document(document)
    return _fields(document.payload, document.revision)


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def _validate_pending(document, fields, changes):
    if not isinstance(changes, Mapping):
        raise SaveError('Origins pending edits require a mapping of field names to values.')
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('The requested Origins field is not mapped.')
        if type(value) is not int or value != fields[key].value(document.payload):
            fields[key].validate(value)


def stage(document, changes, key, value):
    fields = field_map(document)
    _validate_pending(document, fields, changes)
    if type(key) is not str or key not in fields:
        raise SaveError('The requested Origins field is not mapped.')
    result = dict(changes)
    if type(value) is int and value == fields[key].value(document.payload):
        result.pop(key, None)
    else:
        fields[key].validate(value)
        result[key] = value
    return result


def changed_payload(document, changes):
    validate_document(document)
    fields = field_map(document)
    _validate_pending(document, fields, changes)
    validate_weapon_changes(document.payload, document.revision, changes)
    output = bytearray(document.payload)
    for key, value in changes.items():
        if key not in fields:
            raise SaveError('The requested Origins field is not mapped.')
        field = fields[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        field.validate(value)
        output[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    return bytes(output)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    try:
        raw = codec.encode(payload, document.seed, 'slot')
    except codec.SaveFormatError as error:
        raise SaveError(f'Origins output encoding failed: {error}') from error
    reopened = decode(raw, GAME_ID, document.source)
    if (reopened.payload, reopened.seed, reopened.revision) != (payload, document.seed, document.revision):
        raise SaveError('Origins edited copy failed decode read-back verification.')
    return raw


def limit_values(document, changes, keys):
    fields = field_map(document)
    _validate_pending(document, fields, changes)
    result = {}
    for key in keys:
        if type(key) is not str or key not in fields:
            raise SaveError('The requested Origins field is not mapped.')
        field = fields[key]
        current = changes.get(key, field.value(document.payload))
        if field.maxable and type(current) is int and field.minimum <= current <= field.maximum:
            result[key] = field.maximum
    return result


def maximums(document, changes, group=None):
    _validate_pending(document, field_map(document), changes)
    result = dict(changes)
    keys = [field.id for field in fields_for(document) if group is None or field.group == group]
    for key, value in limit_values(document, changes, keys).items():
        result = stage(document, result, key, value)
    return result


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def _unchanged_source(document):
    validate_document(document)
    source = safe_path(document.source)
    with source.open('rb') as stream:
        current = stream.read(MAX_FILE_SIZE + 1)
    if current != document.raw:
        raise SaveError('The opened Origins copy changed on disk. Reopen it before saving or backing up.')
    return source


def backup(document):
    source = _unchanged_source(document)
    result = snapshot_backup(document.raw, source, GAME_ID,
                             safe_path(source.parent / 'WarriorsEditorBackups'))
    _unchanged_source(document)
    return result


def save_as(document, changes, destination):
    destination = safe_path(destination)
    if destination.suffix.casefold() != '.dat':
        raise SaveError('Choose a new .dat destination.')
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    _unchanged_source(document)
    raw = serialize(document, changes)
    backup(document)
    _unchanged_source(document)
    atomic_new(raw, destination)
    try:
        _unchanged_source(document)
        reopened = read_save(destination)
        if reopened.raw != raw:
            raise SaveError('The Origins destination differs from the verified edit.')
        _unchanged_source(document)
    except Exception:
        # Only remove the exact copy we just created. A destination changed by
        # another process is retained; neither an opened input nor a preexisting
        # file is ever removed by this cleanup.
        try:
            with destination.open('rb') as stream:
                ours = stream.read(MAX_FILE_SIZE + 1) == raw
            if ours:
                destination.unlink()
        except OSError:
            pass
        raise
    return reopened


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    backup_path, destination = safe_path(backup_path), safe_path(destination)
    read_save(backup_path, game_id)
    return restore_snapshot(backup_path, destination, GAME_ID, '.dat', MAX_FILE_SIZE,
                            validate_raw=lambda raw: decode(raw, GAME_ID, backup_path))


def field_hint(document, key):
    if key not in field_map(document):
        raise SaveError('The requested Origins field is not mapped.')
    if key in ('skill_points', 'dlc_skill_points'):
        pool = 'DLC' if key == 'dlc_skill_points' else 'Base-game'
        return (pool + ' unspent Skill Points: 0–999. Learned skills and derived '
                'abilities are preserved. The DLC has a separate point pool.')
    if key.startswith('weapon_'):
        return weapon_hint()
    if key.startswith('peace_'):
        opened = field_map(document)[key].value(document.payload) / 100
        return (f'Opened provincial peace: {opened:g}%. Enter 0–10,000 points; '
                '100 points = 1% and 10,000 = 100%. '
                'Peace rewards and their claim flags are preserved. At full peace, '
                'the game may stop offering provincial skirmishes.')
    if key.startswith('bond_'):
        return ('Existing bond only. Level 1–5; training count 0–999. '
                'The completion predicate needs level 5 and at least 3 trainings, '
                'plus other event and reward conditions. Training count is excluded '
                'from Max. Conversations, requests and learned arts are preserved.')
    if key.startswith('battle_history_'):
        return ('Persistent battle history: 0 = incomplete; 1 = cleared. You can '
                'mark a supported battle cleared. This is excluded from Max and '
                'does not finish the active campaign, establish endings, grant '
                'rewards or change story event flags.')
    return 'Gold: 0–999,999. Native merchant balance; lifetime statistics and story data are preserved.'


def inspection_rows(document):
    validate_document(document)
    return ({'group': 'Format', 'label': 'Native slot revision', 'value': document.revision},
            {'group': 'Format', 'label': 'Serialized block length',
             'value': REVISION_LENGTHS[document.revision]}) + tuple(
                 {'group': field.group, 'label': field.label, 'value': field.value(document.payload)}
                 for field in fields_for(document)) + weapon_inspection_rows(document.payload, document.revision)

# Integrity validated by this backend, separately from sample qualification.
INTEGRITY_KIND = 'checksum'
