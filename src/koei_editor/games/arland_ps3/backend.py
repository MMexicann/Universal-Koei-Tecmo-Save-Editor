"""Original Arland PS3 exported-byte editing with title-specific factual maps.

Only the single tagged Cole balance can be reduced. Complete framing is checked;
Apollo handles external PS3 encryption/PFD authentication on reimport. See the
per-game format documents for precise qualification and remaining dependencies.
"""

from dataclasses import dataclass, field as hidden
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import (
    atomic_new,
    restore_snapshot,
    snapshot_backup,
)
from koei_editor.shared.ps3_export import savedata_directory, MAX_SFO_SIZE
from koei_editor.shared.save_safety import safe_path


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    maximum: int
    size: int = 4
    group: str = "Resources"
    slot: int = 0
    minimum: int = 0
    maxable: bool = False
    kind: str = "int"

    def value(self, payload):
        return int.from_bytes(payload[self.offset : self.offset + self.size], "big")

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(
                "Cole can be reduced from the opened balance; use a whole number from 0 to "
                + str(self.maximum)
                + "."
            )


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = (
        "Original decrypted PS3 export. Reduce Cole and inspect character/progression blocks. "
        "Keep original PARAM.SFO beside the copy; reimport and resign using Apollo."
    )


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes = hidden(repr=False)
    payload: bytes = hidden(repr=False)
    context_sha256: str | None = None

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


