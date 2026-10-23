"""Bounded, path-free support diagnostics; no save, installation or network scans."""
from importlib import metadata
import json
import os
import platform
import re
import sys

from koei_editor.shared.report_export import write_report_bytes

SCHEMA = 'koei-toolkit-diagnostics'
MAX_REPORT_BYTES = 64 * 1024
DEPENDENCIES = ('miniaudio', 'trimesh', 'numpy', 'cffi', 'pycparser')
LIMITATIONS = (
    'Dependency metadata availability does not verify native decoders or their dependencies.',
    'Supported platforms still require destination-specific filesystem checks.',
    'This report does not establish edited-save or converted-save loading in a game.',
    'No save files, installation paths, account data, environment variables or logs are collected.',
)
_VERSION = re.compile(r'[0-9]{1,9}(?:\.[0-9]{1,9}){0,3}(?:(?:a|b|rc)[0-9]{1,9})?(?:\.post[0-9]{1,9})?(?:\.dev[0-9]{1,9})?\Z')
_RELEASE = re.compile(r'[0-9]{1,9}\.[0-9]{1,9}(?:\.[0-9]{1,9})?\Z')


def _dependency(name):
    try:
        version = metadata.version(name)
    except metadata.PackageNotFoundError:
        return {'name': name, 'version': None, 'status': 'not_installed'}
    except Exception:
        return {'name': name, 'version': None, 'status': 'unavailable'}
    if type(version) is not str or _VERSION.fullmatch(version) is None:
        return {'name': name, 'version': None, 'status': 'version_unrecognized'}
    return {'name': name, 'version': version, 'status': 'metadata_available'}


def collect_diagnostics(application_version):
    """Collect only fixed public runtime facts and reviewed dependency versions.

    Metadata presence is deliberately separate from successful decoder imports.
    No game discovery, path traversal, native-health probe or network is run.
    """
    if type(application_version) is not str or _RELEASE.fullmatch(application_version) is None:
        raise ValueError('Choose an explicit application release version.')
    from koei_editor.supported_games import SUPPORTED_GAMES
    from koei_editor.conversion import ROUTES
    family = ('Windows' if sys.platform == 'win32' else 'Linux' if sys.platform.startswith('linux')
              else 'macOS' if sys.platform == 'darwin' else 'Other')
    try:
        machine = platform.machine()
    except Exception:
        machine = ''
    machine = machine.lower() if type(machine) is str else ''
    architecture = {'amd64': 'x86_64', 'x86_64': 'x86_64', 'aarch64': 'arm64',
                    'arm64': 'arm64', 'i386': 'x86', 'i686': 'x86', 'x86': 'x86'}.get(machine, 'other')
    windows = os.name == 'nt'
    publication = windows or sys.platform.startswith('linux')
    report = {
        'schema': SCHEMA, 'schema_version': 1,
        'application': {'name': 'Universal Koei Tecmo Game Toolkit', 'version': application_version,
                        'mode': 'frozen' if getattr(sys, 'frozen', False) else 'source'},
        'runtime': {'os_family': family, 'architecture': architecture,
                    'python': '.'.join(str(value) for value in sys.version_info[:3]),
                    'implementation': sys.implementation.name if sys.implementation.name in ('cpython', 'pypy') else 'other'},
        'catalog': {'profiles': len(SUPPORTED_GAMES),
                    'platforms': len({game.platform for game in SUPPORTED_GAMES}),
                    'conversion_routes': len(ROUTES), 'in_game_verified': False},
        'dependencies': [_dependency(name) for name in DEPENDENCIES],
        'capabilities': {
            'save_vault_profiles': {'supported_platform': windows,
                                    'status': 'destination_checks_required' if windows else 'requires_windows'},
            'new_file_publication': {'supported_platform': publication,
                                     'status': 'destination_checks_required' if publication else 'unsupported_platform'},
        },
        'limitations': list(LIMITATIONS),
    }
    report_json(report)
    return report


def _keys(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError('Diagnostics report contains unsupported fields.')


def _validate(report):
    _keys(report, ('schema', 'schema_version', 'application', 'runtime', 'catalog',
                   'dependencies', 'capabilities', 'limitations'))
    if report['schema'] != SCHEMA or type(report['schema_version']) is not int or report['schema_version'] != 1:
        raise ValueError('Unsupported diagnostics schema.')
    app = report['application']
    _keys(app, ('name', 'version', 'mode'))
    if (app['name'] != 'Universal Koei Tecmo Game Toolkit' or type(app['version']) is not str
            or _RELEASE.fullmatch(app['version']) is None or app['mode'] not in ('source', 'frozen')):
        raise ValueError('Invalid diagnostics application facts.')
    runtime = report['runtime']
    _keys(runtime, ('os_family', 'architecture', 'python', 'implementation'))
    if (runtime['os_family'] not in ('Windows', 'Linux', 'macOS', 'Other')
            or runtime['architecture'] not in ('x86_64', 'arm64', 'x86', 'other')
            or type(runtime['python']) is not str or _RELEASE.fullmatch(runtime['python']) is None
            or runtime['implementation'] not in ('cpython', 'pypy', 'other')):
        raise ValueError('Invalid diagnostics runtime facts.')
    catalog = report['catalog']
    _keys(catalog, ('profiles', 'platforms', 'conversion_routes', 'in_game_verified'))
    if (any(type(catalog[key]) is not int or not 0 <= catalog[key] <= 1_000_000
            for key in ('profiles', 'platforms', 'conversion_routes')) or catalog['in_game_verified'] is not False):
        raise ValueError('Invalid diagnostics catalog facts.')
    dependencies = report['dependencies']
    if type(dependencies) is not list or len(dependencies) != len(DEPENDENCIES):
        raise ValueError('Invalid diagnostics dependency list.')
    for item, name in zip(dependencies, DEPENDENCIES):
        _keys(item, ('name', 'version', 'status'))
        if item['name'] != name or item['status'] not in ('metadata_available', 'not_installed', 'unavailable', 'version_unrecognized'):
            raise ValueError('Invalid diagnostics dependency facts.')
        if item['status'] == 'metadata_available':
            if type(item['version']) is not str or _VERSION.fullmatch(item['version']) is None:
                raise ValueError('Invalid dependency version.')
        elif item['version'] is not None:
            raise ValueError('Unavailable dependency version must be unspecified.')
    capabilities = report['capabilities']
    _keys(capabilities, ('save_vault_profiles', 'new_file_publication'))
    for name, unavailable in (('save_vault_profiles', 'requires_windows'),
                              ('new_file_publication', 'unsupported_platform')):
        item = capabilities[name]
        _keys(item, ('supported_platform', 'status'))
        if type(item['supported_platform']) is not bool or item['status'] != (
                'destination_checks_required' if item['supported_platform'] else unavailable):
            raise ValueError('Invalid diagnostics platform capability.')
    if type(report['limitations']) is not list or report['limitations'] != list(LIMITATIONS):
        raise ValueError('Diagnostics evidence limits must be retained.')


def report_json(report):
    """Serialize a reviewed shape without arbitrary log, path or exception fields."""
    _validate(report)
    encoded = json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False) + '\n'
    if len(encoded.encode('ascii')) > MAX_REPORT_BYTES:
        raise ValueError('Diagnostics report exceeds its size bound.')
    return encoded


def export_report(report, destination):
    """Export the exact reviewed JSON to a new local file, never replacing one."""
    return write_report_bytes(report_json(report).encode('ascii'), destination)
