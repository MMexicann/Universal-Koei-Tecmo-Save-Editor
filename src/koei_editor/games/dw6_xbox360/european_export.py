"""Original European 4B4F07E1 extracted DW6_EU.dat conversion profile."""
from koei_editor.games.dw6_xbox360.regional_export import (
    RegionalExport, Format, Document, SAVE_SIZE, OFFICER_BASE, OFFICER_STRIDE,
    OFFICER_COUNT, HORSE_BASE, HORSE_STRIDE, HORSE_COUNT, INTEGRITY_KIND,
)

GAME_ID = 'dw6_xbox360_eu'
FILENAME = 'DW6_EU.dat'
_profile = RegionalExport(GAME_ID, 'European', FILENAME)
FORMAT = _profile.format
decode, read_save, context_raw = _profile.decode, _profile.read_save, _profile.context_raw
validate_document, serialize, backup = _profile.validate_document, _profile.serialize, _profile.backup
