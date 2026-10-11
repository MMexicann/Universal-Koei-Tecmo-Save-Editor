"""PS4 session with searchable inventory/equipment and game-system views."""

from koei_editor.games.sophie2_ps4 import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        items, party, resources, systems = self.backend.inspection_rows(document)
        return (
            InspectionTable(
                "Inventory and equipment",
                (
                    "Location",
                    "Record",
                    "Item ID",
                    "Quality",
                    "Uses",
                    "Capacity",
                    "Traits IDs",
                    "Effects IDs",
                ),
                items,
                "Existing records; numeric IDs remain searchable. Important items, tools, equipment stats, effects and traits remain unchanged.",
            ),
            InspectionTable(
                "Characters",
                ("Name", "Stored level", "Stored EXP"),
                party,
                "Read-only native Party values; growth is controlled by the game.",
            ),
            InspectionTable(
                "Alchemy and wallet",
                ("Stored value", "Value"),
                resources,
                "Read-only values; level/EXP coupling and wallet preview dependencies are preserved.",
            ),
            InspectionTable(
                "Save-backed systems",
                ("System", "Bytes"),
                systems,
                "Complete framed native systems; story, recipe, dream-world and collection progression are preserved.",
            ),
        )


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    subtitle = "PlayStation 4 · CUSA28451 app 1.0"
    summary = "Reduce existing material quality and edit existing battle-item uses within saved capacity. Search inventory, equipment, characters and progression systems."
