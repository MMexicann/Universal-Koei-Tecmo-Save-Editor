"""Ryza 3 DX PC session with searchable native record inspection."""
from koei_editor.games.ryza3_dx_pc import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        inventory,party,sections = self.backend.inspection_rows(document)
        return (
            InspectionTable('Inventory and secret-key records',
                            ('Location','Record','Raw u16 +0','Raw u16 +2','Raw u16 +4',
                             'Raw u16 +6','Raw u16 +8','Raw u16 +10'),inventory,
                            'Existing native 128-byte records. Raw words are observations; IDs, quality, '
                            'effects and key uses have no writable mapping.'),
            InspectionTable('Party records',('Record','Raw i32 +0','Record bytes'),party,
                            'Existing framed records, including nonstandard identities; no character '
                            'name/stat/EXP/equipment mapping is inferred.'),
            InspectionTable('Save-backed systems',('Section','Native bytes'),sections,
                            'Search native sections. A section name alone does not qualify progression edits.'),
        )


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    subtitle = 'Steam PC · Ryza 3 DX native revision-4 profile'
    summary = ('Reduce unspent skill-tree SP and gems for rebuilding/duplication; search existing inventory, '
               'secret-key and Party records.')
