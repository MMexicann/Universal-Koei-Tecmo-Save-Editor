"""Reviewed Workshop exports using the Mod Manager's package rules.

Generic Workshop archives remain independent. This bridge never installs a
loader, opens a game directory or deploys a mod.
"""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import zipfile

from koei_editor.shared.copy_storage import publish_new_child_bound
from koei_editor.shared.save_safety import safe_path
from .packaging import PackageError, build_package, _reject_symlink_components
from .project_manager import load_project


MAX_MANAGER_EXPORT_BYTES = 64 * 1024 * 1024


def _candidate(project_dir, context, folder):
    from koei_editor.shared.mod_manager import review_archive, get_mod_adapter
    manifest = load_project(project_dir)
    get_mod_adapter(manifest.game_id)
    if manifest.platform != 'Windows PC':
        raise PackageError('Manager export requires an explicitly supported Windows PC mod project.')
    if any(item.optional or item.version != '*' for item in manifest.dependencies):
        raise PackageError('Manager export cannot preserve optional or version-constrained dependencies. Use the generic Workshop package.')
    # Reuse Workshop compatibility, rights, path and source-hash checks, rather
    # than creating another project/asset validator.
    generic = folder / 'workshop.zip'
    checked = build_package(project_dir, generic, context)
    if sum(item['size_bytes'] for item in checked['assets']) > MAX_MANAGER_EXPORT_BYTES:
        raise PackageError('Manager export is limited to 64 MiB. Use the generic Workshop package for larger projects.')
    metadata = {'schema_version': 1, 'game_id': manifest.game_id,
                'id': manifest.mod_id, 'name': manifest.name, 'version': manifest.version,
                'dependencies': [item.mod_id for item in manifest.dependencies], 'conflicts': []}
    candidate = folder / 'manager.zip'
    with zipfile.ZipFile(generic) as source, zipfile.ZipFile(candidate, 'w') as archive:
        records = [('koei-mod.json', json.dumps(metadata, ensure_ascii=True, sort_keys=True).encode('ascii')),
                   ('README.md', ('Workshop metadata and self-declared rights; game loading is not verified.\n\n'
                    + source.read('mod.json').decode('utf-8') + '\n\n'
                    + source.read('verification.json').decode('utf-8')).encode('utf-8'))]
        for item in checked['assets']:
            name = item['path'].removeprefix('replacements/')
            if name.casefold() in {'koei-mod.json', 'readme.md'}:
                raise PackageError('Replacement target collides with manager package metadata.')
            records.append((name, source.read(item['path'])))
        for name, data in sorted(records, key=lambda item: item[0].casefold()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, data)
    if candidate.stat().st_size > MAX_MANAGER_EXPORT_BYTES:
        raise PackageError('Manager export, including metadata, exceeds the 64 MiB limit.')
    # This is the same public inspector used by the manager's actual importer.
    reviewed = review_archive(candidate, game_id=manifest.game_id)
    actual_assets = sorted((item.sha256, item.size) for item in reviewed.files)
    declared_assets = sorted((item['sha256'], item['size_bytes']) for item in checked['assets'])
    if actual_assets != declared_assets:
        raise PackageError('Every Workshop replacement must be an installable manager payload file; documentation-only targets are unsupported.')
    raw = candidate.read_bytes()
    token = hashlib.sha256(raw).hexdigest()
    report = {'schema': 'koei-mod-workshop.manager-export.v1', 'success': True,
              'status': 'reviewed', 'read_only': True, 'in_game_verified': False,
              'review_token': token, 'archive_sha256': token,
              'package_review': asdict(reviewed), 'compatibility': checked['compatibility'],
              'limitations': ['No loader is installed and no game files are changed.',
                              'Asset rights and compatibility context are author-declared.',
                              'Export validation does not prove in-game loading.']}
    return raw, report


def review_manager_package(project_dir, context):
    """Review a deterministic manager ZIP without publishing any destination."""
    with tempfile.TemporaryDirectory(prefix='koei-workshop-review-') as folder:
        _raw, report = _candidate(project_dir, context, Path(folder).resolve())
    return report


def export_manager_package(project_dir, output_file, context, *, review_token):
    """Publish a new ZIP only when its exact content matches a prior review."""
    destination = Path(os.path.abspath(output_file))
    if safe_path(output_file) != destination:
        raise PackageError('Choose a new package filename without path aliases.')
    _reject_symlink_components(destination.parent)
    parent = None
    for parent_path in destination.parents:
        info = parent_path.lstat()
        if not stat.S_ISDIR(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
            raise PackageError('Choose an ordinary package folder without aliases or reparse points.')
        if parent_path == destination.parent:
            parent = info
    if not destination.parent.is_dir():
        raise PackageError('Choose an existing ordinary package folder.')
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('Existing package entries are never replaced.')
    with tempfile.TemporaryDirectory(prefix='koei-workshop-export-') as folder:
        raw, report = _candidate(project_dir, context, Path(folder).resolve())
        if not isinstance(review_token, str) or review_token != report['review_token']:
            raise PackageError('The package changed or the review token is invalid. Review it again before export.')
        publish_new_child_bound(raw, destination.parent, destination.name,
                                (parent.st_dev, parent.st_ino), cleanup_pending_on_failure=True)
    return {**report, 'status': 'exported', 'read_only': False}
