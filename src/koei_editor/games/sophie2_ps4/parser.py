"""Exact PS4 Sophie 2 gameplay framing with authenticated Gust re-encoding.

The complete app 1.0 CUSA28451 export has ten native Party slots and BE tagged
scalars, while its packed ItemRecord fields are LE. Only existing ordinary
material quality reductions and bounded battle-item uses are writable.
"""

from collections import Counter
from dataclasses import dataclass, field as hidden
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.sophie2 import atelier_sophie2_codec as codec
from koei_editor.games.sophie2_ps4.context import context
from koei_editor.shared.copy_storage import (
    atomic_new,
    restore_snapshot,
    snapshot_backup,
)
from koei_editor.shared.save_safety import safe_path

GAME_ID = "atelier_sophie2_ps4"
EXTENSION = ".dat"
MAX_FILE_SIZE = codec.MAX_FILE_SIZE
INTEGRITY_KIND = "checksum"
PAYLOAD_SIZE = 629622
RECORD_SIZE = 44
# Independently transcribed small ordinary-material identity facts, not a
# redistributed external catalogue. Unknown IDs remain inspection only.
MATERIAL_NAMES = {
    0: "Drinking Water",
    1: "Crackling Water",
    2: "Blessed Sap",
    3: "Zapping Water",
    4: "Salt Water",
    9: "Koinós Grass",
    11: "Princess Grass",
    14: "Tail Fern",
    21: "Uni",
    22: "Grass Uni",
    26: "Red Flower",
    27: "Blue Flower",
    28: "Green Flower",
    29: "Yellow Flower",
    30: "White Flower",
    36: "Taun",
    37: "Tall Taun",
    45: "Blackberry",
    59: "Broken Rock",
    69: "Eisen Ore",
    70: "Leiden Ore",
    71: "Kupfer Ore",
    89: "Woodchips",
}
# Small individually checked same-game battle-item identity facts; unknown
# records retain their original bytes and remain inspection only.
BATTLE_ITEM_NAMES = {
    295: "Puni Missile",
    298: "Exacraft",
    299: "Draco Bomb",
    303: "God's Gift",
    305: "Heaven's Cleanser",
    306: "Flame of the End",
    307: "Twilight Prism",
    308: "Primal Storm",
    309: "Starry Comet",
    322: "Puni Jelly",
    323: "Healing Elixir",
    328: "Hot Soil Potato Stew",
    330: "Arzneizel",
    331: "Mystery Elixir",
    332: "Lebestrahl",
    348: "Daydream Key",
    356: "Ennui Mirror",
    358: "Moonless Mist",
    359: "Shadow Lynchpin",
}
CHARACTER_NAMES = ("Sophie", "Plachta", "Ramizel", "Alette", "Olias", "Diebold")
ROOT_PROFILE = (
    ("info", 29),
    ("PlayGo", 12),
    ("dlc", 118),
    ("event", 28485),
    ("knowledge", 19296),
    ("money", 32),
    ("party", 8056),
    ("fieldmap", 12101),
    ("friend", 191),
    ("library", 177),
    ("item", 473217),
    ("time", 17),
    ("event_check", 21),
    ("date", 29),
    ("global", 91),
    ("mix_lv", 73),
    ("explore_equip", 1848),
    ("bonus", 577),
    ("system", 3850),
    ("dlcbgm", 8033),
    ("shop", 18891),
    ("mix_recipe", 1611),
    ("achievement", 23142),
    ("barQuest", 7034),
    ("collectData", 7558),
    ("costume", 738),
    ("secret_base", 1955),
    ("battlescore", 428),
    ("lambRoast", 988),
    ("weaponskin", 67),
    ("record", 4419),
    ("RecipeIdea", 3561),
    ("ability", 343),
    ("worldmap", 176),
    ("party_quest", 2394),
    ("summary", 32),
)
POOLS = (
    ("basket", "Basket", "item", "m_unitBasket", 400),
    ("materials", "Material container", "item", "m_unitContainer", 9999),
    ("important", "Important items", "item", "m_unitContainerImportant", 150),
    ("expendable", "Consumable container", "item", "m_unitContainerExpendable", 50),
    ("exploration", "Gathering tools", "explore_equip", "explore_equip_item", 15),
    ("adventure", "Adventure equipment", "explore_equip", "adventure_equip_item", 25),
)


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    size: int
    maximum: int
    group: str
    slot: int = 0
    minimum: int = 0
    maxable: bool = False
    kind: str = "int"

    def value(self, payload):
        return int.from_bytes(payload[self.offset : self.offset + self.size], "little")

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(
                f"{self.label}: use a whole number from {self.minimum} to {self.maximum}."
            )


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = "Atelier Sophie 2: The Alchemist of the Mysterious Dream (PS4)"
    size: int = MAX_FILE_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = (
        "PS4 CUSA28451 app 1.0 complete native gameplay profile. Material quality reductions, "
        "existing consumable uses and searchable inventories/equipment/party. Original "
        "sce_sys/param.sfo is required; console reimport/signing is external."
    )


