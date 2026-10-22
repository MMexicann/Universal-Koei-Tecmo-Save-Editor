"""Portable character and weapon build plans, separate from game saves.

This module stores declarative planning values only. It does not interpret a
game's mechanics, calculate derived stats, parse a save, or write a save. A
game editor remains responsible for validating any values when a user stages
them through its ordinary reviewed editing workflow.
"""
from collections.abc import Mapping
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import re
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.save_safety import safe_path


SCHEMA = 'koei-character-weapon-build'
SCHEMA_VERSION = 1
SUFFIX = '.build.json'
MAX_BYTES = 256 * 1024
MAX_ASSIGNMENTS = 20_000
MAX_EQUIPMENT_SLOTS = 512
MAX_ID_BYTES = 240
MAX_TEXT_BYTES = 4096
MAX_NAME_BYTES = 160
_IDENTIFIER = re.compile(r'[a-z0-9_]+\Z')


def _text(value, label, maximum, *, allow_empty=False):
    if type(value) is not str or (not allow_empty and not value.strip()):
        raise SaveError(f'Build preset {label} must be plain text.')
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise SaveError(f'Build preset {label} contains control characters.')
    try:
        size = len(value.encode('utf-8'))
    except UnicodeError as error:
        raise SaveError(f'Build preset {label} is not valid Unicode.') from error
    if size > maximum:
        raise SaveError(f'Build preset {label} is too long.')
    return value


def _scalar(value, label):
    """Validate an inert JSON scalar without assigning gameplay meaning."""
    if type(value) is bool or value is None:
        # Booleans and null can be IDs/choices in some games, so preserve them
        # as data. Numeric comparisons below explicitly exclude booleans.
        return value
    if type(value) is int:
        if not -(1 << 63) <= value <= (1 << 64) - 1:
            raise SaveError(f'Build preset {label} integer is outside the supported scalar range.')
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise SaveError(f'Build preset {label} cannot be a nonfinite number.')
        return value
    if type(value) is str:
        return _text(value, label, MAX_TEXT_BYTES, allow_empty=True)
    raise SaveError(f'Build preset {label} must be an inert JSON scalar.')


def _mapping(values, label, maximum):
    if not isinstance(values, Mapping):
        raise SaveError(f'Build preset {label} must be a mapping of stable IDs to scalar values.')
    if len(values) > maximum:
        raise SaveError(f'Build preset {label} contains too many entries.')
    result = {}
    for key, value in values.items():
        _text(key, f'{label} ID', MAX_ID_BYTES)
        result[key] = _scalar(value, f'{label} value')
    return MappingProxyType(result)


@dataclass(frozen=True)
class BuildPlan:
    """A portable proposed build with no source-save identity or write API."""

    game_id: str
    platform_id: str
    character_id: str
    name: str
    values: Mapping[str, object] = field(default_factory=dict)
    equipment: Mapping[str, object] = field(default_factory=dict)
    notes: str = ''

    def __post_init__(self):
        for key in ('game_id', 'platform_id', 'character_id'):
            _text(getattr(self, key), key.replace('_', ' '), MAX_ID_BYTES)
        if not _IDENTIFIER.fullmatch(self.game_id):
            raise SaveError('Build preset game ID is invalid.')
        if not _IDENTIFIER.fullmatch(self.platform_id):
            raise SaveError('Build preset platform ID is invalid.')
        _text(self.name, 'name', MAX_NAME_BYTES)
        _text(self.notes, 'notes', MAX_TEXT_BYTES, allow_empty=True)
        values = _mapping(self.values, 'values', MAX_ASSIGNMENTS)
        equipment = _mapping(self.equipment, 'equipment', MAX_EQUIPMENT_SLOTS)
        if len(values) + len(equipment) > MAX_ASSIGNMENTS:
            raise SaveError('Build preset contains too many total assignments.')
        if not values and not equipment:
            raise SaveError('Add at least one planned value or equipment choice to a build preset.')
        object.__setattr__(self, 'values', values)
        object.__setattr__(self, 'equipment', equipment)


@dataclass(frozen=True)
class BuildDelta:
    """A plain comparison difference: left value minus right value."""

    field_id: str
    left_value: int | float
    right_value: int | float
    delta: int | float


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SaveError('Build preset JSON contains a duplicate property name.')
        result[key] = value
    return result


def _reject_constant(_value):
    raise SaveError('Build preset JSON cannot contain nonfinite numbers.')


