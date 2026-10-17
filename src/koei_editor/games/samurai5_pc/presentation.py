"""Searchable serialized records; unproved identities remain explicitly raw."""
from koei_editor.games.samurai5_pc import codec
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation

KINDS = {
    5: 'Musou scenario records', 6: 'Citadel records', 7: 'Weapon records',
    8: 'Skill-gem quantities', 11: 'Officer records', 12: 'Mount records',
    13: 'Residence records', 14: 'Stable records', 15: 'Shop weapon records',
    16: 'Reward records', 17: 'Corps records',
}

class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        self.backend.validate_document(document)
        payload = document.payload
        tables = [InspectionTable('Current resources', ('Group', 'Field', 'Opened value'),
            tuple((item.group, item.label, item.value(payload)) for item in self.backend.FIELDS))]
        checkpoints = []
        for state, kind, offset, _, _ in codec.SECTIONS:
            if kind == 4:
                checkpoints.append((state, 'Current castle save' if state == 4 else 'Preserved checkpoint',
                    int.from_bytes(payload[offset + 12:offset + 16], 'little'),
                    int.from_bytes(payload[offset + 16:offset + 20], 'little')))
        tables.append(InspectionTable('Wallet and checkpoints', ('Native copy', 'Role', 'Gold', 'Cumulative spending'),
            tuple(checkpoints), 'Only copy 4 is edited. Spending history, copies 1–3 and both battle buffers are preserved.'))
        for state, kind, offset, count, stride in codec.SECTIONS:
            if state != 4 or kind not in KINDS:
                continue
            rows = []
            for index in range(count):
                record = payload[offset + index * stride:offset + (index + 1) * stride]
                if kind == 8:
                    if record[0]:
                        identity, rank = divmod(index, 10)
                        rows.append((index, identity, rank, record[0],
                                     'Existing stack: editable' if rank else 'Rank zero: inspection only'))
                elif record != bytes(stride) and record != b'\xff' * stride:
                    rows.append((index, stride, record[:min(stride, 16)].hex(' ')))
            if kind == 8:
                tables.append(InspectionTable(KINDS[kind], ('Native index', 'Gem ID', 'Rank', 'Stored quantity', 'Editing'), tuple(rows),
                    'Existing positive stacks at ranks 1–9 can retain 1–20 gems. Gem names, new acquisition, '
                    'rank changes, unlock eligibility and learned skills remain unavailable.'))
            else:
                tables.append(InspectionTable(KINDS[kind], ('Native index', 'Serialized bytes', 'Raw prefix'), tuple(rows),
                    'Native record boundaries are proved. Raw words are not asserted to be IDs or editable progression.'))
        return tuple(tables)
