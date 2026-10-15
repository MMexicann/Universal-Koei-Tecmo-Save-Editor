"""Typed DW6 PC/US PS3 roster and horse migration into a destination save.

This is a scoped migration, not a story or suspended-battle conversion. See
DW6_CONVERSION.md for the native field geometry and evidence boundaries.
"""
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw6 import dw6_parser as pc
from koei_editor.games.dw6_ps3 import parser as ps3
from koei_editor.games.dw6_ps3 import japanese_export as ps3_jp

TRANSFER_SCOPE = 'roster-and-horses'
SCOPE_DESCRIPTION = 'DW6 roster and horses only; destination story and battle state retained'
NOTES = (
    'Transfers all 41 officer records: the 64-bit skill mask, eight weapons each, outfit, title, stored level, EXP, kills, equipped slot and playable flag.',
    'Transfers all eight complete horse records, including names, growth descriptors, model, EXP, skills, element and combat stats.',
    'Story clears, stages, gallery, challenges, options and suspended battles remain from the destination template. This is a partial progress migration.',
    'Finish any suspended battle in the destination game before creating its template. Keep compatible original DW6 editions; Special and Empires differ.',
)


def _profile(document):
    identity = getattr(getattr(document, 'format', None), 'id', None)
    if identity == pc.GAME_ID:
        pc.validate_document(document)
        return pc, 'little'
    if identity == ps3.GAME_ID:
        ps3.validate_document(document)
        return ps3, 'big'
    if identity == ps3_jp.GAME_ID:
        ps3_jp.validate_document(document)
        return ps3_jp, 'big'
    raise SaveError('DW6 migration requires original PC, US BLUS30110 or Japanese BLJM60041 PS3 saves.')


def _canonical(document):
    backend, endian = _profile(document)
    raw = document.payload
    result = bytearray()
    for index in range(41):
        base = backend.OFFICER_BASE + index * 168
        # Native full-tree masks are ffffffffffff0100 on PC and
        # 0001ffffffffffff on PS3: one 64-bit mask, not two swapped u32s.
        result.extend(int.from_bytes(raw[base:base + 8], endian).to_bytes(8, 'little'))
        for relative in range(8, 164, 4):
            result.extend(int.from_bytes(raw[base + relative:base + relative + 4], endian).to_bytes(4, 'little'))
        # Playable is a byte on BOTH platforms, followed by three opaque bytes.
        # Treating it as a PS3 u32 would turn an unlocked officer into 16777216.
        result.extend(raw[base + 164:base + 168])
    for index in range(8):
        # The record starts 24 bytes BEFORE EXP. Its trailing combat stats end
        # at EXP+36; the next name/model fields belong to the NEXT horse.
        base = backend.HORSE_BASE - 24 + index * 60
        for relative in range(0, 60, 4):
            result.extend(int.from_bytes(raw[base + relative:base + relative + 4], endian).to_bytes(4, 'little'))
    return bytes(result)


def gameplay(document):
    return _canonical(document)


def encode(source, template):
    canonical = gameplay(source)
    backend, endian = _profile(template)
    result = bytearray(template.raw)
    cursor = 0
    for index in range(41):
        base = backend.OFFICER_BASE + index * 168
        record = canonical[cursor:cursor + 168]
        result[base:base + 8] = int.from_bytes(record[:8], 'little').to_bytes(8, endian)
        for relative in range(8, 164, 4):
            result[base + relative:base + relative + 4] = int.from_bytes(record[relative:relative + 4], 'little').to_bytes(4, endian)
        result[base + 164:base + 168] = record[164:168]
        cursor += 168
    for index in range(8):
        base = backend.HORSE_BASE - 24 + index * 60
        for relative in range(0, 60, 4):
            result[base + relative:base + relative + 4] = int.from_bytes(canonical[cursor:cursor + 4], 'little').to_bytes(4, endian)
            cursor += 4
    raw = bytes(result)
    backend.validate_document(backend.decode(raw))
    return raw


def preview_notes(source, template):
    """Describe exactly which complete typed records replace the template."""
    from koei_editor.games.dw6.dw6_metadata import OFFICER_NAMES
    before, after = gameplay(template), gameplay(source)
    changed = [name for i, name in enumerate(OFFICER_NAMES)
               if before[i * 168:(i + 1) * 168] != after[i * 168:(i + 1) * 168]]
    start = 41 * 168
    horses = [str(i + 1) for i in range(8)
              if before[start + i * 60:start + (i + 1) * 60] != after[start + i * 60:start + (i + 1) * 60]]
    return (f'Roster review: {len(changed)} of 41 complete officer records differ from the destination template. '
            'Level, EXP, learned tree, equipment and playable state move together; no independent level or skill-tree unlock is applied.',
            'Officers replaced with different source state: ' + (', '.join(changed) or 'None; all roster records already match.'),
            f'Horse review: {len(horses)} of eight complete records differ. Slots: ' + (', '.join(horses) or 'None; all horse records already match.')
            + '. Empty source slots also replace destination slots; this is replacement, not an inventory merge.')
