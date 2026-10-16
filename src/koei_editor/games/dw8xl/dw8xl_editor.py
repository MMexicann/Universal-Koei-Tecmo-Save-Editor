"""Explicit DW8 Xtreme Legends PC adapter; no cross-game fallback."""
import koei_editor.shared.verified_editor as verified_editor
from koei_editor.shared.verified_gui import Editor as ScalarEditor
from koei_editor.shared.musou_presentations import DW8Presentation


class DW8XLPresentation(DW8Presentation):
    def dashboard(self, document):
        from koei_editor.games.dw8xl.dashboard import dashboard
        return dashboard(self.backend, document)


class Editor(ScalarEditor):
    game_id = 'dw8xl'
    summary = 'Resources, officer stats, weapon compatibility and attribute ranks.'
    presentation_type = DW8XLPresentation


def read_save(path):
    return verified_editor.read_save(path, 'dw8xl')