FORMAT = Format()


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes = hidden(repr=False)
    payload: bytes = hidden(repr=False)
    seed: int = hidden(repr=False)
    header: bytes = hidden(repr=False)
    trailer: bytes = hidden(repr=False)
    footer: bytes = hidden(repr=False)
    context_sha256: str | None = None

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


@dataclass(frozen=True)
class Node:
    name: bytes
    start: int
    body: int
    end: int


def get_format(game_id=GAME_ID):
    if type(game_id) is not str or game_id != GAME_ID:
        raise SaveError("Choose the exact Sophie 2 PS4 CUSA28451 native profile.")
    return FORMAT


def _nodes(payload, start, end, unique=True):
    result = []
    while start < end:
        if start + 5 > end:
            raise SaveError("Truncated Sophie 2 PS4 named node.")
        size = struct.unpack_from("<I", payload, start)[0]
        stop = start + size
        zero = payload.find(b"\0", start + 4, min(stop, start + 85, end))
        if not start + 5 <= stop <= end or zero < 0:
            raise SaveError("Invalid Sophie 2 PS4 tagged framing.")
        name = payload[start + 4 : zero]
        if not name or any(v < 32 or v > 126 for v in name):
            raise SaveError("Invalid Sophie 2 PS4 node name.")
        result.append(Node(name, start, zero + 1, stop))
        start = stop
    if unique and len({n.name for n in result}) != len(result):
        raise SaveError("Duplicate Sophie 2 PS4 tagged node.")
    return tuple(result)


def _node(nodes, name):
    matches = [n for n in nodes if n.name == name.encode()]
    if len(matches) != 1:
        raise SaveError("Missing or ambiguous Sophie 2 PS4 node: " + name + ".")
    return matches[0]


def _children(p, n):
    return _nodes(p, n.body, n.end)


def _be(p, n, width):
    if n.end - n.body != width:
        raise SaveError("Unsupported Sophie 2 PS4 tagged scalar width.")
    return int.from_bytes(p[n.body : n.end], "big")


