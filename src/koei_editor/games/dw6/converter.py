"""Typed DW6 PC/US PS3 roster and horse migration into a destination save.

This is a scoped migration, not a story or suspended-battle conversion. See
DW6_CONVERSION.md for the native field geometry and evidence boundaries.
"""
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw6 import dw6_parser as pc
from koei_editor.games.dw6_ps3 import parser as ps3

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
    raise SaveError('DW6 migration requires original PC or US BLUS30110 PS3 saves.')


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
