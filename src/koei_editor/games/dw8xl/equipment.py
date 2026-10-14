"""Reorder a qualified officer's two already equipped native weapons.

The existing decoded officer map stores two adjacent zero-based pool references
at +0x30/+0x32. This operation preserves their multiset, including all ownership,
weapon state and properties; it cannot equip a third weapon or acquire one.
"""
from dataclasses import dataclass

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.verified_editor import Field


@dataclass(frozen=True)
class WeaponOrderField(Field):
    opened_slots: tuple = ()

    @property
    def experimental_maximum(self):
        return None

    @property
    def mirrors(self):
        return (self.offset + 2,)

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + 2], 'little') + 1

    def validate(self, value):
        if type(value) is not int or value not in self.opened_slots:
            raise SaveError('Choose one of this officer\'s two originally equipped weapon slots.')

    def write(self, payload, value):
        self.validate(value)
        other = self.opened_slots[1] if value == self.opened_slots[0] else self.opened_slots[0]
        payload[self.offset:self.offset + 2] = (value - 1).to_bytes(2, 'little')
        payload[self.offset + 2:self.offset + 4] = (other - 1).to_bytes(2, 'little')


def fields_for_payload(payload, weapon_record, weapon_count):
    fields = []
    for index in range(82):
        offset = 0x7fc9 + index * 0x48 + 0x30
        slots = tuple(int.from_bytes(payload[at:at + 2], 'little') + 1
                      for at in (offset, offset + 2))
        if (slots[0] == slots[1] or any(not 1 <= slot <= weapon_count for slot in slots)
                or any(weapon_record(payload, slot - 1) is None for slot in slots)):
            continue
        fields.append(WeaponOrderField(f'officer_{index}_first_weapon', 'First equipped weapon',
                                       offset, 2, weapon_count, 'Weapon order', index + 1,
                                       minimum=1, maxable=False, opened_slots=slots))
    return tuple(fields)
