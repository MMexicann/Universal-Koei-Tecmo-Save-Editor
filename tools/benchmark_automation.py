"""Repeatable synthetic automation timings; run as a module from the checkout.

Fixture construction, per-sample setup and cleanup are outside timed regions.
There are no player-save inputs and every export uses existing guarded writers.
"""
from argparse import ArgumentParser, ArgumentTypeError
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import tempfile
from time import perf_counter_ns

from koei_editor.game_registry import get_game
from koei_editor.shared import batch_conversion


WORKLOADS = ('decode-small', 'validate-small', 'serialize-small',
             'decode-large', 'validate-large', 'serialize-large',
             'conversion-preflight', 'conversion-export',
             'automation-preflight', 'automation-apply')


def _bounded_count(value):
    try:
        result = int(value)
    except ValueError as error:
        raise ArgumentTypeError('Use a whole-number count.') from error
    if not 1 <= result <= 100:
        raise ArgumentTypeError('Use a count between 1 and 100.')
    return result


def _batch_count(value):
    result = _bounded_count(value)
    if result > 32:
        raise ArgumentTypeError('Use a batch size between 1 and 32.')
    return result


def _nonnegative_count(value):
    try:
        result = int(value)
    except ValueError as error:
        raise ArgumentTypeError('Use a whole-number warmup count.') from error
    if not 0 <= result <= 100:
        raise ArgumentTypeError('Use a warmup count between 0 and 100.')
    return result


@contextmanager
def _in_memory(operation):
    yield operation


@contextmanager
def _cold_decode(adapter, raw):
    # Wo Long memoizes qualification by immutable native bytes. Evict outside
    # the timer so this workload measures a fresh parse, not only a cache hit.
    # This is measurement setup; the actual operation remains the public bound
    # adapter and still performs every normal native integrity check.
    adapter.backend._qualify.cache_clear()
    yield lambda: adapter.decode(raw)


def _scalar_workloads(large):
    if large:
        from tests.test_wolong_format import procedural_payload
        game, raw, key, target = 'wolong', procedural_payload(), 'sen', 123
    else:
        from tests.test_dw4hyper_format import procedural_raw
        game, raw, key, target = 'dw4hyper', procedural_raw(), 'officer_0_attack', 123
    adapter = get_game(game).get_scalar_adapter()
    document = adapter.decode(raw)
    pending = adapter.stage(document, {}, key, target)
    metadata = {'profile': game, 'fixture_bytes': len(raw), 'files': 1,
                'fixture_sha256': hashlib.sha256(raw).hexdigest(), 'staged_fields': len(pending)}
    suffix = 'large' if large else 'small'
    return {
        'decode-' + suffix: ({**metadata, 'cache_policy': 'cold native qualification' if large else 'normal'},
                             lambda: _cold_decode(adapter, raw) if large else
                             _in_memory(lambda: adapter.decode(raw))),
        'validate-' + suffix: ({**metadata, 'cache_policy': 'opened immutable snapshot'},
                               lambda: _in_memory(lambda: adapter.validate_document(document))),
        'serialize-' + suffix: ({**metadata, 'cache_policy': 'normal reviewed snapshot'},
                                lambda: _in_memory(lambda: adapter.serialize(document, pending))),
    }


def _conversion_workload(name, batch_size):
    from tests.test_conversion import fixture, write_copy
    source_raw, template_raw = fixture('dw6'), fixture('dw6_ps3', 1)
    metadata = {'route': 'dw6-to-dw6_ps3', 'files': batch_size,
                'fixture_bytes': len(source_raw) + len(template_raw),
                'bytes_per_operation': batch_size * (len(source_raw) + len(template_raw)),
                'source_fixture_sha256': hashlib.sha256(source_raw).hexdigest(),
                'template_fixture_sha256': hashlib.sha256(template_raw).hexdigest()}

    @contextmanager
    def factory():
        with tempfile.TemporaryDirectory(prefix='koei-benchmark-') as directory:
            root = Path(directory)
            source = write_copy(root / 'source', 'dw6')
            template = write_copy(root / 'template', 'dw6_ps3', 1)
            specs = tuple(batch_conversion.JobSpec('job-' + str(index),
                          'dw6-to-dw6_ps3', source, template, root / ('output-' + str(index)))
                          for index in range(batch_size))
            if name == 'conversion-preflight':
                yield lambda: batch_conversion.prepare_specs(specs)
            else:
                prepared = batch_conversion.prepare_specs(specs)

                def operation():
                    outcomes = batch_conversion.execute(prepared)
                    if not batch_conversion.outcome_report(prepared, outcomes)['success']:
                        raise RuntimeError('Conversion export did not complete.')
                yield operation
    return metadata, factory


