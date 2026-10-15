"""Read-only Origins proficiency and equipped Battle Art record inspection.

Nine separate public native slots corroborate the 50 packed 14-byte records at the
qualified weapon-array end plus 174 bytes. The family/Art relationships guard
this inspection conservatively; an unfamiliar layout never changes the existing
resource writer's qualification. XP is displayed as stored XP, not converted to
a level. Native level gains have separate moveset, rank and reward dependencies.
"""
from dataclasses import dataclass
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.origins import origins_parser as backend
from koei_editor.games.origins import origins_weapons as weapons


RECORD_SIZE = 14
SERIALIZED_COUNT = 50
INVENTORY_GAP = 174
FAMILY_NAMES = MappingProxyType({
    0: 'Spear', 1: 'Twin Pikes', 2: 'Sword', 3: 'Staff', 4: 'Wheels',
    5: 'Gauntlets', 6: 'Podao', 7: 'Crescent Blade', 8: 'Lance',
    9: 'Halberd', 10: 'Bow',
})
_RECORD = struct.Struct('<I4H2s')


@dataclass(frozen=True)
class ProficiencyRecord:
    index: int
    offset: int
    family: str
    stored_xp: int
    battle_arts: tuple
    unmapped_state: bytes


def _formed_art_record(index, arts):
    """Require the independently observed own-family/shared/empty topology.

    This is a layout check, not an ownership or learned-art predicate. Initial
    saves already contain formed Art slots for undiscovered weapon families.
    """
    own_start = index * 20
    own = lambda value: own_start <= value < own_start + 20
    return (sum(own(value) for value in arts) >= 2 and
            all(own(value) or 400 <= value <= 999 or value == 0xffff
                for value in arts))


def proficiency_records(document):
    """Return recognized stored records, or no rows for an unfamiliar layout.

    Invalid/forged documents are refused. Unknown candidate structures merely
    withhold this optional view; parsing and existing scalar edits stay intact.
    Reserved capacity, all XP values and both opaque state bytes are preserved.
    """
    if type(document) is not backend.Document or document.format is not backend.FORMAT:
        raise SaveError('Origins proficiency inspection requires its original save document.')
    backend.validate_document(document)
    revision = document.revision
    base = (weapons.BASES[revision] +
            weapons.RECORD_SIZE * weapons.SERIALIZED_COUNT + INVENTORY_GAP)
    end = base + RECORD_SIZE * SERIALIZED_COUNT
    serialized_end = 0x664 + backend.REVISION_LENGTHS[revision]
    if end > serialized_end or end > len(document.payload):
        return ()
    records = tuple(_RECORD.unpack_from(document.payload, base + index * RECORD_SIZE)
                    for index in range(SERIALIZED_COUNT))
    # All ten original families have formed Art records in both the early and
    # advanced references. Never infer that a weapon is owned from these slots.
    if not all(_formed_art_record(index, record[1:5])
               for index, record in enumerate(records[:10])):
        return ()
    result = []
    family_count = 12 if revision == 29 else 10
    for index, record in enumerate(records[:family_count]):
        if not _formed_art_record(index, record[1:5]):
            continue
        result.append(ProficiencyRecord(
            index, base + index * RECORD_SIZE,
            FAMILY_NAMES.get(index, f'Family ID {index}'), record[0],
            tuple(None if value == 0xffff else value for value in record[1:5]),
            record[5]))
    return tuple(result)
