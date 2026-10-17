"""Declarative automation using the registered, validated scalar save path only.

Each set operation is one dependency-valid assignment group. Assertions observe
staged values. Preparation is read-only; execution is fail-stop, never rollback
or replay, and retains completed copies if a later job fails.
"""
from dataclasses import dataclass, fields as dataclass_fields, is_dataclass
import hashlib
import json
from pathlib import Path
import re

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import edit_presets
from koei_editor.shared.adapter_contract import BoundScalarAdapter, normalize_pending_values
from koei_editor.shared.save_safety import safe_path

SCHEMA = 'koei-automation-workflow'
VERSION = 1
MAX_BYTES = 4 * 1024 * 1024
MAX_OPERATIONS = 2000
MAX_ASSIGNMENTS = 20_000
MAX_JOBS = 32
MAX_BATCH_BYTES = 512 * 1024 * 1024
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z')


class AutomationError(SaveError):
    """Path-free failure context for declarative preflight."""
    def __init__(self, code, job_id=None, operation_index=None):
        super().__init__('Automation preflight failed: ' + code + '.')
        self.code = code
        self.job_id = job_id
        self.operation_index = operation_index


@dataclass(frozen=True)
class Operation:
    op: str
    values: tuple[tuple[str, int | str], ...]


@dataclass(frozen=True)
class Workflow:
    name: str
    game_id: str
    operations: tuple[Operation, ...]


@dataclass(frozen=True)
class JobSpec:
    id: str
    source: Path
    destination: Path


@dataclass(frozen=True)
class PreparedJob:
    spec: JobSpec
    adapter: BoundScalarAdapter
    document: object
    pending: tuple
    rows: tuple
    serialized_sha256: str
    profile_sha256: str
    context_sha256: str


@dataclass(frozen=True)
class PreparedBatch:
    workflow: Workflow
    jobs: tuple[PreparedJob, ...]
    review_token: str


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(',', ':'), allow_nan=False).encode('ascii')


def _native_context_digest(document):
    """Bind opaque original companions without codec state or local paths.

    Registered adapters expose original context through these frozen snapshot
    attributes. Owner dataclasses include complete original Steam/Xbox bytes;
    their source/directory paths deliberately do not distinguish copied bundles.
    Codec headers, seeds and dynamic field definitions are handled separately.
    """
    nodes = 0

    def identity(value, depth=0):
        nonlocal nodes
        nodes += 1
        if depth > 8 or nodes > 1000:
            raise SaveError('Original automation context exceeds its metadata bound.')
        if value is None or type(value) in (str, int, bool):
            return value
        if type(value) is bytes:
            return {'bytes': len(value), 'sha256': _digest(value)}
        if is_dataclass(value) and not isinstance(value, type):
            result = {'type': type(value).__module__ + '.' + type(value).__qualname__,
                      'fields': [[field.name, identity(getattr(value, field.name), depth + 1)]
                                 for field in dataclass_fields(value)
                                 if not isinstance(getattr(value, field.name), Path)]}
            # Steam's original basename is a property of its excluded source
            # path. Native writers require its exact spelling as well as bytes.
            if hasattr(value, 'basename'):
                result['basename'] = identity(value.basename, depth + 1)
            return result
        if type(value) is tuple:
            return [identity(item, depth + 1) for item in value]
        raise SaveError('This adapter does not expose immutable original automation context.')

    context = [[name, identity(getattr(document, name))]
               for name in ('context_sha256', 'context_digest', 'native_directory', 'owner', 'context')
               if hasattr(document, name)]
    return _digest(_canonical(context))


def _text(value, maximum=240):
    try:
        valid = (type(value) is str and bool(value.strip())
                 and len(value.encode('utf-8')) <= maximum
                 and not any(ord(char) < 32 or ord(char) == 127 for char in value))
    except UnicodeError:
        valid = False
    if not valid:
        raise SaveError('Workflow identifiers must be bounded plain text.')
    return value


def _scalar(value):
    if type(value) is int and -(1 << 63) <= value < (1 << 64):
        return value
    if type(value) is str:
        try:
            if len(value.encode('utf-8')) <= 4096:
                return value
        except UnicodeError:
            pass
    raise SaveError('Workflow values must be bounded exact whole numbers or text.')


