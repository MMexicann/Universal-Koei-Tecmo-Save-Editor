"""Original Windows PK resource editor using the shared staged workspace."""
from koei_editor.games.nobu6_pk_pc import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        rows = self.backend.inspection_rows(document)
        specs = (
            ('Save slots', ('Slot', 'State', 'Preview year', 'Season ID', 'Scenario ID', 'Difficulty ID')),
            ('Military districts', ('Slot', 'District', 'Clan', 'Residence castle', 'Leader', 'Gold', 'Rice', 'Horses', 'Firearms')),
            ('Generals', ('Slot', 'Record', 'Name', 'State ID', 'Clan', 'Political talent', 'Battle talent', 'Intelligence talent',
                          'Political proficiency', 'Battle proficiency', 'Intelligence proficiency', 'Loyalty')),
            ('Castles', ('Slot', 'Record', 'Name', 'District', 'Fortification', 'Rice yield', 'Commerce', 'Stored population', 'Loyalty')),
            ('Clans', ('Slot', 'Record', 'Leader ID', 'Leader', 'Court standing', 'Hostile clan ID', 'Friendly clan ID')),
            ('Treasures', ('Slot', 'Record', 'Name', 'Type ID', 'Owner ID', 'Stored bonus', 'State byte')),
        )
        return tuple(InspectionTable(title, columns, data,
                                     'Existing native records are searchable. Only admitted district-resource fields are writable; '
                                     'unknown names/IDs and all progression/ownership remain intact.')
                     for (title, columns), data in zip(specs, rows))


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = parser.EXTENSION
    presentation_type = Presentation
    subtitle = 'Original Japanese Windows Power-Up Kit · eight-slot SAVEDAT.n6p'
    summary = ('Reduce existing district Gold, Rice, Horses and Firearms. Search generals, castles, clans and treasures. '
               'Use a separate save copy outside the game folder.')
