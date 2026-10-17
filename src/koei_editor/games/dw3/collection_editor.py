"""Conservative unlocks for the native movie and music galleries."""
from koei_editor.resources import read_json
import struct

from koei_editor.games.dw3.models import Change, SaveError

DATA = read_json('collection_unlocks.json')
CATEGORIES = {'collection'}


def _owner(document, path):
    properties = document.parsed['properties']
    parent = None
    spec = next((row for row in DATA.values() if row['path'] == path), None)
    if spec is None:
        return None, None
    for depth, name in enumerate(path):
        prop = next((item for item in properties if item['name'] == name), None)
        if (prop is None or prop.get('type') != spec['struct_types'][depth] or
                prop.get('flags') != 0 or prop.get('array_index') != 0 or
                not isinstance(prop.get('value'), list)):
            return None, None
        parent, properties = prop, prop['value']
    return parent, properties


def _array(document, spec):
    owner, props = _owner(document, spec['path'])
    if props is None:
        raise SaveError(f"{spec['label']} options use an unsupported layout.")
    prop = next((item for item in props if item['name'] == spec['array']), None)
    if prop is None:
        return owner, props, None, [False] * spec['total']
    val = prop.get('value')
    if (prop.get('type') != 'ArrayProperty(BoolProperty)' or
            prop.get('flags') != 0 or prop.get('array_index') != 0 or not isinstance(val, dict) or
            type(val.get('count')) is not int or val['count'] < spec['total'] or
            not isinstance(val.get('values'), list) or len(val['values']) != val.get('count') or
            any(type(value) not in (int, bool) or value not in (0, 1, False, True) for value in val['values']) or
            prop.get('data_size') != 4 + val.get('count') or
            type(prop.get('data_offset')) is not int or
            prop['data_offset'] < 0 or prop['data_offset'] + prop['data_size'] > len(document.plaintext)):
        raise SaveError(f"{spec['label']} unlock array uses an unsupported layout.")
    saved = list(map(bool, val['values']))
    if document.plaintext[prop['data_offset']:prop['data_offset'] + prop['data_size']] != struct.pack('<i', len(saved)) + bytes(saved):
        raise SaveError(f"{spec['label']} unlock array does not match its saved bytes.")
    return owner, props, prop, saved


def _entry(spec, index):
    row = next((r for r in spec['rows'] if r['id'] == index), None)
    return row


def collection_state(document, changes=()):
    requested = {(c.field, c.index): c.value for c in changes
                 if isinstance(c, Change) and c.category in CATEGORIES}
    result = {}
    for key, spec in DATA.items():
        try:
            _, _, _, saved = _array(document, spec)
            editable, reason = True, ''
        except (SaveError, KeyError, TypeError):
            saved = [False] * spec['total']
            editable, reason = False, f"{spec['label']} unlock data is missing or has an unsupported layout."
        rows = []
        for row in spec['rows']:
            idx = row['id']
            rows.append({'id': idx, 'name': row['name'],
                         'unlocked': bool(requested.get((spec['field'], idx), saved[idx] if idx < len(saved) else False))})
        result[key] = {'editable': editable, 'reason': reason,
                       'owned': sum(1 for row in rows if row['unlocked']),
                       'total': len(rows), 'rows': rows}
    return result


def unlock_entry_changes(document, gallery, indices):
    """Unlock explicitly selected authored entries; never touch placeholders.

    Validate the complete selection before returning any changes. Native
    acknowledgement arrays are deliberately independent of availability.
    """
    if not isinstance(gallery, str) or gallery not in DATA:
        raise SaveError('Choose the music or movies gallery.')
    spec = DATA[gallery]
    _array(document, spec)
    result = []
    seen = set()
    for index in indices:
        if type(index) is not int or index in seen or _entry(spec, index) is None:
            raise SaveError('Choose distinct supported gallery entry IDs.')
        seen.add(index)
        result.append(Change('collection', index, spec['field'], True))
    if not seen:
        raise SaveError('Choose at least one gallery entry.')
    return result