def validate_workflow(workflow):
    if type(workflow) is not Workflow:
        raise SaveError('Choose a declarative scalar workflow.')
    _text(workflow.name, 160)
    _text(workflow.game_id, 120)
    if re.fullmatch(r'[a-z0-9_]+', workflow.game_id) is None:
        raise SaveError('Workflow requires an exact game/platform ID.')
    if (type(workflow.operations) is not tuple
            or not 1 <= len(workflow.operations) <= MAX_OPERATIONS):
        raise SaveError('Workflow operation count is outside the supported bound.')
    count = 0
    for operation in workflow.operations:
        if type(operation) is not Operation or operation.op not in ('set', 'assert'):
            raise SaveError('Only set and assert operations are supported.')
        if type(operation.values) is not tuple or not operation.values:
            raise SaveError('Each operation requires explicit field/value assignments.')
        if operation.op == 'assert' and len(operation.values) != 1:
            raise SaveError('An assertion requires exactly one field and value.')
        seen = set()
        for item in operation.values:
            if type(item) is not tuple or len(item) != 2:
                raise SaveError('Operation assignments require field/value pairs.')
            key, value = item
            _text(key)
            _scalar(value)
            if key in seen:
                raise SaveError('An operation assigns a field more than once.')
            seen.add(key)
            count += 1
        if count > MAX_ASSIGNMENTS:
            raise SaveError('Workflow assignment count exceeds the supported bound.')
    return workflow


def workflow_data(workflow):
    validate_workflow(workflow)
    return {'schema': SCHEMA, 'version': VERSION, 'name': workflow.name,
            'game_id': workflow.game_id,
            'operations': [({'op': 'set', 'values': dict(operation.values)}
                            if operation.op == 'set' else
                            {'op': 'assert', 'field': operation.values[0][0],
                             'value': operation.values[0][1]})
                           for operation in workflow.operations]}


def dumps(workflow):
    raw = (json.dumps(workflow_data(workflow), ensure_ascii=True, indent=2) + '\n').encode('ascii')
    if len(raw) > MAX_BYTES:
        raise SaveError('Workflow JSON exceeds the supported size.')
    return raw


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SaveError('Automation JSON contains duplicate property names.')
        result[key] = value
    return result


def _json(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise SaveError('Automation JSON must be nonempty and at most 4 MiB.')
    try:
        def invalid(_value):
            raise ValueError('nonfinite')
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_unique, parse_constant=invalid)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise SaveError('Automation input must be valid bounded UTF-8 JSON.') from error


def _keys(data, keys):
    if type(data) is not dict or set(data) != set(keys):
        raise SaveError('Automation JSON has missing or unknown properties.')


def from_data(data):
    _keys(data, ('schema', 'version', 'name', 'game_id', 'operations'))
    if data['schema'] != SCHEMA or type(data['version']) is not int or data['version'] != VERSION:
        raise SaveError('Unsupported automation workflow schema/version.')
    if type(data['operations']) is not list or not 1 <= len(data['operations']) <= MAX_OPERATIONS:
        raise SaveError('Workflow requires a bounded operations list.')
    operations = []
    for row in data['operations']:
        if type(row) is not dict:
            raise SaveError('Each workflow operation must be an object.')
        if row.get('op') == 'set':
            _keys(row, ('op', 'values'))
            if type(row['values']) is not dict:
                raise SaveError('A set operation requires a field/value object.')
            operations.append(Operation('set', tuple(row['values'].items())))
        elif row.get('op') == 'assert':
            _keys(row, ('op', 'field', 'value'))
            operations.append(Operation('assert', ((row['field'], row['value']),)))
        else:
            raise SaveError('Unknown workflow operation; only set/assert are supported.')
    return validate_workflow(Workflow(data['name'], data['game_id'], tuple(operations)))


def loads(raw):
    return from_data(_json(raw))


def load(path):
    with safe_path(path).open('rb') as stream:
        return loads(stream.read(MAX_BYTES + 1))


