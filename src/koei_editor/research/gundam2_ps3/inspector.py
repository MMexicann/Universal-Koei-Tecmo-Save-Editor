"""Published own-title byte sum and four pilot maps; no progression writes."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import struct

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.ps3_export import savedata_directory
from koei_editor.shared.save_safety import safe_path

SAVE_SIZE = 671744
TITLE_IDS = ("BLUS30288", "BLES00528")
PILOTS = (
    ("Amuro Ray", 0x173),
    ("Char Aznable", 0x1B3),
    ("Kamille Bidan", 0x1F3),
    ("Judau Ashta", 0x2B3),
)


@dataclass(frozen=True)
class Document:
    source: Path
    raw: bytes
    context_digest: str = ""


def decode(raw, source=Path("DATA.BIN")):
    if (
        type(raw) is not bytes
        or len(raw) != SAVE_SIZE
        or raw[:4] != struct.pack(">I", 13)
        or raw[0x14:0x1C] != struct.pack(">2I", 32, 0x3D400)
    ):
        raise SaveError(
            "Requires the qualified US/EU revision-13 Gundam 2 PS3 DATA.BIN profile."
        )
    if (sum(raw[0x20:]) & 0xFFFFFFFF) != struct.unpack_from(">I", raw, 0x10)[0]:
        raise SaveError(
            "Gundam 2 native byte-sum integrity failed; damaged input is not repaired."
        )
    return Document(Path(source), raw)


def read_save(path):
    path = safe_path(path)
    if path.suffix.lower() != ".bin":
        raise SaveError("Open a copied PFD-decrypted DATA.BIN export.")
    metadata = safe_path(path.parent / "PARAM.SFO")
    with metadata.open("rb") as stream:
        context = stream.read(4097)
    directory = savedata_directory(context)
    if re.fullmatch(r"(?:BLUS30288|BLES00528)-[0-9]{2}", directory) is None:
        raise SaveError("Requires original US/EU Gundam 2 PARAM.SFO slot metadata.")
    with path.open("rb") as stream:
        document = decode(stream.read(SAVE_SIZE + 1), path)
    with metadata.open("rb") as stream:
        if stream.read(4097) != context:
            raise SaveError("Original PS3 metadata changed during inspection.")
    return Document(path, document.raw, hashlib.sha256(context).hexdigest())


def inspect(document):
    if (
        type(document) is not Document
        or not isinstance(document.source, Path)
        or type(document.context_digest) is not str
    ):
        raise SaveError("Inspect a frozen Gundam 2 native snapshot.")
    decode(document.raw, document.source)
    if document.context_digest and read_save(document.source) != document:
        raise SaveError(
            "The copied gameplay or original PS3 metadata changed during inspection."
        )
    return {
        "profile": "gundam2_ps3",
        "title": "Dynasty Warriors: Gundam 2",
        "platform": "PlayStation 3",
        "registered_editor": False,
        "read_only": True,
        "source_sha256": hashlib.sha256(document.raw).hexdigest(),
        "original_context_bound": bool(document.context_digest),
        "native_checksum_valid": True,
        "game_load_verified": False,
        "pilots": [
            {
                "name": name,
                "stored_level_index": document.raw[offset],
                "stored_pilot_points": struct.unpack_from(
                    ">I", document.raw, offset + 1
                )[0],
            }
            for name, offset in PILOTS
        ],
        "needed": "Pilot-specific EXP/level curves, growth/reward dependencies and destination game-load validation before writes. Other pilots and progression words are not inferred from a stride.",
    }