@lru_cache(maxsize=2)
def _structure(p):
    if (
        type(p) is not bytes
        or len(p) != PAYLOAD_SIZE
        or p[:32] != bytes.fromhex("013379c9") + bytes(28)
    ):
        raise SaveError("Unsupported Sophie 2 PS4 native size/preamble.")
    roots = _nodes(p, 32, len(p))
    if tuple((n.name.decode(), n.end - n.start) for n in roots) != ROOT_PROFILE:
        raise SaveError("Unsupported Sophie 2 PS4 complete native root profile.")
    app = _node(_children(p, _node(roots, "info")), "app_ver")
    if p[app.body : app.end] != struct.pack(">II", 1, 0):
        raise SaveError("Requires qualified Sophie 2 PS4 native app 1.0.")
    item = _children(p, _node(roots, "item"))
    if _be(p, _node(item, "version"), 2) != 2:
        raise SaveError("Unsupported Sophie 2 PS4 item serializer revision.")
    explore = _children(p, _node(roots, "explore_equip"))
    if _be(p, _node(explore, "version"), 2) != 1:
        raise SaveError("Unsupported Sophie 2 PS4 exploration revision.")
    pools = []
    for key, label, root, marker, count in POOLS:
        node = _node(item if root == "item" else explore, marker)
        if (
            node.end - node.body != 4 + count * RECORD_SIZE
            or struct.unpack_from(">I", p, node.body)[0] != count * RECORD_SIZE
        ):
            raise SaveError("Unsupported Sophie 2 PS4 packed inventory extent.")
        pools.append((key, label, node.body + 4, count))
    party = _node(roots, "party")
    start = party.body
    version = _nodes(p, start, start + 14)[0]
    if (
        version.name != b"version"
        or _be(p, version, 2) != 3
        or struct.unpack_from(">I", p, version.end)[0] != 10
    ):
        raise SaveError("Unsupported Sophie 2 PS4 Party revision/count.")
    entries = _nodes(p, version.end + 4, version.end + 4 + 10 * 0x314, False)
    if len(entries) != 10 or any(
        n.name != b"Party" or n.end - n.start != 0x314 for n in entries
    ):
        raise SaveError("Unsupported Sophie 2 PS4 Party extent.")
    identities = tuple(struct.unpack_from(">i", p, n.body)[0] for n in entries)
    if identities != tuple(range(6)) + (-1,) * 4:
        raise SaveError("Unsupported Sophie 2 PS4 occupied/unused Party identities.")
    # All remaining party nodes are bounded after the raw framed array.
    _nodes(p, entries[-1].end, party.end)
    alchemy = _children(p, _node(roots, "mix_lv"))
    for name in ("lv", "exp", "plachta_lv", "plachta_exp"):
        _be(p, _node(alchemy, name), 4)
    wallet = _node(_children(p, _node(roots, "money")), "money")
    if wallet.end - wallet.body != 12:
        raise SaveError("Unsupported Sophie 2 PS4 wallet record extent.")
    return tuple(pools), entries, roots, alchemy, wallet


@lru_cache(maxsize=2)
def _snapshot(raw):
    try:
        header, payload, details = codec.decode_file(raw)
    except (codec.SaveFormatError, IndexError, struct.error) as error:
        raise SaveError("Sophie 2 PS4 native integrity/codec check failed.") from error
    if header[:4] != struct.pack("<I", 2):
        raise SaveError("Unsupported Sophie 2 PS4 outer revision.")
    _structure(payload)
    trailer = raw[codec.HEADER_SIZE + details.padded_size :]
    if trailer:
        raise SaveError("Unsupported extra Sophie 2 PS4 envelope bytes.")
    return header, payload, details, trailer


def decode(raw, game_id=GAME_ID, source=Path("copy.dat")):
    get_format(game_id)
    if type(raw) is not bytes or not codec.HEADER_SIZE < len(raw) <= MAX_FILE_SIZE:
        raise SaveError("An immutable complete bounded Sophie 2 PS4 save is required.")
    h, p, e, t = _snapshot(raw)
    return Document(FORMAT, Path(source), raw, p, e.seed, h, t, e.footer)


def _path(path):
    path = safe_path(path)
    if path.suffix.lower() != EXTENSION:
        raise SaveError(
            "Open a separate PS4 data.dat export with original sce_sys/param.sfo."
        )
    return path


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _path(path)
    stamp = context(path)
    with path.open("rb") as stream:
        doc = decode(stream.read(MAX_FILE_SIZE + 1), game_id, path)
    if context(path) != stamp:
        raise SaveError("Original Sophie 2 PS4 metadata changed while opening.")
    return Document(
        FORMAT,
        path,
        doc.raw,
        doc.payload,
        doc.seed,
        doc.header,
        doc.trailer,
        doc.footer,
        stamp,
    )


