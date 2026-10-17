"""Headless reviewed workflows: ``python -m koei_editor.automation_cli``.

All machine results go to stdout as JSON. Native exceptions and private paths
are deliberately excluded; stable error codes and operation IDs are scriptable.
"""
import argparse
import json
from pathlib import Path
import sys

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import automation, edit_presets
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.save_safety import safe_path


class ArgumentError(ValueError):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgumentError('Invalid automation arguments; use --help for command syntax.')


class OperationAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        operations = list(getattr(namespace, self.dest, None) or [])
        operations.append(('assert' if option_string == '--assert' else 'set', values))
        setattr(namespace, self.dest, operations)


def _parser():
    parser = Parser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    fields = commands.add_parser('fields', help='Inspect verified field IDs and supported bounds.')
    fields.add_argument('--game', required=True)
    fields.add_argument('source')
    build = commands.add_parser('build', help='Create a reusable workflow using ordered --set/--assert options.')
    build.add_argument('--game', required=True)
    build.add_argument('--name', required=True)
    build.add_argument('--set', dest='operations', action=OperationAction, metavar='FIELD=JSON')
    build.add_argument('--assert', dest='operations', action=OperationAction, metavar='FIELD=JSON')
    build.add_argument('--output', required=True)
    for name in ('preview', 'apply', 'recover'):
        command = commands.add_parser(name, help='Review or execute an explicit batch JSON plan.')
        command.add_argument('plan')
        if name == 'recover':
            command.add_argument('--journal', required=True)
        if name == 'apply':
            command.add_argument('--review-token')
            command.add_argument('--journal', help='New durable journal folder; required for execution.')
            command.add_argument('--dry-run', action='store_true')
    for name in ('preset-preview', 'preset-apply'):
        command = commands.add_parser(name, help='Review or execute an exact-source .edits.json preset.')
        command.add_argument('preset')
        command.add_argument('source')
        command.add_argument('destination')
        if name == 'preset-apply':
            command.add_argument('--review-token')
            command.add_argument('--journal')
            command.add_argument('--dry-run', action='store_true')
    return parser


def _build(arguments):
    # Require registered scalar identity before exporting instructions.
    get_game(arguments.game).get_scalar_adapter()
    operations = []
    for kind, assignment in arguments.operations or []:
        key, separator, raw = assignment.partition('=')
        if not separator:
            raise SaveError('Use FIELD=JSON for each workflow operation.')
        try:
            value = json.loads(raw)
        except (ValueError, RecursionError) as error:
            raise SaveError('Workflow values must be JSON integers or strings.') from error
        if kind == 'set' and operations and operations[-1].op == 'set':
            previous = operations.pop()
            operations.append(automation.Operation('set', previous.values + ((key, value),)))
        else:
            operations.append(automation.Operation(kind, ((key, value),)))
    workflow = automation.Workflow(arguments.name, arguments.game, tuple(operations))
    atomic_new(automation.dumps(workflow), arguments.output)
    return {'success': True, 'status': 'workflow_created', 'game_id': workflow.game_id,
            'operation_count': len(operations)}


def _fields(arguments):
    adapter = get_game(arguments.game).get_scalar_adapter()
    document = adapter.read_save(arguments.source)
    fields = []
    for field in adapter.fields_for(document):
        fields.append({'field': field.id, 'kind': getattr(field, 'kind', 'integer'),
                       'value': field.value(document.payload),
                       'minimum': field.minimum, 'maximum': field.maximum,
                       'maxable': getattr(field, 'maxable', True)})
    return {'success': True, 'status': 'inspected', 'game_id': adapter.game_id,
            'source_sha256': document.sha256, 'fields': fields}


def _run(arguments):
    if arguments.command == 'build':
        return _build(arguments)
    if arguments.command == 'fields':
        return _fields(arguments)
    if arguments.command.startswith('preset-'):
        preset = edit_presets.load(arguments.preset)
        batch = automation.prepare_preset(preset, (automation.JobSpec(
            'save', Path(arguments.source), Path(arguments.destination)),))
    else:
        workflow, specs = automation.load_batch(arguments.plan)
        batch = automation.prepare(workflow, specs, allow_existing=arguments.command == 'recover')
    if arguments.command == 'recover':
        from koei_editor.shared.automation_journal import RunJournal
        journal = RunJournal.open(arguments.journal, batch.review_token, automation.journal_jobs(batch))
        return automation.inspect_recovery(batch, journal)
    if arguments.command.endswith('preview') or getattr(arguments, 'dry_run', False):
        return automation.preview(batch)
    if arguments.review_token != batch.review_token:
        raise SaveError('Apply requires the exact review token from a fresh preview.')
    if not arguments.journal:
        raise SaveError('Apply requires a new durable --journal folder.')
    # Imported only for execution; read-only tooling has no filesystem side effects.
    from koei_editor.shared.automation_journal import JournalJob, RunJournal
    automation.validate(batch)
    journal_folder = safe_path(arguments.journal)
    for job in batch.jobs:
        for path in (job.spec.source, job.spec.destination):
            if journal_folder == path or journal_folder in path.parents or path in journal_folder.parents:
                raise SaveError('Keep the journal folder separate from all batch input and output files.')
    jobs = tuple(JournalJob(job.spec.id, job.adapter.game_id, job.document.sha256,
                            job.serialized_sha256, job.profile_sha256) for job in batch.jobs)
    journal = RunJournal.create(journal_folder, batch.review_token, jobs)
    return automation.apply(batch, arguments.review_token, journal=journal)


def main(argv=None):
    """Return 0 on success, 2 on rejected input, 3 on a stopped/ambiguous run."""
    try:
        arguments = _parser().parse_args(argv)
        result = _run(arguments)
        code = 0 if result['success'] else 3
    except Exception as error:
        error_code = ('invalid_arguments' if isinstance(error, ArgumentError) else
                      'destination_exists' if isinstance(error, FileExistsError) else
                      'validation_failed' if isinstance(error, (SaveError, ValueError, UnicodeError)) else
                      'io_failed' if isinstance(error, OSError) else 'operation_failed')
        # Shared parser/adapter messages may include private metadata or paths.
        result = {'success': False, 'status': 'rejected', 'error_code': error_code,
                  'message': str(error) if isinstance(error, ArgumentError) else
                  'Automation did not pass validation or execution checks. Review the plan and use new safe copy destinations.'}
        if isinstance(error, automation.AutomationError):
            result['error_code'] = error.code
            if error.job_id is not None:
                result['job_id'] = error.job_id
            if error.operation_index is not None:
                result['operation_index'] = error.operation_index
        code = 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, allow_nan=False))
    return code


if __name__ == '__main__':
    sys.exit(main())
