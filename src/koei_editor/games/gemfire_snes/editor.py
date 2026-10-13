"""Gemfire province editing using the shared guarded scalar workspace."""
from koei_editor.games.gemfire_snes import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        return (InspectionTable(
            "Native province records",
            ("State offset", "Province", "Faction ID", "Gold", "Food", "Soldiers",
             "Loyalty", "Farming", "Protection", "Editing"),
            parser.province_records(document),
            "State offsets identify structurally qualified existing battery records. "
            "They are not inferred slot numbers. Only saved player provinces are editable; "
            "soldiers, enemy provinces and army/leader relationships stay read only."),)


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = parser.EXTENSION
    presentation_type = Presentation
    subtitle = 'SNES · USA qualified 8 KiB battery records'
    summary = "Player province gold, food, loyalty, farming and protection."
