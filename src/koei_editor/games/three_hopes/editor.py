"""Named native Three Hopes export workspace."""
from koei_editor.games.three_hopes import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    extra_groups = ('Characters', 'Weapons')

    def inspection_tables(self, document):
        characters = self.backend.characters(document)
        weapons = self.backend.weapons(document)
        return super().inspection_tables(document) + (
            InspectionTable('Characters', ('Physical slot', 'Character', 'Native ID',
                'Stored HP', 'Stored level', 'Weapon slot reference'),
                tuple((r['slot'], r['name'], r['id'], r['hp'], r['level'], r['weapon_slot'])
                      for r in characters),
                'Stored records include inactive/default and nonplayable entries. '
                'A named record does not grant recruitment. Growth, skills, class and equipment are read only.'),
            InspectionTable('Weapons', ('Physical slot', 'Weapon', 'Native ID', 'Added might',
                'Added durability', 'Might forge steps', 'Durability forge steps', 'Skill IDs'),
                tuple((r['slot'], r['name'], r['id'], r['might_bonus'], r['durability_bonus'],
                       r['might_forge'], r['durability_forge'], str(r['skill_ids'])) for r in weapons),
                'Forging steps and added might/durability are distinct stored values. '
                'Skill identities, ownership, personal weapons, forge limits and equipped references are preserved.'),
        )


class Editor(ScalarEditor):
    game_id = 'three_hopes'
    backend = parser
    save_extension = ''
    presentation_type = Presentation
    subtitle = 'Nintendo Switch — extracted SlotData export'
    summary = ('Decrease gold/existing material stocks and rename already-qualified Shez/Byleth profiles; named read-only '
               'character/weapon inspection. Recruitment, growth, equipment, renown and story are preserved.')