def load_batch(path):
    """Read {schema_version:1, workflow:{...}, jobs:[{id,source,destination}]}.

    Job paths are relative to the plan file, never to the process directory.
    """
    path = safe_path(path)
    with path.open('rb') as stream:
        data = _json(stream.read(MAX_BYTES + 1))
    _keys(data, ('schema_version', 'workflow', 'jobs'))
    if type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise SaveError('Unsupported automation batch schema version.')
    if type(data['jobs']) is not list or not 1 <= len(data['jobs']) <= MAX_JOBS:
        raise SaveError('Batch job count is outside the supported bound.')
    jobs = []
    for row in data['jobs']:
        _keys(row, ('id', 'source', 'destination'))
        for key in ('source', 'destination'):
            _text(row[key], 4096)
        jobs.append(JobSpec(row['id'], path.parent / row['source'], path.parent / row['destination']))
    return from_data(data['workflow']), tuple(jobs)


def _specs(specs, *, allow_existing=False):
    if type(specs) is not tuple or not 1 <= len(specs) <= MAX_JOBS:
        raise SaveError(f'Prepare between 1 and {MAX_JOBS} explicit save copies.')
    result, ids = [], set()
    for spec in specs:
        if (type(spec) is not JobSpec or type(spec.id) is not str
                or _ID.fullmatch(spec.id) is None or spec.id in ids):
            raise SaveError('Each batch job needs a unique plain 1–64 character ID.')
        source, destination = safe_path(spec.source), safe_path(spec.destination)
        if not source.is_file():
            raise SaveError('A batch source must be an existing separate save copy.')
        if destination.exists() and not allow_existing:
            raise FileExistsError('Every batch destination must be a new file.')
        ids.add(spec.id)
        result.append(JobSpec(spec.id, source, destination))
    outputs = [spec.destination for spec in result]
    for output in outputs:
        if outputs.count(output) != 1 or any(output in other.parents or other in output.parents
                                            for other in outputs if other != output):
            raise SaveError('Batch destinations must be distinct and cannot contain one another.')
        if any(output != other and output.exists() and other.exists()
               and output.samefile(other) for other in outputs):
            raise SaveError('Batch destinations cannot alias one another.')
        if any(output == spec.source or output in spec.source.parents
               or (output.exists() and output.samefile(spec.source)) for spec in result):
            raise SaveError('A batch destination cannot alias or contain an input save.')
    return tuple(result)


def _prepare_job(workflow, spec, adapter):
    try:
        document = adapter.read_save(spec.source)
        edit_presets.validate_source(adapter, document)
    except Exception as error:
        raise AutomationError('invalid_source', spec.id) from error
    fields = adapter.field_map(document)
    pending = {}
    for index, operation in enumerate(workflow.operations, 1):
        for key, value in operation.values:
            if key not in fields:
                raise AutomationError('unsupported_field', spec.id, index)
            if operation.op == 'assert':
                current = pending.get(key, fields[key].value(document.payload))
                if type(current) is not type(value) or current != value:
                    raise AutomationError('assertion_failed', spec.id, index)
        if operation.op == 'set':
            candidate = dict(pending)
            candidate.update(operation.values)
            try:
                pending = normalize_pending_values(document, candidate, fields)
            except Exception as error:
                raise AutomationError('invalid_value', spec.id, index) from error
            # One operation is a complete dependency-validated group. Do not
            # stage fields one at a time: valid loadout swaps need a final map.
            try:
                adapter.changed_payload(document, pending)
            except Exception as error:
                raise AutomationError('native_dependency_failed', spec.id, index) from error
    raw = adapter.serialize(document, pending)
    profile = edit_presets._profile_hash(adapter, document)
    rows = tuple((key, fields[key].value(document.payload), value)
                 for key, value in sorted(pending.items()))
    edit_presets.validate_source(adapter, document)
    return PreparedJob(spec, adapter, document, tuple(sorted(pending.items())), rows,
                       _digest(raw), profile, _native_context_digest(document))


