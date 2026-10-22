"""Validate a selected directory of versioned, data-only community packages.

The report is stable JSON for automated review. This tool does not load saves,
resolve links, install mods, or execute package content.
"""
import argparse
import json
import os
from pathlib import Path
import stat

from koei_editor.shared.community_packages import (
    CommunityPackageError, MAX_BYTES, MAX_ITEMS, SUFFIX, load,
)


MAX_DIRECTORY_ENTRIES = 512
MAX_PACKAGE_FILES = MAX_ITEMS
REPORT_SCHEMA = 'koei-tecmo-community-validation-report'
REPORT_VERSION = 1


class DirectoryError(ValueError):
    """A selected package directory failed bounded discovery."""


def _package_paths(directory):
    path = Path(directory)
    try:
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise DirectoryError('The selected path must be an ordinary directory.')
        names = []
        with os.scandir(path) as entries:
            for count, entry in enumerate(entries, 1):
                if count > MAX_DIRECTORY_ENTRIES:
                    raise DirectoryError('The selected directory contains too many entries.')
                if entry.name.casefold().endswith(SUFFIX.casefold()):
                    names.append(entry.name)
                    if len(names) > MAX_PACKAGE_FILES:
                        raise DirectoryError('The selected directory contains too many package files.')
    except DirectoryError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise DirectoryError('The selected package directory is unavailable.') from error
    return tuple(path / name for name in sorted(names, key=lambda item: (item.casefold(), item)))


def _error(code, message):
    return {'code': code, 'message': message}


def validate_directory(directory):
    """Return a path-free, versioned report for an explicitly selected folder."""
    try:
        paths = _package_paths(directory)
    except DirectoryError as error:
        return {
            'schema': REPORT_SCHEMA,
            'version': REPORT_VERSION,
            'validation_scope': 'package_structure_only',
            'valid': False,
            'summary': {'checked': 0, 'valid': 0, 'invalid': 0},
            'results': [],
            'errors': [_error('directory_unavailable', str(error))],
            'limits': {'package_bytes': MAX_BYTES, 'packages': MAX_PACKAGE_FILES,
                       'directory_entries': MAX_DIRECTORY_ENTRIES},
        }

    results = []
    if not paths:
        error = _error('no_packages_found', f'No *{SUFFIX} files were found in the selected directory.')
        return {
            'schema': REPORT_SCHEMA,
            'version': REPORT_VERSION,
            'validation_scope': 'package_structure_only',
            'valid': False,
            'summary': {'checked': 0, 'valid': 0, 'invalid': 0},
            'results': [],
            'errors': [error],
            'limits': {'package_bytes': MAX_BYTES, 'packages': MAX_PACKAGE_FILES,
                       'directory_entries': MAX_DIRECTORY_ENTRIES},
        }

    for index, path in enumerate(paths, 1):
        record = {
            # Package filenames can contain user supplied identifiers. A stable
            # index keeps the report readable without disclosing those names.
            'file_index': index,
            'valid': False,
            'kind': None,
            'package_id': None,
            'game_id': None,
            'warnings': [],
            'errors': [],
        }
        try:
            package = load(path)
        except CommunityPackageError as error:
            record['errors'].append(_error('invalid_package', str(error)))
        except (OSError, ValueError, RecursionError):
            record['errors'].append(_error('invalid_package', 'The file failed package validation.'))
        else:
            record.update(valid=True, kind=package.kind, package_id=package.id,
                          game_id=package.game_id)
            record['warnings'].append(_error(
                'host_checks_required',
                'A consuming feature must check game, platform, setting, and field support before use.',
            ))
        results.append(record)

    valid_count = sum(item['valid'] for item in results)
    invalid_count = len(results) - valid_count
    return {
        'schema': REPORT_SCHEMA,
        'version': REPORT_VERSION,
        'validation_scope': 'package_structure_only',
        'valid': invalid_count == 0,
        'summary': {'checked': len(results), 'valid': valid_count, 'invalid': invalid_count},
        'results': results,
        'errors': [],
        'limits': {'package_bytes': MAX_BYTES, 'packages': MAX_PACKAGE_FILES,
                   'directory_entries': MAX_DIRECTORY_ENTRIES},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', help='Selected directory containing *.koei-community.json files (not recursive).')
    args = parser.parse_args(argv)
    report = validate_directory(args.directory)
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if report['valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
