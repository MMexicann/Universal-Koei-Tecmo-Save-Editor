"""Dedicated EU Vita workspace in the common scalar interface."""
from koei_editor.games.berserk_vita import parser
from koei_editor.games.berserk_vita.presentation import Presentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    save_extension = '.dat'
    subtitle = 'PS Vita EU decrypted PCSB01085 — save-manager reimport required'
    summary = ('Gold reductions and named existing material quantities; searchable materials and '
               'character status. Keep original sce_sys/param.sfo and the other exported save files.')
