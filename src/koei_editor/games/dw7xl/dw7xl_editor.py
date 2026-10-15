"""Explicit native Windows DW7 XL Definitive Edition adapter."""
import koei_editor.games.dw7xl.dw7xl_parser as dw7xl_parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class DW7Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        rows = self.backend.inspection_rows(document)
        inventory = tuple((row['slot'], 'Owned' if row['owned'] else 'Unowned',
                           row['seal_meter'], f"0x{row['flags']:04X}")
                          for row in self.backend.weapons(document))
        return (InspectionTable('Equipment', ('Officer slot', 'Equipped records / guardian'),
                                tuple((row['label'], row['value']) for row in rows if row['group'] == 'Equipment'),
                                'Switch the active equipped weapon in the Equipment edit group; guardian ownership is not inferred.'),
                InspectionTable('Purchased skills', ('Officer slot', 'Stored skill bits'),
                                tuple((row['label'], row['value']) for row in rows if row['group'] == 'Purchased skills'),
                                'Read only. Officer-specific skill definitions and prerequisites require game parameter data.'),
                InspectionTable('Weapon inventory', ('Physical record', 'Ownership', 'Seal learning meter', 'Stored flags'),
                                inventory, 'Existing owned, unlearned meters permit manual reduction only. Base weapon attack, element and seal capacity come from game data, rather than this save.'),
                InspectionTable('Applied seals', ('Physical record', 'Slot 1', 'Slot 2', 'Slot 3', 'Slot 4', 'Slot 5', 'Editing'),
                                self.backend.applied_seal_rows(document),
                                'Use Applied seals to replace/remove learned ordinary seals in occupied slots. Empty slots remain read only; seal names and capacity require matching game data.'))


class Editor(ScalarEditor):
    game_id = 'dw7xl'
    backend = dw7xl_parser
    presentation_type = DW7Presentation
    subtitle = 'Windows PC save editor'
    summary = 'Gold, officer stats, existing weapon loadouts, learned applied seals and unlearned seal-meter reduction.'


def read_save(path):
    return dw7xl_parser.read_save(path)
