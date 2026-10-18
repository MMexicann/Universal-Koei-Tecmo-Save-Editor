"""Verified bodyguard appearance/outfit unlocks, independent of story clears.

Native setters pad the two model flag arrays to two entries and the two
outfit flag arrays to four entries. They set the matching notification flag
only for a newly unlocked choice. These arrays are legitimately absent until
first use; unknown extra entries are retained. Patches use parsed tags rather
than native object offsets. See SAVE_FORMAT.md for evidence and limitations.
"""
from koei_editor.games.dw3.models import Change, SaveError
from koei_editor.games.dw3.progression_editor import _array_payload, _new_bool_array_tag, _top_terminator

CATEGORIES = {'guard_customization'}
APPEARANCES = (
    {'id': 0, 'name': 'Male'},
    {'id': 1, 'name': 'Female'},
    {'id': 2, 'name': 'Nanman Male'},
    {'id': 3, 'name': 'Nanman Female'},
)
OUTFITS = tuple({'id': index, 'name': name} for index, name in enumerate(
    ('Normal', 'Blue', 'Red', 'Green', 'Purple', 'Yellow', 'White', 'Black', 'Pink')))
FAMILIES = {
    'AppearanceUnlocked': {'state_key': 'appearances', 'choices': APPEARANCES,
                          'base_count': 2, 'count': 2,
                          'availability': 'CanUseSecretGuardModelArray',
                          'notifications': 'NewCanUseSecretGuardModelArray'},
    'OutfitUnlocked': {'state_key': 'outfits', 'choices': OUTFITS,
                      'base_count': 5, 'count': 4,
                      'availability': 'CanUseSecretGuardColorArray',
                      'notifications': 'NewCanUseSecretGuardColorArray'},
}


def _read_flags(document, name, minimum):
    """Missing/short lazy arrays initialize to false, as in native setters."""
    prop = document.properties.get(name)
    if prop is None:
        return None, [0] * minimum
    if (not isinstance(prop, dict) or prop.get('type') != 'ArrayProperty(BoolProperty)' or
            prop.get('flags') != 0 or prop.get('array_index') != 0 or
            not isinstance(prop.get('value'), dict)):
        raise SaveError(f'{name} uses an unsupported boolean array layout.')
    count = prop['value'].get('count')
    entries = prop['value'].get('values')
    offset = prop.get('data_offset')
    if (type(count) is not int or count < 0 or not isinstance(entries, list) or
            len(entries) != count or prop.get('data_size') != 4 + count or
            any(type(entry) is not int or entry not in (0, 1) for entry in entries) or
            type(offset) is not int or not 0 <= offset <= len(document.plaintext) - 4 - count or
            document.plaintext[offset:offset + 4 + count] != _array_payload(entries)):
        raise SaveError(f'{name} does not match its supported saved boolean data.')
    padded = list(entries)
    padded.extend([0] * max(0, minimum - len(padded)))
    return prop, padded


def _requests(changes):
    result = []
    seen = set()
    for change in changes:
        if not isinstance(change, Change):
            raise SaveError('Customization actions require a supported Change object.')
        if not isinstance(change.category, str):
            raise SaveError('Customization actions require a supported category.')
        if change.category not in CATEGORIES:
            continue
        family = FAMILIES.get(change.field) if isinstance(change.field, str) else None
        if (family is None or type(change.index) is not int or change.value is not True or
                not family['base_count'] <= change.index < family['base_count'] + family['count']):
            raise SaveError('Only verified bodyguard appearance/outfit unlocks are supported.')
        identity = (change.field, change.index)
        if identity in seen:
            raise SaveError('Duplicate bodyguard customization actions.')
        seen.add(identity)
        result.append(change)
    return result


def customization_unlock_changes(kind=None, content_id=None):
    """Unlock all six choices, one family, or one known special choice.

    kind is None, 'appearance', or 'outfit'. IDs are native gender/clothing
    enum values (2–3 and 5–8), rather than availability-array positions.
    Base choices are already available and do not need fabricated flags.
    """
    keys = {None: tuple(FAMILIES), 'appearance': ('AppearanceUnlocked',),
            'outfit': ('OutfitUnlocked',)}
    # Retain the previously exposed selector while accepting the documented
    # native family name. This string is a selector, never a module import.
    keys['koei_editor.shared.appearance'] = keys['appearance']
    if (kind is not None and not isinstance(kind, str)) or kind not in keys or (content_id is not None and kind is None):
        raise SaveError('Choose appearance, outfit, or all bodyguard customization.')
    result = []
    for field in keys[kind]:
        family = FAMILIES[field]
        ids = range(family['base_count'], family['base_count'] + family['count'])
        if content_id is not None:
            if type(content_id) is not int or content_id not in ids:
                raise SaveError('This bodyguard customization choice has no verified unlock flag.')
            ids = (content_id,)
        result.extend(Change('guard_customization', index, field, True) for index in ids)
    return result


def customization_state(document, changes=()):
    """Return saved/pending choices and read-only reasons for future layouts."""
    requests = _requests(changes)
    state = {'appearances': [], 'outfits': [], 'editable': True, 'reason': ''}
    reasons = []
    for field, family in FAMILIES.items():
        reason = ''
        try:
            _, available = _read_flags(document, family['availability'], family['count'])
            _, notifications = _read_flags(document, family['notifications'], family['count'])
        except SaveError as error:
            reason = str(error)
            available = notifications = None
            reasons.append(reason)
        if not reason:
            for change in requests:
                if change.field != field:
                    continue
                slot = change.index - family['base_count']
                if not available[slot]:
                    notifications[slot] = 1
                available[slot] = 1
        for choice in family['choices']:
            default = choice['id'] < family['base_count']
            slot = choice['id'] - family['base_count']
            state[family['state_key']].append({**choice, 'available_by_default': default,
                'unlocked': True if default else bool(available[slot]) if available is not None else None,
                'new': False if default else bool(notifications[slot]) if notifications is not None else None,
                'editable': not default and not reason,
                'reason': 'Available by default.' if default else reason})
    if reasons:
        state['editable'] = False
        state['reason'] = '\n'.join(reasons)
    return state


def plan_customization_changes(document, changes, add_property, add_insertion):
    """Root writer supplies checked property replacements and tag insertions."""
    requests = _requests(changes)
    if not requests:
        return
    arrays = {}
    for change in requests:
        family = FAMILIES[change.field]
        for name in (family['availability'], family['notifications']):
            if name not in arrays:
                arrays[name] = _read_flags(document, name, family['count'])
        available = arrays[family['availability']][1]
        notifications = arrays[family['notifications']][1]
        slot = change.index - family['base_count']
        if not available[slot]:
            notifications[slot] = 1
        available[slot] = 1
    missing = []
    for name, (prop, entries) in arrays.items():
        if prop is None:
            missing.append(_new_bool_array_tag(document, name, entries))
        else:
            add_property(prop, _array_payload(entries),
                         f'{name}: verified bodyguard customization unlock')
    if missing:
        add_insertion(_top_terminator(document), b''.join(missing),
                      'Add native lazily initialized bodyguard customization arrays')