def validate_document(document):
    if (
        type(document) is not Document
        or document.format is not FORMAT
        or not isinstance(document.source, Path)
        or any(
            type(getattr(document, k)) is not bytes
            for k in ("raw", "payload", "header", "trailer", "footer")
        )
        or type(document.seed) is not int
        or (
            document.context_sha256 is not None
            and (
                type(document.context_sha256) is not str
                or len(document.context_sha256) != 64
                or any(c not in "0123456789abcdef" for c in document.context_sha256)
            )
        )
    ):
        raise SaveError("A frozen Sophie 2 PS4 snapshot is required.")
    h, p, e, t = _snapshot(document.raw)
    if (h, p, e.seed, e.footer, t) != (
        document.header,
        document.payload,
        document.seed,
        document.footer,
        document.trailer,
    ):
        raise SaveError(
            "The opened Sophie 2 PS4 snapshot was modified outside staging."
        )


@lru_cache(maxsize=2)
def _fields(p):
    pools, party, _, _, _ = _structure(p)
    result = []
    equipment_offsets = tuple(
        node.start + 4 + 0x176 + slot * RECORD_SIZE
        for node in party[:6]
        for slot in range(8)
    )
    occupied_offsets = tuple(
        base + index * RECORD_SIZE
        for _, _, base, count in pools
        for index in range(count)
        if struct.unpack_from("<h", p, base + index * RECORD_SIZE + 4)[0] >= 0
    )
    occupied_offsets += tuple(
        off for off in equipment_offsets if struct.unpack_from("<h", p, off + 4)[0] >= 0
    )
    # Published source reads instance identity as LE16, not a four-byte word.
    # Repeated occupied identities can represent aliases or unusual data; all
    # affected copies remain read-only rather than editing one occurrence.
    counts = Counter(struct.unpack_from("<H", p, off)[0] for off in occupied_offsets)
    equipped = {
        struct.unpack_from("<H", p, off)[0]
        for off in equipment_offsets
        if struct.unpack_from("<h", p, off + 4)[0] >= 0
    }
    for key, label, base, count in pools:
        if key not in ("materials", "expendable"):
            continue
        for index in range(count):
            off = base + index * RECORD_SIZE
            identity = struct.unpack_from("<h", p, off + 4)[0]
            quality = struct.unpack_from("<H", p, off + 6)[0]
            instance = struct.unpack_from("<H", p, off)[0]
            if identity < 0 or counts[instance] != 1:
                continue
            if (
                key == "materials"
                and identity in MATERIAL_NAMES
                and 1 <= quality <= 999
                and not any(p[off + 0x27 : off + 0x2C])
                and instance not in equipped
                and p[off + 0x24 : off + 0x26] == b"\1\1"
            ):
                result.append(
                    Field(
                        f"materials_{index}_quality",
                        f"{MATERIAL_NAMES[identity]}: Quality (reduce only)",
                        off + 6,
                        2,
                        quality,
                        label,
                        index + 1,
                        1,
                    )
                )
            if key == "expendable" and identity in BATTLE_ITEM_NAMES:
                current, capacity = p[off + 0x24 : off + 0x26]
                if 0 < capacity and current <= capacity:
                    result.append(
                        Field(
                            f"expendable_{index}_uses",
                            f"{BATTLE_ITEM_NAMES[identity]}: Remaining uses",
                            off + 0x24,
                            1,
                            capacity,
                            label,
                            index + 1,
                        )
                    )
    # Existing battle-item uses have a stored capacity. Equipment quality and
    # all saved derived stat/effect copies stay unchanged.
    for character, node in enumerate(party[:6]):
        start = node.start + 4 + 0x176
        for slot in range(4, 8):
            off = start + slot * RECORD_SIZE
            identity = struct.unpack_from("<h", p, off + 4)[0]
            current, capacity = p[off + 0x24 : off + 0x26]
            if (
                identity in BATTLE_ITEM_NAMES
                and 0 < capacity
                and current <= capacity
                and counts[struct.unpack_from("<H", p, off)[0]] == 1
            ):
                result.append(
                    Field(
                        f"character_{character}_{slot}_uses",
                        f"Battle item {slot-3}: {BATTLE_ITEM_NAMES[identity]} uses",
                        off + 0x24,
                        1,
                        capacity,
                        CHARACTER_NAMES[character] + " battle items",
                        slot - 3,
                    )
                )
    return tuple(result)


