"""Verify same-source Linux CI evidence and stage downloads without executing them."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tarfile
import tempfile

from tools import package_release as release
from tools.run_tests import verify_reports
from tools.smoke_linux import _archive_snapshot
from tools.linux_build_review import AES_NATIVE_FILES
from koei_editor.shared.copy_storage import publish_new_child_bound
from koei_editor.shared.save_safety import safe_path

ROOT = Path(__file__).resolve().parents[1]
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
REQUIRED_COMMANDS = frozenset({'version', 'games', 'routes', 'diagnostics',
                               'doctor-procedural-aes', 'doctor-procedural-aes-cbc', 'gui-smoke'})
HASH = re.compile(r'[0-9a-f]{64}\Z')


def _bindings(path):
    path = Path(os.path.abspath(path))
    bindings = []
    for parent in reversed((path, *path.parents)):
        info = parent.lstat()
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or getattr(info, 'st_file_attributes', 0) & 0x400):
            raise ValueError('Artifact and output folders must be ordinary directories without aliases.')
        bindings.append((parent, info))
    return bindings


@contextmanager
def _directory(bindings):
    if os.name == 'nt':
        from koei_editor.shared.anchored_read_windows import directory_chain
        with directory_chain(bindings) as directory:
            yield directory
        return
    if not hasattr(os, 'O_NOFOLLOW') or not hasattr(os, 'O_DIRECTORY') or os.open not in os.supports_dir_fd:
        raise ValueError('Safe no-follow artifact access is unavailable on this host.')
    descriptors = []
    try:
        for path, expected in bindings:
            options = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            descriptor = (os.open(path, options) if not descriptors else
                          os.open(path.name, options, dir_fd=descriptors[-1]))
            descriptors.append(descriptor)
            current = os.fstat(descriptor)
            if not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != (expected.st_dev, expected.st_ino):
                raise ValueError('An artifact directory changed identity.')
        yield descriptors[-1]
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _read_ordinary(path, limit):
    path = Path(os.path.abspath(path))
    with _directory(_bindings(path.parent)) as parent:
        descriptor = (parent.open_child(path.name) if os.name == 'nt' else
                      os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0), dir_fd=parent))
        with os.fdopen(descriptor, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                    or not 0 < before.st_size <= limit):
                raise ValueError('An artifact input is not a bounded ordinary file.')
            raw = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
            identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
            if len(raw) != before.st_size or identity(before) != identity(after):
                raise ValueError('An artifact input changed during verification.')
    return raw


def _json(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Duplicate evidence JSON fields.')
            value[key] = item
        return value
    def constant(_value):
        raise ValueError('Non-finite evidence JSON numbers.')
    try:
        result = json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=constant)
    except (UnicodeError, RecursionError) as error:
        raise ValueError('Invalid bounded evidence JSON.') from None
    if type(result) is not dict:
        raise ValueError('Evidence JSON must be an object.')
    return result


def _runtime(value):
    if type(value) is not dict or not 2 <= len(value) <= 20000:
        raise ValueError('The smoke runtime inventory is missing or unbounded.')
    for name, item in value.items():
        release._bundled_path(name)
        if (type(item) is not dict or set(item) != {'sha256', 'size_bytes', 'mode'}
                or type(item['sha256']) is not str or not HASH.fullmatch(item['sha256'])
                or type(item['size_bytes']) is not int or item['size_bytes'] < 0
                or type(item['mode']) is not int or item['mode'] not in (0o644, 0o755)):
            raise ValueError('A smoke runtime entry has invalid hash, size or permissions.')
    return value


def verify_publication(artifact_dir, output_dir, *, root=ROOT):
    """Validate captured CI bytes, then exclusively publish three release files.

    Output must be an existing ordinary directory. A late destination collision
    fails without replacing anything. Earlier successfully published files may
    remain after a later failure and must be inspected before retrying.
    """
    root = Path(root).resolve()
    version, sources = release.verified_sources(root)
    stem = release.artifact_name(root) + '-Linux-x86_64'
    artifact = Path(os.path.abspath(artifact_dir))
    archive_name, checksum_name = stem + '.tar.gz', stem + '.SHA256SUMS'
    report_name = 'LinuxVerification-v' + version + '.json'
    archive_raw = _read_ordinary(artifact / 'release' / archive_name, MAX_ARCHIVE_BYTES)
    checksum_raw = _read_ordinary(artifact / 'release' / checksum_name, 4096)
    suite_raw = _read_ordinary(artifact / 'test-results/linux.json', MAX_JSON_BYTES)
    smoke_raw = _read_ordinary(artifact / 'test-results/linux-smoke.json', MAX_JSON_BYTES)
    suite, smoke = _json(suite_raw), _json(smoke_raw)
    archive = {'file_name': archive_name, 'sha256': hashlib.sha256(archive_raw).hexdigest(),
               'size_bytes': len(archive_raw)}
    if checksum_raw != (archive['sha256'] + '  ' + archive_name + '\n').encode('ascii'):
        raise ValueError('The Linux archive checksum does not match its exact downloaded bytes.')
    if suite.get('platform') != 'linux' or not str(suite.get('python', '')).startswith('3.13.'):
        raise ValueError('Publication needs the native Linux CPython 3.13 full-suite evidence.')
    with tempfile.TemporaryDirectory(prefix='koei-linux-publication-') as temporary:
        private = Path(temporary).resolve()
        # The existing verifier reads an owned immutable copy, never a reopened
        # downloaded path whose parent/leaf could have been replaced.
        suite_copy = private / 'linux.json'
        suite_copy.write_bytes(suite_raw)
        verified = verify_reports([suite_copy], root / 'tests')
        expected_suite = {'sha256': hashlib.sha256(suite_raw).hexdigest(),
                          'source_fingerprint': verified['source_fingerprint'],
                          'module_count': len(verified['inventory']), 'counts': verified['counts'],
                          'platform': suite['platform'], 'python': suite['python']}
        manifest_digest = hashlib.sha256(sources[release.MANIFEST]).hexdigest()
        commands = smoke.get('commands')
        if (type(smoke.get('schema_version')) is not int or smoke['schema_version'] != 1
                or smoke.get('platform') != 'linux-x86_64' or smoke.get('clean') is not True
                or smoke.get('version') != version or smoke.get('fixture_scope') != 'procedural_only'
                or smoke.get('source_manifest_sha256') != manifest_digest
                or smoke.get('suite') != expected_suite or smoke.get('archive') != archive
                or type(commands) is not list or any(type(item) is not str for item in commands)
                or len(commands) != len(set(commands)) or not REQUIRED_COMMANDS <= set(commands)):
            raise ValueError('Linux smoke evidence is incomplete or belongs to different source/archive bytes.')
        runtime = _runtime(smoke.get('runtime'))
        if type(smoke.get('runtime_files')) is not int or smoke['runtime_files'] != len(runtime):
            raise ValueError('Linux smoke runtime count differs from its inventory.')
        required = {stem, 'cli/' + stem + '-CLI'}
        required.update(prefix + name for prefix in ('_internal/', 'cli/_internal/') for name in AES_NATIVE_FILES)
        if not required <= runtime.keys():
            raise ValueError('Linux GUI, CLI or native AES runtime is incomplete.')
        archive_copy = private / archive_name
        archive_copy.write_bytes(archive_raw)
        try:
            archived = _archive_snapshot(archive_copy, stem)
        except (tarfile.TarError, EOFError):
            raise ValueError('The Linux release archive is malformed.') from None
        if archived != runtime:
            raise ValueError('The Linux archive differs from the exact runtime that passed smoke.')
    # Confirm that the tested source and reviewed manifest stayed fixed while
    # the downloaded archive was read and checked.
    _after_version, after_sources = release.verified_sources(root)
    if hashlib.sha256(after_sources[release.MANIFEST]).hexdigest() != manifest_digest:
        raise ValueError('The reviewed public source manifest changed during publication verification.')
    from tools.run_tests import source_fingerprint
    if source_fingerprint(root / 'tests') != verified['source_fingerprint']:
        raise ValueError('The tested source changed during publication verification.')
    report = {'schema': 'koei-linux-publication-verification', 'schema_version': 1,
              'success': True, 'version': version, 'platform': 'linux-x86_64',
              'source_manifest_sha256': manifest_digest, 'suite': expected_suite,
              'smoke_sha256': hashlib.sha256(smoke_raw).hexdigest(),
              'archive': archive, 'commands': sorted(REQUIRED_COMMANDS),
              'fixture_scope': 'procedural_only', 'in_game_verified': False,
              'runtime_files': len(runtime), 'runtime': runtime}
    report_raw = (json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('ascii')
    release.scan_bundled_data(report_name, report_raw)
    checksum_output = (archive['sha256'] + '  ' + archive_name + '\n'
                       + hashlib.sha256(report_raw).hexdigest() + '  ' + report_name + '\n').encode('ascii')
    output = Path(os.path.abspath(output_dir))
    bindings = _bindings(output)
    if safe_path(output) != output:
        raise ValueError('Release outputs cannot use directory aliases.')
    outputs = ((archive_name, archive_raw), (report_name, report_raw), (checksum_name, checksum_output))
    for name, _raw in outputs:
        try:
            (output / name).lstat()
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError('All Linux publication output filenames must be new.')
    info = bindings[-1][1]
    for name, raw in outputs:
        publish_new_child_bound(raw, output, name, (info.st_dev, info.st_ino), cleanup_pending_on_failure=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    def directory(value):
        if not value.strip():
            raise argparse.ArgumentTypeError('An explicit nonempty directory is required.')
        return Path(value)
    parser.add_argument('--artifact-dir', required=True, type=directory)
    parser.add_argument('--output-dir', required=True, type=directory)
    arguments = parser.parse_args(argv)
    try:
        result = verify_publication(arguments.artifact_dir, arguments.output_dir)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, 'Linux publication verification failed (' + type(error).__name__ + '). No existing release file was replaced.\n')
    print('Verified Linux ' + result['version'] + ' downloads staged with source-bound evidence.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
