"""Typed original DW6 gallery availability and challenge-board migration.

This explicit scope extends stored Musou campaign migration. Native accessors
establish 40 music bits and 170 movie bits, plus five ten-rank challenge boards
of u16 score, one-byte officer reference and one opaque byte. Native regional
exports corroborate their different locations; there is no constant file delta.
"""
from koei_editor.games.dw6 import campaign_conversion as campaigns
from koei_editor.games.dw6 import converter as roster

TRANSFER_SCOPE = 'roster-stages-musou-slots-gallery-and-challenges'
ROUTE_LABEL = 'progress, Musou slots, gallery and challenges'
SCOPE_DESCRIPTION = ('41 officers, eight horses, stages, Musou history and 20 run slots, '
                     '40 music/170 movie availability bits and five challenge boards; '
                     'destination options and interim battle retained')
NOTES = (
    campaigns.NOTES[0],
    campaigns.NOTES[1],
    'Also replaces the 40 music and 170 movie availability bits and all five ten-rank challenge boards. '
    'Each challenge score travels with its officer reference; this replaces records, not a best-score merge.',
    'Unseen or locked source gallery entries replace destination availability too. '
    'The six reserved high bits after movie 170 remain from the destination template.',
    'Options, controller mappings, native framing and the entire interim battle remain from the destination. '
    'Finish suspended battles before making both copies. Loading or resuming in-game remains unverified.',
)
MUSIC_COUNT, MOVIE_COUNT = 40, 170
GALLERY_BYTES = 27
BOARD_COUNT, RANK_COUNT, RECORD_STRIDE = 5, 10, 4

# The PC-only options section changes the gallery-to-slot delta. Western PS3
# also omits the fourteen bytes present before Japanese/PC challenge boards.
_LAYOUTS = {
    'dw6': (0xB4, 0x2BF6),
    'dw6_ps3': (0xAC, 0x2BA8),
    'dw6_ps3_eu': (0xAC, 0x2BA8),
    'dw6_ps3_jp': (0xAC, 0x2BB6),
    'dw6_xbox360_na': (0xAC, 0x2BA8),
    'dw6_xbox360_eu': (0xAC, 0x2BA8),
}


def _bases(document):
    backend, endian = roster._profile(document)
    gallery, challenges = _LAYOUTS[backend.GAME_ID]
    return gallery, challenges, endian


def _records(document):
    gallery, challenges, endian = _bases(document)
    raw = document.payload
    result = bytearray(raw[gallery:gallery + GALLERY_BYTES])
    # Only 170 movie bits are established. Reserved high bits do not contribute
    # to the canonical review/hash and are not transplanted from the source.
    result[-1] &= 3
    for index in range(BOARD_COUNT * RANK_COUNT):
        at = challenges + index * RECORD_STRIDE
        result.extend(int.from_bytes(raw[at:at + 2], endian).to_bytes(2, 'little'))
        result.extend(raw[at + 2:at + RECORD_STRIDE])
    return bytes(result)


def gameplay(document):
    return campaigns.gameplay(document) + _records(document)


def encode(source, template):
    records = _records(source)
    gallery, challenges, endian = _bases(template)
    result = bytearray(campaigns.encode(source, template))
    result[gallery:gallery + GALLERY_BYTES - 1] = records[:GALLERY_BYTES - 1]
    last = gallery + GALLERY_BYTES - 1
    result[last] = (result[last] & 0xFC) | records[GALLERY_BYTES - 1]
    for index in range(BOARD_COUNT * RANK_COUNT):
        a = GALLERY_BYTES + index * RECORD_STRIDE
        b = challenges + index * RECORD_STRIDE
        result[b:b + 2] = int.from_bytes(records[a:a + 2], 'little').to_bytes(2, endian)
        result[b + 2:b + RECORD_STRIDE] = records[a + 2:a + RECORD_STRIDE]
    backend, _endian = roster._profile(template)
    raw = bytes(result)
    backend.validate_document(backend.decode(raw))
    return raw


def preview_notes(source, template):
    before, after = _records(template), _records(source)
    music_changes = sum((a ^ b).bit_count() for a, b in zip(before[:5], after[:5]))
    movie_changes = sum((a ^ b).bit_count() for a, b in zip(before[5:GALLERY_BYTES], after[5:GALLERY_BYTES]))
    changed = [str(index + 1) for index in range(BOARD_COUNT)
               if before[GALLERY_BYTES + index * RANK_COUNT * RECORD_STRIDE:
                         GALLERY_BYTES + (index + 1) * RANK_COUNT * RECORD_STRIDE]
               != after[GALLERY_BYTES + index * RANK_COUNT * RECORD_STRIDE:
                        GALLERY_BYTES + (index + 1) * RANK_COUNT * RECORD_STRIDE]]
    return campaigns.preview_notes(source, template) + (
        f'Gallery review: {music_changes} of 40 music and {movie_changes} of 170 movie availability bits differ. '
        'Source availability replaces destination state; reserved bits remain from the destination.',
        f'Challenge review: {len(changed)} of five complete ten-rank boards differ. Board numbers: '
        + (', '.join(changed) or 'None; all challenge records already match.')
        + '. All 50 scores, their officer references and record padding move together.',
    )
