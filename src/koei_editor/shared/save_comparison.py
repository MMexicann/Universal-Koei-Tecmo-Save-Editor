"""Read-only same-profile comparison of independently qualified copied saves."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from koei_editor.game_registry import GAMES, get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.scalar_presentation import ScalarPresentation

COMPARABLE_GAMES = tuple(game for game in GAMES if game.scalar_backend is not None)


@dataclass(frozen=True)
class FieldDifference:
    id: str
    group: str
    label: str
    record: str
    left_label: str | None
    right_label: str | None
    left: int | str | None
    right: int | str | None
    status: str


@dataclass(frozen=True)
class Comparison:
    game_id: str
    left: object
    right: object
    rows: tuple[FieldDifference, ...]
    unchanged_fields: int
    changed_payload_bytes: int
    outside_field_bytes: int


def adapter_for(game_id):
    game = get_game(game_id)
    if game not in COMPARABLE_GAMES:
        raise SaveError('Choose a registered scalar game/platform profile for comparison.')
    return game.get_scalar_adapter()


def _definition(field):
    # Dynamic editing limits depend on the opened value; they are not identity.
    return tuple(getattr(field, key, None) for key in
                 ('offset', 'size', 'group', 'slot', 'label', 'kind', 'encoding'))


def _value(field, document):
    value = field.value(document.payload)
    if type(value) not in (int, str):
        raise SaveError('Comparison requires an exact integer or text scalar value.')
    return value


def compare_documents(game_id, left, right):
    adapter = adapter_for(game_id)
    adapter.validate_document(left)
    adapter.validate_document(right)
    lhs, rhs = adapter.field_map(left), adapter.field_map(right)
    rows, unchanged = [], 0
    presentation = ScalarPresentation(adapter.backend, game_id)
    mask = bytearray(max(len(left.payload), len(right.payload)))
    for document, mapping in ((left, lhs), (right, rhs)):
        for field in mapping.values():
            if (type(field.offset) is not int or type(field.size) is not int
                    or field.offset < 0 or field.size < 1
                    or field.offset + field.size > len(document.payload)):
                raise SaveError('A comparison field lies outside its qualified native payload.')
            mask[field.offset:field.offset + field.size] = b'\1' * field.size
    for key in dict.fromkeys((*lhs, *rhs)):
        first, second = lhs.get(key), rhs.get(key)
        before = _value(first, left) if first is not None else None
        after = _value(second, right) if second is not None else None
        if first is None: status = 'available_in_second'
        elif second is None: status = 'available_in_first'
        elif _definition(first) != _definition(second): status = 'definition_changed'
        elif type(before) is type(after) and before == after:
            unchanged += 1
            continue
        else: status = 'value_changed'
        field = second if second is not None else first
        rows.append(FieldDifference(key, field.group, field.label, presentation.record_name(field),
            first.label if first is not None else None, second.label if second is not None else None,
            before, after, status))
    changes = outside = 0
    common = min(len(left.payload), len(right.payload))
    for index, (before, after) in enumerate(zip(left.payload, right.payload)):
        if before != after:
            changes += 1
            outside += not mask[index]
    changes += abs(len(left.payload) - len(right.payload))
    outside += sum(not value for value in mask[common:])
    return Comparison(game_id, left, right, tuple(rows), unchanged, changes, outside)


def prepare(game_id, left_path, right_path):
    adapter = adapter_for(game_id)
    left, right = adapter.read_save(left_path), adapter.read_save(right_path)
    result = compare_documents(game_id, left, right)
    validate_sources(result)
    return result


def validate_sources(comparison):
    if type(comparison) is not Comparison:
        raise SaveError('A frozen qualified comparison is required.')
    adapter = adapter_for(comparison.game_id)
    for document in (comparison.left, comparison.right):
        adapter.validate_document(document)
        if adapter.read_save(document.source) != document:
            raise SaveError('A compared save or its original metadata changed. Compare the copies again.')


def report(comparison):
    if type(comparison) is not Comparison:
        raise SaveError('A frozen qualified comparison is required.')
    expected = compare_documents(comparison.game_id, comparison.left, comparison.right)
    if comparison != expected:
        raise SaveError('The comparison does not match its immutable native snapshots.')
    game = get_game(comparison.game_id)
    return {'schema_version': 1, 'game_id': game.id, 'title': game.title,
            'platform': game.platform, 'read_only': True,
            'first_sha256': comparison.left.sha256, 'second_sha256': comparison.right.sha256,
            'first_payload_sha256': hashlib.sha256(comparison.left.payload).hexdigest(),
            'second_payload_sha256': hashlib.sha256(comparison.right.payload).hexdigest(),
            'unchanged_fields': comparison.unchanged_fields, 'different_fields': len(comparison.rows),
            'changed_payload_bytes': comparison.changed_payload_bytes,
            'bytes_outside_editable_spans': comparison.outside_field_bytes,
            'notes': ['Fields align by the selected profile’s field IDs. Conditional record availability and changed definitions are shown separately.',
                      'Counts outside editable storage spans include native integrity, padding or unmapped game state. Changes within a packed field’s storage byte are counted within that span; they do not qualify additional bits or writes.',
                      'This report contains scalar values, including any editable names. Keep it private if those values are personal.'],
            'differences': [{name: getattr(row, name) for name in
                ('id', 'group', 'label', 'record', 'left_label', 'right_label', 'left', 'right', 'status')}
                for row in comparison.rows]}


def export(comparison, destination):
    destination = safe_path(destination)
    if destination.suffix.lower() != '.json':
        raise SaveError('Choose a new .json comparison report.')
    if destination.exists():
        raise FileExistsError('Choose a new report; existing files are never replaced.')
    result = report(comparison)
    raw = (json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    validate_sources(comparison)
    atomic_new(raw, destination)
    try:
        validate_sources(comparison)
        with destination.open('rb') as stream:
            if stream.read(len(raw) + 1) != raw:
                raise SaveError('The comparison report changed during actual read-back.')
    except Exception:
        # Remove only our verified output, never a file changed by another actor.
        try:
            with destination.open('rb') as stream:
                unchanged = stream.read(len(raw) + 1) == raw
            if unchanged: destination.unlink()
        except OSError:
            pass
        raise
    return destination
