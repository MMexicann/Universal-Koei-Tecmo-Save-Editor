"""Original WO4 PC resources and searchable native record views."""
from koei_editor.games.wo4 import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        history, elements, officers, weapons = self.backend.inspection_rows(document)
        return (
            InspectionTable('Resource histories', ('History', 'Stored amount'), history,
                            'Earned history is separate from available resources and stays intact.'),
            InspectionTable('Weapon-element inventory', ('Element ID', 'Quantity'), elements,
                            'Existing ordinary quantities have individual controls; unknown or unusual values stay intact.'),
            InspectionTable('Officer records', ('Officer ID', 'Stored EXP', 'Skill Points', 'Raw u32 +21',
                                               'Raw u16 +25', 'Raw u16 +27'), officers,
                            'Skill Points have individual controls for existing progressed records; EXP, learned skills and equipped references remain read only.'),
            InspectionTable('Weapon records', ('Record', 'Raw u16 +0', 'Raw u16 +2', 'Raw u8 +4',
                                              'Raw IDs +5', 'Raw ranks +13'), weapons,
                            'Search native weapon records. Names, ownership, attack and fusion properties need independent mappings.'),
        )


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    save_extension = '.bin'
    subtitle = 'Windows PC · original Warriors Orochi 4'
    summary = ('Edit Gems, Crystals, Growth Points, existing weapon-element quantities and officer Skill Points; '
               'reduce existing Skill Orbs; '
               'search officer, weapon, inventory and resource-history records.')