def _automation_workload(name, batch_size):
    from koei_editor.shared import automation
    from tests.test_dw4hyper_format import procedural_raw
    raw = procedural_raw()
    workflow = automation.Workflow('Benchmark attack edit', 'dw4hyper',
                                   (automation.Operation('set', (('officer_0_attack', 123),)),))
    metadata = {'profile': 'dw4hyper', 'files': batch_size, 'fixture_bytes': len(raw),
                'bytes_per_operation': batch_size * len(raw),
                'fixture_sha256': hashlib.sha256(raw).hexdigest(), 'staged_fields_per_file': 1}

    @contextmanager
    def factory():
        with tempfile.TemporaryDirectory(prefix='koei-benchmark-') as directory:
            root = Path(directory)
            specs = []
            for index in range(batch_size):
                source = root / ('source-' + str(index) + '.dat')
                source.write_bytes(raw)  # Procedural fixtures only, never player saves.
                specs.append(automation.JobSpec('job-' + str(index), source,
                                               root / ('edited-' + str(index) + '.dat')))
            if name == 'automation-preflight':
                yield lambda: automation.prepare(workflow, tuple(specs))
            else:
                prepared = automation.prepare(workflow, tuple(specs))

                def operation():
                    report = automation.apply(prepared, prepared.review_token)
                    if not report['success']:
                        raise RuntimeError('Automation batch did not complete.')
                yield operation
    return metadata, factory


def _measure(name, metadata, factory, warmups, iterations):
    for _ in range(warmups):
        with factory() as operation:
            operation()
    samples = []
    for _ in range(iterations):
        with factory() as operation:
            start = perf_counter_ns()
            operation()
            elapsed = perf_counter_ns() - start
        samples.append(elapsed / 1_000_000_000)
    ordered = sorted(samples)
    median = statistics.median(samples)
    total_bytes = metadata.get('bytes_per_operation', metadata['fixture_bytes'])
    return {'name': name, 'workload': metadata, 'samples_seconds': samples,
            'median_seconds': median, 'mean_seconds': statistics.mean(samples),
            'min_seconds': min(samples), 'max_seconds': max(samples),
            'p95_seconds': ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)],
            'median_mib_per_second': total_bytes / (1024 * 1024) / median if median else None}


def main(argv=None):
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--iterations', type=_bounded_count, default=3)
    parser.add_argument('--warmups', type=_nonnegative_count, default=1)
    parser.add_argument('--batch-size', type=_batch_count, default=4)
    parser.add_argument('--workloads', nargs='+', choices=WORKLOADS, default=list(WORKLOADS))
    parser.add_argument('--output', type=Path, help='Create a new JSON report; existing files are protected.')
    args = parser.parse_args(argv)
    report = {'schema_version': 1, 'success': False,
              'fixture_kind': 'procedural; not player saves or in-game qualification',
              'application_version': version('universal-koei-tecmo-save-editor'),
              'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
              'machine': {'system': platform.system(), 'release': platform.release(),
                          'architecture': platform.machine(), 'processor': platform.processor(),
                          'logical_cpus': os.cpu_count(), 'python': platform.python_version(),
                          'implementation': platform.python_implementation()},
              'configuration': {'iterations': args.iterations, 'warmups': args.warmups,
                                'batch_size': args.batch_size},
              'timing': {'clock': 'perf_counter_ns', 'setup_and_cleanup_timed': False,
                         'thresholds_enforced': False, 'p95_method': 'nearest rank'},
              'results': []}
    scalar = {}
    active = 'setup'
    try:
        for name in dict.fromkeys(args.workloads):
            active = name
            if name.endswith('-small') or name.endswith('-large'):
                if name not in scalar:
                    scalar.update(_scalar_workloads(name.endswith('-large')))
                metadata, factory = scalar[name]
            elif name.startswith('automation-'):
                metadata, factory = _automation_workload(name, args.batch_size)
            else:
                metadata, factory = _conversion_workload(name, args.batch_size)
            report['results'].append(_measure(name, metadata, factory, args.warmups, args.iterations))
        report['success'] = True
    except Exception as error:
        # Exception text can contain private paths; reports expose only stage
        # and exception type. No machine hostname, user name or cwd is recorded.
        report['failure'] = {'workload': active, 'error_type': type(error).__name__}
    encoded = json.dumps(report, indent=2, allow_nan=False) + '\n'
    if args.output:
        try:
            with args.output.open('x', encoding='utf-8') as stream:
                stream.write(encoded)
        except OSError as error:
            report['success'] = False
            report['failure'] = {'workload': 'report-write', 'error_type': type(error).__name__}
            sys.stdout.write(json.dumps(report, indent=2, allow_nan=False) + '\n')
            return 1
    sys.stdout.write(encoded)
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
