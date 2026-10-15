"""Qualified one-way original DW7 XL PS3 to Definitive Edition PC migration.

Native PC accessors and copied original XL exports establish individual numeric
widths and byte bitsets. Revision, platform options, online data, padding and
the inactive interim-battle object remain from the destination PC template.
This module never pads, truncates or blanket-swaps an unknown file region.
"""
from functools import lru_cache

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw7xl import dw7xl_codec as codec
from koei_editor.games.dw7xl import dw7xl_parser as pc
from koei_editor.games.dw7xl_ps3 import parser as ps3


SUPPORTED_DIRECTIONS = frozenset({(ps3.GAME_ID, pc.GAME_ID)})
TRANSFER_SCOPE = 'dw7xl-qualified-persistent-progress'
ROUTE_LABEL = 'qualified persistent progress'
SCOPE_DESCRIPTION = ('Original US/European PS3 DW7 Xtreme Legends to Definitive Edition PC: '
                     'qualified system progress, 92 officer records, 1,738 weapons, '
                     '16 guardian records, stage context and 80 challenge records; '
                     'destination PC settings, online data and inactive battle retained')
NOTES = (
    'Requires original US BLUS30873 or European BLES01496 DW7 Xtreme Legends, '
    'PFD-decrypted APP.BIN and its exact original PARAM.SFO. Base DW7, Empires and Vita differ.',
    'Transfers existing typed progress and complete relationships between officers, weapons, '
    'learned seals and guardians. Source state replaces the corresponding destination values; '
    'this is not a best-value or inventory merge.',
    'PC settings, online/profile data, unqualified bytes, padding and the complete inactive '
    'interim battle stay from the destination PC template. Finish suspended battles in both games first.',
    'Both copies must have zero bytes in the unidentified story and Legend progress extensions. '
    'A nonzero extension is rejected rather than mixing potentially meaningful unknown progression.',
    'The destination PC revision and cipher seed are retained, and its native checksum is recomputed. '
    'PS3 DLC ownership does not establish PC DLC entitlements or equivalent edition completion. '
    'Actual destination game loading and re-saving remain unverified.',
)
OFFICER_BASE, OFFICER_COUNT, OFFICER_STRIDE = 0x2039, 92, 128
WEAPON_BASE, WEAPON_COUNT, WEAPON_STRIDE = 0x4E39, 1738, 20
GUARDIAN_BASE, GUARDIAN_COUNT = 0xD601, 16
CONTEXT_BASE, CONTEXT_WORDS = 0xD641, 75
CHALLENGE_BASE, CHALLENGE_COUNT, CHALLENGE_STRIDE = 0xD6D7, 80, 20
INTERIM_BASE = 0xDD1F
STORY_BASE, STORY_COUNT, STORY_STRIDE = 4 + 0xCEE, 4, 0x132
LEGEND_BASE = 4 + 0x11B8

# System-relative numeric ranges: (relative start, count, width). These are
# independently typed accessors, not a default word size for the 0x1F78 block.
_SYSTEM_NUMERIC = (
    (0x000, 5, 4),
    (0x014, 766, 4),
    (0xC0C, 9, 4),
    (0xC30, 10, 4),
    (0xC58, 3, 4),
    (0xC64, 4, 4),
    (0xC74, 9, 4),
    (0xC98, 6, 2),
    (0xCA4, 18, 4),
    (0xCEC, 1, 2),
    (0x16BC, 75, 2),
)
_LEGEND_NUMERIC = (
    (0x000, 4, 2),
    (0x008, 180, 4),
    (0x2D8, 1, 4),
    (0x2DC, 22, 4),
    (0x334, 22, 4),
    (0x38C, 1, 2),
    (0x3A8, 11, 2),
    (0x3FE, 92, 2),
    (0x4B6, 32, 2),
    (0x4F6, 6, 2),
)
_REQUIRED_ZERO = tuple((STORY_BASE + index * STORY_STRIDE + 0xCE, 100)
                       for index in range(STORY_COUNT)) + (
    (LEGEND_BASE + 0x38E, 26), (LEGEND_BASE + 0x502, 2),
)


@lru_cache(maxsize=1)
def _numeric_fields():
    fields = []
    for base, count, width in _SYSTEM_NUMERIC:
        fields.extend((4 + base + index * width, width) for index in range(count))
    for index in range(STORY_COUNT):
        base = STORY_BASE + index * STORY_STRIDE
        # Native gains and selections are 103 shorts. Both copies must have
        # zero in the following 100 unqualified bytes, which stay untouched.
        fields.extend((base + relative, 2) for relative in range(0, 0xCE, 2))
    for base, count, width in _LEGEND_NUMERIC:
        fields.extend((LEGEND_BASE + base + index * width, width) for index in range(count))
    for index in range(OFFICER_COUNT):
        base = OFFICER_BASE + index * OFFICER_STRIDE
        fields.extend((base + relative, 4) for relative in (0, 0x70))
        fields.extend((base + relative, 2) for relative in tuple(range(4, 0x6E, 2)) + (0x74, 0x7A, 0x7C))
    for index in range(WEAPON_COUNT):
        base = WEAPON_BASE + index * WEAPON_STRIDE
        fields.append((base, 4))
        fields.extend((base + relative, 2) for relative in range(4, 18, 2))
    # Guardians are two u16s: ownership and another native short, not a u32.
    fields.extend((GUARDIAN_BASE + index * 2, 2) for index in range(GUARDIAN_COUNT * 2))
    fields.extend((CONTEXT_BASE + index * 2, 2) for index in range(CONTEXT_WORDS))
    for index in range(CHALLENGE_COUNT):
        base = CHALLENGE_BASE + index * CHALLENGE_STRIDE
        fields.extend((base + relative, 4) for relative in (0, 16))
        fields.extend((base + relative, 2) for relative in range(4, 16, 2))
    return tuple(sorted(fields))


