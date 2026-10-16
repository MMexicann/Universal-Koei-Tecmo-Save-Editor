"""Reviewed, source-bound scalar edit plans. JSON data never supplies code or offsets.

A preset can be reused with the exact original save, including a byte-identical
copy at another safe path. Native field eligibility and dependencies remain the
bound adapter's responsibility. Importing and preflighting never writes a save.
"""
from collections.abc import Mapping
from dataclasses import dataclass, fields as dataclass_fields, is_dataclass
import hashlib
import json
from pathlib import Path
import re

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import (
    BoundScalarAdapter, normalize_pending_values)
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.experimental_limits import above_supported, experimental_limits
from koei_editor.shared.save_safety import safe_path


SCHEMA = 'koei-reviewed-edit-preset'
SCHEMA_VERSION = 1
SUFFIX = '.edits.json'
MAX_BYTES = 4 * 1024 * 1024
MAX_EDITS = 20_000
MAX_TEXT_BYTES = 4096
_HASH = re.compile(r'[0-9a-f]{64}\Z')


@dataclass(frozen=True)
class PresetEdit:
    field: str
    value: int | str


@dataclass(frozen=True)
class EditPreset:
    name: str
    game_id: str
    source_sha256: str
    profile_sha256: str
    experimental: bool
    edits: tuple[PresetEdit, ...]


@dataclass(frozen=True)
class PresetRow:
    field: object
    opened: int | str
    before: int | str
    after: int | str
    imported: bool


@dataclass(frozen=True)
class PresetPlan:
    preset: EditPreset
    adapter: BoundScalarAdapter
    document: object
    pending: tuple
    result: tuple
    rows: tuple[PresetRow, ...]
    experimental_count: int
    serialized_sha256: str


def _text(value, label, maximum):
    if (type(value) is not str or not value.strip()
            or any(ord(character) < 32 or ord(character) == 127 for character in value)):
        raise SaveError(f'Preset {label} must be nonempty plain text.')
    try:
        size = len(value.encode('utf-8'))
    except UnicodeError as error:
        raise SaveError(f'Preset {label} is not valid Unicode.') from error
    if size > maximum:
        raise SaveError(f'Preset {label} is too long.')
    return value


def _scalar(value):
    if type(value) is int:
        if not -(1 << 63) <= value <= (1 << 64) - 1:
            raise SaveError('Preset whole numbers must fit within 64-bit scalar storage.')
    elif type(value) is str:
        # Editable names may legitimately be empty. Backend encoding/length
        # rules are authoritative during preflight, not inferred here.
        try:
            if len(value.encode('utf-8')) > MAX_TEXT_BYTES:
                raise SaveError('A preset text value is too long.')
        except UnicodeError as error:
            raise SaveError('A preset text value is not valid Unicode.') from error
    else:
        raise SaveError('Preset values must be exact whole numbers or text, never booleans or fractions.')
    return value


def _hash(value, label):
    if type(value) is not str or not _HASH.fullmatch(value):
        raise SaveError(f'Preset {label} must be a lowercase SHA-256 digest.')
    return value


def validate_preset(preset):
    if type(preset) is not EditPreset:
        raise SaveError('Choose a reviewed scalar edit preset.')
    _text(preset.name, 'name', 160)
    _text(preset.game_id, 'game/profile', 120)
    if not re.fullmatch(r'[a-z0-9_]+', preset.game_id):
        raise SaveError('Preset game/profile identity is invalid.')
    _hash(preset.source_sha256, 'source identity')
    _hash(preset.profile_sha256, 'field definition identity')
    if type(preset.experimental) is not bool:
        raise SaveError('Preset experimental status must be an explicit boolean.')
    if type(preset.edits) is not tuple or not 0 < len(preset.edits) <= MAX_EDITS:
        raise SaveError(f'A preset must contain from 1 to {MAX_EDITS:,} field assignments.')
    seen = set()
    for edit in preset.edits:
        if type(edit) is not PresetEdit:
            raise SaveError('Preset assignments must retain their reviewed field/value structure.')
        _text(edit.field, 'field identity', 240)
        _scalar(edit.value)
        if edit.field in seen:
            raise SaveError('A preset assigns the same field more than once.')
        seen.add(edit.field)
    return preset


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SaveError('Preset JSON contains a duplicate property name.')
        result[key] = value
    return result


def _keys(value, expected, label):
    if type(value) is not dict or set(value) != set(expected):
        raise SaveError(f'Preset {label} has missing or unknown properties.')