def _exact_keys(value, expected, label):
    if type(value) is not dict or set(value) != set(expected):
        raise SaveError(f'Build preset {label} has missing or unknown properties.')


def encode_plan(plan):
    """Encode a validated plan as bounded UTF-8 JSON bytes."""
    if type(plan) is not BuildPlan:
        raise SaveError('Choose a character and weapon build plan.')
    data = {
        'schema': SCHEMA,
        'version': SCHEMA_VERSION,
        'game_id': plan.game_id,
        'platform_id': plan.platform_id,
        'character_id': plan.character_id,
        'name': plan.name,
        'values': dict(sorted(plan.values.items())),
        'equipment': dict(sorted(plan.equipment.items())),
        'notes': plan.notes,
    }
    try:
        raw = (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    except (ValueError, UnicodeError, RecursionError) as error:
        raise SaveError('The build preset cannot be encoded as bounded UTF-8 JSON.') from error
    if not 0 < len(raw) <= MAX_BYTES:
        raise SaveError(f'Build preset JSON must fit within {MAX_BYTES // 1024} KiB.')
    return raw


def decode_plan(raw):
    """Decode a bounded UTF-8 plan, rejecting duplicate and unknown keys."""
    if type(raw) is str:
        try:
            raw = raw.encode('utf-8')
        except UnicodeError as error:
            raise SaveError('Build preset is not valid UTF-8 text.') from error
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise SaveError(f'Choose a nonempty build preset no larger than {MAX_BYTES // 1024} KiB.')
    try:
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant)
    except SaveError:
        raise
    except (ValueError, UnicodeError, RecursionError) as error:
        raise SaveError('The build preset is not a valid UTF-8 JSON document.') from error
    _exact_keys(data, ('schema', 'version', 'game_id', 'platform_id', 'character_id',
                       'name', 'values', 'equipment', 'notes'), 'document')
    if type(data['schema']) is not str or data['schema'] != SCHEMA:
        raise SaveError('This JSON document is not a supported character and weapon build preset.')
    if type(data['version']) is not int or data['version'] != SCHEMA_VERSION:
        raise SaveError('This build preset schema version is not supported.')
    for key in ('values', 'equipment'):
        if type(data[key]) is not dict:
            raise SaveError(f'Build preset {key} must be a JSON object.')
    return BuildPlan(data['game_id'], data['platform_id'], data['character_id'], data['name'],
                     data['values'], data['equipment'], data['notes'])


def load_plan(path):
    """Load a bounded `.build.json` plan without interpreting it as a save."""
    path = safe_path(path)
    if not path.name.lower().endswith(SUFFIX):
        raise SaveError(f'Choose a {SUFFIX} build preset, not a game save.')
    try:
        with path.open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
    except OSError as error:
        raise SaveError('The build preset could not be read.') from error
    return decode_plan(raw)


def destination_path(path):
    """Complete the dedicated suffix, matching native save-dialog behavior."""
    path = Path(path)
    name = path.name
    if not name.lower().endswith(SUFFIX):
        if name.lower().endswith('.json'):
            name = name[:-5]
        if not name.lower().endswith('.build'):
            name += '.build'
        path = path.with_name(name + '.json')
    return safe_path(path)


def save_plan(plan, path):
    """Create a new JSON preset file; never replace an existing file."""
    destination = destination_path(path)
    return atomic_new(encode_plan(plan), destination)


def compare_build_plans(left, right):
    """Return numeric A-minus-B value deltas for shared stable field IDs.

    These are comparison differences only; this function does not apply a
    game's equipment, buff, damage, or progression formula.
    """
    if type(left) is not BuildPlan or type(right) is not BuildPlan:
        raise SaveError('Compare two character and weapon build plans.')
    if (left.game_id, left.platform_id, left.character_id) != (
            right.game_id, right.platform_id, right.character_id):
        raise SaveError('Compare builds for the same game, platform, and character.')
    deltas = []
    for field_id in sorted(set(left.values) & set(right.values)):
        a, b = left.values[field_id], right.values[field_id]
        if type(a) not in (int, float) or type(b) not in (int, float):
            continue
        difference = a - b
        if type(difference) is float and not math.isfinite(difference):
            raise SaveError('The comparison difference is outside finite numeric range.')
        deltas.append(BuildDelta(field_id, a, b, difference))
    return tuple(deltas)
