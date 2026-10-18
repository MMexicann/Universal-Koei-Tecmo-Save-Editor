"""Explicit DW8 Xtreme Legends PC adapter; no cross-game fallback."""
import koei_editor.shared.verified_editor as verified_editor
from koei_editor.shared.verified_gui import Editor as ScalarEditor
from koei_editor.shared.musou_presentations import DW8Presentation


class DW8XLPresentation(DW8Presentation):
    extra_groups = DW8Presentation.extra_groups + ('Weapon attribute identities',)

    def record_name(self, field):
        if field.group == 'Weapon attribute identities':
            return f'Weapon slot {field.slot:04}'
        return super().record_name(field)

    def field_hint(self, document, field):
        if field.group == 'Weapon attribute identities':
            return ('Replace this existing ranked attribute using a verified ranked ID '
                    'present in the opened weapon pool. Choosing an ID in another eligible ranked slot '
                    'swaps both identities together; ranks stay at their original positions. '
                    'Restore both identity slots together with Revert Selected, or Undo the swap. '
                    'Unknown/unranked slots cannot be swapped. Duplicate final IDs are rejected. '
                    'The paired rank and other properties are retained; rank edits may be staged separately. '
                    'Empty, unranked, unknown and unusual slots are preserved. Max excludes identity choices. '
                    'This edits a property directly; it does not spend gems or sacrifice a weapon. '
                    'Edited in-game loading remains untested.')
        if field.group == 'Weapon attributes':
            return ('Rank of this existing attribute position, including any staged identity replacement. '
                    'The label identifies the opened attribute. Normal ranks are 1 through 10. '
                    'Replacement identities require a final rank from 1 through 10. '
                    'Weapon identity, attack, acquisition state and equipped references are retained.')
        return super().field_hint(document, field)

    def dashboard(self, document):
        from koei_editor.games.dw8xl.dashboard import dashboard
        return dashboard(self.backend, document)


class Editor(ScalarEditor):
    game_id = 'dw8xl'
    summary = 'Resources, officer stats, weapon compatibility, existing attribute identities and ranks.'
    presentation_type = DW8XLPresentation


def read_save(path):
    return verified_editor.read_save(path, 'dw8xl')
