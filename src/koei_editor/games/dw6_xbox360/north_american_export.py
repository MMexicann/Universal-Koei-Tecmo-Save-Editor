"""Original North American 4B4F07E0 extracted DW6_NA.dat conversion profile."""
from koei_editor.games.dw6_xbox360.regional_export import (
    RegionalExport, Format, Document, SAVE_SIZE, OFFICER_BASE, OFFICER_STRIDE,
    OFFICER_COUNT, HORSE_BASE, HORSE_STRIDE, HORSE_COUNT, INTEGRITY_KIND,
)

GAME_ID = 'dw6_xbox360_na'
FILENAME = 'DW6_NA.dat'
_profile = RegionalExport(GAME_ID, 'North American', FILENAME)
FORMAT = _profile.format
decode, read_save, context_raw = _profile.decode, _profile.read_save, _profile.context_raw
validate_document, serialize, backup = _profile.validate_document, _profile.serialize, _profile.backup
