"""Repeatable shell/search measurements; never opens a player save.

Run as ``python -m tools.benchmark_application --gui`` after an editable install.
Use --python to compare a separate interpreter installed from another checkout.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc


QUERIES = ('', 'd', 'dw', 'dw7', 'dw7 pc', 'sóphie 2', 'horse', 'ps3',
           'meruru vita', 'hyrule', 'coin', 'does not exist')


def _milliseconds(action):
    start = time.perf_counter()
    action()
    return (time.perf_counter() - start) * 1000


def _widgets(widget):
    return 1 + sum(_widgets(child) for child in widget.winfo_children())


def _worker(iterations, gui, memory):
    start = time.perf_counter()
    import koei_editor.application as application
    from koei_editor.shared import library_catalog
    imported_ms = (time.perf_counter() - start) * 1000
    source = Path(application.__file__).resolve().parents[2]
    revision = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                              text=True, capture_output=True, check=True).stdout.strip()
    digest = hashlib.sha256()
    for path in sorted((source / 'src' / 'koei_editor').rglob('*')):
        if path.suffix in ('.py', '.json') and path.is_file():
            digest.update(path.relative_to(source).as_posix().encode('utf-8'))
            digest.update(b'\0')
            digest.update(path.read_bytes())
    # This interpreter's installed application is the subject, even when the
    # benchmark harness is launched from a different checkout.
    result = {'source': str(source), 'revision': revision, 'source_sha256': digest.hexdigest(),
              'python': platform.python_version(), 'platform': platform.platform(),
              'game_count': len(application.GAMES), 'gui': gui, 'memory_run': memory}
    metrics = {}
    if memory:
        tracemalloc.start()
    else:
        metrics['application_import_ms'] = imported_ms
    start = time.perf_counter()
    index_type = getattr(library_catalog, 'LibraryCatalog', None)
    index = index_type(application.GAMES) if index_type else None
    search = index.matching_games if index else lambda query: library_catalog.matching_games(application.GAMES, query)
    if not memory:
        metrics['catalog_build_ms'] = (time.perf_counter() - start) * 1000
    result['search_engine'] = 'indexed' if index else 'iterable'
    expected = [tuple(game.id for game in search(query)) for query in QUERIES]
    start = time.perf_counter()
    for _ in range(iterations):
        for query, ids in zip(QUERIES, expected):
            if tuple(game.id for game in search(query)) != ids:
                raise RuntimeError('Search result changed during a benchmark.')
    if not memory:
        metrics['search_mean_ms'] = (time.perf_counter() - start) * 1000 / (iterations * len(QUERIES))
    result['query_results'] = expected
    if memory:
        retained, peak = tracemalloc.get_traced_memory()
        metrics['catalog_search_python_retained_bytes'] = retained
        metrics['catalog_search_python_peak_bytes'] = peak
        tracemalloc.stop()
    if gui:
        import tkinter as tk
        if memory:
            tracemalloc.start()
        with tempfile.TemporaryDirectory(prefix='koei-shell-benchmark-') as directory:
            start = time.perf_counter()
            root = tk.Tk()
            try:
                app = application.Application(root, preferences_path=Path(directory) / 'prefs.json',
                                              persist_preferences=False)
                root.update_idletasks()
                startup_ms = (time.perf_counter() - start) * 1000
                if memory:
                    metrics['shell_startup_python_peak_bytes'] = tracemalloc.get_traced_memory()[1]
                    tracemalloc.stop()
                else:
                    metrics['shell_startup_ms'] = startup_ms
                    metrics['shell_startup_widgets'] = _widgets(root)
                    metrics['shell_startup_modules'] = len(sys.modules)

                    def navigate(scope):
                        app.platform_choice.set(scope)
                        app.show_platform()
                        root.update_idletasks()

                    metrics['all_platforms_first_navigation_ms'] = _milliseconds(
                        lambda: navigate(library_catalog.ALL_PLATFORMS))
                    metrics['all_platforms_widgets'] = _widgets(root)
                    metrics['library_warm_navigation_ms'] = _milliseconds(
                        lambda: [navigate(scope) for scope in
                                 ('Windows PC', library_catalog.ALL_PLATFORMS) * 3]) / 6
                    render_calls = []
                    original_show = app.show_platform

                    def counted_show(*args, **kwargs):
                        render_calls.append(1)
                        return original_show(*args, **kwargs)

                    app.show_platform = counted_show
                    for query in ('d', 'dw', 'dw7', 'dw7 ', 'dw7 p', 'dw7 pc'):
                        app.library_search.set(query)
                    # Let any queued debounce complete through the real event loop.
                    root.after(250, root.quit)
                    root.mainloop()
                    metrics['search_burst_renders'] = len(render_calls)
                    if tuple(game.id for game in app.library_matches) != ('dw7xl',):
                        raise RuntimeError('Debounced GUI search did not finish correctly.')
            finally:
                root.destroy()
                if tracemalloc.is_tracing():
                    tracemalloc.stop()
    result['metrics'] = metrics
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=5)
    parser.add_argument('--iterations', type=int, default=100)
    parser.add_argument('--gui', action='store_true', help='requires a desktop/display')
    parser.add_argument('--python', default=sys.executable, help='installed interpreter to measure')
    parser.add_argument('--output', type=Path, help='write JSON report (contains local source path)')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--memory', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.samples < 1 or args.iterations < 1:
        parser.error('samples and iterations must be positive')
    if args.worker:
        print(json.dumps(_worker(args.iterations, args.gui, args.memory)))
        return
    runs = []
    for memory in (False, True):
        for _ in range(args.samples):
            command = [args.python, '-m', 'tools.benchmark_application', '--worker',
                       '--iterations', str(args.iterations)]
            if args.gui:
                command.append('--gui')
            if memory:
                command.append('--memory')
            completed = subprocess.run(command, text=True, capture_output=True)
            if completed.returncode:
                parser.exit(completed.returncode, completed.stderr)
            runs.append(json.loads(completed.stdout))
    first = runs[0]
    for run in runs[1:]:
        for key in ('source', 'revision', 'source_sha256', 'game_count', 'query_results', 'search_engine'):
            if run[key] != first[key]:
                raise RuntimeError(f'Application changed between samples: {key}')
    summary = {}
    for key in sorted({key for run in runs for key in run['metrics']}):
        values = sorted(run['metrics'][key] for run in runs if key in run['metrics'])
        summary[key] = {'median': statistics.median(values), 'min': min(values),
                        'p95': values[math.ceil(.95 * len(values)) - 1]}
    report = {'metadata': {key: value for key, value in first.items()
                           if key not in ('metrics', 'memory_run')},
              'samples_per_mode': args.samples, 'iterations': args.iterations,
              'summary': summary, 'runs': runs}
    encoded = json.dumps(report, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding='utf-8')
    print(encoded, end='')


if __name__ == '__main__':
    main()
