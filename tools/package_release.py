"""Package only manifest-verified public sources and the built Windows editor."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'tools/SOURCE_MANIFEST.json'
PACKAGE_ROOT = 'src/koei_editor'
ROOT_FILES = {'.gitignore', '.gitattributes', 'LICENSE', 'README.md', 'AGENTS.md', 'pyproject.toml', 'launch.pyw', 'CONTRIBUTING.md'}
TOOL_FILES = {'tools/__init__.py', 'tools/build_windows.py', 'tools/package_release.py',
              'tools/refresh_manifest.py', 'tools/update_supported_games.py', 'tools/AGENTS.md',
              'tools/run_tests.py', 'tools/test_timings.json',
              'tools/requirements/build.txt', 'tools/requirements/dev.txt'}
ADAPTER_TEMPLATE_FILES = {'tools/adapter_template/new_game_parser.py', 'tools/adapter_template/new_game_editor.py',
                          'tools/adapter_template/contract_test.py', 'tools/adapter_template/INSTRUCTIONS.md'}
PUBLIC_TEST_HELPERS = {'tests/scalar_contract.py', 'tests/__init__.py'}
PUBLIC_GUIDES = {'src/koei_editor/AGENTS.md', 'src/koei_editor/games/AGENTS.md',
                'src/koei_editor/shared/AGENTS.md', 'src/koei_editor/research/AGENTS.md',
                'src/koei_editor/data/AGENTS.md', 'tests/README.md', 'licenses/README.md'}
RUNTIME_DATA = ('officer_names.json', 'game_metadata.json', 'unique_weapons.json',
                'verified_limits.json', 'item_limits.json', 'native_enums.json',
                'bodyguard_growth.json', 'bodyguard_items.json', 'bodyguard_weapons.json',
                'weapon_bonus_rules.json', 'progression_routes.json', 'collection_unlocks.json',
                'origins_evidence.json', 'support_catalog.json')
WINDOWS_DOCS = ('README.md', 'LICENSE', 'docs/CHANGELOG.md', 'docs/THIRD_PARTY_NOTICES.md',
                'docs/BUILDING.md', 'docs/ARCHITECTURE.md', 'docs/VALIDATION.md', 'docs/EXPANSION_COVERAGE.md',
                'docs/DYNASTY_RESEARCH.md', 'docs/OROCHI_RESEARCH.md', 'docs/SAMURAI_RESEARCH.md',
                'docs/PIRATE_ABYSS_RESEARCH.md', 'docs/STARS_WO4_RESEARCH.md', 'docs/NIOH3_RESEARCH.md',
                'docs/DW8_COMPATIBILITY.md', 'docs/SOPHIE2_COVERAGE.md', 'docs/PW3_COVERAGE.md',
                'docs/SUPPORTED_GAMES.md', 'docs/DW6_RESEARCH.md', 'docs/HYRULE_FORMATS.md',
                'docs/PS3_EXPANSION.md', 'docs/SWITCH_WARRIORS_RESEARCH.md',
                'docs/FIRE_EMBLEM_WARRIORS_FORMAT.md')
PERSONAL_PATH = re.compile(r'''(?i)(?:[a-z]:[\\/]+Users[\\/]+(?!Player(?:[\\/]|\b))[^\\/\s"']+|/(?:home|Users)/[^/\s"']+)''')
MODULE_NAME = re.compile(r'koei_editor(?:\.[A-Za-z_]\w*)*\Z')
CODEC_LICENSES = {
    'src/koei_editor/games/sophie2/atelier_sophie2_codec.py': 'licenses/atelier-sophie2-save-editor-MIT.txt',
    'src/koei_editor/research/katana/katana_codec.py': 'licenses/katana-save-data-resigner-MIT.txt',
}


def _repo_path(root, name):
    relative = PurePosixPath(name)
    path = root.joinpath(*relative.parts)
    if (any(root.joinpath(*relative.parts[:index]).is_symlink() for index in range(1, len(relative.parts) + 1))
            or not path.resolve().is_relative_to(root)):
        raise ValueError(f'Source path escapes the repository: {name}')
    return path


def version(root=ROOT):
    """Check the application, Windows builder and installed project together."""
    root = root.resolve()
    values = []
    for name in ('src/koei_editor/application.py', 'tools/build_windows.py'):
        tree = ast.parse(_repo_path(root, name).read_text(encoding='utf-8'))
        assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == 'VERSION' for target in node.targets)]
        if len(assignments) != 1:
            raise ValueError(f'{name} must declare one VERSION.')
        values.append(ast.literal_eval(assignments[0].value))
    project = tomllib.loads(_repo_path(root, 'pyproject.toml').read_text(encoding='utf-8'))
    values.append(project.get('project', {}).get('version'))
    if any(type(value) is not str or not re.fullmatch(r'\d+\.\d+(?:\.\d+)?', value) for value in values):
        raise ValueError('Application, build and project versions must be explicit release numbers.')
    if len(set(values)) != 1:
        raise ValueError('Application, build and project versions do not match.')
    return values[0]


def artifact_name(root=ROOT):
    return f'UniversalKoeiTecmoSaveEditor-v{version(root)}'


def public_path(name):
    if type(name) is not str or '\\' in name or ':' in name:
        raise ValueError('Manifest paths must be relative POSIX paths.')
    path = PurePosixPath(name)
    if (path.is_absolute() or any(part in ('..', '.', '') for part in name.split('/')) or str(path) != name
            or any(part.startswith('.') for part in path.parts) and path.parts[0] not in {'.github', '.gitignore', '.gitattributes'}):
        raise ValueError('Manifest path escapes or aliases the source tree.')
    parts = path.parts
    allowed = name in ROOT_FILES or name in TOOL_FILES or name in ADAPTER_TEMPLATE_FILES or name in PUBLIC_TEST_HELPERS or name in PUBLIC_GUIDES
    if parts[:2] == ('src', 'koei_editor'):
        if path.suffix == '.py':
            allowed = all(part.isidentifier() for part in parts[1:-1]) and path.stem.isidentifier()
        elif parts[:3] == ('src', 'koei_editor', 'data') and len(parts) == 4:
            allowed = allowed or parts[-1] in RUNTIME_DATA
    elif parts[0] == 'docs':
        allowed = (len(parts) == 2 and path.suffix == '.md') or (
            len(parts) == 3 and parts[1] == 'releases' and bool(re.fullmatch(r'v\d+\.\d+(?:\.\d+)?\.md', parts[2])))
    elif parts[0] == 'tests':
        allowed = allowed or (len(parts) == 2 and parts[1].startswith('test_') and path.suffix == '.py')
    elif parts[0] == 'licenses':
        allowed = allowed or (len(parts) == 2 and path.suffix in {'.txt', '.terms'})
    elif parts[:2] == ('.github', 'workflows'):
        allowed = len(parts) == 3 and path.suffix in {'.yml', '.yaml'}
    if not allowed or name == MANIFEST:
        raise ValueError(f'Not a public source file: {name}')
    return path


def _module_path(root, module):
    if not MODULE_NAME.fullmatch(module):
        raise ValueError('Local runtime modules must belong to the reviewed koei_editor package: ' + module)
    base = root / 'src' / Path(*module.split('.'))
    if base.is_dir():
        return (base / '__init__.py').relative_to(root).as_posix()
    return base.with_suffix('.py').relative_to(root).as_posix()


def _local_imports(root, module, tree):
    path = _module_path(root, module)
    package = module if path.endswith('/__init__.py') else module.rpartition('.')[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split('.')
                if node.level > len(parts):
                    raise ValueError('Relative import escapes the reviewed package: ' + module)
                base = '.'.join(parts[:len(parts) - node.level + 1])
                if node.module:
                    base += '.' + node.module
            else:
                base = node.module or ''
            names = [base]
            for alias in node.names:
                candidate = base + '.' + alias.name
                if alias.name != '*' and candidate.startswith('koei_editor.'):
                    location = root / 'src' / Path(*candidate.split('.'))
                    if location.with_suffix('.py').is_file() or location.is_dir():
                        names.append(candidate)
        else:
            continue
        for name in names:
            if name == 'koei_editor' or name.startswith('koei_editor.'):
                yield name
            elif name:
                # Local modules outside the reviewed package must not disappear
                # silently from the source closure as if they were external libraries.
                location = root / Path(*name.split('.'))
                src_location = root / 'src' / Path(*name.split('.'))
                if any(item.is_dir() or item.with_suffix('.py').is_file() for item in (location, src_location)):
                    raise ValueError('Local dependency is outside the reviewed runtime package: ' + name)


def _required_runtime(root, sources):
    pending = ['koei_editor.application', 'koei_editor.game_registry', 'koei_editor.__main__']
    registry = ast.parse(sources.get('src/koei_editor/game_registry.py', b''))
    for node in ast.walk(registry):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'Game':
            values = list(node.args[7:9])
            values.extend(keyword.value for keyword in node.keywords
                          if keyword.arg in ('editor_module', 'parser_module', 'scalar_backend'))
            pending.extend(value.value for value in values if isinstance(value, ast.Constant) and type(value.value) is str)
    required, visited = set(), set()
    while pending:
        module = pending.pop()
        if module in visited:
            continue
        visited.add(module)
        name = _module_path(root, module)
        required.add(name)
        parts = module.split('.')
        pending.extend('.'.join(parts[:index]) for index in range(1, len(parts)))
        pending.extend(_local_imports(root, module, ast.parse(sources.get(name, b''))))
    return required


def verified_sources(root=ROOT):
    root = root.resolve()
    manifest_bytes = _repo_path(root, MANIFEST).read_bytes()
    manifest = json.loads(manifest_bytes)
    release_version = version(root)
    if not isinstance(manifest, dict) or manifest.get('version') != release_version:
        raise ValueError('Manifest version does not match the editor.')
    entries = manifest.get('files')
    if not isinstance(entries, list) or not entries:
        raise ValueError('The source manifest is empty.')
    sources, seen = {}, set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'path', 'bytes', 'sha256'}:
            raise ValueError('Unsupported source manifest entry.')
        name = public_path(entry['path']).as_posix()
        if name.casefold() in seen:
            raise ValueError('Duplicate manifest path.')
        seen.add(name.casefold())
        data = _repo_path(root, name).read_bytes()
        if type(entry['bytes']) is not int or len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError(f'Source hash or length mismatch: {name}')
        text = data.decode('utf-8-sig')
        if '\0' in text or PERSONAL_PATH.search(text):
            raise ValueError(f'Binary content or personal home path in public source: {name}')
        sources[name] = data
    required = set(WINDOWS_DOCS) | TOOL_FILES | {'pyproject.toml', 'launch.pyw', 'docs/RELEASE_NOTES.md',
                                                '.github/workflows/windows-release.yml'}
    required.update(_required_runtime(root, sources))
    required.update(PACKAGE_ROOT + '/data/' + name for name in RUNTIME_DATA)
    if (root / '.gitattributes').exists():
        required.add('.gitattributes')
    if (root / 'tools/adapter_template').exists():
        required.update(ADAPTER_TEMPLATE_FILES | {'tests/scalar_contract.py'})
    for codec, notice in CODEC_LICENSES.items():
        if codec in required or codec in sources:
            required.add(notice)
    missing = required - sources.keys()
    if missing:
        raise ValueError('Required public sources missing from manifest: ' + ', '.join(sorted(missing)))
    if not any(name.startswith('licenses/') for name in sources):
        raise ValueError('Bundled dependency licenses are missing.')
    sources[MANIFEST] = manifest_bytes
    return release_version, sources


def write_zip(path, entries):
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def scan_bundled_data(label, data):
    if data is None:
        return
    for text in (data.decode('latin-1'), data.decode('utf-16-le', errors='ignore'),
                 data[1:].decode('utf-16-le', errors='ignore')):
        if PERSONAL_PATH.search(text):
            raise ValueError(f'Personal home path in bundled content: {label}')


def embedded_metadata(sources):
    expected = {name.removeprefix('src/'): data for name, data in sources.items()
                if name.startswith(PACKAGE_ROOT + '/data/') and name.endswith('.json')}
    expected.update({'LICENSE': sources['LICENSE'], 'THIRD_PARTY_NOTICES.md': sources['docs/THIRD_PARTY_NOTICES.md']})
    for codec, notice in CODEC_LICENSES.items():
        if codec in sources:
            expected[notice] = sources[notice]
    return expected



def _bundled_path(name):
    normalized = name.replace('\\', '/')
    path = PurePosixPath(normalized)
    if (path.is_absolute() or ':' in normalized or '..' in path.parts
            or any(part.casefold() in {'work', 'tests', 'fixtures', 'source-fixtures'} for part in path.parts)
            or path.suffix.casefold() in {'.sav', '.dat', '.bin', '.pak', '.key', '.psu', '.ps2', '.psv',
                                         '.max', '.cbs', '.vmc', '.sys', '.exe', '.rar', '.7z', '.ct'}):
        raise ValueError(f'Private or unsafe file in executable archive: {name}')
    return normalized, path

def verify_executable(root=ROOT, archive_reader=None):
    _, sources = verified_sources(root)
    executable = root / 'dist' / f'{artifact_name(root)}.exe'
    if executable.is_symlink() or not executable.resolve().is_relative_to(root.resolve()):
        raise ValueError('The executable must be built inside this repository.')
    binary = executable.read_bytes()
    if not binary.startswith(b'MZ'):
        raise ValueError('The built executable is not a Windows executable.')
    scan_bundled_data('executable', binary)
    if archive_reader is None:
        from PyInstaller.archive.readers import CArchiveReader
        archive_reader = CArchiveReader
    archive, bundled = archive_reader(str(executable)), set()
    expected = embedded_metadata(sources)
    for name, entry in archive.toc.items():
        normalized, path = _bundled_path(name)
        if path.suffix.lower() == '.json' and normalized not in expected:
            raise ValueError(f'Unreviewed JSON data in executable archive: {name}')
        data = archive.extract(name)
        scan_bundled_data(name, data)
        if normalized in expected:
            if data != expected[normalized]:
                raise ValueError(f'Bundled metadata differs from manifest: {name}')
            bundled.add(normalized)
        if entry[-1] == 'z':
            pyz = archive.open_embedded_archive(name)
            for module in pyz.toc:
                if any(part.casefold() in {'tests', 'fixtures', 'source-fixtures'} for part in module.split('.')):
                    raise ValueError(f'Private or unsafe module in executable archive: {module}')
                scan_bundled_data(module, pyz.extract(module, raw=True))
        elif path.suffix == '.zip':
            with zipfile.ZipFile(io.BytesIO(data)) as library:
                for module in library.namelist():
                    _, module_path = _bundled_path(module)
                    if module_path.suffix.casefold() == '.json':
                        raise ValueError(f'Unreviewed JSON data in executable library: {module}')
                    scan_bundled_data(module, library.read(module))
    if expected.keys() - bundled:
        raise ValueError('Verified metadata missing from executable: ' + ', '.join(sorted(expected.keys() - bundled)))
    return len(archive.toc)


def package(root=ROOT, output=None):
    root = root.resolve()
    _, sources = verified_sources(root)
    name = artifact_name(root)
    executable = root / 'dist' / f'{name}.exe'
    if executable.is_symlink() or not executable.resolve().is_relative_to(root):
        raise ValueError('The executable must be built inside this repository.')
    binary = executable.read_bytes()
    if not binary.startswith(b'MZ'):
        raise ValueError('The built executable is not a Windows executable.')
    verify_executable(root)
    output = Path(output) if output is not None else root / 'release'
    assets = [output / f'{name}-Windows.zip', output / f'{name}-Source.zip', output / f'{name}.exe', output / 'SHA256SUMS.txt']
    if any(path.exists() for path in assets):
        raise ValueError('Release outputs already exist; choose a new output directory.')
    windows = {doc: sources[doc] for doc in WINDOWS_DOCS}
    # Ship the complete approved documentation set, including the index and
    # supplier checklist. Never discover unreviewed files from the checkout.
    windows.update({path: data for path, data in sources.items()
                    if path.startswith('docs/') and path.endswith('.md')})
    windows.update({doc: sources[doc] for doc in ('docs/RELEASE_NOTES.md', 'AGENTS.md', 'CONTRIBUTING.md') if doc in sources})
    windows.update({path: data for path, data in sources.items() if path.startswith('licenses/')})
    windows[f'{name}.exe'] = binary
    prefix = f'{name}-Source/'
    output.mkdir(parents=True, exist_ok=True)
    write_zip(assets[0], windows)
    write_zip(assets[1], {prefix + path: data for path, data in sources.items()})
    with assets[2].open('xb') as stream:
        stream.write(binary)
    with assets[3].open('x', encoding='ascii', newline='\n') as stream:
        for path in assets[:3]:
            stream.write(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n')
    return assets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='store_true', help='Print the matching app/build/project release version.')
    parser.add_argument('--verify-only', action='store_true', help='Validate public source hashes without creating archives.')
    parser.add_argument('--verify-executable', action='store_true', help='Inspect the built runtime archive (requires PyInstaller).')
    parser.add_argument('--output', type=Path, help='New release output directory (default: release).')
    arguments = parser.parse_args()
    if arguments.version:
        print(version())
    elif arguments.verify_executable:
        print(f'Verified {verify_executable()} bundled archive entries.')
    elif arguments.verify_only:
        release_version, sources = verified_sources()
        print(f'v{release_version}: verified {len(sources) - 1} public source files.')
    else:
        for path in package(output=arguments.output):
            print(path.name)


if __name__ == '__main__':
    main()
