"""Independent source-backed PS3 adapter. See docs/PS3_EXPANSION.md.

Published Apollo patch facts are reimplemented; no GPL source or player data is
included. Actual public PS3 exports were decrypted privately for qualification.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path

from koei_editor.games.dw3.models import SaveError
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

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'big')

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
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

GAME_ID = 'dw7e_ps3'
TITLE_IDS = ('NPUB30846-SYSTEM',)
SAVE_SIZE = 0x1D8C6
REVISION = bytes.fromhex('12072200')
FORMAT = Format(GAME_ID, 'Dynasty Warriors 7 Empires (PS3, US system export)',
                SAVE_SIZE, (Field('bonus_points', 'Bonus points', 0xA54, 4, 99999),),
                'Open a copied, decrypted US PS3 SYSTEM DATA.BIN export. Edit bonus '
                'points, then reimport and resign with Apollo. Campaign saves are '
                'not supported by this system profile; automatic Max is unavailable.')


def qualify(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:4] != REVISION:
        raise SaveError('Requires a decrypted PS3 DW7 Empires US SYSTEM DATA.BIN revision 0x12072200 '
                        'of 0x1D8C6 bytes. Encrypted exports and PC saves are rejected.')


def seal(payload):
    # These source-backed patches have no game-internal checksum operation;
    # PS3 encryption and PFD authentication are external to the decrypted file.
    return payload


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
    validate_optional_context(path, TITLE_IDS, exact=True)
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
    return bytes(result)


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
    validate_optional_context(document.source, TITLE_IDS, exact=True)
    validate_optional_context(destination, TITLE_IDS, exact=True)
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
    validate_optional_context(safe_path(destination), TITLE_IDS, exact=True)
    return restore_snapshot(backup_path, destination, GAME_ID, '.bin', SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, GAME_ID))


def record_label(slot, group='Officers'):
    return f'Officer slot {slot}' if slot else group


def field_hint(document, field):
    validate_document(document)
    return ('Manual source-backed editing bound; automatic Max is disabled. '
            'Unknown/higher original values remain unchanged. Export a decrypted '
            'copy with Apollo; after editing, reimport and resign it with Apollo. '
            'Encrypted console files, PARAM.PFD signing and PC saves are not handled.')


# Console encryption/PFD authentication remains external to this file.
INTEGRITY_KIND = 'external'
