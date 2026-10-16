"""Native Orochi Z resources and existing weapon editor."""
from koei_editor.games.orochiz import orochiz_parser as backend
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class OrochiZPresentation(ScalarPresentation):
    def inspection_tables(self, document):
        officers = tuple((row['id'], row['stored_level'] + 1, row['exp'],
                          ' / '.join(str(value) for value in row['stats'][:2]),
                          row['stats'][2], ' / '.join(str(value) for value in row['stats'][3:]),
                          row['proficiency'], row['equipped_slot'] + 1)
                         for row in backend.officers(document))
        weapons = tuple((row['officer'], row['slot'] + 1, row['id'],
                         'Empty' if row['id'] == backend.EMPTY_WEAPON else 'Stored weapon',
                         row['bonus'], row['capacity'], f"0x{row['mask']:04X}",
                         ', '.join(f'{identity}:{row["ranks"][identity] + 1}'
                                   for identity in range(15) if row['mask'] & (1 << identity)),
                         f"0x{row['alchemy']:04X}") for row in backend.weapons(document))
        return (InspectionTable('Officer progression',
                                ('Officer ID', 'Stored level + 1', 'EXP', 'Base Life / Musou',
                                 'Base attack', 'Base Defense / Speed',
                                 'Stored proficiency', 'Equipped slot + 1'), officers,
                                'Read only. Search by officer ID. Qualified existing weapons can be selected '
                                'in Equipment. Qualified base stats have independent per-officer bounds. '
                                'Level and proficiency remain unchanged.'),
                InspectionTable('Weapon inventory',
                                ('Officer ID', 'Slot', 'Weapon ID', 'Status', 'Attack bonus',
                                 'Attribute slots', 'Owned attributes', 'Attribute ID:level',
                                 'Alchemy abilities'), weapons,
                                'Search by officer, slot or weapon ID. Existing attack bonus, attribute capacity '
                                'and owned ranked attributes can be edited. Other weapon data stays unchanged.'))


class Editor(ScalarEditor):
    game_id = 'orochiz'
    save_extension = '.dat'
    backend = backend
    presentation_type = OrochiZPresentation
    subtitle = 'Windows PC save.dat editor'
    summary = 'Stock EXP, base Life/Musou/Attack/Defense/Speed, EXP within current levels, existing weapons and equipment.'


def read_save(path):
    return backend.read_save(path)
