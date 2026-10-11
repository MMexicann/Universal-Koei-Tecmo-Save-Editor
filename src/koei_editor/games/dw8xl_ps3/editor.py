"""US PS3 native save workspace using shared review/Undo/copy protection."""

from koei_editor.games.dw8xl_ps3 import parser
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = ".bin"
    subtitle = "PS3 US PSN NPUB31449 — PFD-decrypted native export"
    summary = (
        "Gold, gems, materials, 82 officer records, four weapon-action "
        "compatibilities and existing weapon attribute ranks; searchable records. "
        "Keep matching PARAM.SFO; reimport and resign with Apollo."
    )
