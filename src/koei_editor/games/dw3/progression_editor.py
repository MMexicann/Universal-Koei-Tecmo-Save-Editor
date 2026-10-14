"""Explicit story actions, separate from stat and equipment presets.

The route metadata comes from shipped DataTables and reflected native enum
IDs. Patches use parsed property tags, never build-specific disk offsets.
"""
from koei_editor.resources import read_json
import struct

from koei_editor.games.dw3.models import Change, SaveError, fields
from koei_editor.shared.experimental_limits import within_numeric_limits

METADATA = read_json('progression_routes.json')
ROUTES = {row['officer_id']: row for row in METADATA['officers']}
SIDE_STORIES = {row['id']: row for row in METADATA['side_stories']}
CATEGORIES = {'progression'}
SIDE_ARRAYS = ('CanUseReMusouArray', 'NewCanUseReMusouArray')
ELIXIR_MAX = METADATA['limits']['HuanglongElixirs']
ELIXIR_STORAGE_MAX = 0x7fffffff
FIRST_CLEAR_ELIXIRS = METADATA['limits']['first_clear_elixirs']


def _elixir_property(document):
    """Return a verified scalar, native omitted zero, or a layout refusal."""
    prop = document.properties.get('BeansNum')
    if prop is None:
        # GameStatusSaveGame's constructor/reset initialize this Int32 to zero.
        # Default-valued tags can be omitted from a new/reset save.
        return None, 0, ''
    if (not isinstance(prop, dict) or prop.get('type') != 'IntProperty' or
            prop.get('data_size') != 4 or prop.get('flags') != 0 or
            prop.get('array_index') != 0 or type(prop.get('value')) is not int):
        return None, None, 'The Huanglong Elixir counter uses an unsupported scalar layout.'
    saved = prop['value']
    offset = prop.get('data_offset')
    if (type(offset) is not int or not 0 <= offset <= len(document.plaintext) - 4 or
            struct.unpack_from('<i', document.plaintext, offset)[0] != saved):
        return None, saved, 'The Huanglong Elixir counter does not match its saved bytes.'
    if not 0 <= saved <= ELIXIR_STORAGE_MAX:
        return None, saved, 'The saved Huanglong Elixir count is outside nonnegative signed 32-bit storage.'
    return prop, saved, ''


def elixir_count_change(value):
    """Set the final balance; do not silently coerce strings, floats or bools."""
    if not within_numeric_limits(value, 0, ELIXIR_MAX, storage_maximum=ELIXIR_STORAGE_MAX):
        raise SaveError(f'Huanglong Elixirs: supported 0–{ELIXIR_MAX}; experimental storage maximum {ELIXIR_STORAGE_MAX}.')
    return Change('progression', 0, 'HuanglongElixirs', value)


def _requested_elixir_count(changes, document=None):
    value = None
    found = False
    for change in changes:
        if change.category != 'progression' or change.field != 'HuanglongElixirs':
            continue
        if type(change.index) is not int or change.index != 0:
            raise SaveError('Huanglong Elixirs use the single global counter at index 0.')
        if found:
            raise SaveError('Duplicate Huanglong Elixir count changes.')
        saved = _elixir_property(document)[1] if document is not None else None
        if type(change.value) is int and change.value == saved:
            value = change.value
        else:
            value = elixir_count_change(change.value).value
        found = True
    return value


def elixir_state(document, changes=()):
    """Read the saved/pending balance without making unsupported saves fail open.

    An explicit count is the final balance, including when the same batch marks
    new Musou clears. Otherwise each new clear awards three, capped at 999;
    an existing balance above that cap is preserved.
    """
    prop, saved, reason = _elixir_property(document)
    if reason:
        return {'value': saved, 'saved_value': saved, 'editable': False, 'reason': reason}
    requests = list(changes)
    explicit = _requested_elixir_count(requests, document)
    value = saved
    if explicit is not None:
        value = explicit
    else:
        seen = set()
        for change in requests:
            if change.category != 'progression' or change.field != 'MusouCleared':
                continue
            route = ROUTES.get(change.index) if type(change.index) is int else None
            if (route is None or not route['route_length'] or change.value is not True or
                    change.index >= len(document.records('PCSaveDataArray'))):
                raise SaveError('This officer has no supported Musou Mode story.')
            if change.index in seen:
                raise SaveError('Duplicate story actions.')
            seen.add(change.index)
            _, cleared = _bool_array(document, 'EngiClearCharaArray', change.index + 1)
            if not cleared[change.index]:
                value = max(value, min(ELIXIR_MAX, value + FIRST_CLEAR_ELIXIRS))
    return {'value': value, 'saved_value': saved, 'editable': True, 'reason': ''}