@lru_cache(maxsize=1)
def _byte_spans():
    # Native 59B9F0/59D103 index the four bytes at +0x76 individually.
    # Swapping this region as one u32 would change which flags are enabled.
    officer_spans = tuple((OFFICER_BASE + index * OFFICER_STRIDE + relative, size)
                          for index in range(OFFICER_COUNT) for relative, size in ((0x76, 4), (0x7E, 1)))
    # Native 6AFA84 sets these 64 collection enums one BYTE at a time.
    return ((LEGEND_BASE + 0x3BE, 64),) + officer_spans


def _profile(document):
    game_id = getattr(getattr(document, 'format', None), 'id', None)
    if game_id == pc.GAME_ID:
        pc.validate_document(document)
        order = 'little'
    elif game_id == ps3.GAME_ID:
        ps3.validate_document(document)
        order = 'big'
    else:
        raise SaveError('DW7 XL migration requires original US/European XL PS3 and Definitive Edition PC snapshots.')
    if any(any(document.payload[offset:offset + size]) for offset, size in _REQUIRED_ZERO):
        raise SaveError('The DW7 XL source or destination copy contains nonzero unqualified story or Legend '
                        'progress extensions. Their meaning is not mapped, so these copies cannot be converted safely.')
    if document.payload[INTERIM_BASE] != 0:
        raise SaveError('Finish the suspended DW7 XL battle in the source and destination games '
                        'before making their copied saves. Active or unknown interim states cannot be converted.')
    return order


def gameplay(document):
    order = _profile(document)
    result = bytearray()
    for offset, width in _numeric_fields():
        result.extend(int.from_bytes(document.payload[offset:offset + width], order).to_bytes(width, 'little'))
    for offset, size in _byte_spans():
        result.extend(document.payload[offset:offset + size])
    return bytes(result)


def encode(source, template):
    _profile(source)
    _profile(template)
    if (source.format.id, template.format.id) not in SUPPORTED_DIRECTIONS:
        raise SaveError('This qualified DW7 XL route converts original US/European PS3 to Definitive Edition PC only.')
    canonical = gameplay(source)
    result, cursor = bytearray(template.payload), 0
    for offset, width in _numeric_fields():
        result[offset:offset + width] = canonical[cursor:cursor + width]
        cursor += width
    for offset, size in _byte_spans():
        result[offset:offset + size] = canonical[cursor:cursor + size]
        cursor += size
    raw = codec.encode(bytes(result), template.seed)
    reopened = pc.decode(raw)
    pc.validate_document(reopened)
    if gameplay(reopened) != canonical:
        raise SaveError('DW7 XL converted PC copy failed typed gameplay read-back verification.')
    return raw


def preview_notes(source, template):
    source_order, target_order = _profile(source), _profile(template)

    def changed(base, count, stride, numeric, byte_spans=()):
        differing = 0
        for index in range(count):
            start = base + index * stride
            numeric_changed = any(
                int.from_bytes(source.payload[start + offset:start + offset + width], source_order)
                != int.from_bytes(template.payload[start + offset:start + offset + width], target_order)
                for offset, width in numeric)
            bytes_changed = any(source.payload[start + offset:start + offset + size]
                                != template.payload[start + offset:start + offset + size]
                                for offset, size in byte_spans)
            differing += numeric_changed or bytes_changed
        return differing

    officer_numbers = tuple((offset, 4) for offset in (0, 0x70)) + tuple(
        (offset, 2) for offset in tuple(range(4, 0x6E, 2)) + (0x74, 0x7A, 0x7C))
    officers = changed(OFFICER_BASE, OFFICER_COUNT, OFFICER_STRIDE, officer_numbers, ((0x76, 4), (0x7E, 1)))
    weapons = changed(WEAPON_BASE, WEAPON_COUNT, WEAPON_STRIDE,
                      ((0, 4),) + tuple((offset, 2) for offset in range(4, 18, 2)))
    guardians = changed(GUARDIAN_BASE, GUARDIAN_COUNT, 4, ((0, 2), (2, 2)))
    challenges = changed(CHALLENGE_BASE, CHALLENGE_COUNT, CHALLENGE_STRIDE,
                         ((0, 4), (16, 4)) + tuple((offset, 2) for offset in range(4, 16, 2)))
    return (
        f'Officer review: {officers} of 92 native records differ, including the 65 playable slots. '
        'Stats, purchased flags, equipment and source progression move together; names are not guessed.',
        f'Weapon review: {weapons} of 1,738 physical records differ. Ownership, learning state, '
        'five stored references and their system seal flags are transferred together; this replaces records.',
        f'Guardian review: {guardians} of 16 existing records differ. '
        f'Challenge review: {challenges} of 80 complete result records differ.',
        'Destination PC settings, online data, unqualified bytes and the complete inactive battle are retained. '
        'Source and destination suspended battles must already be finished. No conversion has been loaded in-game.',
    )
