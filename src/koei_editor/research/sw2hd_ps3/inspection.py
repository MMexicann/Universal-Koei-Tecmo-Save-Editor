"""Source-backed diagnostic facts, without gameplay/profile/write support.

Apollo NPJB00439.savepatch documents a money scalar and duplicated additive
checksum. The native header, exact revision/size and complete serialized layout
remain unqualified; a matching diagnostic result alone must not expose writes.
"""
from dataclasses import dataclass

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.ps3_export import savedata_directory

SOURCE_URL = 'https://github.com/bucanero/apollo-patches/blob/main/PS3/NPJB00439.savepatch'
RECORD_SOURCE_URL = 'https://web.save-editor.com/cache/bbs_savedata_ps3/7070.html'
CHECKSUM_RANGE = (0x8, 0x36E0)  # End is exclusive.
CHECKSUM_OFFSETS = (0x36E0, 0x23790)
MONEY_OFFSET = 0x2758
MIN_CANDIDATE_SIZE = 0x23794
MAX_CANDIDATE_SIZE = 2 * 1024 * 1024  # Processing ceiling, not native size.
PSN_TITLE_ID = 'NPJB00439'
# Only independently published anchors, never an invented complete roster.
EXP_ANCHORS = ((0x2C, 'Sanada Yukimura'), (0xE3C, 'Ina'), (0x1D3C, 'Shibata Katsuie'))
WEAPON_ANCHORS = ((0x47, 2), (0x5A, 3), (0x6D, 4))


@dataclass(frozen=True)
class ExperienceProbe:
    offset: int
    published_officer_label: str
    stored_value: int
    identity_qualified: bool = False


@dataclass(frozen=True)
class WeaponProbe:
    offset: int
    published_position: int
    raw_record: bytes
    stored_type: int
    stored_element: int
    stored_effect_ids: tuple[int, ...]
    stored_effect_values: tuple[int, ...]
    stored_effect_count: int
    ownership_qualified: bool = False


@dataclass(frozen=True)
class Inspection:
    size: int
    candidate_money: int
    expected_byte_sum: int
    stored_checksums: tuple[int, int]
    checksums_match: bool
    editable: bool = False
    qualified_game_profile: bool = False
    experience_probes: tuple[ExperienceProbe, ...] = ()
    weapon_probes: tuple[WeaponProbe, ...] = ()


@dataclass(frozen=True)
class ExportInspection:
    """Matching companion identity is distinct from qualified gameplay bytes.

    Retain only the public title ID, never the original metadata, directory
    suffix, account fields or console signing context.
    """
    candidate_title_id: str
    payload_probe: Inspection
    title_context_matches: bool = True
    editable: bool = False
    qualified_game_profile: bool = False


def inspect_export(raw, metadata):
    """Inspect explicit copied bytes with matching PSN export context.

    This rejects the separate NPJB00464 Empires export, disc-compilation
    metadata and other games even when their filename is DATA.BIN. A matching
    SFO and duplicated checksum cannot establish the missing native layout,
    revision or complete integrity; the result never permits gameplay writes.
    No files are read or written by this diagnostic.
    """
    directory = savedata_directory(metadata)
    if directory != PSN_TITLE_ID and not directory.startswith(PSN_TITLE_ID + '-'):
        raise SaveError('SW2 with Xtreme Legends HD candidate context requires '
                        'NPJB00439; Empires and compilation metadata are separate.')
    return ExportInspection(PSN_TITLE_ID, inspect(raw))


def inspect(raw):
    """Probe a bounded candidate; matching sums do not validate a save.

    The published additive range covers only an initial section. Bytes outside
    it, including the header, may change while both sums still match. Probes
    deliberately retain unusual integers and unknown IDs/counts as raw facts;
    no ownership, level/stat dependency, natural cap or native profile is inferred.
    """
    if (type(raw) is not bytes or not MIN_CANDIDATE_SIZE <= len(raw) <= MAX_CANDIDATE_SIZE):
        raise SaveError('Source-only SW2 HD diagnostic requires bounded decrypted candidate bytes.')
    expected = sum(raw[CHECKSUM_RANGE[0]:CHECKSUM_RANGE[1]]) & 0xFFFFFFFF
    actual = tuple(int.from_bytes(raw[offset:offset + 4], 'big') for offset in CHECKSUM_OFFSETS)
    money = int.from_bytes(raw[MONEY_OFFSET:MONEY_OFFSET + 4], 'big')
    experience = tuple(ExperienceProbe(offset, label, int.from_bytes(raw[offset:offset + 4], 'big'))
                       for offset, label in EXP_ANCHORS)
    weapons = []
    for offset, position in WEAPON_ANCHORS:
        record = raw[offset:offset + 0x13]
        weapons.append(WeaponProbe(offset, position, record, record[0], record[1],
                                   tuple(record[2:10]), tuple(record[10:18]), record[18]))
    return Inspection(len(raw), money, expected, actual, actual == (expected, expected),
                      experience_probes=experience, weapon_probes=tuple(weapons))