def _bool_array(document, name, minimum, *, optional=False):
    prop = document.properties.get(name)
    if prop is None and optional:
        return None, [0] * minimum
    if (prop is None or prop['type'] != 'ArrayProperty(BoolProperty)' or
            not isinstance(prop['value'], dict)):
        raise SaveError(f'{name} is not a supported boolean array.')
    value = prop['value']
    count = value.get('count')
    entries = value.get('values')
    if (type(count) is not int or not isinstance(entries, list) or
            len(entries) != count or (count < minimum and not optional) or
            prop['data_size'] != 4 + count or
            any(type(v) is not int or v not in (0, 1) for v in entries)):
        raise SaveError(f'{name} has an unsupported progression layout.')
    result = list(entries)
    if optional and len(result) < minimum:
        result.extend([0] * (minimum - len(result)))
    return prop, result


def progression_state(document):
    """Read completion and side-story availability without altering the save."""
    _, cleared = _bool_array(document, 'EngiClearCharaArray', 0)
    _, available = _bool_array(document, 'CanUseReMusouArray', 3, optional=True)
    _, stages = _bool_array(document, 'CanUseScenarioArray', 0)
    officers = []
    for index, route in sorted(ROUTES.items()):
        if index >= len(document.records('PCSaveDataArray')):
            continue
        record = fields(document.records('PCSaveDataArray')[index])
        progress = record.get('Progress')
        if (progress is None or progress['type'] != 'IntProperty' or
                progress['data_size'] != 4 or type(progress['value']) is not int):
            raise SaveError('Unsupported saved Musou progression.')
        officers.append({**route, 'cleared': index < len(cleared) and bool(cleared[index]),
                         'progress': progress['value'],
                         'has_musou_route': route['route_length'] > 0,
                         'can_clear': route['route_length'] > 0 and index < len(cleared)})
    stories = [{**row, 'unlocked': bool(available[index]),
                'free_mode_unlocked': all(i < len(stages) and stages[i] for i in row['free_mode_scenario_ids'])}
               for index, row in sorted(SIDE_STORIES.items())]
    return {'officers': officers, 'side_stories': stories}


def musou_clear_changes(document, officer_id=None):
    """Plan selected/all existing Musou routes; never invent routes for39–41."""
    eligible = [row['officer_id'] for row in progression_state(document)['officers']
                if row['can_clear']]
    if officer_id is not None:
        if type(officer_id) is not int or officer_id not in eligible:
            raise SaveError('This officer has no supported Musou Mode story.')
        eligible = [officer_id]
    return [Change('progression', index, 'MusouCleared', True) for index in eligible]


def side_story_changes(story_id=None):
    if story_id is not None and (type(story_id) is not int or story_id not in SIDE_STORIES):
        raise SaveError('Unsupported side story.')
    indices = sorted(SIDE_STORIES) if story_id is None else [story_id]
    return [Change('progression', index, 'SideStoryUnlocked', True) for index in indices]


def _array_payload(entries):
    return struct.pack('<i', len(entries)) + bytes(entries)


def _fstring(value):
    raw = value.encode('utf-8') + b'\0'
    return struct.pack('<i', len(raw)) + raw


def _new_elixir_tag(value):
    """Verified complete scalar tag: no type children, four bytes, no flags."""
    return (_fstring('BeansNum') + _fstring('IntProperty') +
            struct.pack('<iiBi', 0, 4, 0, value))


def _new_bool_array_tag(document, name, entries):
    """Reuse the verified type/flags prefix of an existing top-level bool tag."""
    template, _ = _bool_array(document, 'CanUseScenarioArray', 0)
    reader_name_end = template['tag_offset'] + 4
    length = struct.unpack_from('<i', document.plaintext, template['tag_offset'])[0]
    if length <= 0:
        raise SaveError('Unsupported boolean tag name encoding.')
    reader_name_end += length
    prefix = bytearray(document.plaintext[reader_name_end:template['data_offset']])
    relative_size = template['size_offset'] - reader_name_end
    if (template['flags'] != 0 or template['array_index'] != 0 or
            not 0 <= relative_size <= len(prefix) - 4):
        raise SaveError('Unsupported boolean array tag metadata.')
    struct.pack_into('<i', prefix, relative_size, 4 + len(entries))
    return _fstring(name) + bytes(prefix) + _array_payload(entries)


def _top_terminator(document):
    payload_end = 4 + document.parsed['payload_size']
    trailer = bytes.fromhex(document.parsed['trailer_hex'])
    offset = payload_end - len(trailer) - len(_fstring('None'))
    if document.plaintext[offset:offset + len(_fstring('None'))] != _fstring('None'):
        raise SaveError('Cannot locate the verified top-level property terminator.')
    return offset


