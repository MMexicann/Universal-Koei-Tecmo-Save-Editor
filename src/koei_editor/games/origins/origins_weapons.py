"""Native Origins weapon inventory inspection and conservative upgrade fields.

Offsets are decoded-body offsets, excluding the four-byte codec envelope.
Weapon IDs, traits, equipment references and empty/reserved records are never
manufactured. Proficiency XP is intentionally not a writable inventory field:
native level gains also grant rewards and set moveset unlock records.
"""
from dataclasses import dataclass
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import within_numeric_limits


BASES = MappingProxyType({16: 0x1567, 17: 0x1567, 29: 0x162f})
RECORD_SIZE = 27
SERIALIZED_COUNT = 1000
INVENTORY_COUNT = 850
MAXIMUM_UPGRADE = 99
MAXIMUM_WEAPON_ID = 299

# Factual ID eligibility from the native weapon catalogue (table 4327),
# linked by catalogue factory RVA 0xb365b0 and loader RVA 0xc28100.
# Grade/family must be valid; flag bit 0 permits native reforging materials.
KNOWN_WEAPON_IDS = frozenset({
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22,
    23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43,
    44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64,
    65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85,
    86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 110, 111, 112, 113, 114,
    115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131,
    132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148,
    149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165,
    166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182,
    183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 220,
    230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246,
    247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261, 262, 263,
    264, 265, 266, 267, 268, 269, 285, 286, 287, 288, 289, 290, 291, 292, 293, 294, 295,
    296, 297, 298,
})

REFORGABLE_WEAPON_IDS = frozenset({
    0, 1, 2, 3, 4, 5, 6, 10, 11, 12, 13, 14, 15, 16, 20, 21, 22, 23, 24, 25, 26, 30, 31,
    32, 33, 34, 35, 36, 40, 41, 42, 43, 44, 45, 46, 50, 51, 52, 53, 54, 55, 56, 60, 61,
    62, 63, 64, 65, 66, 70, 71, 72, 73, 74, 75, 76, 80, 81, 82, 83, 84, 85, 86, 90, 91,
    92, 93, 94, 95, 96, 110, 111, 112, 113, 114, 115, 117, 118, 119, 120, 121, 122, 124,
    125, 126, 127, 128, 129, 131, 132, 133, 134, 135, 136, 138, 139, 140, 141, 142, 143,
    145, 146, 147, 148, 149, 150, 152, 153, 154, 155, 156, 157, 159, 160, 161, 162, 163,
    164, 166, 167, 168, 169, 170, 171, 173, 174, 175, 176, 177, 178, 180, 181, 182, 183,
    184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 220, 230, 231,
    232, 233, 234, 235, 236, 240, 241, 242, 243, 244, 245, 246, 250, 251, 252, 253, 254,
    255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 266, 267, 268, 269, 285, 286,
    287, 288, 289, 290, 292, 293, 294, 295, 296, 297,
})


@dataclass(frozen=True)
class WeaponRecord:
    index: int
    offset: int
    weapon_id: int
    upgrade: int
    traits: tuple
    trait_levels: tuple
    instance_id: int
    flags: tuple

    @property
    def qualification_note(self):
        if self.weapon_id not in KNOWN_WEAPON_IDS:
            return 'Unqualified weapon catalogue ID'
        if self.weapon_id not in REFORGABLE_WEAPON_IDS:
            return 'Native material flag excludes this weapon'
        if not self.upgrade_qualified:
            return 'Stored reinforcement exceeds supported range'
        return 'Qualified existing reforgable weapon'

    @property
    def upgrade_qualified(self):
        return (self.weapon_id in REFORGABLE_WEAPON_IDS and
                within_numeric_limits(self.upgrade, 0, MAXIMUM_UPGRADE, storage_maximum=255))


def weapon_records(payload, revision):
    """Return occupied inventory records; reserved records remain untouched."""
    if revision not in BASES:
        raise SaveError('Unsupported Origins weapon inventory revision.')
    base = BASES[revision]
    if len(payload) < base + RECORD_SIZE * SERIALIZED_COUNT:
        raise SaveError('Origins weapon inventory is truncated.')
    result = []
    for index in range(INVENTORY_COUNT):
        offset = base + index * RECORD_SIZE
        weapon_id = int.from_bytes(payload[offset:offset + 2], 'little')
        # Native signed WORD getter recognizes IDs 0..299; FFFF is empty.
        if not 0 <= weapon_id <= MAXIMUM_WEAPON_ID:
            continue
        traits = tuple(int.from_bytes(payload[offset + 3 + slot * 2:
                                              offset + 5 + slot * 2], 'little')
                       for slot in range(6))
        result.append(WeaponRecord(index, offset, weapon_id, payload[offset + 2],
                                   traits, tuple(payload[offset + 15:offset + 21]),
                                   int.from_bytes(payload[offset + 21:offset + 25], 'little'),
                                   tuple(payload[offset + 25:offset + 27])))
    return tuple(result)


def weapon_specs(payload, revision):
    """Return origins_parser.Field keyword dictionaries for qualified records."""
    return tuple(dict(id=f'weapon_{record.index:04d}_upgrade',
                      label=f'Weapon {record.index + 1} (ID {record.weapon_id}) reinforcement',
                      offset=record.offset + 2, size=1,
                      maximum=MAXIMUM_UPGRADE, minimum=0,
                      group='Weapons', slot=record.index + 1)
                 for record in weapon_records(payload, revision)
                 if record.upgrade_qualified)


def validate_weapon_changes(payload, revision, changes):
    """Reject weapon keys which do not belong to the original occupied records."""
    specs = {spec['id']: spec for spec in weapon_specs(payload, revision)}
    for key, value in changes.items():
        if not key.startswith('weapon_'):
            continue
        if key not in specs:
            raise SaveError('This Origins weapon upgrade is not qualified for editing.')
        if not within_numeric_limits(value, 0, MAXIMUM_UPGRADE, storage_maximum=255):
            raise SaveError('Origins weapon upgrades require a whole number from 0 to 99.')


def weapon_inspection_rows(payload, revision):
    return tuple({'group': 'Weapons',
                  'label': f'Weapon {record.index + 1} (ID {record.weapon_id})',
                  'value': f'+{record.upgrade}; ' +
                           ('upgrade editable' if record.upgrade_qualified else
                            'upgrade inspection only')}
                 for record in weapon_records(payload, revision))


def weapon_hint():
    return ('Inventory weapon reforging level: 0–99. Only existing weapons with '
            'a verified reforgable weapon ID are editable, including +0. '
            'Special, unknown and reserved records remain unchanged. Weapon ID, grade, traits, '
            'equipment, proficiency, movesets and achievement flags are preserved.')