def fields_for(document):
    validate_document(document)
    return _fields(document.payload)


def field_map(document):
    return MappingProxyType({f.id: f for f in fields_for(document)})


def changed_payload(document, changes):
    fields = field_map(document)
    if type(changes) is not dict:
        raise SaveError("Pending Sophie 2 PS4 edits must be a dictionary.")
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError(
                "Only qualified existing material quality and battle-item uses are writable."
            )
        f = fields[key]
        if type(value) is int and value == f.value(document.payload):
            continue
        f.validate(value)
        output[f.offset : f.offset + f.size] = value.to_bytes(f.size, "little")
    return bytes(output)


def serialize(document, changes):
    p = changed_payload(document, changes)
    if p == document.payload:
        return document.raw
    raw = (
        codec.encode_file(document.header, p, document.seed, document.footer)
        + document.trailer
    )
    result = decode(raw, GAME_ID, document.source)
    if (result.payload, result.header, result.seed, result.footer, result.trailer) != (
        p,
        document.header,
        document.seed,
        document.footer,
        document.trailer,
    ):
        raise SaveError("Sophie 2 PS4 edited native readback failed.")
    return raw


def stage(document, changes, key, value):
    changed_payload(document, changes)
    fields = field_map(document)
    if type(key) is not str or key not in fields:
        raise SaveError("The selected Sophie 2 PS4 mechanic is inspection only.")
    result = dict(changes)
    if type(value) is int and value == fields[key].value(document.payload):
        result.pop(key, None)
    else:
        fields[key].validate(value)
        result[key] = value
    return result


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    fields = field_map(document)
    if any(type(key) is not str or key not in fields for key in keys):
        raise SaveError("Choose a verified Sophie 2 PS4 field.")
    return {key: fields[key].maximum for key in keys if fields[key].maxable}


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)


def review(document, changes):
    changed_payload(document, changes)
    return [
        (f, f.value(document.payload), changes[f.id])
        for f in fields_for(document)
        if f.id in changes
    ]


def _validate_source(document):
    validate_document(document)
    source = _path(document.source)
    if document.context_sha256 is None or context(source) != document.context_sha256:
        raise SaveError(
            "The original PS4 metadata changed or was not qualified; reopen the copy."
        )
    try:
        with source.open("rb") as stream:
            current = stream.read(MAX_FILE_SIZE + 1)
    except OSError as error:
        raise SaveError(
            "The opened PS4 copy is unavailable. Reopen a separate save copy."
        ) from error
    if current != document.raw:
        raise SaveError("The opened PS4 copy changed on disk. Reopen it before saving.")
    return source


