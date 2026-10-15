"""Typed persistent stage/Musou migration, separate from suspended battles.

The official English demo's native constructors establish 45 twenty-byte stage
records (three u32s, byte flags and padding), followed by seventeen four-byte
Musou records (two byte flags and padding). Complete native PC/US/Japanese PS3
exports corroborate both arrays between the officer and horse boundaries.
"""
from koei_editor.games.dw6 import converter as roster

TRANSFER_SCOPE = 'roster-stages-and-musou'
ROUTE_LABEL = 'roster, horses, stages and Musou history'
SCOPE_DESCRIPTION = ('41 officers, eight horses, 45 persistent stage records and 17 Musou availability/clear records; '
                     'destination gallery, challenges, options and suspended battles retained')
NOTES = (
    'Stage records include their three native counters, completion/difficulty flags and stage availability. '
    'Musou availability and clear flags move together with all 41 officers and eight horses.',
    'This is a partial persistent-progress migration. Gallery, challenge boards, options and suspended battles '
    'remain from the destination template; it does not continue an active campaign or battle.',
    'Finish any suspended battle in the destination game before creating its template. '
    'Original PC, US BLUS30110 and Japanese BLJM60041 only; Special and Empires differ.',
)
STAGE_COUNT, STAGE_STRIDE, MUSOU_COUNT, MUSOU_STRIDE = 45, 20, 17, 4


def _bases(document):
    backend, endian = roster._profile(document)
    stages = backend.OFFICER_BASE + 41 * 168
    musou = stages + STAGE_COUNT * STAGE_STRIDE
    return stages, musou, endian


def _progress(document):
    stages, musou, endian = _bases(document)
    raw, result = document.payload, bytearray()
    for index in range(STAGE_COUNT):
        base = stages + index * STAGE_STRIDE
        for relative in (0, 4, 8):
            result.extend(int.from_bytes(raw[base + relative:base + relative + 4], endian).to_bytes(4, 'little'))
        # Native stage +12, +13 and +16 are BYTEs, never an endian-swapped u32.
        result.extend(raw[base + 12:base + STAGE_STRIDE])
    # The constructor initializes byte +0 and byte +1, not a packed integer.
    result.extend(raw[musou:musou + MUSOU_COUNT * MUSOU_STRIDE])
    return bytes(result)


def gameplay(document):
    return roster.gameplay(document) + _progress(document)


def encode(source, template):
    progress = _progress(source)
    stages, musou, endian = _bases(template)
    result = bytearray(roster.encode(source, template))
    for index in range(STAGE_COUNT):
        a, b = index * STAGE_STRIDE, stages + index * STAGE_STRIDE
        for relative in (0, 4, 8):
            result[b + relative:b + relative + 4] = int.from_bytes(progress[a + relative:a + relative + 4], 'little').to_bytes(4, endian)
        result[b + 12:b + STAGE_STRIDE] = progress[a + 12:a + STAGE_STRIDE]
    result[musou:musou + MUSOU_COUNT * MUSOU_STRIDE] = progress[STAGE_COUNT * STAGE_STRIDE:]
    backend, _endian = roster._profile(template)
    raw = bytes(result)
    backend.validate_document(backend.decode(raw))
    return raw


def preview_notes(source, template):
    before, after = _progress(template), _progress(source)
    changed_stages = [str(i) for i in range(STAGE_COUNT)
                      if before[i * STAGE_STRIDE:(i + 1) * STAGE_STRIDE] != after[i * STAGE_STRIDE:(i + 1) * STAGE_STRIDE]]
    start = STAGE_COUNT * STAGE_STRIDE
    changed_modes = [str(i) for i in range(MUSOU_COUNT)
                     if before[start + i * MUSOU_STRIDE:start + (i + 1) * MUSOU_STRIDE]
                     != after[start + i * MUSOU_STRIDE:start + (i + 1) * MUSOU_STRIDE]]
    return roster.preview_notes(source, template) + (
        f'Stage review: {len(changed_stages)} of 45 persistent records differ. Native stage IDs: '
        + (', '.join(changed_stages) or 'None; all stage records already match.') + '.',
        f'Musou history review: {len(changed_modes)} of 17 availability/clear records differ. Native mode IDs: '
        + (', '.join(changed_modes) or 'None; all Musou records already match.')
        + '. Source history replaces destination history, including incomplete and locked entries.',
    )