def _token(workflow, jobs):
    return _digest(_canonical({'workflow': workflow_data(workflow), 'jobs': [
        {'id': job.spec.id, 'source': str(job.spec.source), 'destination': str(job.spec.destination),
         'source_sha256': job.document.sha256, 'profile_sha256': job.profile_sha256,
         'context_sha256': job.context_sha256,
         'output_sha256': job.serialized_sha256, 'pending': job.pending, 'rows': job.rows}
        for job in jobs]}))


def prepare(workflow, specs, *, adapter=None, allow_existing=False):
    """Prepare every job without backup creation or writes; exact game only."""
    validate_workflow(workflow)
    specs = _specs(specs, allow_existing=allow_existing)
    if adapter is None:
        adapter = get_game(workflow.game_id).get_scalar_adapter()
    if (type(adapter) is not BoundScalarAdapter or adapter.game_id != workflow.game_id
            or adapter.experimental):
        raise SaveError('Automation requires the exact registered scalar profile in supported mode.')
    jobs, total = [], 0
    for spec in specs:
        total += spec.source.stat().st_size
        if total > MAX_BATCH_BYTES:
            raise SaveError('Batch inputs exceed the 512 MiB preparation budget.')
        if spec.destination.suffix.lower() != adapter.extension:
            raise SaveError('Batch destination has the wrong game/profile extension.')
        jobs.append(_prepare_job(workflow, spec, adapter))
    jobs = tuple(jobs)
    batch = PreparedBatch(workflow, jobs, _token(workflow, jobs))
    validate(batch, allow_existing=allow_existing)
    return batch


def prepare_preset(preset, specs, *, adapter=None):
    """Import a source-bound .edits.json plan for byte-identical source copies."""
    edit_presets.validate_preset(preset)
    workflow = Workflow(preset.name, preset.game_id,
                        (Operation('set', tuple((edit.field, edit.value) for edit in preset.edits)),))
    batch = prepare(workflow, specs, adapter=adapter)
    for job in batch.jobs:
        edit_presets.prepare(job.adapter, job.document, {}, preset)
    return batch


def validate(batch, *, allow_existing=False):
    if (type(batch) is not PreparedBatch or type(batch.jobs) is not tuple
            or not batch.jobs or any(type(job) is not PreparedJob for job in batch.jobs)):
        raise SaveError('Prepare a complete automation batch before execution.')
    validate_workflow(batch.workflow)
    if _token(batch.workflow, batch.jobs) != batch.review_token:
        raise SaveError('The reviewed batch changed. Prepare a new preview.')
    _specs(tuple(job.spec for job in batch.jobs), allow_existing=allow_existing)
    for job in batch.jobs:
        if (type(job.adapter) is not BoundScalarAdapter
                or job.adapter.game_id != batch.workflow.game_id or job.adapter.experimental):
            raise SaveError('The reviewed adapter identity changed.')
        # Re-derive the review from declarative operations, rather than trusting
        # a caller-supplied frozen dataclass or its self-reported digest.
        fresh = _prepare_job(batch.workflow, job.spec, job.adapter)
        if fresh != job:
            raise SaveError('Native source, fields, operations, or review changed after preparation.')
    return batch


def preview(batch):
    """Path-free structured review suitable for CI logs and GUI renderers."""
    validate(batch)
    return {'success': True, 'status': 'prepared', 'review_token': batch.review_token,
            'game_id': batch.workflow.game_id, 'jobs': [
                {'id': job.spec.id, 'status': 'prepared', 'source_sha256': job.document.sha256,
                 'output_sha256': job.serialized_sha256, 'changed_fields': len(job.pending),
                 'changes': [{'field': key, 'before': before, 'after': after}
                             for key, before, after in job.rows]}
                for job in batch.jobs]}


