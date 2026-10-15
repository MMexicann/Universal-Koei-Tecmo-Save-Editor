"""Original US/EU DW7 XL PS3 scalar editor and searchable native inspections."""
from koei_editor.games.dw7xl_ps3 import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class DW7XLPS3Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        rows = parser.inspection_rows(document)
        tables = []
        for group in ('Status', 'Equipment', 'Purchased skills'):
            selected = tuple((row['label'], row['value']) for row in rows if row['group'] == group)
            if selected:
                tables.append(InspectionTable(group, ('Record', 'Stored value'), selected,
                                              'Native PS3 records. Progress, ownership and purchased skill flags are read only.'))
        inventory = tuple((row['slot'], 'Owned' if row['owned'] else 'Unowned',
                           row['seal_meter'], f"0x{row['flags']:04X}")
                          for row in parser.weapons(document))
        tables.append(InspectionTable('Weapon inventory',
                                      ('Physical record', 'Ownership', 'Seal learning meter', 'Stored flags'),
                                      inventory,
                                      'Only existing owned, unlearned meters allow decreases. Names, identities and seal rewards are preserved.'))
        return tuple(tables)


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.bin'
    presentation_type = DW7XLPS3Presentation
    subtitle = 'Original US/EU PS3 · PFD-decrypted APP.BIN and original PARAM.SFO'
    summary = ('Edit Gold and 65 officers’ stored stats/skill points; decrease existing unlearned seal meters; '
               'choose an already equipped owned weapon. External reimport/resigning required.')


def read_save(path):
    return parser.read_save(path)
