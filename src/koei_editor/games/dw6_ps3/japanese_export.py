"""Conversion-only original Japanese BLJM60041 export, independently qualified.

The complete native 212,176-byte reference corroborates the typed officer,
horse, stage and Musou arrays. Its framing and exact original PARAM.SFO stay
region-specific. PFD authentication remains external; no scalar editor is added.
"""
from koei_editor.games.dw6_ps3.regional_export import (
    RegionalExport, Format, Document, OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT,
    HORSE_BASE, HORSE_STRIDE, HORSE_COUNT, INTEGRITY_KIND,
)

GAME_ID = 'dw6_ps3_jp'
SAVE_SIZE = 212176
TITLE_DIRECTORY = 'BLJM60041-SAVEDATA'
_profile = RegionalExport(GAME_ID, SAVE_SIZE, TITLE_DIRECTORY, 'Japanese')
FORMAT = _profile.format
decode, read_save, context_raw = _profile.decode, _profile.read_save, _profile.context_raw
validate_document, serialize = _profile.validate_document, _profile.serialize
_storage = _profile.storage
backup = _storage.backup
