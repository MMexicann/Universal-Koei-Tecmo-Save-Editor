"""Nioh 3 balance/common-stack reductions and read-only inventory views."""
from koei_editor.games.nioh3 import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Nioh3Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        rows = self.backend.inspection_rows(document)
        return tuple(InspectionTable(group, ('Record', 'Opened values'),
                                     tuple((row['label'], row['value']) for row in rows
                                           if row['group'] == group),
                                     'Unknown IDs and equipment remain read only. '
                                     'Equipment level and pre-forge level are distinct.')
                     for group in ('Balances', 'Item box', 'Storehouse', 'Equipment', 'Native profile'))


class Editor(ScalarEditor):
    game_id = 'nioh3'
    save_extension = '.bin'
    backend = parser
    presentation_type = Nioh3Presentation
    subtitle = 'Native PC USER balance and common-item reductions'
    summary = ('Edit existing Amrita/Gold balances and common-item quantities; inspect equipment level, '
               'pre-forge level and reinforcement separately. Default limits allow reductions; '
               'increases require experimental editing. Max is unavailable.')


def read_save(path):
    return parser.read_save(path)
