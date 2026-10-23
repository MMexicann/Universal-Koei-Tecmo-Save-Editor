"""Qualify the extracted native Linux GUI and headless CLI without player files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import tarfile
import tempfile
import time

from tools.build_linux import ROOT, artifact_name
from tools import package_release as release

OUTPUT_BOUND = 524288
MAX_RUNTIME_FILE = 512 * 1024 * 1024
MAX_RUNTIME_TOTAL = 2 * 1024 * 1024 * 1024


def _file_digest(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(data)
    return digest.hexdigest()


def _snapshot(folder):
    files = {}
    for path in folder.rglob('*'):
        if path.is_symlink():
            raise ValueError('Extracted Linux runtime must contain ordinary files.')
        if path.is_file():
            files[path.relative_to(folder).as_posix()] = {
                'sha256': _file_digest(path), 'size_bytes': path.stat().st_size,
                'mode': stat.S_IMODE(path.stat().st_mode)}
        elif not path.is_dir():
            raise ValueError('Extracted Linux runtime contains a special file.')
    return files


def _archive_snapshot(archive_path, top):
    """Compare the exact packaged ordinary files with the extracted smoke input."""
    files, total = {}, 0
    launchers = {top, 'cli/' + top + '-CLI'}
    with tarfile.open(archive_path, 'r:gz') as archive:
        for member in archive:
            if (not member.name.startswith(top + '/') or not member.isfile()
                    or len(files) >= 20000 or not 0 <= member.size <= MAX_RUNTIME_FILE
                    or member.uid or member.gid or member.uname or member.gname or member.mtime):
                raise ValueError('Linux archive contains an unqualified member.')
            relative = member.name.removeprefix(top + '/')
            release._bundled_path(relative)
            expected_mode = 0o755 if relative in launchers else 0o644
            if relative in files or member.mode != expected_mode:
                raise ValueError('Linux archive contains duplicate names or unexpected permissions.')
            total += member.size
            if total > MAX_RUNTIME_TOTAL:
                raise ValueError('Linux archive exceeds its qualification size bound.')
            digest, size = hashlib.sha256(), 0
            with archive.extractfile(member) as stream:
                for data in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(data)
                    size += len(data)
                    if size > member.size:
                        raise ValueError('Linux archive entry exceeds its declared size.')
            if size != member.size:
                raise ValueError('Linux archive entry is truncated.')
            files[relative] = {'sha256': digest.hexdigest(), 'size_bytes': size, 'mode': member.mode}
    return files


def _suite_evidence(root):
    """Use the existing complete-inventory verifier, including source freshness."""
    from tools.run_tests import verify_reports
    path = root / 'test-results/linux.json'
    raw = path.read_bytes()
    reviewed = verify_reports([path], root / 'tests')
    if path.read_bytes() != raw:
        raise ValueError('The native Linux suite evidence changed during verification.')
    report = json.loads(raw)
    if report.get('platform') != 'linux' or not str(report.get('python', '')).startswith('3.13.'):
        raise ValueError('Linux qualification requires the native CPython 3.13 full-suite report.')
    return {'sha256': hashlib.sha256(raw).hexdigest(),
            'source_fingerprint': reviewed['source_fingerprint'],
            'module_count': len(reviewed['inventory']), 'counts': reviewed['counts'],
            'platform': report['platform'], 'python': report['python']}


def _bounded(command, cwd, env, *, timeout=120):
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                if (time.monotonic() > deadline or os.fstat(stdout.fileno()).st_size > OUTPUT_BOUND
                        or os.fstat(stderr.fileno()).st_size > OUTPUT_BOUND):
                    raise RuntimeError('Native Linux command exceeded its qualification bound.')
                time.sleep(0.05)
            stdout.seek(0)
            stderr.seek(0)
            output, errors = stdout.read(OUTPUT_BOUND + 1), stderr.read(OUTPUT_BOUND + 1)
            if process.returncode or errors or len(output) > OUTPUT_BOUND:
                raise RuntimeError('Native Linux command failed or produced unexpected stderr.')
            return output.decode('utf-8')
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)


def _doctor_probe(cli, cwd, headless, game_id, raw, filename):
    fixture = cwd / filename
    fixture.write_bytes(raw)
    entries_before = set(cwd.iterdir())
    result = json.loads(_bounded([str(cli), 'doctor', '--game', game_id, str(fixture)], cwd, headless))
    if (result.get('success') is not True or result.get('read_only') is not True
            or result.get('sha256') != hashlib.sha256(raw).hexdigest()
            or fixture.read_bytes() != raw or set(cwd.iterdir()) != entries_before):
        raise ValueError('Frozen Linux crypto inspection or source preservation failed.')


def smoke(extracted, root=ROOT):
    root, extracted = Path(root).resolve(), Path(extracted).resolve()
    version, sources = release.verified_sources(root)
    suite = _suite_evidence(root)
    name = artifact_name(root)
    folder = extracted / name
    gui, cli = folder / name, folder / 'cli' / artifact_name(root, cli=True)
    before = _snapshot(folder)
    if not before or not gui.is_file() or not cli.is_file():
        raise ValueError('Expected extracted Linux GUI and CLI executables are missing.')
    archive_path = root / 'release' / (name + '.tar.gz')
    if archive_path.is_symlink() or not archive_path.is_file():
        raise ValueError('The exact ordinary Linux release archive is missing.')
    archive = {'file_name': archive_path.name, 'sha256': _file_digest(archive_path),
               'size_bytes': archive_path.stat().st_size}
    if _archive_snapshot(archive_path, name) != before:
        raise ValueError('Extracted Linux smoke input differs from the packaged archive.')
    env = os.environ.copy()
    for key in ('PYTHONPATH', 'PYTHONHOME', 'TCL_LIBRARY', 'TK_LIBRARY'):
        env.pop(key, None)
    headless = env.copy()
    headless.pop('DISPLAY', None)
    from koei_editor.game_registry import ALL_ADAPTERS
    from koei_editor.conversion import ROUTES
    from tests.test_elixirs_v11 import synthetic_reset_save
    from tests.test_wo4_pc import generated_raw as wo4_cbc_raw
    report = {'schema_version': 1, 'platform': 'linux-x86_64', 'clean': False,
              'version': version, 'fixture_scope': 'procedural_only', 'commands': [],
              'source_manifest_sha256': hashlib.sha256(sources[release.MANIFEST]).hexdigest(),
              'suite': suite, 'archive': archive}
    with tempfile.TemporaryDirectory(prefix='koei-linux-smoke-') as temporary:
        cwd = Path(temporary).resolve()
        version = _bounded([str(cli), '--version'], cwd, headless)
        if version.strip() != 'Universal Koei Tecmo Game Toolkit ' + report['version']:
            raise ValueError('Frozen Linux CLI version does not match reviewed source.')
        report['commands'].append('version')
        for command, key, expected in (
                ('games', 'games', {game.id for game in ALL_ADAPTERS}),
                ('routes', 'routes', {route.id for route in ROUTES})):
            value = json.loads(_bounded([str(cli), command, '--json'], cwd, headless))
            rows = value[key]
            if (value.get('schema') != 'koei-toolkit-' + command
                    or value.get('read_only') is not True or value.get('in_game_verified') is not False
                    or len(rows) != len(expected) or {row['id'] for row in rows} != expected):
                raise ValueError('Frozen Linux catalog differs from reviewed source.')
            report['commands'].append(command)
        diagnostic = json.loads(_bounded([str(cli), 'diagnostics', '--json'], cwd, headless))
        if (diagnostic['application']['mode'] != 'frozen'
                or diagnostic['application']['version'] != report['version']
                or diagnostic['runtime']['os_family'] != 'Linux'
                or not diagnostic['runtime']['python'].startswith('3.13.')):
            raise ValueError('Frozen Linux diagnostics report has incorrect runtime facts.')
        report['commands'].append('diagnostics')
        _doctor_probe(cli, cwd, headless, 'dw3', synthetic_reset_save().encrypted, 'procedural.sav')
        report['commands'].append('doctor-procedural-aes')
        _doctor_probe(cli, cwd, headless, 'wo4_pc', wo4_cbc_raw(), 'procedural-cbc.bin')
        report['commands'].append('doctor-procedural-aes-cbc')
        command = [str(gui), '--smoke-test']
        if not env.get('DISPLAY'):
            xvfb = shutil.which('xvfb-run')
            if xvfb is None:
                raise RuntimeError('GUI smoke needs a display or xvfb-run.')
            command = [xvfb, '-a', *command]
        _bounded(command, cwd, env, timeout=180)
        report['commands'].append('gui-smoke')
    if _snapshot(folder) != before:
        raise ValueError('Native smoke changed its extracted runtime.')
    if _file_digest(archive_path) != archive['sha256'] or _suite_evidence(root) != suite:
        raise ValueError('Linux archive, tested source or full-suite evidence changed during smoke.')
    _version, after_sources = release.verified_sources(root)
    if hashlib.sha256(after_sources[release.MANIFEST]).hexdigest() != report['source_manifest_sha256']:
        raise ValueError('The reviewed source manifest changed during Linux smoke.')
    report['runtime_files'] = len(before)
    report['runtime'] = before
    report['clean'] = True
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('extracted', type=Path)
    arguments = parser.parse_args(argv)
    report = smoke(arguments.extracted)
    destination = ROOT / 'test-results/linux-smoke.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print('Extracted Linux GUI, headless catalogs, diagnostics and procedural AES inspection passed.')


if __name__ == '__main__':
    main()