def loads(raw):
    """Parse a bounded JSON document with no duplicate names or extra keys."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise SaveError(f'Choose a nonempty edit preset no larger than {MAX_BYTES // 1024 // 1024} MiB.')
    try:
        def invalid_constant(_value):
            raise SaveError('Preset JSON cannot contain nonfinite numbers.')
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                          parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise SaveError('The edit preset is not a valid UTF-8 JSON document.') from error
    _keys(data, ('schema', 'version', 'name', 'game_id', 'scope',
                 'profile_sha256', 'experimental', 'edits'), 'document')
    if data['schema'] != SCHEMA or type(data['schema']) is not str:
        raise SaveError('This JSON document is not a supported edit preset.')
    if type(data['version']) is not int or data['version'] != SCHEMA_VERSION:
        raise SaveError('This edit preset schema version is not supported.')
    _keys(data['scope'], ('kind', 'source_sha256'), 'scope')
    if type(data['scope']['kind']) is not str or data['scope']['kind'] != 'source':
        raise SaveError('Only presets bound to the exact original save are supported.')
    if type(data['edits']) is not list or not 0 < len(data['edits']) <= MAX_EDITS:
        raise SaveError(f'A preset must contain from 1 to {MAX_EDITS:,} field assignments.')
    edits = []
    for entry in data['edits']:
        _keys(entry, ('field', 'value'), 'assignment')
        edits.append(PresetEdit(entry['field'], entry['value']))
    return validate_preset(EditPreset(data['name'], data['game_id'], data['scope']['source_sha256'],
                                      data['profile_sha256'], data['experimental'], tuple(edits)))


def dumps(preset):
    validate_preset(preset)
    data = {'schema': SCHEMA, 'version': SCHEMA_VERSION, 'name': preset.name,
            'game_id': preset.game_id,
            'scope': {'kind': 'source', 'source_sha256': preset.source_sha256},
            'profile_sha256': preset.profile_sha256, 'experimental': preset.experimental,
            'edits': [{'field': edit.field, 'value': edit.value} for edit in preset.edits]}
    raw = (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    if len(raw) > MAX_BYTES:
        raise SaveError('The edit preset exceeds the supported file size.')
    return raw


def load(path):
    path = safe_path(path)
    if not path.name.lower().endswith(SUFFIX):
        raise SaveError('Choose an .edits.json preset, not a game save or change-review report.')
    with path.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    return loads(raw)


def destination_path(path):
    """Complete the dedicated suffix, including Windows native dialog results."""
    path = Path(path)
    name = path.name
    if not name.lower().endswith(SUFFIX):
        if name.lower().endswith('.json'):
            name = name[:-5]
        if not name.lower().endswith('.edits'):
            name += '.edits'
        path = path.with_name(name + '.json')
    return safe_path(path)


def _bound(adapter, document):
    if type(adapter) is not BoundScalarAdapter:
        raise SaveError('Edit presets require an explicitly bound scalar editor.')
    adapter.validate_document(document)
    if (type(document.raw) is not bytes or type(document.payload) is not bytes
            or hashlib.sha256(document.raw).hexdigest() != document.sha256):
        raise SaveError('The opened immutable save identity is invalid.')


def validate_source(adapter, document):
    """Requalify the source and companion context without creating any files."""
    _bound(adapter, document)
    if adapter.read_save(document.source) != document:
        raise SaveError('The opened save or its original metadata changed. Reopen a separate copy.')


def _definition_value(value, depth=0):
    """Canonical immutable native metadata, including compound constraints."""
    if depth > 8:
        raise SaveError('Preset field metadata exceeds the supported nesting depth.')
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is tuple and len(value) <= MAX_EDITS:
        return [_definition_value(item, depth + 1) for item in value]
    raise SaveError('This scalar profile does not expose stable preset field definitions.')


def field_definitions_sha256(adapter, document, field_ids=None):
    # Metadata is identity, never an instruction to patch offsets. Include all
    # declared frozen field data, not only common scalar attributes: bit shifts,
    # endian/storage encodings, mirrors and enumerations affect native meaning.
    # Class identity also distinguishes subclasses with different validators.
    fields = adapter.field_map(document)
    if field_ids is not None:
        if (type(field_ids) not in (tuple, list, set, frozenset)
                or any(type(key) is not str or key not in fields for key in field_ids)
                or len(field_ids) != len(set(field_ids))):
            raise SaveError('Choose distinct mapped fields for their native definition identity.')
        fields = {key: fields[key] for key in field_ids}
    definitions = []
    shared = {'offset', 'size', 'group', 'slot', 'label', 'kind', 'encoding',
              'minimum', 'maximum', 'maxable', 'experimental_maximum',
              'storage', 'byteorder', 'endian', 'shift', 'bit', 'bits',
              'display_bias', 'mirrors', 'choices', 'forbidden'}
    for key, field in sorted(fields.items()):
        attributes = set(shared)
        if is_dataclass(field):
            attributes.update(item.name for item in dataclass_fields(field))
        definition = [key, type(field).__module__ + '.' + type(field).__qualname__]
        definition.append([[attribute, _definition_value(getattr(field, attribute, None))]
                           for attribute in sorted(attributes)])
        definitions.append(definition)
    raw = json.dumps(definitions, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('ascii')
    return hashlib.sha256(raw).hexdigest()


def _profile_hash(adapter, document):
    return field_definitions_sha256(adapter, document)


def _pending(adapter, document, changes):
    if not isinstance(changes, Mapping) or len(changes) > MAX_EDITS:
        raise SaveError('The complete pending map must contain verified scalar field assignments.')
    # The adapter's serializer checks every requested value, final native
    # dependencies and the reparsed encoded result. No stage-order side effects
    # may silently replace an imported assignment.
    with experimental_limits(adapter.experimental):
        result = normalize_pending_values(document, changes, adapter.field_map(document))
    raw = adapter.serialize(document, result)
    adapter.review(document, result)
    return result, raw


def _snapshot(changes):
    if not isinstance(changes, Mapping) or len(changes) > MAX_EDITS:
        raise SaveError('The complete pending map must contain verified scalar field assignments.')
    return dict(changes)


def create(adapter, document, changes, name):
    """Freeze all staged edits, including hidden fields; never invoke Max."""
    validate_source(adapter, document)
    result, _raw = _pending(adapter, document, _snapshot(changes))
    fields = adapter.field_map(document)
    preset = EditPreset(name, adapter.game_id, document.sha256, _profile_hash(adapter, document),
                        any(above_supported(fields[key], value) for key, value in result.items()),
                        tuple(PresetEdit(key, value) for key, value in sorted(result.items())))
    validate_preset(preset)
    # Verify the bounded serialized form before a file dialog/write begins.
    dumps(preset)
    validate_source(adapter, document)
    return preset


def prepare(adapter, document, changes, preset):
    """Preflight a complete candidate map; no editor state or file is changed."""
    validate_preset(preset)
    validate_source(adapter, document)
    if preset.game_id != adapter.game_id:
        raise SaveError('This preset belongs to a different game/platform profile.')
    if preset.source_sha256 != document.sha256:
        raise SaveError('This preset requires the exact original save. Inventory and record IDs cannot be transferred to another save.')
    if preset.profile_sha256 != _profile_hash(adapter, document):
        raise SaveError('The preset field definitions changed. Review and export a new preset with this editor version.')
    current, _raw = _pending(adapter, document, _snapshot(changes))
    fields = adapter.field_map(document)
    assignments = {edit.field: edit.value for edit in preset.edits}
    candidate = dict(current)
    candidate.update(assignments)
    result, raw = _pending(adapter, document, candidate)
    count = sum(above_supported(fields[key], value) for key, value in result.items())
    imported_experimental = any(key in result and above_supported(fields[key], result[key])
                                for key in assignments)
    if imported_experimental and not preset.experimental:
        raise SaveError('The preset understates its experimental edits. Export a new reviewed preset.')
    rows = tuple(PresetRow(fields[key], fields[key].value(document.payload),
                           current.get(key, fields[key].value(document.payload)),
                           result.get(key, fields[key].value(document.payload)), key in assignments)
                 for key in sorted(set(current) | set(result) | set(assignments)))
    plan = PresetPlan(preset, adapter, document, tuple(sorted(current.items())),
                      tuple(sorted(result.items())), rows, count, hashlib.sha256(raw).hexdigest())
    # Native serializers/field hooks can take time. Recheck the actual source
    # and complete original context after the entire frozen plan is prepared.
    validate_source(adapter, document)
    return plan


def confirm(plan, adapter, document, changes):
    """Return a fresh validated map only while the complete preview is current."""
    if type(plan) is not PresetPlan or plan.adapter is not adapter or plan.document is not document:
        raise SaveError('The editor session changed. Import the preset again for a fresh review.')
    current, _raw = _pending(adapter, document, _snapshot(changes))
    if tuple(sorted(current.items())) != plan.pending:
        raise SaveError('Pending edits changed after the preview. Import the preset again to review the complete result.')
    expected = prepare(adapter, document, current, plan.preset)
    if expected != plan:
        raise SaveError('The preset preview changed. Import the preset again for a fresh review.')
    return dict(expected.result)


def export(preset, adapter, document, path):
    """Write JSON to a new file; keep any completed report if a later check fails."""
    destination = destination_path(path)
    # Re-preflight the frozen preset instead of exporting unchecked data.
    prepare(adapter, document, {}, preset)
    raw = dumps(preset)
    result = atomic_new(raw, destination)
    try:
        validate_source(adapter, document)
        with result.open('rb') as stream:
            actual = stream.read(MAX_BYTES + 1)
        if actual != raw:
            raise SaveError('The exported preset changed after creation.')
    except Exception as error:
        raise SaveError('Preset verification did not finish after creation. The JSON file was retained; '
                        'do not use it. Reopen the source and choose a new destination.\n\n' + str(error)) from error
    return result
