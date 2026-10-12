"""Contributor scaffold. Unregistered and deliberately rejects unmapped saves.

Rename this file and replace the explicit format/codec seams using evidence.
Do not publish the placeholder as supported or use it to manufacture saves.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path

from koei_editor.shared.copy_storage import atomic_new, snapshot_backup, restore_snapshot
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'new_game_pc'
EXTENSION = '.dat'


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int  # Validated exact size or evidence-based bounded read ceiling.
    fields: tuple
    sample_verified: bool = False
    note: str = 'Unmapped contributor scaffold; no support claim.'


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    # Add frozen container metadata/seeds here; preserve them when encoding.

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


FORMAT = Format(GAME_ID, 'New game / exact platform and revision', 0, ())


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Choose this explicitly registered game/platform.')
    return FORMAT


def _decode_snapshot(raw):
    # Validate native title/revision, size, structures and all integrity before
    # returning a payload. Store any codec/container metadata in Document.
    raise SaveError('Native format qualification has not been implemented.')


def _encode_snapshot(document, payload):
    # Preserve opaque bytes/seeds/container data; recompute mapped integrity.
    raise SaveError('Native surgical encoding has not been implemented.')


def decode(raw, game_id=GAME_ID, source=Path('copy.dat')):
    layout = get_format(game_id)
    if type(raw) is not bytes or not 0 < len(raw) <= layout.size:
        raise SaveError('A qualified native save size is required.')
    return Document(layout, Path(source), raw, _decode_snapshot(raw))


def _copy_path(path):
    path = safe_path(path)
    if path.suffix.lower() != EXTENSION:
        raise SaveError(f'Choose an explicit {EXTENSION} save copy.')
    return path


def read_save(path, game_id=GAME_ID):
    layout = get_format(game_id)
    path = _copy_path(path)
    with path.open('rb') as stream:
        return decode(stream.read(layout.size + 1), game_id, path)


def validate_document(document):
    if not isinstance(document, Document) or document.format != FORMAT:
        raise SaveError('The snapshot belongs to a different game/platform.')
    if decode(document.raw, GAME_ID, document.source).payload != document.payload:
        raise SaveError('The immutable decoded snapshot was modified.')


def fields_for(document):
    validate_document(document)
    # Dynamic fields must describe existing validated occupied records only.
    return FORMAT.fields


def field_map(document):
    return {field.id: field for field in fields_for(document)}


def stage(document, changes, key, value):
    fields = field_map(document)
    changes = normalize_pending_values(document, changes, fields)
    if type(key) is not str or key not in fields:
        raise SaveError('This field is not mapped for the opened save.')
    result = dict(changes)
    opened = fields[key].value(document.payload)
    if type(value) is type(opened) and value == opened:
        result.pop(key, None)
    else:
        fields[key].validate(value)
        result[key] = value
    return result


def limit_values(document, changes, keys):
    fields, result = field_map(document), {}
    changes = normalize_pending_values(document, changes, fields)
    for key in keys:
        if type(key) is not str or key not in fields:
            raise SaveError('This field is not mapped for the opened save.')
        field = fields[key]
        if getattr(field, 'maxable', True) and changes.get(key, field.value(document.payload)) <= field.maximum:
            result[key] = field.maximum
    return result


def maximums(document, changes, group=None):
    changes = normalize_pending_values(document, changes, field_map(document))
    result = dict(changes)
    keys = [field.id for field in fields_for(document) if group is None or field.group == group]
    for key, value in limit_values(document, changes, keys).items():
        result = stage(document, result, key, value)
    return result


def changed_payload(document, changes):
    fields = field_map(document)
    changes = normalize_pending_values(document, changes, fields)
    output = bytearray(document.payload)
    for key, value in changes.items():
        if key not in fields:
            raise SaveError('This field is not mapped for the opened save.')
        field = fields[key]
        field.validate(value)
        # Replace only after verifying this field's actual storage encoding.
        raise SaveError('Mapped field storage encoding has not been implemented.')
    return bytes(output)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    raw = _encode_snapshot(document, payload)
    if decode(raw, GAME_ID, document.source).payload != payload:
        raise SaveError('Edited save failed native read-back verification.')
    return raw


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def backup(document):
    validate_document(document)
    return snapshot_backup(document.raw, document.source, GAME_ID)


def save_as(document, changes, destination):
    validate_document(document)
    destination = _copy_path(destination)
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    if read_save(document.source).raw != document.raw:
        raise SaveError('The opened copy changed on disk. Reopen it first.')
    raw = serialize(document, changes)
    backup(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    layout = get_format(game_id)
    read_save(backup_path, game_id)
    return restore_snapshot(backup_path, destination, game_id, EXTENSION, layout.size)
