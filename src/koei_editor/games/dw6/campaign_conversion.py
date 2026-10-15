"""Typed original DW6 Musou run slots, separate from interim battle snapshots.

The native constructor builds twenty 132-byte records immediately before the
officer array. Each has five timestamp words, six 16-byte result records and
four selection words. Result flags/padding are bytes, not endian-swapped words.
Complete PC and US/European/Japanese exports independently corroborate the map.
"""
from koei_editor.games.dw6 import converter as roster
from koei_editor.games.dw6 import progression_conversion as progress

TRANSFER_SCOPE = 'roster-stages-musou-and-slots'
ROUTE_LABEL = 'progress and Musou save slots'
SCOPE_DESCRIPTION = ('41 officers, eight horses, 45 stage records, 17 Musou availability/clear records and '
                     '20 Musou run slots; destination gallery, challenges, options and interim battle retained')
NOTES = (
    progress.NOTES[0],
    'Also replaces all 20 stored Musou run slots, including timestamps, six stage-result records per slot, '
    'and their mode, difficulty, stage and horse selections. Empty source slots replace destination slots too.',
    'This transfers stored campaign slots, not an interim battle snapshot. Gallery, challenge boards, options '
    'and suspended battles remain from the destination template. No active battle is resumed by this route.',
    'Finish suspended battles before making the source copy and destination template. '
    'Original PC, US BLUS30110, European BLES00215 and Japanese BLJM60041 PS3, '
    'and North American 4B4F07E0/European 4B4F07E1 Xbox 360 only; Special and Empires differ.',
)
SLOT_COUNT, SLOT_STRIDE, RESULT_COUNT, RESULT_STRIDE = 20, 132, 6, 16


def _base(document):
    backend, endian = roster._profile(document)
    return backend.OFFICER_BASE - SLOT_COUNT * SLOT_STRIDE, endian


def _word_offsets():
    yield from range(0, 20, 4)
    for index in range(RESULT_COUNT):
        yield from range(20 + index * RESULT_STRIDE, 32 + index * RESULT_STRIDE, 4)
    yield from range(116, SLOT_STRIDE, 4)


_WORDS = tuple(_word_offsets())


def _slots(document):
    base, endian = _base(document)
    result = bytearray(document.payload[base:base + SLOT_COUNT * SLOT_STRIDE])
    for index in range(SLOT_COUNT):
        start = index * SLOT_STRIDE
        for relative in _WORDS:
            at = start + relative
            result[at:at + 4] = int.from_bytes(result[at:at + 4], endian).to_bytes(4, 'little')
    return bytes(result)


def gameplay(document):
    return progress.gameplay(document) + _slots(document)


def encode(source, template):
    slots = _slots(source)
    base, endian = _base(template)
    result = bytearray(progress.encode(source, template))
    for index in range(SLOT_COUNT):
        start = index * SLOT_STRIDE
        record = bytearray(slots[start:start + SLOT_STRIDE])
        for relative in _WORDS:
            record[relative:relative + 4] = int.from_bytes(record[relative:relative + 4], 'little').to_bytes(4, endian)
        result[base + start:base + start + SLOT_STRIDE] = record
    backend, _endian = roster._profile(template)
    raw = bytes(result)
    backend.validate_document(backend.decode(raw))
    return raw


def preview_notes(source, template):
    before, after = _slots(template), _slots(source)
    changed = [str(index + 1) for index in range(SLOT_COUNT)
               if before[index * SLOT_STRIDE:(index + 1) * SLOT_STRIDE]
               != after[index * SLOT_STRIDE:(index + 1) * SLOT_STRIDE]]
    return progress.preview_notes(source, template) + (
        f'Musou slot review: {len(changed)} of 20 complete run slots differ. Slots: '
        + (', '.join(changed) or 'None; all Musou slots already match.')
        + '. Source slots replace destination slots; current interim battle data is excluded.',
    )