def plan_progression_changes(document, changes, add_property, add_insertion):
    """Root writer supplies verified property replacements and one insertion.

    Clear actions reproduce the persistent completion flag/progress and the
    native first-clear elixir award. They do not fabricate an in-progress run,
    battle records, timestamps or achievement events. Side actions unlock the
    ruler, Musou side story and its two Free Mode variants without marking the
    side story cleared.
    """
    requests = [change for change in changes if change.category in CATEGORIES]
    if not requests:
        return
    explicit_elixirs = _requested_elixir_count(requests, document)
    seen = set()
    arrays = {}
    direct_unlocks = {}
    def array(name, minimum, optional=False):
        if name not in arrays:
            arrays[name] = _bool_array(document, name, minimum, optional=optional)
        elif len(arrays[name][1]) < minimum:
            raise SaveError(f'{name} is too short for the requested story action.')
        return arrays[name][1]
    clear_requests = []
    for change in requests:
        if change.field == 'HuanglongElixirs':
            # Validated above; the single counter is written after all clears.
            continue
        if (not isinstance(change, Change) or type(change.index) is not int or
                change.value is not True or change.field not in ('MusouCleared', 'SideStoryUnlocked')):
            raise SaveError('Only explicit supported story unlock/clear actions are allowed.')
        ident = (change.index, change.field)
        if ident in seen:
            raise SaveError('Duplicate story actions.')
        seen.add(ident)
        if change.field == 'MusouCleared':
            route = ROUTES.get(change.index)
            if route is None or not route['route_length']:
                raise SaveError('This officer has no supported Musou Mode story.')
            if change.index >= len(document.records('PCSaveDataArray')):
                raise SaveError('The selected officer record is absent.')
            cleared = array('EngiClearCharaArray', change.index + 1)
            was_cleared = bool(cleared[change.index])
            cleared[change.index] = 1
            clear_requests.append((change.index, route, was_cleared))
        else:
            story = SIDE_STORIES.get(change.index)
            if story is None:
                raise SaveError('Unsupported side story.')
            available = array('CanUseReMusouArray', 3, True)
            fresh = not available[change.index]
            available[change.index] = 1
            if fresh:
                array('NewCanUseReMusouArray', 3, True)[change.index] = 1
            array('CanUseCharaArray', story['ruler_id'] + 1)[story['ruler_id']] = 1
            direct_unlocks.setdefault('CanUseCharaArray', set()).add(story['ruler_id'])
            stages = array('CanUseScenarioArray', max(story['free_mode_scenario_ids']) + 1)
            for stage in story['free_mode_scenario_ids']:
                stages[stage] = 1
                direct_unlocks.setdefault('CanUseScenarioArray', set()).add(stage)
    # Several clears share the elixir balance and several side unlocks share
    # each availability array, so produce exactly one patch per property.
    newly_cleared = 0
    for index, route, was_cleared in clear_requests:
        record = fields(document.records('PCSaveDataArray')[index])
        progress = record.get('Progress')
        if (progress is None or progress['type'] != 'IntProperty' or
                progress['data_size'] != 4 or type(progress['value']) is not int):
            raise SaveError('Unsupported saved Musou progression.')
        value = max(progress['value'], route['route_length'])
        add_property(progress, struct.pack('<i', value),
                     f'{route["officer"]}: Musou progress -> {value}')
        newly_cleared += not was_cleared
    missing = []
    if explicit_elixirs is not None or newly_cleared:
        beans, saved_elixirs, reason = _elixir_property(document)
        if reason:
            raise SaveError(reason)
        value = (explicit_elixirs if explicit_elixirs is not None else
                 max(saved_elixirs, min(ELIXIR_MAX, saved_elixirs + FIRST_CLEAR_ELIXIRS * newly_cleared)))
        reason = (f'Huanglong Elixirs: explicit final balance -> {value}'
                  if explicit_elixirs is not None else
                  f'{newly_cleared} new Musou clears: Huanglong Elixirs -> {value}')
        if beans is not None:
            add_property(beans, struct.pack('<i', value), reason)
        elif value:
            # Keep an unchanged implicit zero byte-identical; materialize only
            # a requested nondefault balance (including first-clear rewards).
            missing.append(_new_elixir_tag(value))
    for name, (prop, entries) in arrays.items():
        if prop is None:
            missing.append(_new_bool_array_tag(document, name, entries))
        elif name in direct_unlocks:
            # Other GUI actions can already stage individual content flags.
            # Avoid whole-array overlap and refuse an explicitly contradictory
            # relock instead of making the patch order decide the outcome.
            for index in sorted(direct_unlocks[name]):
                existing = [c for c in changes if c.category == 'unlock' and
                            c.field == name and c.index == index]
                if existing:
                    if any(c.value is not True for c in existing):
                        raise SaveError('A side-story unlock conflicts with a pending content relock.')
                    continue
                leaf = dict(prop, data_offset=prop['data_offset'] + 4 + index, data_size=1)
                add_property(leaf, bytes([entries[index]]),
                             f'{name}[{index}]: explicit side-story unlock')
        else:
            add_property(prop, _array_payload(entries), f'{name}: explicit story action')
    if missing:
        add_insertion(_top_terminator(document), b''.join(missing),
                      'Add native lazily initialized progression properties')
