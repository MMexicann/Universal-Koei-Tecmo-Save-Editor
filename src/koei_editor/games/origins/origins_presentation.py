"""Searchable views of independently mapped Origins inventory records."""
from koei_editor.games.origins.origins_weapons import weapon_records
from koei_editor.games.origins.origins_proficiency import proficiency_records
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation


class OriginsPresentation(ScalarPresentation):
    def dashboard(self, document):
        from koei_editor.games.origins.origins_dashboard import dashboard
        return dashboard(self.backend, document)

    def inspection_tables(self, document):
        self.backend.validate_document(document)
        weapons = tuple(
            (record.index + 1, record.weapon_id, record.upgrade,
             ', '.join(str(value) for value in record.traits),
             ', '.join(str(value) for value in record.trait_levels),
             'Editable' if record.upgrade_qualified else 'Inspection only',
             record.instance_id, ' '.join(f'{value:02X}' for value in record.flags),
             record.qualification_note)
            for record in weapon_records(document.payload, document.revision)
        )
        tables = [InspectionTable(
            'Weapons', ('Inventory slot', 'Weapon ID', 'Reinforcement', 'Six trait IDs',
                        'Six trait levels', 'Reinforcement editing', 'Stored instance ID',
                        'Opaque flag bytes (hex)', 'Qualification'), weapons,
            'Existing inventory records. Search any column. Trait IDs/levels, equipment references '
            'and progression are preserved. Stored instance IDs and opaque flags are read-only; '
            'duplicate IDs do not establish interchangeable equipment. Weapon names remain numeric.')]
        proficiency = proficiency_records(document)
        tables.append(InspectionTable(
            'Proficiency', ('Family ID', 'Weapon family', 'Stored XP',
                            'Battle Art 1', 'Battle Art 2', 'Battle Art 3', 'Battle Art 4'),
            tuple((record.index, record.family, record.stored_xp,
                   *('Empty' if value is None else value for value in record.battle_arts))
                  for record in proficiency),
            ('Stored XP and equipped Battle Art IDs. Records can exist before a weapon is acquired. '
             'Proficiency levels and unlocks are not editable here.' if proficiency else
             'Stored proficiency records are unavailable for this copy. '
             'Proficiency levels and unlocks are not editable here.')))
        grouped = {}
        for row in self.backend.inspection_rows(document):
            if row['group'] != 'Weapons':
                grouped.setdefault(row['group'], []).append((row['group'], row['label'], row['value']))
        for group, rows in grouped.items():
            tables.append(InspectionTable(group, ('Group', 'Record / field', 'Opened value'), tuple(rows)))
        return tuple(tables)
