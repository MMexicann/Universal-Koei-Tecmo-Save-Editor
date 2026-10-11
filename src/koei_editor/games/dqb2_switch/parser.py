"""Qualified Switch CMNDAT records with a separately bound document identity.

Complete native Switch exports establish the same byte layout as the reviewed
original PC writer. Shared scalar/codec operations do not probe other games or
accept another adapter's documents/backups. See docs/DQB2_SWITCH_FORMAT.md.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib

from koei_editor.games.dqb2_pc import parser as family
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup

GAME_ID = 'dqb2_switch'
EXTENSION = '.bin'
HEADER_SIZE = family.HEADER_SIZE
BODY_SIZE = family.BODY_SIZE
SAVE_SIZE = family.PADDED_SIZE
MAX_SIZE = SAVE_SIZE
INTEGRITY_KIND = 'checksum'
Field = family.Field
ORDINARY_ITEMS = family.ORDINARY_ITEMS


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Dragon Quest Builders 2 (original Nintendo Switch CMNDAT)'
    size: int = SAVE_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = ('Extracted original Switch CMNDAT.BIN revision 0x40004: reduce '
                 'existing named medicine/seed stacks, preserving at least one. '
                 'Search pockets/bag and inspect player/equipment status. Reimport '
                 'with a console save manager, retaining all original slot companions. '
                 'This does not decrypt/sign console saves or transfer save ownership.')


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
        raise SaveError('Select the original Nintendo Switch Dragon Quest Builders 2 profile.')
    return FORMAT


def _qualify(raw):
    if (type(raw) is not bytes or len(raw) != SAVE_SIZE
            or raw[:16] != bytes.fromhex('61657243020100020400040002020000')):
        raise SaveError('Requires the qualified complete extracted Switch CMNDAT revision 0x40004 profile.')


def decode(raw, game_id=GAME_ID, source=Path('CMNDAT.BIN')):
    get_format(game_id)
    _qualify(raw)
    decoded = family.decode(raw, family.GAME_ID, source)
    return Document(FORMAT, Path(source), raw, decoded.payload)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    # Use the reviewed family copy-path policy as well as native zlib gates;
    # Switch selection must not accidentally access a live PC/cloud save.
    path = _destination(path)
    with path.open('rb') as stream:
        raw = stream.read(MAX_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes):
        raise SaveError('A frozen original Switch CMNDAT snapshot is required.')
    _qualify(document.raw)
    if family.decode(document.raw).payload != document.payload:
        raise SaveError('The Switch CMNDAT snapshot no longer matches its original decoded bytes.')


def _family_view(document):
    """Internal immutable view for the explicitly qualified shared record writer."""
    validate_document(document)
    return family.Document(family.FORMAT, document.source, document.raw, document.payload)


def fields_for(document):
    return family.fields_for(_family_view(document))


def field_map(document):
    return family.field_map(_family_view(document))


def changed_payload(document, changes):
    return family.changed_payload(_family_view(document), changes)


def serialize(document, changes):
    output = family.serialize(_family_view(document), changes)
    # The shared writer preserves the original native padded capacity. Require
    # that edited output remains within this separately qualified Switch scope.
    _qualify(output)
    return output


def stage(document, changes, key, value):
    return family.stage(_family_view(document), changes, key, value)


def limit_values(document, changes, keys):
    return family.limit_values(_family_view(document), changes, keys)


def maximums(document, changes, group=None):
    return family.maximums(_family_view(document), changes, group)


def review(document, changes):
    return family.review(_family_view(document), changes)


def _source(document):
    validate_document(document)
    current = read_save(document.source)
    if current.raw != document.raw:
        raise SaveError('The original Switch CMNDAT copy changed. Reopen it before saving.')
    return current.source


def backup(document):
    source = _source(document)
    return snapshot_backup(document.raw, source, GAME_ID, source.parent / 'UniversalEditorBackups')


def _destination(path):
    # Qualified family path guards are used without parsing an absent target.
    return family._copy_path(path)


def save_as(document, changes, destination):
    source = _source(document)
    destination = _destination(destination)
    if source == destination or destination.exists():
        raise FileExistsError('Choose a new file; original and existing Switch saves are never replaced.')
    output = serialize(document, changes)
    backup(document)
    _source(document)
    atomic_new(output, destination)
    return read_save(destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(_destination(backup_path), _destination(destination), GAME_ID,
                            EXTENSION, SAVE_SIZE, validate_raw=lambda raw: decode(raw))


def record_label(slot, group='Bag'):
    return family.record_label(slot, group)


def item_records(document):
    return family.item_records(_family_view(document))


def player_records(document):
    return family.player_records(_family_view(document))
