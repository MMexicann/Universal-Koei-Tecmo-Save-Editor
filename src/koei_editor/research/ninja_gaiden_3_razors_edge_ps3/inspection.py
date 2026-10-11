"""Native NPUB31184 story inspection; full gameplay integrity is unresolved.

Three distinct public native stories establish framing and the metadata CRC.
That CRC covers a separate, unresolved payload-integrity word. Published Karma
patches do not qualify writing while that active integrity remains unknown.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import struct

from koei_editor.games.dw3.models import SaveError
from koei_editor.research.ninja_gaiden_sigma2_pc.inspection import metadata_crc
from koei_editor.shared.ps3_export import MAX_SFO_SIZE, savedata_directory
from koei_editor.shared.save_safety import safe_path

SIZE = 0x8970
REVISION = 6
PATCH_SOURCE = 'https://github.com/bucanero/apollo-patches/blob/main/PS3/NPUB31184.savepatch'


@dataclass(frozen=True)
class Inspection:
    raw: bytes
    revision: int
    metadata_crc_verified: bool
    unresolved_payload_checksum: int
    ryu_karma: int
    ayane_karma: int
    integrity_verified: bool = False
    writable: bool = False
    title_verified: bool = False
    context_sha256: str | None = None


def inspect(raw):
    if type(raw) is not bytes or len(raw) != SIZE:
        raise SaveError('Razor\'s Edge PS3 story inspection requires the complete 35,184-byte native copy.')
    if (struct.unpack_from('>II', raw) != (SIZE, REVISION)
            or raw[8:12] != bytes(4) or raw[16:20] != b'\x01\0\0\0'
            or raw[24:32] != bytes(8)):
        raise SaveError('Unmapped Razor\'s Edge PS3 story framing; system/other titles are excluded.')
    if struct.unpack_from('>I', raw, 12)[0] != metadata_crc(raw[16:28]):
        raise SaveError('Razor\'s Edge native metadata CRC does not match.')
    return Inspection(raw, REVISION, True, struct.unpack_from('>I', raw, 20)[0],
                      struct.unpack_from('>I', raw, 0x11E8)[0],
                      struct.unpack_from('>I', raw, 0x11F0)[0])


def _context(source):
    companion = safe_path(Path(source).parent / 'PARAM.SFO')
    try:
        with companion.open('rb') as stream:
            raw = stream.read(MAX_SFO_SIZE + 1)
    except OSError as error:
        raise SaveError('Keep the original NPUB31184 PARAM.SFO beside the copied decrypted story.') from error
    directory = savedata_directory(raw)
    if re.fullmatch(r'NPUB31184STORY_P_(?:SAV0|SAVE-[0-9A-F]{8})', directory) is None:
        raise SaveError('Metadata does not identify a supported NPUB31184 story/checkpoint export.')
    return hashlib.sha256(raw).hexdigest()


def read_save(source):
    source = safe_path(source)
    stamp = _context(source)
    with source.open('rb') as stream:
        raw = stream.read(SIZE + 1)
    result = inspect(raw)
    if _context(source) != stamp:
        raise SaveError('The original PS3 metadata changed while inspecting the copy.')
    return Inspection(result.raw, result.revision, result.metadata_crc_verified,
                      result.unresolved_payload_checksum, result.ryu_karma,
                      result.ayane_karma, title_verified=True, context_sha256=stamp)


def encode(inspection, raw=None):
    """Return the immutable original only; metadata CRC repair cannot permit edits."""
    if (type(inspection) is not Inspection
            or any(type(getattr(inspection, name)) is not bool for name in
                   ('metadata_crc_verified', 'integrity_verified', 'writable', 'title_verified'))
            or any(type(getattr(inspection, name)) is not int for name in
                   ('revision', 'unresolved_payload_checksum', 'ryu_karma', 'ayane_karma'))
            or inspection.integrity_verified or inspection.writable
            or inspection.title_verified != (inspection.context_sha256 is not None)
            or (inspection.context_sha256 is not None and (
                type(inspection.context_sha256) is not str
                or re.fullmatch('[0-9a-f]{64}', inspection.context_sha256) is None))):
        raise SaveError('An unchanged read-only Razor\'s Edge inspection is required.')
    checked = inspect(inspection.raw)
    for name in ('raw', 'revision', 'metadata_crc_verified', 'unresolved_payload_checksum',
                 'ryu_karma', 'ayane_karma'):
        if getattr(checked, name) != getattr(inspection, name):
            raise SaveError('The Razor\'s Edge inspection snapshot changed after parsing.')
    if raw is not None and (type(raw) is not bytes or raw != inspection.raw):
        raise SaveError('Razor\'s Edge gameplay integrity is unresolved; changes are forbidden.')
    return inspection.raw
