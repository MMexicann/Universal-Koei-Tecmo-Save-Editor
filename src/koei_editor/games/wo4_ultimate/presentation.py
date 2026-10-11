"""Resources and attribute inventory with searchable native record identities."""
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        balances = tuple((row['group'], row['label'], row['value'])
                         for row in self.backend.inspection_rows(document))
        return (
            InspectionTable('Balances and earnings', ('Group', 'Stored value', 'Value'), balances,
                'Spendable Gems and Crystals are separate from lifetime earnings. Growth Points are '
                'the shared training EXP pool. Officer EXP and promotions stay intact; Skill Points are separate.'),
            InspectionTable('Attribute-element inventory', ('Attribute ID', 'Quantity', 'Editing'),
                self.backend.element_records(document),
                'Existing ordinary quantities support individual and validated Max actions. '
                'Attribute ID 0, unowned/zero stacks and unusual values are preserved. '
                'Weapon fusion, sockets, camp upgrades and attached weapon ranks are separate systems.'),
            InspectionTable('Officer progression', ('Record', 'Stored EXP', 'Unspent Skill Points', 'Promotions', 'Unspent Upgrade Stones', 'Editing'),
                self.backend.officer_records(document),
                'Progressed records support Skill Points; promoted officers also support their unspent Upgrade Stones. '
                'EXP, promotions, learned skills and allocated stats remain intact.'),
            InspectionTable('Weapon inventory — inspection only', ('Record', 'Weapon ID', 'Stored attributes ID:rank'),
                self.backend.weapon_records(document),
                'Ten serialized attribute slots per record are shown using native IDs and stored ranks. '
                'Rank encoding, camp capacity, compatibility, crafted ownership and equipment stay intact.'),
        )
