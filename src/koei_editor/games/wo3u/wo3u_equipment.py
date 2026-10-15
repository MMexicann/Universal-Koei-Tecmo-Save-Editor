"""Native WO3 PC item and mount references, separate from acquisition/rank.

The packed officer serializer writes six signed selectors; the native equipment
menu checks the 64-bit ownership mask and rejects duplicate selectors. IDs
28..31 use a separate four-entry mount lookup and two stored loadouts.
"""
from koei_editor.games.dw3.models import SaveError

ITEM_OWNERSHIP_OFFSET, ITEM_RANK_OFFSET, ITEM_COUNT = 0xD9AC, 0xD9B4, 64
EQUIPPED_ITEM_OFFSET, ITEM_SLOT_COUNT_OFFSET, EMPTY_ITEM = 38, 44, 255
MOUNT_IDS = frozenset(range(28, 32))
# The native mount menu stores a lookup-table ordinal, rather than the item ID.
# The two persisted loadouts are distinct from every officer's six item slots.
MOUNT_LOADOUT_OFFSETS = (0xE943, 0xE0DF)
MOUNT_ITEM_IDS = (28, 29, 30, 31)


def owned_items(payload):
    mask = int.from_bytes(payload[ITEM_OWNERSHIP_OFFSET:ITEM_OWNERSHIP_OFFSET + 8], 'little')
    return tuple(identity for identity in range(ITEM_COUNT)
                 if identity not in MOUNT_IDS and mask & (1 << identity)
                 and int.from_bytes(payload[ITEM_RANK_OFFSET + 2 * identity:
                                            ITEM_RANK_OFFSET + 2 * identity + 2], 'little') > 0)


def qualified_slots(payload, officer_base):
    count = payload[officer_base + ITEM_SLOT_COUNT_OFFSET]
    if not 2 <= count <= 6:
        return 0
    selectors = payload[officer_base + EQUIPPED_ITEM_OFFSET:
                        officer_base + EQUIPPED_ITEM_OFFSET + 6]
    allowed = owned_items(payload)
    active = [identity for identity in selectors[:count] if identity != EMPTY_ITEM]
    if (any(identity not in allowed for identity in active)
            or len(active) != len(set(active))
            or any(identity != EMPTY_ITEM for identity in selectors[count:])):
        return 0
    return count


def options(payload):
    return ((EMPTY_ITEM, 'Unequipped'),) + tuple(
        (identity, f'Owned item ID {identity}') for identity in owned_items(payload))


def validate_selectors(original, changed, officer_base):
    count = qualified_slots(original, officer_base)
    if not count:
        raise SaveError('This officer has an unsupported existing item-equipment layout.')
    allowed = owned_items(original)
    selectors = changed[officer_base + EQUIPPED_ITEM_OFFSET:
                        officer_base + EQUIPPED_ITEM_OFFSET + count]
    active = [identity for identity in selectors if identity != EMPTY_ITEM]
    if any(identity not in allowed for identity in active):
        raise SaveError('Select an already owned ordinary item with an existing positive rank.')
    if len(active) != len(set(active)):
        raise SaveError('An officer cannot equip the same item in two slots. Unequip it first.')


def owned_mounts(payload):
    """Original owned binary mount items, as native lookup-table ordinals."""
    mask = int.from_bytes(payload[ITEM_OWNERSHIP_OFFSET:ITEM_OWNERSHIP_OFFSET + 8], 'little')
    return tuple(selector for selector, identity in enumerate(MOUNT_ITEM_IDS)
                 if mask & (1 << identity)
                 and int.from_bytes(payload[ITEM_RANK_OFFSET + 2 * identity:
                                            ITEM_RANK_OFFSET + 2 * identity + 2], 'little') == 1)


def qualified_mount_loadouts(payload):
    allowed = owned_mounts(payload)
    if not allowed:
        return ()
    return tuple(index for index, offset in enumerate(MOUNT_LOADOUT_OFFSETS)
                 if payload[offset] == EMPTY_ITEM or payload[offset] in allowed)


def mount_options(payload):
    return ((EMPTY_ITEM, 'Unequipped'),) + tuple(
        (selector, f'Owned mount item ID {MOUNT_ITEM_IDS[selector]}')
        for selector in owned_mounts(payload))


def validate_mount_selector(original, index, value):
    if index not in qualified_mount_loadouts(original):
        raise SaveError('This mount loadout has an unsupported original selector or ownership state.')
    if value != EMPTY_ITEM and value not in owned_mounts(original):
        raise SaveError('Choose an originally owned mount with a supported rank, or Unequipped.')