class Backend:
    def __init__(
        self,
        game_id,
        title,
        size,
        sizes,
        title_ids,
        cole_offset,
        names,
        stride,
        *,
        header=bytes.fromhex("0132b533"),
        money_tag=3,
        character_tag=4,
        calendar_tag=11,
    ):
        self.GAME_ID, self.SAVE_SIZE = game_id, size
        self.FORMAT = Format(game_id, title, size)
        self.sizes, self.title_ids = tuple(sizes), tuple(title_ids)
        self.cole_offset, self.names, self.stride = cole_offset, tuple(names), stride
        self.header = header + bytes(28)
        self.money_tag, self.character_tag, self.calendar_tag = (
            money_tag,
            character_tag,
            calendar_tag,
        )
        self._qualify = lru_cache(maxsize=2)(self._qualify_uncached)

    def get_format(self, game_id=None):
        if game_id is not None and (
            type(game_id) is not str or game_id != self.GAME_ID
        ):
            raise SaveError("Choose this exact original PS3 Atelier profile.")
        return self.FORMAT

    def _qualify_uncached(self, raw):
        if (
            type(raw) is not bytes
            or len(raw) != self.SAVE_SIZE
            or raw[:32] != self.header
        ):
            raise SaveError(
                "Requires the complete qualified original decrypted PS3 gameplay profile."
            )
        chunks, start = [], 32
        for index, length in enumerate(self.sizes, 1):
            if start + 8 + length > len(raw) or struct.unpack_from(
                ">II", raw, start
            ) != (index, length):
                raise SaveError(
                    "Original PS3 Atelier chunk order/length/revision is unsupported."
                )
            chunks.append((index, start + 8, length))
            start += 8 + length
        if (
            start + 8 > len(raw)
            or struct.unpack_from(">II", raw, start) != (1024, len(raw) - start)
            or chunks[self.money_tag - 1][1] != self.cole_offset
            or chunks[self.money_tag - 1][2] != 4
        ):
            raise SaveError(
                "Original PS3 Atelier terminal frame or unique Cole tag does not match."
            )
        # The observed framed records, including any stored NPC/DLC records,
        # qualify this profile. Their level/stat bytes remain inspection only.
        base = chunks[self.character_tag - 1][1]
        if chunks[self.character_tag - 1][2] != len(self.names) * self.stride + 12:
            raise SaveError("Unsupported PS3 character array extent.")
        if tuple(
            struct.unpack_from(">i", raw, base + i * self.stride)[0]
            for i in range(len(self.names))
        ) != tuple(range(len(self.names))):
            raise SaveError("Unsupported PS3 character identity/order profile.")
        return tuple(chunks)

    def decode(self, raw, game_id=None, source=Path("copy.bin")):
        self.get_format(game_id)
        if type(raw) is not bytes:
            raise SaveError("An immutable complete decrypted PS3 save is required.")
        self._qualify(raw)
        return Document(self.FORMAT, Path(source), raw, raw)

    @staticmethod
    def _path(path):
        path = safe_path(path)
        if path.suffix.lower() != ".bin":
            raise SaveError("Use a separate decrypted USR-DATA .bin export copy.")
        return path

    def _context(self, path):
        companion = safe_path(Path(path).parent / "PARAM.SFO")
        try:
            with companion.open("rb") as stream:
                raw = stream.read(MAX_SFO_SIZE + 1)
        except OSError as error:
            raise SaveError(
                "Keep original PARAM.SFO beside the copied decrypted PS3 export."
            ) from error
        directory = savedata_directory(raw)
        if not any(
            directory == title or directory.startswith(title + "-")
            for title in self.title_ids
        ):
            raise SaveError("Original PS3 metadata has an unsupported title or region.")
        return hashlib.sha256(raw).hexdigest()

    def read_save(self, path, game_id=None):
        self.get_format(game_id)
        path = self._path(path)
        stamp = self._context(path)
        with path.open("rb") as stream:
            document = self.decode(stream.read(self.SAVE_SIZE + 1), game_id, path)
        if self._context(path) != stamp:
            raise SaveError("Original PS3 metadata changed while opening.")
        return Document(self.FORMAT, path, document.raw, document.payload, stamp)

    def validate_document(self, document):
        if (
            type(document) is not Document
            or document.format is not self.FORMAT
            or not isinstance(document.source, Path)
            or type(document.raw) is not bytes
            or type(document.payload) is not bytes
            or document.raw != document.payload
            or (
                document.context_sha256 is not None
                and (
                    type(document.context_sha256) is not str
                    or len(document.context_sha256) != 64
                    or any(c not in "0123456789abcdef" for c in document.context_sha256)
                )
            )
        ):
            raise SaveError("A frozen original PS3 Atelier snapshot is required.")
        self._qualify(document.raw)

    def fields_for(self, document):
        self.validate_document(document)
        return (
            Field(
                "cole",
                "Cole (reduce only)",
                self.cole_offset,
                int.from_bytes(
                    document.payload[self.cole_offset : self.cole_offset + 4], "big"
                ),
            ),
        )

    def field_map(self, document):
        return MappingProxyType({f.id: f for f in self.fields_for(document)})

    def changed_payload(self, document, changes):
        fields = self.field_map(document)
        if type(changes) is not dict:
            raise SaveError("Pending PS3 Atelier edits must be a dictionary.")
        output = bytearray(document.payload)
        for key, value in changes.items():
            if type(key) is not str or key not in fields:
                raise SaveError("Only the single spendable Cole balance is writable.")
            f = fields[key]
            if type(value) is int and value == f.value(document.payload):
                continue
            f.validate(value)
            output[f.offset : f.offset + 4] = value.to_bytes(4, "big")
        return bytes(output)

    def serialize(self, document, changes):
        raw = self.changed_payload(document, changes)
        self._qualify(raw)
        return document.raw if raw == document.payload else raw

    def stage(self, document, changes, key, value):
        self.changed_payload(document, changes)
        fields = self.field_map(document)
        if type(key) is not str or key not in fields:
            raise SaveError("This PS3 Atelier mechanic is inspection only.")
        result = dict(changes)
        if type(value) is int and value == fields[key].value(document.payload):
            result.pop(key, None)
        else:
            fields[key].validate(value)
            result[key] = value
        return result

    def limit_values(self, document, changes, keys):
        self.changed_payload(document, changes)
        fields = self.field_map(document)
        if any(type(key) is not str or key not in fields for key in keys):
            raise SaveError("Choose a verified PS3 Atelier field.")
        return {}

    def maximums(self, document, changes, group=None):
        self.changed_payload(document, changes)
        return dict(changes)

    def review(self, document, changes):
        self.changed_payload(document, changes)
        return [
            (f, f.value(document.payload), changes[f.id])
            for f in self.fields_for(document)
            if f.id in changes
        ]

    def _validate_source(self, document):
        self.validate_document(document)
        source = self._path(document.source)
        if (
            document.context_sha256 is None
            or self._context(source) != document.context_sha256
        ):
            raise SaveError(
                "Original PS3 metadata changed or was not qualified; reopen the copy."
            )
        try:
            with source.open("rb") as stream:
                raw = stream.read(self.SAVE_SIZE + 1)
        except OSError as error:
            raise SaveError(
                "The original PS3 copy is unavailable; reopen it."
            ) from error
        if raw != document.raw:
            raise SaveError("The opened PS3 copy changed on disk; reopen it.")
        return source

    def backup(self, document):
        source = self._validate_source(document)
        snapshot = snapshot_backup(
            document.raw, source, self.GAME_ID, source.parent / "UniversalEditorBackups"
        )
        metadata = {
            "game_id": self.GAME_ID,
            "kind": "arland-ps3-export-context",
            "context_sha256": document.context_sha256,
            "save_sha256": document.sha256,
        }
        try:
            atomic_new(
                json.dumps(metadata).encode(),
                snapshot.with_name(snapshot.name + ".context.json"),
            )
        except Exception:
            snapshot.unlink(missing_ok=True)
            snapshot.with_suffix(".json").unlink(missing_ok=True)
            raise
        return snapshot

    def save_as(self, document, changes, destination):
        source = self._validate_source(document)
        destination = self._path(destination)
        if self._context(destination) != document.context_sha256:
            raise SaveError(
                "Keep the same unchanged original PARAM.SFO beside the destination."
            )
        if source == destination or destination.exists():
            raise FileExistsError(
                "Choose a new destination; existing files are never replaced."
            )
        raw = self.serialize(document, changes)
        self.backup(document)
        self._validate_source(document)
        if self._context(destination) != document.context_sha256:
            raise SaveError("Destination PS3 metadata changed before writing.")
        atomic_new(raw, destination)
        return self.read_save(destination)

    def restore(self, backup_path, destination, game_id=None):
        self.get_format(game_id)
        destination = self._path(destination)
        backup_path = safe_path(backup_path)
        stamp = self._context(destination)
        try:
            with safe_path(
                backup_path.with_name(backup_path.name + ".context.json")
            ).open("rb") as stream:
                raw = stream.read(1025)
            if len(raw) > 1024:
                raise SaveError("PS3 backup context metadata is oversized.")
            metadata = json.loads(raw)
        except (OSError, ValueError, UnicodeError) as error:
            raise SaveError(
                "PS3 backup context metadata is missing or damaged."
            ) from error
        if (
            type(metadata) is not dict
            or metadata.get("game_id") != self.GAME_ID
            or metadata.get("kind") != "arland-ps3-export-context"
            or metadata.get("context_sha256") != stamp
            or type(metadata.get("save_sha256")) is not str
            or len(metadata["save_sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in metadata["save_sha256"])
        ):
            raise SaveError(
                "Restore requires the same original PS3 metadata as the backup."
            )

        def validate(raw):
            if hashlib.sha256(raw).hexdigest() != metadata["save_sha256"]:
                raise SaveError(
                    "The PS3 backup bytes differ from their original context binding."
                )
            self.decode(raw, game_id)
            if self._context(destination) != stamp:
                raise SaveError("Destination PS3 metadata changed before restoring.")

        return restore_snapshot(
            backup_path,
            destination,
            self.GAME_ID,
            ".bin",
            self.SAVE_SIZE,
            validate_raw=validate,
        )

    def prepare_copy_context(self, document, output):
        self._validate_source(document)
        output = safe_path(output)
        output.mkdir(parents=True, exist_ok=True)
        companion = safe_path(output / "PARAM.SFO")
        with safe_path(document.source.parent / "PARAM.SFO").open("rb") as stream:
            raw = stream.read(MAX_SFO_SIZE + 1)
        if hashlib.sha256(raw).hexdigest() != document.context_sha256:
            raise SaveError("Original PS3 metadata changed during diagnostic copy.")
        if companion.exists():
            if companion.read_bytes() != raw:
                raise SaveError("Diagnostic PS3 metadata differs from the original.")
        else:
            atomic_new(raw, companion)

    def inspection_rows(self, document):
        self.validate_document(document)
        chunks = self._qualify(document.payload)
        base = chunks[self.character_tag - 1][1]
        # Only observed/publicly named level and EXP are labelled. Stats have
        # several derived copies and inconsistent third-party patch addresses.
        characters = tuple(
            (
                name,
                index,
                int.from_bytes(
                    document.payload[
                        base + index * self.stride + 4 : base + index * self.stride + 8
                    ],
                    "big",
                ),
                int.from_bytes(
                    document.payload[
                        base + index * self.stride + 8 : base + index * self.stride + 12
                    ],
                    "big",
                ),
            )
            for index, name in enumerate(self.names)
        )
        labels = {
            self.money_tag: "Cole",
            self.character_tag: "Character records",
            7: "Item records",
        }
        if self.calendar_tag is not None:
            labels[self.calendar_tag] = "Calendar words"
        sections = tuple(
            (tag, labels.get(tag, "Opaque serialized system"), length)
            for tag, _, length in chunks
        )
        return characters, sections

    def field_hint(self, document, key):
        fields = self.field_map(document)
        if type(key) is not str or key not in fields:
            raise SaveError("Choose a verified PS3 Atelier field.")
        return (
            "Reduce the existing spendable Cole balance. Max leaves it unchanged. "
            "Growth, equipment, rewards, calendar and story flags are preserved. "
            "Reimport the edited decrypted copy and resign through Apollo."
        )

    @staticmethod
    def record_label(slot, group="Resources"):
        return group if not slot else f"Record {slot}"