def backup(document):
    source = _validate_source(document)
    snapshot = snapshot_backup(
        document.raw, source, GAME_ID, source.parent / "UniversalEditorBackups"
    )
    metadata = {
        "game_id": GAME_ID,
        "kind": "sophie2-ps4-export-context",
        "context_sha256": document.context_sha256,
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
    source = _validate_source(document)
    destination = _path(destination)
    if context(destination) != document.context_sha256:
        raise SaveError(
            "Keep the same unchanged original sce_sys/param.sfo beside the destination."
        )
    if source == destination or destination.exists():
        raise FileExistsError("Choose a new file; existing files are never replaced.")
    raw = serialize(document, changes)
    backup(document)
    _validate_source(document)
    if context(destination) != document.context_sha256:
        raise SaveError("The destination PS4 metadata changed before writing.")
    atomic_new(raw, destination)
    return read_save(destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    destination, backup_path = _path(destination), safe_path(backup_path)
    stamp = context(destination)
    try:
        with safe_path(backup_path.with_name(backup_path.name + ".context.json")).open(
            "rb"
        ) as stream:
            raw_metadata = stream.read(1025)
        if len(raw_metadata) > 1024:
            raise SaveError("PS4 backup context metadata is oversized.")
        metadata = json.loads(raw_metadata)
    except (OSError, ValueError, UnicodeError) as error:
        raise SaveError("PS4 backup context metadata is missing or damaged.") from error
    if (
        type(metadata) is not dict
        or metadata.get("game_id") != GAME_ID
        or metadata.get("kind") != "sophie2-ps4-export-context"
        or metadata.get("context_sha256") != stamp
        or type(metadata.get("save_sha256")) is not str
        or len(metadata["save_sha256"]) != 64
        or any(c not in "0123456789abcdef" for c in metadata["save_sha256"])
    ):
        raise SaveError(
            "Restore requires the same original PS4 metadata as the backup."
        )

    def validate_restored(raw):
        if hashlib.sha256(raw).hexdigest() != metadata["save_sha256"]:
            raise SaveError(
                "The PS4 backup bytes differ from their original context binding."
            )
        decode(raw, game_id)
        if context(destination) != stamp:
            raise SaveError("The destination PS4 metadata changed before restoring.")

    return restore_snapshot(
        backup_path,
        destination,
        GAME_ID,
        EXTENSION,
        MAX_FILE_SIZE,
        validate_raw=validate_restored,
    )


def prepare_copy_context(document, output):
    _validate_source(document)
    output = safe_path(output)
    output.mkdir(parents=True, exist_ok=True)
    companion = safe_path(output / "sce_sys" / "param.sfo")
    with safe_path(document.source.parent / "sce_sys" / "param.sfo").open(
        "rb"
    ) as stream:
        raw = stream.read(4097)
    if hashlib.sha256(raw).hexdigest() != document.context_sha256:
        raise SaveError("Original PS4 metadata changed during diagnostic copy.")
    companion.parent.mkdir(exist_ok=True)
    if companion.exists():
        if companion.read_bytes() != raw:
            raise SaveError("Diagnostic PS4 metadata differs from the original.")
    else:
        atomic_new(raw, companion)


def record_label(slot, group="Resources"):
    return f"{group} record {slot}" if slot else group


def field_hint(document, key):
    fields = field_map(document)
    if type(key) is not str or key not in fields:
        raise SaveError("Choose a verified Sophie 2 PS4 field.")
    f = fields[key]
    return (
        "Reduce existing material quality without changing effects, traits or saved derived stats. "
        if f.id.endswith("quality")
        else "Edit remaining uses within this existing item’s saved capacity. "
    ) + (
        "Max leaves this field unchanged; acquisition, growth, recipes and story records are preserved."
    )


def inspection_rows(document):
    validate_document(document)
    p = document.payload
    pools, party, roots, alchemy, wallet = _structure(p)
    rows = []
    regions = [
        (label, index + 1, base + index * RECORD_SIZE)
        for _, label, base, count in pools
        for index in range(count)
    ]
    regions.extend(
        (
            CHARACTER_NAMES[c] + " equipment",
            slot + 1,
            node.start + 4 + 0x176 + slot * RECORD_SIZE,
        )
        for c, node in enumerate(party[:6])
        for slot in range(8)
    )
    for label, index, off in regions:
        identity = struct.unpack_from("<h", p, off + 4)[0]
        if identity < 0:
            continue
        rows.append(
            (
                label,
                index,
                identity,
                struct.unpack_from("<H", p, off + 6)[0],
                p[off + 0x24],
                p[off + 0x25],
                str(struct.unpack_from("<hhh", p, off + 0x0A)),
                str(struct.unpack_from("<hhhh", p, off + 0x10)),
            )
        )
    characters = tuple(
        (CHARACTER_NAMES[c], _be_raw(p, node.body + 4), _be_raw(p, node.body + 8))
        for c, node in enumerate(party[:6])
    )
    resources = (("Cole (read only)", _be_raw(p, wallet.body)),) + tuple(
        (name, _be(p, _node(alchemy, name), 4))
        for name in ("lv", "exp", "plachta_lv", "plachta_exp")
    )
    sections = tuple((n.name.decode(), n.end - n.start) for n in roots)
    return tuple(rows), characters, resources, sections


def _be_raw(p, off):
    return int.from_bytes(p[off : off + 4], "big")
