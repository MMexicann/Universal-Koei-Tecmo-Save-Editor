"""Reviewed fixed-resource assignments reusable across qualified save copies.

The native codec, complete-map validation and typed read-back come from the
existing bound adapter/edit preset pipeline. JSON never supplies executable
instructions, patch offsets or a way to acknowledge experimental editing.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import edit_presets as source_presets
from koei_editor.shared import preset_portability
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.experimental_limits import above_supported
from koei_editor.shared.save_safety import safe_path


SCHEMA = 'koei-compatible-resource-preset'
SCHEMA_VERSION = 1
SUFFIX = '.compatible.edits.json'
MAX_BYTES = source_presets.MAX_BYTES
MAX_EDITS = 512
MAX_TARGETS = 32


@dataclass(frozen=True)
class CompatibleEdit:
    field: str
    value: int | str
    definition_sha256: str


@dataclass(frozen=True)
class CompatiblePreset:
    name: str
    game_id: str
    revision: str
    policy_sha256: str
    experimental: bool
    edits: tuple[CompatibleEdit, ...]


@dataclass(frozen=True)
class CompatiblePlan:
    preset: CompatiblePreset
    adapter: object
    document: object
    selected: tuple[str, ...]
    pending: tuple
    result: tuple
    rows: tuple
    experimental_count: int
    serialized_sha256: str


@dataclass(frozen=True)
class BatchTarget:
    label: str
    editor: object
    plan: CompatiblePlan


@dataclass(frozen=True)
class CompatibleBatch:
    targets: tuple[BatchTarget, ...]


def validate(preset):
    if type(preset) is not CompatiblePreset:
        raise SaveError('Choose a reusable resource editing preset.')
    source_presets._text(preset.name, 'name', 160)
    source_presets._text(preset.game_id, 'game/platform', 120)
    if not source_presets.re.fullmatch(r'[a-z0-9_]+', preset.game_id):
        raise SaveError('Preset game/platform identity is invalid.')
    source_presets._text(preset.revision, 'native revision', 120)
    source_presets._hash(preset.policy_sha256, 'portability policy')
    if type(preset.experimental) is not bool:
        raise SaveError('Preset experimental status must be an explicit boolean.')
    if type(preset.edits) is not tuple or not 0 < len(preset.edits) <= MAX_EDITS:
        raise SaveError(f'A reusable preset must contain 1–{MAX_EDITS} assignments.')
    seen = set()
    for edit in preset.edits:
        if type(edit) is not CompatibleEdit:
            raise SaveError('Reusable preset assignments have an invalid structure.')
        source_presets._text(edit.field, 'field identity', 240)
        source_presets._scalar(edit.value)
        source_presets._hash(edit.definition_sha256, 'native field definition')
        if edit.field in seen:
            raise SaveError('A preset assigns the same field more than once.')
        seen.add(edit.field)
    return preset


def dumps(preset):
    validate(preset)
    data = {'schema': SCHEMA, 'version': SCHEMA_VERSION, 'name': preset.name,
            'game_id': preset.game_id, 'revision': preset.revision,
            'policy_sha256': preset.policy_sha256, 'experimental': preset.experimental,
            'edits': [{'field': edit.field, 'value': edit.value,
                       'definition_sha256': edit.definition_sha256} for edit in preset.edits]}
    raw = (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    if len(raw) > MAX_BYTES:
        raise SaveError('The reusable preset exceeds its supported file size.')
    return raw


def loads(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise SaveError('Choose a nonempty reusable preset no larger than 4 MiB.')
    try:
        def invalid_constant(_value):
            raise ValueError('Nonfinite JSON number')
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=source_presets._unique_object,
                          parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise SaveError('The reusable preset is not valid UTF-8 JSON.') from error
    source_presets._keys(data, ('schema', 'version', 'name', 'game_id', 'revision',
                               'policy_sha256', 'experimental', 'edits'), 'document')
    if data['schema'] != SCHEMA or type(data['version']) is not int or data['version'] != SCHEMA_VERSION:
        raise SaveError('This is not a supported reusable resource preset. '
                        'Source-bound .edits.json files use the original Edit Presets dialog.')
    if type(data['edits']) is not list or not 0 < len(data['edits']) <= MAX_EDITS:
        raise SaveError('The reusable preset has an invalid assignment count.')
    edits = []
    for entry in data['edits']:
        source_presets._keys(entry, ('field', 'value', 'definition_sha256'), 'assignment')
        edits.append(CompatibleEdit(entry['field'], entry['value'], entry['definition_sha256']))
    return validate(CompatiblePreset(data['name'], data['game_id'], data['revision'],
                                    data['policy_sha256'], data['experimental'], tuple(edits)))


def read_bytes(path):
    """Bounded ordinary-file read, with per-API change tokens on Windows."""
    path = safe_path(path)
    before = path.lstat()
    def ordinary(info):
        return (stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and not getattr(info, 'st_file_attributes', 0)
                & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
    def token(info):
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns
    if not ordinary(before) or not 0 < before.st_size <= MAX_BYTES:
        raise SaveError('Choose a bounded ordinary reusable preset file.')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if not ordinary(opened) or token(opened)[:-1] != token(before)[:-1]:
            raise SaveError('The reusable preset changed before reading.')
        chunks, remaining = [], MAX_BYTES + 1
        while remaining:
            block = os.read(descriptor, min(65536, remaining))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        if token(os.fstat(descriptor)) != token(opened) or token(path.lstat()) != token(before):
            raise SaveError('The reusable preset changed while reading.')
        raw = b''.join(chunks)
        if len(raw) != opened.st_size or len(raw) > MAX_BYTES:
            raise SaveError('The reusable preset changed size while reading.')
        return raw
    finally:
        os.close(descriptor)


def load(path):
    if not Path(path).name.casefold().endswith(SUFFIX):
        raise SaveError('Choose a .compatible.edits.json file, not a game save or source-bound preset.')
    return loads(read_bytes(path))


def destination_path(path):
    path = Path(path)
    if not path.name.casefold().endswith(SUFFIX):
        name = path.name[:-5] if path.name.casefold().endswith('.json') else path.name
        path = path.with_name(name + SUFFIX)
    return safe_path(path)


def export(preset, path):
    raw = dumps(preset)
    result = atomic_new(raw, destination_path(path))
    try:
        if read_bytes(result) != raw:
            raise SaveError('The exported reusable preset changed after creation.')
    except Exception as error:
        raise SaveError('Preset verification failed after creation. The file was retained; '
                        'do not use it. Choose a new destination.\n\n' + str(error)) from error
    return result


def _selection(preset, selected):
    keys = tuple(edit.field for edit in preset.edits)
    if selected is None:
        return tuple(sorted(keys))
    if (type(selected) not in (tuple, list, set, frozenset) or not selected
            or any(type(key) is not str or key not in keys for key in selected)
            or len(selected) != len(set(selected))):
        raise SaveError('Select at least one distinct assignment from this preset.')
    return tuple(sorted(selected))


def create(adapter, document, changes, name, selected=None):
    """Freeze selected eligible staged assignments; never silently drop fields."""
    source_presets.validate_source(adapter, document)
    current, _raw = source_presets._pending(adapter, document, source_presets._snapshot(changes))
    chosen = tuple(sorted(current)) if selected is None else selected
    if (type(chosen) not in (tuple, list, set, frozenset) or not chosen
            or any(type(key) is not str or key not in current for key in chosen)
            or len(chosen) != len(set(chosen))):
        raise SaveError('Choose distinct currently staged fields to create the reusable preset.')
    policy = preset_portability.policy(adapter, document)
    preset_portability.require_fields(policy, chosen)
    mapping = adapter.field_map(document)
    edits = tuple(CompatibleEdit(key, current[key],
                                source_presets.field_definitions_sha256(adapter, document, (key,)))
                  for key in sorted(chosen))
    preset = CompatiblePreset(name, adapter.game_id, policy.revision, preset_portability.identity(policy),
                              any(above_supported(mapping[key], current[key]) for key in chosen), edits)
    dumps(preset)
    source_presets.validate_source(adapter, document)
    return preset


def prepare(adapter, document, changes, preset, selected=None):
    """Review complete pending state and native serialized/read-back candidate."""
    validate(preset)
    source_presets.validate_source(adapter, document)
    if preset.game_id != adapter.game_id:
        raise SaveError('This preset belongs to a different game/platform profile.')
    policy = preset_portability.policy(adapter, document)
    if preset.revision != policy.revision:
        raise SaveError('This reusable preset requires the exact native save revision.')
    if preset.policy_sha256 != preset_portability.identity(policy):
        raise SaveError('The reviewed portability policy changed. Create and review a new preset.')
    chosen = _selection(preset, selected)
    preset_portability.require_fields(policy, chosen)
    edits = {edit.field: edit for edit in preset.edits}
    mapping = adapter.field_map(document)
    for key in chosen:
        if key not in mapping:
            raise SaveError('A selected preset resource is unavailable in this target save.')
        if edits[key].definition_sha256 != source_presets.field_definitions_sha256(adapter, document, (key,)):
            raise SaveError('A selected native field definition changed. Review a new preset with this editor.')
        if type(edits[key].value) is not type(mapping[key].value(document.payload)):
            raise SaveError('A selected preset value has a different native scalar type.')
    current, _raw = source_presets._pending(adapter, document, source_presets._snapshot(changes))
    candidate = dict(current)
    candidate.update((key, edits[key].value) for key in chosen)
    result, raw = source_presets._pending(adapter, document, candidate)
    count = sum(above_supported(mapping[key], value) for key, value in result.items())
    if (not preset.experimental and any(above_supported(mapping[key], result[key])
                                        for key in chosen if key in result)):
        raise SaveError('The reusable preset understates its experimental edits.')
    rows = tuple(source_presets.PresetRow(mapping[key], mapping[key].value(document.payload),
                                         current.get(key, mapping[key].value(document.payload)),
                                         result.get(key, mapping[key].value(document.payload)), key in chosen)
                 for key in sorted(set(current) | set(result) | set(chosen)))
    plan = CompatiblePlan(preset, adapter, document, chosen, tuple(sorted(current.items())),
                          tuple(sorted(result.items())), rows, count, hashlib.sha256(raw).hexdigest())
    source_presets.validate_source(adapter, document)
    return plan


def confirm(plan, adapter, document, changes):
    if type(plan) is not CompatiblePlan or plan.adapter is not adapter or plan.document is not document:
        raise SaveError('The target session changed. Preview the selected assignments again.')
    current, _raw = source_presets._pending(adapter, document, source_presets._snapshot(changes))
    if tuple(sorted(current.items())) != plan.pending:
        raise SaveError('Pending edits changed after preview. Review the complete result again.')
    expected = prepare(adapter, document, current, plan.preset, plan.selected)
    if expected != plan:
        raise SaveError('The reusable preset preview changed. Prepare it again.')
    return dict(expected.result)


def apply_plan(plan, editor):
    """Stage the validated complete map once; restore state on refresh/source failure."""
    result = confirm(plan, editor.adapter, editor.document, dict(editor.changes))
    original = dict(editor.changes)
    history = [dict(snapshot) for snapshot in editor.history]
    try:
        editor._accept_pending(result)
        source_presets.validate_source(plan.adapter, plan.document)
    except Exception:
        editor.changes = original
        editor.history[:] = history
        try:
            editor.refresh()
        except Exception:
            pass
        raise
    return result


def prepare_batch(preset, targets, selected=None):
    """Preflight every explicitly selected open copy; never silently skip one."""
    if type(targets) not in (tuple, list) or not 0 < len(targets) <= MAX_TARGETS:
        raise SaveError(f'Choose between 1 and {MAX_TARGETS} target editors.')
    prepared, editors, sources = [], set(), set()
    for label, editor in targets:
        try:
            source = safe_path(editor.document.source)
            if id(editor) in editors or source in sources:
                raise SaveError('Choose each opened save copy only once.')
            plan = prepare(editor.adapter, editor.document, dict(editor.changes), preset, selected)
        except Exception as error:
            raise SaveError(f'{label}: {error}') from error
        editors.add(id(editor))
        sources.add(source)
        prepared.append(BatchTarget(str(label), editor, plan))
    return CompatibleBatch(tuple(prepared))


def apply_batch(batch):
    """All-or-nothing in-memory staging, with one normal Undo per target."""
    if (type(batch) is not CompatibleBatch or not 0 < len(batch.targets) <= MAX_TARGETS
            or any(type(target) is not BatchTarget for target in batch.targets)
            or len({id(target.editor) for target in batch.targets}) != len(batch.targets)):
        raise SaveError('Preview the selected target editors again.')
    states = []
    # Revalidate every preview before the first target changes.
    for target in batch.targets:
        editor = target.editor
        try:
            result = confirm(target.plan, editor.adapter, editor.document, dict(editor.changes))
        except Exception as error:
            raise SaveError(f'{target.label}: {error}') from error
        states.append((target, result, dict(editor.changes),
                       [dict(snapshot) for snapshot in editor.history]))
    try:
        for target, result, _previous, _history in states:
            target.editor._accept_pending(result)
        # A callback failure or source change in any target restores all others.
        for target, result, _previous, _history in states:
            editor = target.editor
            if (editor.adapter is not target.plan.adapter or editor.document is not target.plan.document
                    or editor.changes != result):
                raise SaveError('A target session changed while staging the batch.')
            source_presets.validate_source(editor.adapter, editor.document)
    except Exception:
        for target, _result, previous, history in states:
            target.editor.changes = previous
            target.editor.history[:] = history
        for target, _result, _previous, _history in states:
            try:
                target.editor.refresh()
            except Exception:
                pass
        raise
    return tuple(result for _target, result, _previous, _history in states)
