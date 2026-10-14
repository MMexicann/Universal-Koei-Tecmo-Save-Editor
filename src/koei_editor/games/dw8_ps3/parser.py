"""Original US PS3 PSN Dynasty Warriors 8 native plaintext export.

Independently qualified against the complete Apollo NPUB31234 player export.
See docs/DW8_PS3_FORMAT.md. Console PFD authentication stays external.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.shared.copy_storage import (
    atomic_new,
    restore_snapshot,
    snapshot_backup,
)
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.ps3_export import MAX_SFO_SIZE, savedata_directory

GAME_ID = "dw8_ps3"
SAVE_SIZE = 0xA28A7
PAYLOAD_SIZE = SAVE_SIZE
TITLE_DIRECTORY = "NPUB31234-SAVEDATA"
SIGNATURE = bytes.fromhex("13011300")
INTEGRITY_KIND = "external"
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
    encoding: str = 'unsigned big-endian integer'
    evidence: str = 'Apollo NPUB31234 active native resource patches; complete original public export'

    @property
    def experimental_maximum(self):
        return (1 << (8 * self.size)) - 1

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'big')

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from 0 to the opened balance ({self.maximum}).')


BASE_FIELDS = ()


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = "Dynasty Warriors 8 (US PS3 PSN native NPUB31234)"
    size: int = SAVE_SIZE
    fields: tuple = BASE_FIELDS
    sample_verified: bool = True
    published_format: bool = True
    editing_verified: bool = False
    game_load_verified: bool = False
    note: str = (
        "Open a copied original US PS3 PSN APP.BIN decrypted from PARAM.PFD, "
        "with unchanged PARAM.SFO beside it. Existing Gold and Ambition-mode weapon/facility material reductions. "
        "Reimport and resign with Apollo; story, equipment ownership and EXP stay unchanged."
    )


FORMAT = Format()


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    context_digest: str = ""

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError("Select original US PS3 PSN Dynasty Warriors 8.")
    return FORMAT


def _path(path):
    lexical = Path(path).absolute()
    if any(part.is_symlink() for part in (lexical, *lexical.parents)):
        raise SaveError('Use a separate DW8 copy without symbolic-link aliases.')
    if lexical.is_file() and lexical.stat().st_nlink != 1:
        raise SaveError('Use a separate DW8 copy without hard-link aliases.')
    return safe_path(path)


@lru_cache(maxsize=8)
def _decode_bytes(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:4] != SIGNATURE:
        raise SaveError('Requires the exact 665,767-byte original US PS3 PSN DW8 APP.BIN revision 0x13011300.')
    # Native snapshot and active exact-title Apollo patches are already plaintext.
    # PFD decrypt/resign is external; no XL byte cipher or additive suffix applies.
    return raw


def decode(raw, game_id=GAME_ID, source=Path("APP.BIN")):
    get_format(game_id)
    if type(raw) is not bytes:
        raise SaveError("Immutable native save bytes are required.")
    return Document(FORMAT, Path(source), raw, _decode_bytes(raw))


def _context_raw(path):
    companion = _path(Path(path).parent / "PARAM.SFO")
    try:
        with companion.open("rb") as stream:
            metadata = stream.read(MAX_SFO_SIZE + 1)
    except FileNotFoundError as error:
        raise SaveError(
            "Keep the matching NPUB31234-SAVEDATA PARAM.SFO beside the copied APP.BIN; "
            "the gameplay payload does not independently identify its region."
        ) from error
    if savedata_directory(metadata) != TITLE_DIRECTORY:
        raise SaveError(
            "The copied PS3 context must identify exactly NPUB31234-SAVEDATA."
        )
    return metadata


def _context(path, required=False):
    if not required and not (Path(path).parent / "PARAM.SFO").exists():
        return ""
    return hashlib.sha256(_context_raw(path)).hexdigest()


def _require_opened_context(document, destination=None):
    if (
        not document.context_digest
        or _context(document.source, required=True) != document.context_digest
    ):
        raise SaveError(
            "The opened export context changed. Reopen before copying or saving."
        )
    if (
        destination is not None
        and _context(destination, required=True) != document.context_digest
    ):
        raise SaveError("Use the same unchanged export context for the destination.")


def prepare_copy_context(document, output_dir):
    """Copy required identity context opaquely into a private local test folder.

    The entire bounded original is preserved; only directory identity is parsed.
    This is export context, never rebuilt console metadata or signing support.
    """
    validate_document(document)
    metadata = _context_raw(document.source)
    if (
        not document.context_digest
        or hashlib.sha256(metadata).hexdigest() != document.context_digest
    ):
        raise SaveError("The opened export context changed. Reopen before copying.")
    destination = _path(Path(output_dir) / "PARAM.SFO")
    if destination.exists():
        raise FileExistsError(
            "Self-test context must have a new PARAM.SFO destination."
        )
    _require_opened_context(document)
    return atomic_new(metadata, destination)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _path(path)
    if path.suffix.lower() != ".bin":
        raise SaveError("Open a separate PFD-decrypted PS3 APP.BIN copy.")
    digest = _context(path, required=True)
    with path.open("rb") as stream:
        document = decode(stream.read(SAVE_SIZE + 1), game_id, path)
    if _context(path, required=True) != digest:
        raise SaveError("The export context changed while opening. Reopen it.")
    return replace(document, context_digest=digest)


def validate_document(document):
    if (
        type(document) is not Document
        or document.format is not FORMAT
        or not isinstance(document.source, Path)
        or type(document.raw) is not bytes
        or type(document.payload) is not bytes
        or type(document.context_digest) is not str
        or _decode_bytes(document.raw) != document.payload
    ):
        raise SaveError("An immutable native PS3 DW8 snapshot is required.")


def fields_for(document):
    validate_document(document)
    return tuple(Field(key, label + ' (reduce only)', offset, size,
                       int.from_bytes(document.payload[offset:offset + size], 'big'))
                 for key, label, offset, size in (
                     ('gold', 'Gold', 0xBD, 4),
                     ('facility_materials', 'Ambition facility materials', 0x21CF9, 2),
                     ('weapon_materials', 'Ambition weapon materials', 0x21CFB, 2)))


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def changed_payload(document, changes):
    if not isinstance(changes, Mapping):
        raise SaveError("Pending edits must be a field/value mapping.")
    mapping = field_map(document)
    result = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in mapping:
            raise SaveError(
                "Only qualified original US PS3 DW8 fields are writable."
            )
        field = mapping[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        field.validate(value)
        result[field.offset : field.offset + field.size] = value.to_bytes(
            field.size, "big"
        )
    return bytes(result)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    if _decode_bytes(payload) != payload:
        raise SaveError('Native original PS3 DW8 edited copy read-back failed.')
    return payload


def stage(document, changes, key, value):
    changed_payload(document, changes)
    mapping = field_map(document)
    if type(key) is not str or key not in mapping:
        raise SaveError("This field is not qualified in the opened PS3 copy.")
    field = mapping[key]
    result = dict(changes)
    if type(value) is int and value == field.value(document.payload):
        result.pop(key, None)
    else:
        field.validate(value)
        result[key] = value
    return result


def limit_values(document, changes, keys):
    mapping = field_map(document)
    changed_payload(document, changes)
    try:
        requested = tuple(keys)
    except TypeError as error:
        raise SaveError(
            "A sequence of qualified string field IDs is required."
        ) from error
    if any(type(key) is not str or key not in mapping for key in requested):
        raise SaveError("This field is not qualified in the opened PS3 copy.")
    return {}


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)


def review(document, changes):
    changed_payload(document, changes)
    return [
        (field, field.value(document.payload), changes[field.id])
        for field in fields_for(document)
        if field.id in changes
    ]


def _validate_source(document):
    validate_document(document)
    _require_opened_context(document)
    source = _path(document.source)
    with source.open("rb") as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError(
                "The opened copy changed on disk. Reopen before backing up or saving."
            )
    return source


def backup(document):
    source = _validate_source(document)
    snapshot = snapshot_backup(
        document.raw, source, GAME_ID, source.parent / "UniversalEditorBackups"
    )
    metadata = {
        "game_id": GAME_ID,
        "kind": "dw8-ps3-export-context",
        "context_sha256": document.context_digest,
        "save_sha256": document.sha256,
    }
    try:
        atomic_new(
            json.dumps(metadata).encode("utf-8"),
            snapshot.with_name(snapshot.name + ".context.json"),
        )
    except Exception:
        snapshot.unlink(missing_ok=True)
        snapshot.with_suffix(".json").unlink(missing_ok=True)
        raise
    return snapshot


def save_as(document, changes, destination):
    validate_document(document)
    destination = _path(destination)
    if destination.suffix.lower() != ".bin":
        raise SaveError("Choose a new native PS3 .bin copy destination.")
    _require_opened_context(document, destination)
    if destination.exists():
        raise FileExistsError("Choose a new file; existing files are never replaced.")

    def check_source():
        with _path(document.source).open("rb") as stream:
            if stream.read(SAVE_SIZE + 1) != document.raw:
                raise SaveError(
                    "The opened copy changed on disk. Reopen before saving."
                )

    check_source()
    raw = serialize(document, changes)
    backup(document)
    _require_opened_context(document, destination)
    check_source()
    atomic_new(raw, destination)
    _require_opened_context(document, destination)
    reopened = read_save(destination)
    if reopened.raw != raw or reopened.context_digest != document.context_digest:
        raise SaveError("The written DW8 copy or its original export context changed during read-back.")
    _require_opened_context(document, destination)
    return reopened


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    destination, backup_path = _path(destination), _path(backup_path)
    digest = _context(destination, required=True)
    try:
        companion = _path(backup_path.with_name(backup_path.name + ".context.json"))
        with companion.open("rb") as stream:
            raw_metadata = stream.read(1025)
        if len(raw_metadata) > 1024:
            raise SaveError("DW8 backup context metadata is too large.")
        metadata = json.loads(raw_metadata)
    except (OSError, ValueError, UnicodeError) as error:
        raise SaveError(
            "DW8 backup context metadata is missing or damaged."
        ) from error
    if (
        type(metadata) is not dict
        or metadata.get("game_id") != GAME_ID
        or metadata.get("kind") != "dw8-ps3-export-context"
        or metadata.get("context_sha256") != digest
        or type(metadata.get("save_sha256")) is not str
        or len(metadata["save_sha256"]) != 64
    ):
        raise SaveError("Restore requires the same original PARAM.SFO as the backup.")

    def validate_restore(raw):
        decode(raw, GAME_ID)
        if hashlib.sha256(raw).hexdigest() != metadata["save_sha256"]:
            raise SaveError(
                "The backup context belongs to another native save snapshot."
            )
        if _context(destination, required=True) != digest:
            raise SaveError("The export context changed during restore.")

    restored = restore_snapshot(
        backup_path,
        destination,
        GAME_ID,
        ".bin",
        SAVE_SIZE,
        validate_raw=validate_restore,
    )
    if _context(destination, required=True) != digest:
        raise SaveError("The original export context changed after restore.")
    reopened = read_save(restored, game_id)
    if (reopened.context_digest != digest or reopened.sha256 != metadata["save_sha256"]
            or _context(destination, required=True) != digest):
        raise SaveError("The restored DW8 copy or its original export context changed during read-back.")
    return restored


def record_label(slot, group='Resources'):
    return group


def field_hint(document, field):
    validate_document(document)
    return ('Reduce only the opened resource balance. Max is disabled; fame, officer '
            'levels/EXP, unlocking, equipment and facility tiers stay intact. '
            'Reimport and resign with Apollo; keep the original PARAM.SFO unchanged.')


def inspection_rows(document):
    validate_document(document)
    return (('Original US PSN export', TITLE_DIRECTORY),
            ('Native revision', '0x13011300'),
            ('Game data bytes', len(document.raw)),
            ('Ambition fame (read only)', int.from_bytes(document.payload[0x221D5:0x221D7], 'big')))
