"""Wo Long currencies, conservative stack reductions and rich inspection."""
from koei_editor.games.wolong import wolong_parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class WolongPresentation(ScalarPresentation):
    def inspection_tables(self, document):
        rows = self.backend.inspection_rows(document)
        return tuple(InspectionTable(group, ('Record', 'Opened data'),
                                     tuple((row['label'], row['value']) for row in rows if row['group'] == group),
                                     'Identity, history and progression stay separate from available resources.')
                     for group in ('Inventory', 'Companions', 'Progression', 'Profile'))


class Editor(ScalarEditor):
    game_id = 'wolong'
    save_extension = '.bin'
    backend = wolong_parser
    presentation_type = WolongPresentation
    subtitle = 'Windows PC resources and inventory inspection'
    summary = ('Edit available currencies manually; reduce existing ordinary stacks; '
               'experimental custom-name editing for enabled battle sets '
               '(native rename unverified); '
               'search inventory, equipment and companion records. Max is disabled.')


def read_save(path):
    return wolong_parser.read_save(path)
