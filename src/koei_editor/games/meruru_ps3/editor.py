"""PS3 copied-save session with searchable character/system inspection."""

from koei_editor.games.meruru_ps3 import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        characters, sections = self.backend.inspection_rows(document)
        return (
            InspectionTable(
                "Characters",
                ("Name", "Native ID", "Stored level", "Stored EXP"),
                characters,
                "Read-only original character records, including NPC/DLC entries; derived stats and growth dependencies remain under game control.",
            ),
            InspectionTable(
                "Save-backed systems",
                ("Tag", "System", "Bytes"),
                sections,
                "Complete framed native systems; opaque record data is preserved.",
            ),
        )


class Editor(ScalarEditor):
    save_extension = ".bin"
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    subtitle = "Original PlayStation 3 · decrypted export"
    summary = "Reduce Cole; inspect named character levels/EXP and serialized systems. Keep original PARAM.SFO beside the copy, then reimport and resign with Apollo."