def apply(batch, review_token, *, journal=None, cancelled=None):
    """Apply one reviewed batch, stop on first failure, retain all evidence.

    An intent without completion is ambiguous, including an exception after the
    native writer creates a copy. Never delete, overwrite, or auto-replay it.
    """
    if type(review_token) is not str or review_token != batch.review_token:
        raise SaveError('Apply requires the exact token from a fresh dry-run review.')
    validate(batch)  # All jobs pass freshness and native checks before any write.
    if journal is not None:
        journal.validate_binding(batch.review_token, journal_jobs(batch))
    outcomes, failed = [], False
    for job in batch.jobs:
        if failed:
            outcomes.append({'id': job.spec.id, 'status': 'not_started'})
            continue
        try:
            if cancelled is not None and cancelled():
                outcomes.append({'id': job.spec.id, 'status': 'cancelled'})
                failed = True
                continue
            # Recheck all unstarted sources before each write, without treating
            # already completed output destinations as new jobs.
            for candidate in batch.jobs[len(outcomes):]:
                edit_presets.validate_source(candidate.adapter, candidate.document)
                if safe_path(candidate.spec.destination) != candidate.spec.destination:
                    raise SaveError('Destination identity changed after review.')
                if candidate.spec.destination.exists():
                    raise FileExistsError('A reviewed destination is no longer new.')
            if journal is not None:
                journal.intent(job.spec.id)
            result = job.adapter.save_as(job.document, dict(job.pending), job.spec.destination)
            if (_digest(result.raw) != job.serialized_sha256
                    or _native_context_digest(result) != job.context_sha256):
                raise SaveError('Saved output differs from the reviewed native result.')
            edit_presets.validate_source(job.adapter, job.document)
            if journal is not None:
                journal.complete(job.spec.id)
            outcomes.append({'id': job.spec.id, 'status': 'completed',
                             'output_sha256': job.serialized_sha256})
        except Exception as error:
            # Native messages and OSError strings may disclose personal paths.
            # The type/classification is intentional; no traceback in receipts.
            code = ('destination_exists' if isinstance(error, FileExistsError) else
                    'validation_failed' if isinstance(error, SaveError) else
                    'io_failed' if isinstance(error, OSError) else 'operation_failed')
            outcomes.append({'id': job.spec.id, 'status': 'failed', 'error_code': code,
                             'requires_inspection': True})
            failed = True
    # A later writer or another process may alter an earlier completed output.
    # Requalify actual files before reporting the batch result, retaining every
    # output and journal event if final verification discovers a problem.
    for index, (job, outcome) in enumerate(zip(batch.jobs, outcomes)):
        if outcome['status'] != 'completed':
            continue
        try:
            edit_presets.validate_source(job.adapter, job.document)
            if safe_path(job.spec.destination) != job.spec.destination:
                raise SaveError('Completed destination identity changed.')
            actual = job.adapter.read_save(job.spec.destination)
            if (_digest(actual.raw) != job.serialized_sha256
                    or _native_context_digest(actual) != job.context_sha256):
                raise SaveError('Completed destination differs from the reviewed output.')
        except Exception:
            outcomes[index] = {'id': job.spec.id, 'status': 'verification_failed',
                               'error_code': 'completed_output_changed', 'requires_inspection': True}
            failed = True
    return {'success': not failed, 'status': 'stopped' if failed else 'completed',
            'review_token': batch.review_token, 'jobs': outcomes}


def journal_jobs(batch):
    from koei_editor.shared.automation_journal import JournalJob
    return tuple(JournalJob(job.spec.id, job.adapter.game_id, job.document.sha256,
                            job.serialized_sha256, job.profile_sha256) for job in batch.jobs)


def inspect_recovery(batch, journal):
    """Inspect the current explicit paths, never replay or remove anything."""
    validate(batch, allow_existing=True)
    journal.validate_binding(batch.review_token, journal_jobs(batch))
    jobs = {job.spec.id: job for job in batch.jobs}
    def verify(job_id):
        job = jobs[job_id]
        destination = job.spec.destination
        if safe_path(destination) != destination:
            return 'invalid'
        if not destination.exists():
            return 'absent'
        try:
            document = job.adapter.read_save(destination)
            # Native read_save binds the exact game/profile and integrity.
            # The reviewed digest covers every output byte. Do not compare
            # input/output field maps: valid edits can remove eligible fields.
            if (_digest(document.raw) == job.serialized_sha256
                    and _native_context_digest(document) == job.context_sha256):
                return 'verified'
        except Exception:
            pass
        return 'invalid'
    report = journal.inspect(verify)
    return {'success': report.safe_to_resume, 'status': 'recovery_inspected',
            'review_token': batch.review_token, **report.as_dict()}
