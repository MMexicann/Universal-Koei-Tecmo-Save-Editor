"""PS3 copied-save session with searchable character/system inspection."""

from koei_editor.games.rorona_ps3 import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        characters, sections = self.backend.inspection_rows(document)
        return (
            InspectionTable(
                "Characters",
                ("Name", "Native ID", "Raw u32 +4", "Raw u32 +8"),
                characters,
                "Read-only seven original character records; The first status word has a published address; its meaning and adjacent words remain unqualified. Growth and stat dependencies remain under game control.",
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
    summary = "Reduce Cole; inspect named character raw records and serialized systems. Keep original PARAM.SFO beside the copy, then reimport and resign with Apollo."
