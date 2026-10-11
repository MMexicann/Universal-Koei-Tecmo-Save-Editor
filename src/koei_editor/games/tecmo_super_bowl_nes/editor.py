"""Battery-save team management in the shared searchable editing workspace."""
from koei_editor.games.tecmo_super_bowl_nes import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        return (InspectionTable('Season teams', ('Team record', 'Wins', 'Losses', 'Ties',
                                'Raw playbook selectors (hex)', 'Packed starters (hex)',
                                'Packed injuries (hex)', 'Raw conditions (hex)'),
                                parser.inspection_rows(document),
                                'Team numbers follow the native 28-team array. ROM roster names '
                                'are not stored in battery saves. Standings, starters and injuries '
                                'are read only; condition edits do not heal injuries. Playbook '
                                'nibbles above 7 are inspection only and stay intact.'),
                InspectionTable('Player condition and injury',
                                ('Team record', 'Position', 'Condition', 'Injury status', 'Editing'),
                                parser.player_records(document),
                                'Injured offensive skill players have read-only conditions. '
                                'Native injury recovery and weekly updates control those records.'))


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.sav'
    presentation_type = Presentation
    subtitle = 'NES · compatible 28-team battery SRAM'
    summary = 'Team control, healthy player conditions and eight per-slot playbook choices.'
