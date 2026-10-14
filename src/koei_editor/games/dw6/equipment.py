"""Typed original DW6 equipment choices shared by the PC and US PS3 profiles.

Disk positions and bit ordinals are independently corroborated by cnopt's
research, static inspection of the older editor, Apollo and native exports.
No third-party implementation is included. Officer growth is deliberately separate.
"""

from dataclasses import dataclass

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw6.dw6_metadata import WEAPON_NAMES

WEAPON_SKILLS = (
    "Air Wave",
    "Mystic Seal",
    "True Musou",
    "Leech",
    "Concentration",
    "Balance",
    "Berserk",
    "Renbu Spirit",
    "Arrow Sight",
    "Flash",
)
HORSE_SKILLS = (
    "Arrow Dance",
    "Find Saddle",
    "Find Weapon",
    "Musou Spirit",
    "Renbu Gait",
    "Winged Hoof",
    "Jagged Hoof",
    "Steel Hoof",
    "Water Spirit",
    "Stone Spirit",
    "Wind Spirit",
)


@dataclass(frozen=True)
class EquipmentField:
    id: str
    label: str
    offset: int
    group: str
    slot: int
    endian: str
    bit: int | None = None
    choices: tuple = ()
    size: int = 4
    minimum: int = 0
    maximum: int = 1
    maxable: bool = False
    experimental: bool = False
    kind: str = "choice"

    @property
    def encoding(self):
        return f"unsigned {self.endian}-endian u32" + (
            f" bit {self.bit}" if self.bit is not None else ""
        )

    @property
    def experimental_maximum(self):
        return None

    def value(self, payload):
        word = int.from_bytes(payload[self.offset : self.offset + 4], self.endian)
        return (word >> self.bit) & 1 if self.bit is not None else word

    def validate(self, value):
        if type(value) is not int or value not in (
            tuple(v for v, _ in self.choices) if self.choices else (0, 1)
        ):
            raise SaveError(f"Choose a qualified value for {self.label}.")

    def write(self, raw, value):
        self.validate(value)
        if self.bit is not None:
            current = int.from_bytes(raw[self.offset : self.offset + 4], self.endian)
            value = (current & ~(1 << self.bit)) | (value << self.bit)
        raw[self.offset : self.offset + 4] = value.to_bytes(4, self.endian)


def _word(raw, offset, endian):
    return int.from_bytes(raw[offset : offset + 4], endian)


def _skills(key, label, offset, group, slot, endian, names, limit, raw):
    mask = _word(raw, offset, endian)
    if mask >> len(names) or mask.bit_count() > limit:
        return ()  # Unknown or over-capacity originals remain inspectable, never normalized.
    return tuple(
        EquipmentField(
            f"{key}_skill_{bit}", f"{label}: {name}", offset, group, slot, endian, bit
        )
        for bit, name in enumerate(names)
    )


def fields(raw, officer_base, horse_exp_base, endian, horse_qualified):
    result = []
    for officer in range(41):
        base = officer_base + officer * 168
        choices = []
        for weapon in range(8):
            offset = base + 8 + weapon * 16
            identity, element = (
                _word(raw, offset, endian),
                _word(raw, offset + 8, endian),
            )
            if identity >= len(WEAPON_NAMES) or element not in range(4):
                continue
            label = WEAPON_NAMES[identity]
            choices.append((weapon, f"Slot {weapon + 1}: {label}"))
            result.extend(
                _skills(
                    f"officer_{officer}_weapon_{weapon}",
                    label,
                    offset + 12,
                    "Weapon skills",
                    officer * 8 + weapon + 1,
                    endian,
                    WEAPON_SKILLS,
                    5,
                    raw,
                )
            )
        opened = _word(raw, base + 160, endian)
        if opened in dict(choices):
            result.append(
                EquipmentField(
                    f"officer_{officer}_equipped_weapon",
                    "Equipped weapon slot",
                    base + 160,
                    "Equipment",
                    officer + 1,
                    endian,
                    choices=tuple(choices),
                    maximum=7,
                )
            )
    for horse in range(8):
        if not horse_qualified(horse):
            continue
        base = horse_exp_base + horse * 60
        result.extend(
            _skills(
                f"horse_{horse}",
                "Horse skill",
                base + 12,
                "Horse skills",
                horse + 1,
                endian,
                HORSE_SKILLS,
                4,
                raw,
            )
        )
        if _word(raw, base + 8, endian) in range(4):
            result.append(
                EquipmentField(
                    f"horse_{horse}_element",
                    "Horse element",
                    base + 8,
                    "Horse elements",
                    horse + 1,
                    endian,
                    choices=(
                        (0, "Fire"),
                        (1, "Ice"),
                        (2, "Lightning"),
                        (3, "No element"),
                    ),
                    maximum=3,
                )
            )
    return tuple(result)


def apply(raw, pending, mapping, endian):
    result = bytearray(raw)
    masks = {}
    for key, value in pending.items():
        field = mapping[key]
        if isinstance(field, EquipmentField):
            field.write(result, value)
            if field.bit is not None:
                masks[field.offset] = 5 if field.group == "Weapon skills" else 4
        else:
            result[field.offset : field.offset + field.size] = value.to_bytes(
                field.size, endian
            )
    for offset, limit in masks.items():
        if _word(result, offset, endian).bit_count() > limit:
            raise SaveError(
                f"This existing record supports at most {limit} equipment skills. Remove a skill before adding another."
            )
    return bytes(result)


def options(field):
    if isinstance(field, EquipmentField):
        return field.choices or ((0, "Disabled"), (1, "Enabled"))
    return ()


def hint(field):
    if field.group in ("Weapon skills", "Horse skills"):
        count = 5 if field.group == "Weapon skills" else 4
        return f"Named equipment skill; at most {count} per record. Remove a skill before adding another at capacity. Growth, officer skill tree and inventory stay unchanged; Max is disabled."
    if field.group == "Equipment":
        return "Select an existing known weapon in this officer’s own inventory. Empty and unknown records are unavailable; Max is disabled."
    return "Choose the element on this qualified existing horse. EXP, growth, model, names and skills stay unchanged; Max is disabled."


def skill_names(mask, names):
    known = [name for bit, name in enumerate(names) if mask & (1 << bit)]
    if mask >> len(names):
        known.append(f"unknown bits 0x{mask & ~((1 << len(names)) - 1):X}")
    return ", ".join(known) or "None"
