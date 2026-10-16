"""Explicit Steam PC Warriors Orochi 3 Ultimate Definitive adapter."""
import koei_editor.games.wo3u.wo3u_parser as wo3u_parser
from koei_editor.shared.verified_gui import Editor as ScalarEditor
from koei_editor.shared.scalar_presentation import ScalarPresentation, InspectionTable


class WO3Presentation(ScalarPresentation):
    extra_groups = ('Weapons', 'Equipment', 'Mount equipment', 'Upgrade stones', 'Weapon compatibility')

    def inspection_tables(self, document):
        rows = self.backend.inspection_rows(document)
        progression = tuple((row['label'], row['value']) for row in rows
                            if row['group'] == 'Progression')
        weapons = tuple((row['label'], row['value']) for row in rows
                        if row['group'] == 'Weapons')
        resources = tuple((field.group, field.label, field.value(document.payload))
                          for field in self.backend.fields_for(document)
                          if field.group not in ('Officers', 'Weapons', 'Mount equipment', 'Weapon compatibility'))
        mounts = tuple((row['label'], row['value']) for row in rows
                       if row['group'] == 'Mount equipment')
        items = tuple((row['id'], row['kind'], 'Yes' if row['owned'] else 'No',
                       row['rank'], '; '.join(row['references']) or 'None')
                      for row in self.backend.item_inventory(document))
        return (
            InspectionTable('Progression', ('Record', 'Opened progression'), progression,
                            'Level, EXP, promotion and item-slot dependencies remain read only.'),
            InspectionTable('Weapons', ('Owner / slot', 'Opened equipment'), weapons,
                            'Search by proven attribute names or weapon IDs. Unknown IDs are preserved.'),
            InspectionTable('Resources', ('Group', 'Resource', 'Opened balance'), resources,
                            'Resource edit limits are published patch limits; bulk Max excludes them.'),
            InspectionTable('Item inventory',
                            ('Native item ID', 'Kind', 'Owned', 'Stored rank', 'Equipped references'), items,
                            'Read only. Search by native ID or officer. Ownership, rank and equipped '
                            'references are separate; unfamiliar or unowned records are preserved.'),
            InspectionTable('Mount loadouts', ('Loadout', 'Opened mount'), mounts,
                            'Two stored loadouts. Choose only originally owned mounts; '
                            'acquisition and ranks stay unchanged.'),
        )


class Editor(ScalarEditor):
    game_id = 'wo3u'
    save_extension = '.bin'
    presentation_type = WO3Presentation
    backend = wo3u_parser
    subtitle = 'Steam Windows PC save editor'
    summary = 'Officer stats, upgrade stones, owned items and mounts, growth points, crafting, weapons and compatibility reset.'


def read_save(path):
    return wo3u_parser.read_save(path)