def unlock_music_changes(document):
    return unlock_entry_changes(document, 'music', [row['id'] for row in DATA['music']['rows']])


def unlock_movie_changes(document):
    return unlock_entry_changes(document, 'movies', [row['id'] for row in DATA['movies']['rows']])


def original_value(document, change):
    spec = DATA.get('music' if change.field == 'Music' else 'movies' if change.field == 'Movie' else '')
    if (spec is None or type(change.index) is not int or
            change.index not in {row['id'] for row in spec['rows']}):
        raise SaveError('Unsupported collection unlock.')
    _, _, _, saved = _array(document, spec)
    return saved[change.index]


def _fstring(value):
    encoded = value.encode('utf-8') + b'\0'
    return struct.pack('<i', len(encoded)) + encoded


def _walk(properties):
    for prop in properties:
        yield prop
        value = prop.get('value')
        if isinstance(value, list):
            yield from _walk(value)
        elif isinstance(value, dict) and isinstance(value.get('records'), list):
            for record in value['records']:
                yield from _walk(record)


def _make_tag(document, owner, props, spec, values):
    template = next((prop for prop in _walk(document.parsed['properties'])
                     if prop.get('type') == 'ArrayProperty(BoolProperty)' and
                     prop.get('flags') == 0 and prop.get('array_index') == 0), None)
    if template is None:
        raise SaveError(f"Cannot safely create the missing {spec['label']} unlock array.")
    begin = template['tag_offset']
    name_len = struct.unpack_from('<i', document.plaintext, begin)[0]
    if name_len <= 0 or begin + 4 + name_len > template['data_offset']:
        raise SaveError('Unsupported boolean array tag name encoding.')
    prefix_begin = begin + 4 + name_len
    prefix = bytearray(document.plaintext[prefix_begin:template['data_offset']])
    size_relative = template['size_offset'] - prefix_begin
    if (template.get('flags') != 0 or template.get('array_index') != 0 or
            size_relative < 0 or size_relative + 4 > len(prefix)):
        raise SaveError('Unsupported boolean array tag metadata.')
    struct.pack_into('<i', prefix, size_relative, 4 + len(values))
    return _fstring(spec['array']) + bytes(prefix) + struct.pack('<i', len(values)) + bytes(values)


def _insert_at(owner, props, document):
    if owner is None:
        raise SaveError('Cannot locate the verified option struct for a missing unlock array.')
    end = owner['data_offset'] + owner['data_size']
    marker = _fstring('None')
    offset = end - len(marker)
    if document.plaintext[offset:end] != marker:
        raise SaveError('Cannot locate the option struct terminator.')
    return offset


def plan_collection_changes(document, changes, add_property, add_insertion):
    requests = [c for c in changes if isinstance(c, Change) and c.category in CATEGORIES]
    if not requests:
        return
    by_field = {'Music': DATA['music'], 'Movie': DATA['movies']}
    seen = set()
    for change in requests:
        if (change.field not in by_field or type(change.index) is not int or
                type(change.value) is not bool or change.value is not True):
            raise SaveError('Unsupported collection action.')
        spec = by_field[change.field]
        if change.index not in {row['id'] for row in spec['rows']}:
            raise SaveError('Unsupported collection ID.')
        key = (change.field, change.index)
        if key in seen:
            raise SaveError('Duplicate collection action.')
        seen.add(key)
    grouped = {field: [c.index for c in requests if c.field == field] for field in by_field}
    for field, indices in grouped.items():
        if not indices:
            continue
        spec = by_field[field]
        owner, props, prop, values = _array(document, spec)
        changed = list(values)
        for index in indices:
            changed[index] = True
        reason = f"Unlock {'music' if field == 'Music' else 'movie'} gallery"
        if prop is None:
            tag = _make_tag(document, owner, props, spec, changed)
            add_insertion(_insert_at(owner, props, document), tag, reason)
        else:
            add_property(prop, struct.pack('<i', len(changed)) + bytes(changed), reason)

