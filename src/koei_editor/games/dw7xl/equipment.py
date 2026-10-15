"""Native PC equipment choices qualified by the immutable opened save.

Weapon attack, element and capacity are external game parameters, not members
of the serialized twenty-byte inventory record. These operations select known
existing loadouts and learned seals; they never change those parameters.
"""
from functools import lru_cache

from koei_editor.games.dw3.models import SaveError


OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT = 0x2039, 0x80, 65
WEAPON_BASE, WEAPON_STRIDE, WEAPON_COUNT = 0x4E39, 20, 1738
SEAL_MASK, SMITH_REFERENCES, SUSPEND_FLAG = 0xC9C, 0x1564, 0xDD1F
EMPTY = 0xFFFF


def word(payload, offset):
    return int.from_bytes(payload[offset:offset + 2], 'little')


def owned(payload, reference):
    return (0 <= reference < WEAPON_COUNT
            and bool(word(payload, WEAPON_BASE + reference * WEAPON_STRIDE + 4) & 1))


@lru_cache(maxsize=4)
def reserved_references(payload):
    # The native weapon picker excludes these five smith-learning records.
    return frozenset(word(payload, SMITH_REFERENCES + index * 2) for index in range(5))


@lru_cache(maxsize=4)
def weapon_choices(payload):
    """Only references witnessed equipped on a playable officer in this copy.

    Ownership alone does not qualify the external DLC/availability predicate.
    The opened equipped references provide that witness without a catalog.
    """
    if payload[SUSPEND_FLAG]:
        return ()
    reserved = reserved_references(payload)
    return tuple(sorted({reference
                         for index in range(OFFICER_COUNT)
                         for relative in (18, 20)
                         for reference in (word(payload, OFFICER_BASE + index * OFFICER_STRIDE + relative),)
                         if owned(payload, reference) and reference not in reserved}))


@lru_cache(maxsize=4)
def learned_seals(payload):
    # The native seal picker deliberately excludes IDs 64..91. They are not
    # interchangeable with the ordinary 64 equippable seal IDs.
    return tuple(identity for identity in range(64)
                 if word(payload, SEAL_MASK + 2 * (identity // 16)) & (1 << (identity % 16)))


@lru_cache(maxsize=4)
def seal_records(payload):
    if payload[SUSPEND_FLAG]:
        return ()
    learned, reserved = frozenset(learned_seals(payload)), reserved_references(payload)
    records = []
    for index in range(WEAPON_COUNT):
        start = WEAPON_BASE + index * WEAPON_STRIDE
        flags = word(payload, start + 4)
        if not owned(payload, index) or flags & ~0x1F or index in reserved:
            continue
        seals = tuple(word(payload, start + relative) for relative in range(8, 18, 2))
        used = tuple(value for value in seals if value != EMPTY)
        if not used or len(set(used)) != len(used) or any(value not in learned for value in used):
            continue
        records.append((index, seals))
    return tuple(records)


def reference_key(key):
    return key.startswith('officer_') and key.endswith(('_weapon_1', '_weapon_2'))


def seal_key(key):
    return key.startswith('weapon_') and '_applied_seal_' in key


def validate_changes(original, result, changes):
    """Validate dependent final values together, without changing other fields."""
    references = [key for key in changes if reference_key(key)]
    seals = [key for key in changes if seal_key(key)]
    if not references and not seals:
        return
    if original[SUSPEND_FLAG]:
        raise SaveError('Finish the suspended DW7 XL battle before editing weapons or applied seals.')
    choices, learned = frozenset(weapon_choices(original)), frozenset(learned_seals(original))
    for key in references:
        officer = int(key.split('_')[1])
        position = int(key[-1]) - 1
        start = OFFICER_BASE + officer * OFFICER_STRIDE
        reference = word(result, start + 18 + position * 2)
        if reference not in choices:
            raise SaveError('Choose an owned weapon already equipped by a playable officer in the opened copy; '
                            'smith-learning records are excluded.')
        first, second, active = (word(result, start + relative) for relative in (18, 20, 22))
        if first == second:
            raise SaveError('An officer cannot equip the same physical weapon in both slots.')
        if active not in (0, 1) or not owned(original, (first, second)[active]):
            raise SaveError('The final active weapon must refer to an existing owned weapon.')
    touched = {int(key.split('_')[1]) for key in seals}
    for index in touched:
        start = WEAPON_BASE + index * WEAPON_STRIDE
        values = tuple(word(result, start + relative) for relative in range(8, 18, 2))
        used = tuple(value for value in values if value != EMPTY)
        if any(value not in learned for value in used):
            raise SaveError('Choose an ordinary seal already learned in the opened save, or remove the seal.')
        if len(set(used)) != len(used):
            raise SaveError('A physical weapon cannot contain the same applied seal twice.')


def options(payload, key, current=None):
    current = payload if current is None else current
    if reference_key(key):
        officer, position = int(key.split('_')[1]), int(key[-1]) - 1
        other = word(current, OFFICER_BASE + officer * OFFICER_STRIDE + 18 + (1 - position) * 2)
        return tuple((reference, f'Inventory slot {reference + 1} · equipped in opened copy')
                     for reference in weapon_choices(payload) if reference != other)
    if seal_key(key):
        index, position = int(key.split('_')[1]), int(key.rsplit('_', 1)[1]) - 1
        start = WEAPON_BASE + index * WEAPON_STRIDE
        other = {word(current, start + 8 + relative * 2) for relative in range(5) if relative != position}
        return ((EMPTY, 'Remove seal'),) + tuple((identity, f'Seal ID {identity} · already learned')
                                                for identity in learned_seals(payload) if identity not in other)
    return ()
