"""US PS3 DW8 XL native byte-cipher export, distinct from PC outer framing.

Independently qualified against the complete Apollo NPUB31449 player export.
See docs/DW8XL_PS3_FORMAT.md. Console PFD authentication stays external.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw3.game_content import DW8_ATTRIBUTE_NAMES
from koei_editor.shared.verified_editor import DW8_FIELDS, DW8_RANKED_ATTRIBUTES, Field
from koei_editor.shared.experimental_limits import experimental_enabled
from koei_editor.shared.koei_codec import byte_cipher
from koei_editor.shared.copy_storage import (
    atomic_new,
    restore_snapshot,
    snapshot_backup,
)
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.ps3_export import MAX_SFO_SIZE, savedata_directory

GAME_ID = "dw8xl_ps3"
SAVE_SIZE = 0xB7F45
PAYLOAD_SIZE = SAVE_SIZE - 1
TITLE_DIRECTORY = "NPUB31449-SAVEDATA"
SIGNATURE = bytes.fromhex("f002101309")
INTEGRITY_KIND = "checksum"
WEAPON_BASE, WEAPON_STRIDE, WEAPON_COUNT = 0xE715, 0x18, 1830
# The published PS3 patch explicitly corroborates resources, stats, the four
# aptitude bytes and six attribute-rank bytes. Reuse our scalar descriptors,
# excluding automatic Max: patch targets alone do not establish native caps.
BASE_FIELDS = tuple(replace(field, maxable=False) for field in DW8_FIELDS)


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = "Dynasty Warriors 8 Xtreme Legends (US PS3 PSN native NPUB31449)"
    size: int = SAVE_SIZE
    fields: tuple = BASE_FIELDS
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = (
        "Open a copied original US PS3 PSN APP.BIN decrypted from PARAM.PFD, "
        "with unchanged PARAM.SFO beside it. Gold, gems, materials, stored officer "
        "stats, weapon-action compatibility and existing weapon attribute ranks. "
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
        raise SaveError("Select original US PS3 PSN DW8 Xtreme Legends.")
    return FORMAT


@lru_cache(maxsize=8)
def _decode_bytes(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE:
        raise SaveError(
            "Requires a PFD-decrypted US PS3 DW8 XL APP.BIN of 753,477 bytes."
        )
    payload = byte_cipher(raw[:-1], 0x13100200)
    if payload[:5] != SIGNATURE:
        raise SaveError(
            "Unsupported native PS3 DW8 XL revision; PC and other editions are separate."
        )
    if sum(payload) & 255 != raw[-1]:
        raise SaveError("PS3 DW8 XL native gameplay checksum failed.")
    return payload


def decode(raw, game_id=GAME_ID, source=Path("APP.BIN")):
    get_format(game_id)
    if type(raw) is not bytes:
        raise SaveError("Immutable native save bytes are required.")
    return Document(FORMAT, Path(source), raw, _decode_bytes(raw))


def _context_raw(path):
    companion = safe_path(Path(path).parent / "PARAM.SFO")
    try:
        with companion.open("rb") as stream:
            metadata = stream.read(MAX_SFO_SIZE + 1)
    except FileNotFoundError as error:
        raise SaveError(
            "Keep the matching NPUB31449-SAVEDATA PARAM.SFO beside the copied APP.BIN; "
            "the gameplay payload does not independently identify its region."
        ) from error
    if savedata_directory(metadata) != TITLE_DIRECTORY:
        raise SaveError(
            "The copied PS3 context must identify exactly NPUB31449-SAVEDATA."
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
    destination = safe_path(Path(output_dir) / "PARAM.SFO")
    if destination.exists():
        raise FileExistsError(
            "Self-test context must have a new PARAM.SFO destination."
        )
    _require_opened_context(document)
    return atomic_new(metadata, destination)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
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
        or type(document.raw) is not bytes
        or type(document.payload) is not bytes
        or type(document.context_digest) is not str
        or _decode_bytes(document.raw) != document.payload
    ):
        raise SaveError("An immutable native PS3 DW8 XL snapshot is required.")


@lru_cache(maxsize=4)
def _mapped_fields(payload, experimental=False):
    fields = list(BASE_FIELDS)
    for index in range(WEAPON_COUNT):
        start = WEAPON_BASE + index * WEAPON_STRIDE
        identity = int.from_bytes(payload[start + 2 : start + 4], "little")
        if payload[start] not in (1, 3) or identity == 0xFFFF:
            continue
        # Factual source rank bytes are relative +12..17; preserve unknown
        # attributes, zero/unusual ranks, IDs and every adjacent ownership byte.
        for slot in range(6):
            attr, rank = payload[start + 6 + slot], payload[start + 12 + slot]
            if attr in DW8_RANKED_ATTRIBUTES and 1 <= rank <= (255 if experimental else 10):
                fields.append(
                    Field(
                        f"weapon_{index}_rank_{slot}",
                        f'{DW8_ATTRIBUTE_NAMES.get(attr, "Attribute")} rank (ID {attr})',
                        start + 12 + slot,
                        1,
                        10,
                        "Weapon attributes",
                        index + 1,
                        1,
                        False,
                    )
                )
    return tuple(fields)


def fields_for(document):
    validate_document(document)
    return _mapped_fields(document.payload, experimental_enabled())


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def field_options(document, key):
    if type(key) is not str:
        raise SaveError("A qualified string field ID is required.")
    field = field_map(document).get(key)
    if field is None:
        raise SaveError("This field is not qualified in the opened PS3 copy.")
    if "_compatibility_" in key:
        return tuple((value, f"{value // 25} stars") for value in (25, 50, 75, 100))
    return ()


def changed_payload(document, changes):
    if not isinstance(changes, Mapping):
        raise SaveError("Pending edits must be a field/value mapping.")
    mapping = field_map(document)
    result = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in mapping:
            raise SaveError(
                "Only qualified original US PS3 DW8 XL fields are writable."
            )
        field = mapping[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        field.validate(value)
        result[field.offset : field.offset + field.size] = value.to_bytes(
            field.size, "little"
        )
    return bytes(result)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    raw = byte_cipher(payload, 0x13100200) + bytes([sum(payload) & 255])
    if _decode_bytes(raw) != payload:
        raise SaveError("Native PS3 edited copy verification failed.")
    return raw


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
    source = safe_path(document.source)
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
        "kind": "dw8xl-ps3-export-context",
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
    destination = safe_path(destination)
    if destination.suffix.lower() != ".bin":
        raise SaveError("Choose a new native PS3 .bin copy destination.")
    _require_opened_context(document, destination)
    if destination.exists():
        raise FileExistsError("Choose a new file; existing files are never replaced.")

    def check_source():
        with safe_path(document.source).open("rb") as stream:
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
    return read_save(destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    destination, backup_path = safe_path(destination), safe_path(backup_path)
    digest = _context(destination, required=True)
    try:
        companion = safe_path(backup_path.with_name(backup_path.name + ".context.json"))
        with companion.open("rb") as stream:
            raw_metadata = stream.read(1025)
        if len(raw_metadata) > 1024:
            raise SaveError("DW8 XL backup context metadata is too large.")
        metadata = json.loads(raw_metadata)
    except (OSError, ValueError, UnicodeError) as error:
        raise SaveError(
            "DW8 XL backup context metadata is missing or damaged."
        ) from error
    if (
        type(metadata) is not dict
        or metadata.get("game_id") != GAME_ID
        or metadata.get("kind") != "dw8xl-ps3-export-context"
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

    return restore_snapshot(
        backup_path,
        destination,
        GAME_ID,
        ".bin",
        SAVE_SIZE,
        validate_raw=validate_restore,
    )


def record_label(slot, group="Officers"):
    return (
        f"Weapon slot {slot}"
        if group == "Weapon attributes"
        else f"Officer slot {slot}" if slot else group
    )


def field_hint(document, field):
    validate_document(document)
    return (
        "Manual source-backed PS3 field. Max is disabled because published patch "
        "targets do not establish natural caps. Original higher/unusual values and "
        "ownership, EXP, skills and story flags remain unchanged. Reimport and resign with Apollo."
    )


def inspection_rows(document):
    validate_document(document)
    rows = []
    for index in range(82):
        start = 0x7FC9 + index * 0x48
        rows.append(
            {
                "group": "Officer progression",
                "label": f"Officer slot {index + 1}",
                "value": f"Stored level index: {document.payload[start + 0x17]}; "
                f'EXP: {int.from_bytes(document.payload[start+0x1C:start+0x20], "little")}; '
                f'weapon references: {int.from_bytes(document.payload[start+0x30:start+0x32], "little")}, '
                f'{int.from_bytes(document.payload[start+0x32:start+0x34], "little")} (read only)',
            }
        )
    for index in range(WEAPON_COUNT):
        start = WEAPON_BASE + index * WEAPON_STRIDE
        identity = int.from_bytes(document.payload[start + 2 : start + 4], "little")
        if identity != 0xFFFF:
            attributes = ", ".join(
                f'{DW8_ATTRIBUTE_NAMES.get(document.payload[start+6+j], "Unknown")} '
                f"#{document.payload[start+6+j]}: {document.payload[start+12+j]}"
                for j in range(6)
            )
            rows.append(
                {
                    "group": "Weapons",
                    "label": f"Weapon slot {index + 1} — ID {identity}",
                    "value": f"Affinity byte: {document.payload[start+4]}; {attributes}",
                }
            )
    return tuple(rows)
