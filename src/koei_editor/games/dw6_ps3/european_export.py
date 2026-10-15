"""Conversion-only original European BLES00215 export.

Four independent native exports establish the exact 212,240-byte framing and
corroborate the typed officer, horse, stage and Musou arrays. Original metadata
is bound and preserved; US metadata is never substituted despite equal sizes.
"""
from koei_editor.games.dw6_ps3.regional_export import (
    RegionalExport, Format, Document, OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT,
    HORSE_BASE, HORSE_STRIDE, HORSE_COUNT, INTEGRITY_KIND,
)

GAME_ID = 'dw6_ps3_eu'
SAVE_SIZE = 212240
TITLE_DIRECTORY = 'BLES00215-SAVEDATA'
_profile = RegionalExport(GAME_ID, SAVE_SIZE, TITLE_DIRECTORY, 'European')
FORMAT = _profile.format
decode, read_save, context_raw = _profile.decode, _profile.read_save, _profile.context_raw
validate_document, serialize = _profile.validate_document, _profile.serialize
_storage = _profile.storage
backup = _storage.backup
