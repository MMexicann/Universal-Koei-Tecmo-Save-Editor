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
import zlib

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'tools/SOURCE_MANIFEST.json'
PACKAGE_ROOT = 'src/koei_editor'
ROOT_FILES = {'.gitignore', '.gitattributes', 'LICENSE', 'README.md', 'AGENTS.md', 'pyproject.toml', 'launch.pyw', 'CONTRIBUTING.md'}
TOOL_FILES = {'tools/__init__.py', 'tools/build_windows.py', 'tools/package_release.py',
              'tools/scan_release.ps1', 'tools/smoke_windows.ps1', 'tools/smoke_cli_windows.ps1', 'tools/benchmark_automation.py', 'tools/benchmark_application.py',
              'tools/check_community_plugins.py', 'tools/community_plugin_template/example.plugin.json',
              'tools/refresh_manifest.py', 'tools/update_supported_games.py', 'tools/AGENTS.md',
              'tools/run_tests.py', 'tools/test_timings.json', 'tools/inspect_candidate.py',
              'tools/requirements/build.txt', 'tools/requirements/dev.txt',
              'tools/pyinstaller_hooks/hook-trimesh.py',
              'tools/numpy_build_provenance.py',
              'tools/pyinstaller_hooks/hook-numpy.__config__.py',
              'tools/pyinstaller_hooks/hook-numpy.lib._datasource.py',
              'tools/pyinstaller_hooks/pre_safe_import_module/hook-distutils.py'}
COMMUNITY_TEMPLATE_FILES = frozenset(
    f'tools/community_package_templates/{kind}.koei-community.json'
    for kind in ('character_build', 'mod_list', 'configuration_preset',
                 'playthrough_manifest', 'compatibility_report'))
TOOL_FILES.update({'tools/check_community_packages.py'} | COMMUNITY_TEMPLATE_FILES)
TOOL_FILES.update({'tools/build_linux.py', 'tools/package_linux.py',
                   'tools/smoke_linux.py',
                   'tools/linux_build_review.py', 'tools/linux_dependency_review.json',
                   'tools/requirements/linux-build.txt',
                   'tools/linux_hooks/hook-numpy.__config__.py',
                   'tools/linux_hooks/hook-numpy.lib._datasource.py'})
TOOL_FILES.add('tools/linux_hooks/hook-Crypto.py')
TOOL_FILES.add('tools/verify_linux_publication.py')
COMMUNITY_SCHEMA_FILES = frozenset(
    f'docs/schemas/koei-community-{kind}-v1.schema.json'
    for kind in ('character_build', 'mod_list', 'configuration_preset',
                 'playthrough_manifest', 'compatibility_report'))
SOURCE_ONLY_GUIDES = frozenset({'docs/COMMUNITY_TOOLKIT.md', 'docs/releases/toolkit-v1.0.md'})
ADAPTER_TEMPLATE_FILES = {'tools/adapter_template/new_game_parser.py', 'tools/adapter_template/new_game_editor.py',
                          'tools/adapter_template/contract_test.py', 'tools/adapter_template/INSTRUCTIONS.md'}
PUBLIC_TEST_HELPERS = {'tests/scalar_contract.py', 'tests/gui_paging.py', 'tests/__init__.py',
                       'tests/owned_directory_contract.py'}
PUBLIC_GUIDES = {'src/koei_editor/AGENTS.md', 'src/koei_editor/games/AGENTS.md',
                'src/koei_editor/shared/AGENTS.md', 'src/koei_editor/research/AGENTS.md',
                'src/koei_editor/data/AGENTS.md', 'tests/README.md', 'licenses/README.md'}
# Exact static-tool files are public in the Source ZIP, not Windows runtime data.
LOCALIZATION_STUDIO_FILES = {
    'localization-studio/LICENSE',
    'localization-studio/README.md',
    'localization-studio/index.html',
    'localization-studio/package.json',
    'localization-studio/styles.css',
    'localization-studio/docs/RESEARCH.md',
    'localization-studio/docs/SUPPORTED_FORMATS.md',
    'localization-studio/reports/validation-report.json',
    'localization-studio/src/app.mjs',
    'localization-studio/src/formats.mjs',
    'localization-studio/tests/browser-smoke.html',
    'localization-studio/tests/formats.test.mjs',
    'localization-studio/tests/run-browser-smoke.mjs',
}
MOD_TESTING_SANDBOX_SOURCES = {
    '.github/workflows/mod-testing-sandbox.yml',
    'docs/MOD_TESTING_SANDBOX.md',
    'tools/mod_testing_sandbox/README.md',
    'tools/mod_testing_sandbox/index.html',
    'tools/mod_testing_sandbox/package.json',
    'tools/mod_testing_sandbox/scripts/build.mjs',
    'tools/mod_testing_sandbox/src/main.mjs',
    'tools/mod_testing_sandbox/src/sandbox-core.mjs',
    'tools/mod_testing_sandbox/src/styles.css',
    'tools/mod_testing_sandbox/src/workspace-store.mjs',
    'tools/mod_testing_sandbox/test/security.test.mjs',
    'tools/mod_testing_sandbox/test/workspace-store.test.mjs',
    'tools/mod_testing_sandbox/test/workshop-folder-ui.test.mjs',
}
RUNTIME_DATA = ('officer_names.json', 'game_metadata.json', 'unique_weapons.json',
                'verified_limits.json', 'item_limits.json', 'native_enums.json',
                'bodyguard_growth.json', 'bodyguard_items.json', 'bodyguard_weapons.json',
                'weapon_bonus_rules.json', 'progression_routes.json', 'collection_unlocks.json',
                'origins_evidence.json', 'dw6_migration_evidence.json', 'support_catalog.json',
                'save_discovery.json', 'game_data_encyclopedia.json',
                'game_troubleshooting.json', 'version_compatibility.json')
# Explicit user guides are reviewed runtime metadata in both Windows builds.
# Repository/developer documentation remains confined to the Source ZIP.
RUNTIME_GUIDES = ('docs/CLI.md', 'docs/DIAGNOSTICS.md', 'docs/GAME_DATA_ENCYCLOPEDIA.md', 'docs/ASSET_EXPLORER.md', 'docs/RESEARCH_IMPORT.md', 'docs/AUTOMATION.md', 'docs/APPLICATION_SHELL.md', 'docs/HELP_AND_COMPATIBILITY.md',
                  'docs/CONTROLLER_INPUT_PROFILES.md',
                  'docs/GAME_TROUBLESHOOTING.md',
                  'docs/WARRIORS_PS4_TRANSFERS.md',
                  'docs/WO3U_PS4_RESOURCE_TRANSFER.md',
                  'docs/COMMUNITY_PLUGINS.md', 'docs/REAL_GAME_VALIDATION.md', 'docs/PROGRESSION_DASHBOARDS.md', 'docs/EDITOR_WORKSPACE.md', 'docs/ORIGINS_REQUEST_STATUS.md',
                  'docs/SAVE_CONVERSION.md', 'docs/SAVE_COMPARISON.md',
                  'docs/BATCH_CONVERSION.md', 'docs/DW6_CONVERSION.md', 'docs/DW6_PS3_FORMAT.md',
                  'docs/DW7XL_CONVERSION.md', 'docs/DW7XL_WEAPONS.md',
                  'docs/DW7XL_PS3.md', 'docs/NOA2_SWITCH_FORMAT.md',
                  'docs/SAVE_LIBRARY.md', 'docs/EDIT_PRESETS.md', 'docs/REUSABLE_PRESETS.md',
                  'docs/FIELD_PINS_AND_REVIEWS.md', 'docs/SMART_PLAYTHROUGH_PROFILES.md',
                  'docs/GAME_CONFIGURATION.md')
RUNTIME_GUIDES += ('docs/TOOLKIT_FEATURES.md', 'docs/MOD_MANAGER.md',
                   'docs/MOD_CREATION_WORKSHOP.md', 'docs/MOD_WORKSHOP_MANAGER.md',
                   'docs/NEXUS_MODS_BROWSER.md', 'docs/PATCH_COMPATIBILITY_ANALYZER.md',
                   'docs/MOD_TESTING_SANDBOX.md', 'docs/BROWSER_COMPANIONS.md',
                   'docs/FEATURE_STATUS.md')
RUNTIME_LICENSES = ('licenses/Python-LICENSE.txt', 'licenses/PyInstaller-COPYING.txt',
                   'licenses/Tk-license.terms', 'licenses/OpenSSL-LICENSE.txt',
                   'licenses/G1Tool-MIT.txt', 'licenses/miniaudio-MIT.txt',
                   'licenses/trimesh-MIT.txt', 'licenses/numpy-BSD-3-Clause.txt',
                   'licenses/numpy-libdivide.txt', 'licenses/numpy-pythoncapi-compat.txt',
                   'licenses/numpy-highway.txt', 'licenses/numpy-dragon4.txt',
                   'licenses/numpy-x86-simd-sort.txt', 'licenses/numpy-svml.txt',
                   'licenses/numpy-pocketfft.txt', 'licenses/numpy-lapack-lite.txt',
                   'licenses/numpy-ma.txt', 'licenses/numpy-random.txt',
                   'licenses/numpy-random-distributions.txt', 'licenses/numpy-mt19937.txt',
                   'licenses/numpy-pcg64.txt', 'licenses/numpy-philox.txt',
                   'licenses/numpy-sfc64.txt', 'licenses/numpy-splitmix64.txt',
                   'licenses/cffi-MIT-0.txt', 'licenses/cffi-libffi-MIT.txt',
                   'licenses/pycparser-BSD-3-Clause.txt')
WINDOWS_DOCS = ('docs/CLI.md', 'docs/DIAGNOSTICS.md', 'docs/GAME_DATA_ENCYCLOPEDIA.md', 'docs/RESEARCH_IMPORT.md', 'docs/AUTOMATION.md', 'docs/APPLICATION_SHELL.md', 'docs/ASSET_EXPLORER.md', 'docs/HELP_AND_COMPATIBILITY.md',
                'docs/CONTROLLER_INPUT_PROFILES.md',
                'docs/GAME_TROUBLESHOOTING.md',
                'docs/WARRIORS_PS4_TRANSFERS.md',
                'docs/WO3U_PS4_RESOURCE_TRANSFER.md',
                'docs/COMMUNITY_PLUGINS.md', 'docs/REAL_GAME_VALIDATION.md', 'README.md', 'LICENSE', 'docs/CHANGELOG.md', 'docs/THIRD_PARTY_NOTICES.md',
                'docs/PROGRESSION_DASHBOARDS.md',
                'docs/EXPERIMENTAL_EDITING.md', 'docs/EDITOR_WORKSPACE.md', 'docs/ORIGINS_REQUEST_STATUS.md',
                'docs/SAVE_CONVERSION.md', 'docs/SAVE_COMPARISON.md', 'docs/BATCH_CONVERSION.md',
                'docs/DW6_CONVERSION.md', 'docs/DW6_PS3_FORMAT.md', 'docs/DW7XL_CONVERSION.md',
                'docs/DW7XL_WEAPONS.md', 'docs/DW7XL_PS3.md', 'docs/NOA2_SWITCH_FORMAT.md',
                'docs/SAVE_LIBRARY.md', 'docs/EDIT_PRESETS.md', 'docs/REUSABLE_PRESETS.md',
                'docs/FIELD_PINS_AND_REVIEWS.md',
                'docs/SMART_PLAYTHROUGH_PROFILES.md', 'docs/GAME_CONFIGURATION.md',
                'docs/FATAL_FRAME2_PS2_FORMAT.md', 'docs/TROY_PS3_FORMAT.md', 'docs/WARRIORS_V26_DEPTH.md',
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
    'src/koei_editor/research/asset_explorer/g1t.py': 'licenses/G1Tool-MIT.txt',
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
    return f'UniversalKoeiTecmoGameToolkit-v{version(root)}'


def runtime_directory(root=ROOT):
    """The complete PyInstaller portable application, including its dependencies."""
    return Path(root) / 'dist' / artifact_name(root)


def executable_path(root=ROOT):
    return runtime_directory(root) / (artifact_name(root) + '.exe')


def standalone_executable_path(root=ROOT):
    """Self-contained onefile build; never substitute the portable launcher."""
    return Path(root) / 'dist-standalone' / (artifact_name(root) + '.exe')


def cli_executable_path(root=ROOT):
    """Separate self-contained console build; never substitute a GUI executable."""
    return Path(root) / 'dist-cli' / (artifact_name(root) + '-CLI.exe')


def public_path(name):
    if type(name) is not str or '\\' in name or ':' in name:
        raise ValueError('Manifest paths must be relative POSIX paths.')
    path = PurePosixPath(name)
    if (path.is_absolute() or any(part in ('..', '.', '') for part in name.split('/')) or str(path) != name
            or any(part.startswith('.') for part in path.parts) and path.parts[0] not in {'.github', '.gitignore', '.gitattributes'}):
        raise ValueError('Manifest path escapes or aliases the source tree.')
    parts = path.parts
    allowed = (name in ROOT_FILES or name in TOOL_FILES or name in ADAPTER_TEMPLATE_FILES
               or name in PUBLIC_TEST_HELPERS or name in PUBLIC_GUIDES
               or name in MOD_TESTING_SANDBOX_SOURCES)
    if parts[:2] == ('src', 'koei_editor'):
        if path.suffix == '.py':
            allowed = all(part.isidentifier() for part in parts[1:-1]) and path.stem.isidentifier()
        elif parts[:3] == ('src', 'koei_editor', 'data') and len(parts) == 4:
            allowed = allowed or parts[-1] in RUNTIME_DATA
    elif parts[0] == 'docs':
        allowed = (len(parts) == 2 and path.suffix == '.md') or (
            len(parts) == 3 and parts[1] == 'releases' and bool(re.fullmatch(r'v\d+\.\d+(?:\.\d+)?\.md', parts[2])))
        allowed = allowed or name in COMMUNITY_SCHEMA_FILES or name in SOURCE_ONLY_GUIDES
    elif parts[0] == 'tests':
        allowed = allowed or (len(parts) == 2 and parts[1].startswith('test_') and path.suffix == '.py')
    elif parts[0] == 'licenses':
        allowed = allowed or (len(parts) == 2 and path.suffix in {'.txt', '.terms'})
    elif parts[0] == 'localization-studio':
        allowed = name in LOCALIZATION_STUDIO_FILES
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
                          if keyword.arg in ('editor_module', 'parser_module', 'scalar_backend',
                                             'workshop_module'))
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
    required = set(WINDOWS_DOCS) | set(RUNTIME_GUIDES) | TOOL_FILES | {'pyproject.toml', 'launch.pyw', 'src/koei_editor/cli.py', 'docs/RELEASE_NOTES.md',
                                                '.github/workflows/windows-release.yml'}
    required.update(SOURCE_ONLY_GUIDES | COMMUNITY_SCHEMA_FILES)
    if (root / 'tools/mod_testing_sandbox').is_dir():
        required.update(MOD_TESTING_SANDBOX_SOURCES)
    required.update(_required_runtime(root, sources))
    required.update(PACKAGE_ROOT + '/data/' + name for name in RUNTIME_DATA)
    required.update(RUNTIME_LICENSES)
    if (root / '.gitattributes').exists():
        required.add('.gitattributes')
    if (root / 'tools/adapter_template').exists():
        required.update(ADAPTER_TEMPLATE_FILES | {'tests/scalar_contract.py'})
    if (root / 'localization-studio').is_dir():
        required.update(LOCALIZATION_STUDIO_FILES)
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
    from koei_editor.shared.browser_companions import BROWSER_RESOURCE_SOURCES
    missing = set(BROWSER_RESOURCE_SOURCES.values()) - sources.keys()
    if missing:
        raise ValueError('Bundled browser resources are missing from the reviewed source inventory: '
                         + ', '.join(sorted(missing)))
    expected = {name.removeprefix('src/'): data for name, data in sources.items()
                if name.startswith(PACKAGE_ROOT + '/data/') and name.endswith('.json')}
    expected.update({'licenses/LICENSE': sources['LICENSE'],
                     'licenses/THIRD_PARTY_NOTICES.md': sources['docs/THIRD_PARTY_NOTICES.md']})
    expected.update({name: sources[name] for name in RUNTIME_LICENSES})
    expected.update({'guides/' + name.removeprefix('docs/'): sources[name] for name in RUNTIME_GUIDES})
    expected.update({name: sources[source] for name, source in BROWSER_RESOURCE_SOURCES.items()})
    for codec, notice in CODEC_LICENSES.items():
        if codec in sources:
            expected[notice] = sources[notice]
    return expected



def _bundled_path(name):
    normalized = name.replace('\\', '/')
    path = PurePosixPath(normalized)
    if (path.is_absolute() or ':' in normalized
            or any(part in ('..', '.', '') for part in normalized.split('/'))
            or any(part.startswith('.') for part in path.parts)
            or any(part.casefold() in {'work', 'tests', 'fixtures', 'source-fixtures', '__pycache__'} for part in path.parts)
            or path.suffix.casefold() in {'.sav', '.dat', '.bin', '.pak', '.key', '.psu', '.ps2', '.psv',
                                         '.max', '.cbs', '.vmc', '.sys', '.exe', '.rar', '.7z', '.ct'}):
        raise ValueError(f'Private or unsafe file in executable archive: {name}')
    return normalized, path


# External native runtime modules remain an explicit allowlist. The asset
# inspection stack needs pinned miniaudio, cffi and NumPy extensions in addition
# to CPython/Tcl/Tk; an arbitrary extension is never admitted by its suffix.
NATIVE_DLL = re.compile(
    r'(?:python(?:3|3\d+)\.dll|vcruntime140(?:_1)?\.dll|msvcp140\.dll|ucrtbase\.dll|'
    r'api-ms-win-[a-z0-9-]+\.dll|lib(?:crypto|ssl)-\d+(?:-x64)?\.dll|'
    r'libffi-\d+\.dll|(?:lib)?(?:tcl|tk)\d+t?\.dll|tcl9tk90\.dll|'
    r'libtommath\.dll|zlib1\.dll|sqlite3\.dll)\Z', re.I)
NUMPY_DLLS = frozenset({
    'numpy.libs/libscipy_openblas64_-ed4f167a5330424524f45258e7ca2c8d.dll',
    'numpy.libs/msvcp140-a4c2229bdc2a2a630acdc095b4d86008.dll',
})
STDLIB_EXTENSIONS = frozenset({
    '_asyncio', '_bz2', '_ctypes', '_decimal', '_elementtree', '_hashlib', '_lzma',
    '_multiprocessing', '_overlapped', '_queue', '_socket', '_sqlite3', '_ssl',
    '_tkinter', '_uuid', '_wmi', '_zoneinfo', '_zstd', 'pyexpat', 'select', 'unicodedata', 'zlib',
})
ASSET_EXTENSION = re.compile(r'(?:_miniaudio|_cffi_backend)(?:\.cp314-win_amd64)?\.pyd\Z', re.I)
NUMPY_EXTENSION = re.compile(
    r'numpy/(?:_core/(?:_multiarray_umath|_multiarray_tests|_operand_flag_tests|_rational_tests|_simd|_struct_ufunc_tests|_umath_tests)|'
    r'fft/_pocketfft_umath|linalg/(?:_umath_linalg|lapack_lite)|'
    r'random/(?:bit_generator|mtrand|_bounded_integers|_common|_generator|_mt19937|_pcg64|_philox|_sfc64))'
    r'(?:\.cp314-win_amd64)?\.pyd\Z', re.I)
# Exact resources from the hash-locked trimesh 5.1.1 wheel. Optional viewers,
# executable templates and format-schema archives are outside our preview scope.
TRIMESH_RESOURCES = {
    'trimesh/resources/creation.json': '8bbd9d1eec4d3a4da06e74a36215864c42fe5b37967564757b7b7fde20cfd18b',
    'trimesh/resources/units_to_inches.json': 'aeaffb35476bfb1a6d168317f5a842bb838b3c62f171c2ab6a02a2e4f75b4f6c',
    'trimesh/resources/color_map.json.gzip': 'd0476d6b5697444c8b359fd933e7effde10023329aeddbebf132d803ec031735',
    'trimesh/resources/templates/ply.json': '3317874b902a0eac387906ff7eb900a32c31a642718d275c1eef43c8f5e93640',
}
# Official Windows/universal wheels verified against tools/requirements/build.txt.
# Only their runtime METADATA is shipped; DELVEWHEEL, RECORD, installer markers,
# entry points and duplicate licenses are build metadata, not application data.
REVIEWED_WHEEL_HASHES = {
    'pyinstaller-6.22.3.dist-info': '500bd58c7bf7e584a8435adccbd763a0b918d5c12b08d74ff50fd79b2915458b',
    'altgraph-0.17.5.dist-info': 'f3a22400bce1b0c701683820ac4f3b159cd301acab067c51c653e06961600597',
    'packaging-26.3.dist-info': 'd7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c',
    'pefile-2024.8.26.dist-info': '76f8b485dcd3b1bb8166f1128d395fa3d87af26360c2358fb75b80019b957c6f',
    'pyinstaller_hooks_contrib-2026.8.dist-info': '6d21d65323ea4467753afc21f52d7d0e69416ae8101dd88269bf273ad48db084',
    'pywin32_ctypes-0.2.3.dist-info': '8a1513379d709975552d202d942d9837758905c8d01eb82b8bcc30918929e7b8',
    'setuptools-84.0.0.dist-info': '51a52592b3b99e102b609654876bd65f19f999935166d1352678931132b0c670',
    'miniaudio-1.71.dist-info': '154b085dd914a0e79e3d93160e1a07aacb27d66c65f9ef6a0d87c1a194f32c04',
    'cffi-2.1.1.dist-info': '3222ba5d678f80a030e6afbcc33dc1ae5cb45facabb61cee2c7016b8432fde48',
    'pycparser-3.12.dist-info': 'a076f3f489b39b43ed13563a1dafe42447445bec2e294154ec5c57fcdda4c85e',
    'trimesh-5.1.1.dist-info': 'c5be85a3e31e9ff749f9b0aecc204e37a2cf7cca4e92cd066bb5f3d3c1127765',
    'numpy-2.5.4.dist-info': '2ca144f15135b6212a5c47b1e2aeca6e412f102f95a2d5d88d8aec77eb255de3',
}
RUNTIME_DEPENDENCY_METADATA = {
    'miniaudio-1.71.dist-info/METADATA': '4c375f306c54fe64792ffc56fb2a2b5a6458d644149d268898393364cab56f1c',
    'cffi-2.1.1.dist-info/METADATA': '67b6a7595df7ede2195016a05d285faa7d362a8f57c238984edb8bb674b5770d',
    'pycparser-3.12.dist-info/METADATA': 'ad8db5fe2b0e0a3b0e8419fe5041b80be92470a40b06bd9c1462a0a8bb637c92',
    'trimesh-5.1.1.dist-info/METADATA': '83ff5dabdef64a3ee82e560f419c06c7d5d40704e3cefe1807ea136db79b01b7',
    'numpy-2.5.4.dist-info/METADATA': 'e2b909d6a37d76c2bc130f528d7fed0c517322bce16dc7846b6a6df30e200403',
}


def verify_dependency_metadata_lock(root=ROOT):
    text = (Path(root) / 'tools/requirements/build.txt').read_text(encoding='utf-8')
    locked, flags = {}, set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line in {'--require-hashes', '--only-binary=:all:'} and line not in flags:
            flags.add(line)
            continue
        match = re.fullmatch(r'([\w-]+)==([^ ]+) --hash=sha256:([0-9a-f]{64})', line)
        if match is None:
            raise ValueError('Unreviewed dependency lock syntax.')
        name, version, digest = match.groups()
        directory = name.replace('-', '_') + '-' + version + '.dist-info'
        if directory in locked:
            raise ValueError('Duplicate reviewed wheel lock entry.')
        locked[directory] = digest
    if locked != REVIEWED_WHEEL_HASHES or flags != {'--require-hashes', '--only-binary=:all:'}:
        raise ValueError('Dependency metadata review differs from the hash-locked wheels.')


def _is_distribution_metadata(path):
    return any(part.casefold().endswith('.dist-info') for part in path.parts)


def filter_runtime_metadata(datas, root=ROOT):
    """Minimize PyInstaller Analysis data before either executable is assembled."""
    verify_dependency_metadata_lock(root)
    retained, seen, metadata = [], set(), set()
    for entry in datas:
        if not isinstance(entry, (tuple, list)) or len(entry) != 3 or not isinstance(entry[0], str):
            raise ValueError('Invalid PyInstaller runtime data entry.')
        name, source, kind = entry
        if not _is_distribution_metadata(PurePosixPath(name.replace('\\', '/'))):
            retained.append(entry)
            continue
        normalized, relative = _bundled_path(name)
        if (kind != 'DATA' or len(relative.parts) < 2
                or relative.parts[0] not in REVIEWED_WHEEL_HASHES
                or any(part.casefold().endswith('.dist-info') for part in relative.parts[1:])
                or normalized.casefold() in seen):
            raise ValueError(f'Unreviewed dependency metadata collection: {name}')
        seen.add(normalized.casefold())
        if normalized in RUNTIME_DEPENDENCY_METADATA:
            with Path(source).open('rb') as stream:
                data = stream.read(65537)
            _validate_runtime_file(normalized, data, {})
            metadata.add(normalized)
            retained.append(entry)
    if metadata != RUNTIME_DEPENDENCY_METADATA.keys():
        raise ValueError('Required runtime dependency metadata missing from build analysis.')
    return retained


TCL_PACKAGE_DLLS = frozenset({'_tcl_data/dde1.4/tcldde14.dll', '_tcl_data/reg1.3/tclreg13.dll'})
TCL_RESOURCE_SUFFIXES = frozenset({'', '.tcl', '.tm', '.msg', '.enc', '.txt', '.n'})


def _verify_library_zip(label, data, require_stdlib=False):
    seen = set()
    total_bytes = 0
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as library:
            for info in library.infolist():
                total_bytes += info.file_size
                if info.file_size > 32 * 1024 * 1024 or total_bytes > 128 * 1024 * 1024 or info.flag_bits & 1:
                    raise ValueError(f'Oversized or encrypted executable library: {label}')
                name = info.filename.rstrip('/') if info.is_dir() else info.filename
                normalized, path = _bundled_path(name)
                if normalized.casefold() in seen or (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError(f'Duplicate or symlink file in executable library: {label}/{name}')
                seen.add(normalized.casefold())
                if path.suffix.casefold() == '.json':
                    raise ValueError(f'Unreviewed JSON data in executable library: {name}')
                if not info.is_dir():
                    scan_bundled_data(label + '/' + name, library.read(info))
            if require_stdlib and not {'encodings/__init__.pyc', 'encodings/utf_8.pyc'} <= seen:
                raise ValueError(f'Standard library runtime is incomplete: {label}')
    except zipfile.BadZipFile as error:
        raise ValueError(f'Invalid executable library ZIP: {label}') from error
    return seen


def _verify_tcl_zip(label, data, prefix, entry):
    """Tcl/Tk 9 official Windows DLLs contain their scripts as ZIP resources."""
    names = _verify_library_zip(label, data)
    if prefix + '/' + entry not in names:
        raise ValueError(f'Tcl/Tk embedded runtime library is incomplete: {label}')
    with zipfile.ZipFile(io.BytesIO(data)) as library:
        for info in library.infolist():
            if info.is_dir():
                continue
            path = PurePosixPath(info.filename)
            if (not info.filename.startswith(prefix + '/')
                    or (path.suffix.casefold() not in TCL_RESOURCE_SUFFIXES | {'.terms', '.gif', '.eps'}
                        and info.filename != 'tcl_library/cookiejar/public_suffix_list.dat.gz')):
                raise ValueError(f'Unreviewed Tcl/Tk embedded runtime resource: {label}/{info.filename}')
            if info.filename.endswith('.gz'):
                decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
                try:
                    content = decoder.decompress(library.read(info), 32 * 1024 * 1024 + 1)
                except zlib.error as error:
                    raise ValueError(f'Invalid Tcl embedded compressed resource: {label}/{info.filename}') from error
                if len(content) > 32 * 1024 * 1024 or not decoder.eof or decoder.unused_data:
                    raise ValueError(f'Unbounded Tcl embedded compressed resource: {label}/{info.filename}')
                scan_bundled_data(label + '/' + info.filename, content)


def _validate_runtime_file(name, data, expected):
    """Apply the same resource/native/privacy rules inside either distribution."""
    normalized, relative = _bundled_path(name)
    if _is_distribution_metadata(relative):
        if normalized not in RUNTIME_DEPENDENCY_METADATA:
            raise ValueError(f'Unreviewed dependency metadata in runtime: {name}')
        if hashlib.sha256(data).hexdigest() != RUNTIME_DEPENDENCY_METADATA[normalized]:
            raise ValueError(f'Bundled dependency metadata differs from the pinned wheel: {name}')
        scan_bundled_data(name, data)
        return normalized
    if normalized in TRIMESH_RESOURCES:
        if hashlib.sha256(data).hexdigest() != TRIMESH_RESOURCES[normalized]:
            raise ValueError(f'Bundled trimesh resource differs from the pinned wheel: {name}')
        scan_bundled_data(name, data)
        return normalized
    if relative.suffix.casefold() == '.json' and normalized not in expected:
        raise ValueError(f'Unreviewed JSON data in runtime: {name}')
    if normalized in expected:
        if data != expected[normalized]:
            raise ValueError(f'Bundled metadata differs from manifest: {name}')
    elif normalized == 'base_library.zip':
        _verify_library_zip(name, data, require_stdlib=True)
    elif relative.suffix.casefold() in {'.dll', '.pyd'}:
        approved = (normalized in TCL_PACKAGE_DLLS
                    or (relative.suffix.casefold() == '.dll' and len(relative.parts) == 1
                        and NATIVE_DLL.fullmatch(relative.name))
                    or (relative.suffix.casefold() == '.dll' and normalized in NUMPY_DLLS)
                    or (relative.suffix.casefold() == '.pyd' and (
                        len(relative.parts) == 1 and relative.stem in STDLIB_EXTENSIONS
                        or len(relative.parts) == 1 and ASSET_EXTENSION.fullmatch(relative.name)
                        or NUMPY_EXTENSION.fullmatch(normalized))))
        if not approved or not data.startswith(b'MZ'):
            raise ValueError(f'Unreviewed or invalid native runtime dependency: {name}')
        if normalized == 'tcl90.dll':
            _verify_tcl_zip(name, data, 'tcl_library', 'init.tcl')
        elif normalized == 'tcl9tk90.dll':
            _verify_tcl_zip(name, data, 'tk_library', 'tk.tcl')
    elif relative.parts[0] not in {'_tcl_data', '_tk_data'} or relative.suffix.casefold() not in TCL_RESOURCE_SUFFIXES:
        raise ValueError(f'Unreviewed runtime file: {name}')
    scan_bundled_data(name, data)
    return normalized


def _validate_runtime_inventory(entries, expected):
    required = {'base_library.zip', '_tkinter.pyd'}
    if 'tcl90.dll' in entries or 'tcl9tk90.dll' in entries:
        required.update({'tcl90.dll', 'tcl9tk90.dll', 'libtommath.dll', 'zlib1.dll'})
    else:
        required.update({'tcl86t.dll', 'tk86t.dll', '_tcl_data/init.tcl', '_tk_data/tk.tcl'})
    required.update(expected)
    required.update(TRIMESH_RESOURCES)
    required.update(RUNTIME_DEPENDENCY_METADATA)
    missing = required - entries.keys()
    if len([name for name in entries if re.fullmatch(r'python3\d+\.dll', name)]) != 1:
        missing.add('one versioned CPython runtime DLL')
    if missing:
        raise ValueError('Verified metadata missing from executable or runtime dependencies missing: '
                         + ', '.join(sorted(missing)))


def _runtime_snapshot(root, sources):
    """Capture the complete portable runtime, rejecting unsafe paths."""
    root = root.resolve()
    folder = _repo_path(root, runtime_directory(root).relative_to(root).as_posix())
    if not folder.is_dir():
        raise ValueError('The complete portable runtime folder is missing; rebuild with --onedir.')
    expected = embedded_metadata(sources)
    launcher = executable_path(root).name
    entries, internal_entries, seen = {}, {}, set()
    for path in sorted(folder.rglob('*')):
        name = path.relative_to(folder).as_posix()
        if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()):
            raise ValueError(f'Runtime path escapes the portable folder or is a symlink: {name}')
        if name.casefold() in seen:
            raise ValueError(f'Duplicate runtime path: {name}')
        seen.add(name.casefold())
        if path.is_dir():
            if name != '_internal' and not name.startswith('_internal/'):
                raise ValueError(f'Unexpected directory in portable runtime: {name}')
            _bundled_path(name)
            continue
        if not path.is_file():
            raise ValueError(f'Non-regular file in portable runtime: {name}')
        data = path.read_bytes()
        if name == launcher:
            if not data.startswith(b'MZ'):
                raise ValueError('The built executable is not a Windows executable.')
            scan_bundled_data(name, data)
        else:
            normalized, _ = _bundled_path(name)
            if not normalized.startswith('_internal/'):
                raise ValueError(f'Unexpected external runtime file: {name}')
            internal = _validate_runtime_file(normalized.removeprefix('_internal/'), data, expected)
            internal_entries[internal] = data
        entries[name] = data
    if launcher not in entries:
        raise ValueError('The portable launcher is missing.')
    _validate_runtime_inventory(internal_entries, expected)
    return entries


def _verify_archive(executable, sources, archive_reader=None, require_complete_runtime=False):
    if archive_reader is None:
        from PyInstaller.archive.readers import CArchiveReader
        archive_reader = CArchiveReader
    archive, seen, runtime = archive_reader(str(executable)), set(), {}
    expected = embedded_metadata(sources)
    for name, entry in archive.toc.items():
        normalized, path = _bundled_path(name)
        if normalized.casefold() in seen:
            raise ValueError(f'Duplicate file in executable archive: {name}')
        seen.add(normalized.casefold())
        if (path.suffix.lower() == '.json' and normalized not in expected
                and normalized not in TRIMESH_RESOURCES):
            raise ValueError(f'Unreviewed JSON data in executable archive: {name}')
        data = archive.extract(name)
        scan_bundled_data(name, data)
        if _is_distribution_metadata(path):
            _validate_runtime_file(normalized, data, expected)
        if normalized in expected and data != expected[normalized]:
            raise ValueError(f'Bundled metadata differs from manifest: {name}')
        if entry[-1] == 'z':
            pyz = archive.open_embedded_archive(name)
            for module in pyz.toc:
                if any(part.casefold() in {'tests', 'fixtures', 'source-fixtures'} for part in module.split('.')):
                    raise ValueError(f'Private or unsafe module in executable archive: {module}')
                scan_bundled_data(module, pyz.extract(module, raw=True))
        elif require_complete_runtime and entry[-1] in {'b', 'x'}:
            if type(data) is not bytes:
                raise ValueError(f'Invalid standalone embedded runtime data: {name}')
            internal = _validate_runtime_file(normalized, data, expected)
            runtime[internal] = data
        elif normalized in TRIMESH_RESOURCES:
            _validate_runtime_file(normalized, data, expected)
        elif path.suffix == '.zip':
            _verify_library_zip(name, data)
        elif path.suffix.casefold() in {'.dll', '.pyd'}:
            if type(data) is not bytes:
                raise ValueError(f'Invalid embedded native runtime data: {name}')
            _validate_runtime_file(normalized, data, expected)
    if not any(entry[-1] == 'z' for entry in archive.toc.values()):
        raise ValueError('The executable is missing its embedded Python module archive.')
    if require_complete_runtime:
        _validate_runtime_inventory(runtime, expected)
    return len(archive.toc)


def verify_executable(root=ROOT, archive_reader=None):
    root = root.resolve()
    _, sources = verified_sources(root)
    runtime = _runtime_snapshot(root, sources)
    count = _verify_archive(executable_path(root), sources, archive_reader)
    if runtime != _runtime_snapshot(root, sources):
        raise ValueError('Portable runtime changed during validation; rebuild before packaging.')
    return count


def _standalone_snapshot(root):
    root = root.resolve()
    path = _repo_path(root, standalone_executable_path(root).relative_to(root).as_posix())
    if not path.is_file():
        raise ValueError('The self-contained standalone executable is missing; build with --standalone.')
    binary = path.read_bytes()
    if not binary.startswith(b'MZ'):
        raise ValueError('The standalone executable is not a Windows executable.')
    scan_bundled_data('standalone executable', binary)
    return binary


def verify_standalone(root=ROOT, archive_reader=None):
    root = root.resolve()
    _, sources = verified_sources(root)
    binary = _standalone_snapshot(root)
    count = _verify_archive(standalone_executable_path(root), sources, archive_reader, require_complete_runtime=True)
    if binary != _standalone_snapshot(root):
        raise ValueError('Standalone executable changed during validation; rebuild before packaging.')
    return count


def _cli_snapshot(root):
    root = root.resolve()
    path = _repo_path(root, cli_executable_path(root).relative_to(root).as_posix())
    if not path.is_file():
        raise ValueError('The console CLI executable is missing; build with --cli.')
    binary = path.read_bytes()
    # Do not accept a renamed windowed GUI executable as the console download.
    header = int.from_bytes(binary[0x3c:0x40], 'little') if len(binary) >= 0x40 else -1
    if (not binary.startswith(b'MZ') or header < 0x40 or header > len(binary) - 94
            or binary[header:header + 4] != b'PE\0\0'
            or int.from_bytes(binary[header + 4:header + 6], 'little') != 0x8664):
        raise ValueError('The CLI executable is not a 64-bit Windows PE executable.')
    optional_size = int.from_bytes(binary[header + 20:header + 22], 'little')
    optional = header + 24
    if (optional_size < 70 or optional + optional_size > len(binary)
            or int.from_bytes(binary[optional:optional + 2], 'little') != 0x20b
            or int.from_bytes(binary[optional + 68:optional + 70], 'little') != 3):
        raise ValueError('The CLI executable must use the Windows console subsystem.')
    scan_bundled_data('CLI executable', binary)
    return binary


def verify_cli(root=ROOT, archive_reader=None):
    root = root.resolve()
    _, sources = verified_sources(root)
    binary = _cli_snapshot(root)
    count = _verify_archive(cli_executable_path(root), sources, archive_reader, require_complete_runtime=True)
    if binary != _cli_snapshot(root):
        raise ValueError('CLI executable changed during validation; rebuild before packaging.')
    return count


def package(root=ROOT, output=None):
    root = root.resolve()
    _, sources = verified_sources(root)
    name = artifact_name(root)
    runtime = _runtime_snapshot(root, sources)
    verify_executable(root)
    if runtime != _runtime_snapshot(root, sources):
        raise ValueError('Portable runtime changed during validation; rebuild before packaging.')
    standalone = _standalone_snapshot(root)
    verify_standalone(root)
    if standalone != _standalone_snapshot(root):
        raise ValueError('Standalone executable changed during validation; rebuild before packaging.')
    cli = _cli_snapshot(root)
    verify_cli(root)
    if cli != _cli_snapshot(root):
        raise ValueError('CLI executable changed during validation; rebuild before packaging.')
    output = Path(output) if output is not None else root / 'release'
    assets = [output / f'{name}-Windows.zip', output / f'{name}-Source.zip',
              output / f'{name}.exe', output / f'{name}-CLI.exe', output / 'SHA256SUMS.txt']
    if any(path.exists() for path in assets):
        raise ValueError('Release outputs already exist; choose a new output directory.')
    # The user ZIP is exactly the validated application folder, including the
    # explicitly reviewed user guides. Developer/repository documents stay in Source.
    windows = {name + '/' + path: data for path, data in runtime.items()}
    prefix = f'{name}-Source/'
    output.mkdir(parents=True, exist_ok=True)
    write_zip(assets[0], windows)
    write_zip(assets[1], {prefix + path: data for path, data in sources.items()})
    with assets[2].open('xb') as stream:
        stream.write(standalone)
    if assets[2].read_bytes() != standalone or _standalone_snapshot(root) != standalone:
        raise ValueError('Standalone executable changed during release copying; do not publish these outputs.')
    with assets[3].open('xb') as stream:
        stream.write(cli)
    if assets[3].read_bytes() != cli or _cli_snapshot(root) != cli:
        raise ValueError('CLI executable changed during release copying; do not publish these outputs.')
    with assets[4].open('x', encoding='ascii', newline='\n') as stream:
        for path in assets[:4]:
            stream.write(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n')
    return assets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='store_true', help='Print the matching app/build/project release version.')
    parser.add_argument('--executable-path', action='store_true', help='Print the portable Windows launcher path.')
    parser.add_argument('--bundle-path', action='store_true', help='Print the complete portable Windows runtime folder.')
    parser.add_argument('--standalone-path', action='store_true', help='Print the self-contained standalone EXE path.')
    parser.add_argument('--cli-path', action='store_true', help='Print the self-contained console CLI EXE path.')
    parser.add_argument('--verify-cli', action='store_true', help='Validate the complete embedded console CLI runtime.')
    parser.add_argument('--verify-standalone', action='store_true', help='Validate the complete embedded standalone runtime.')
    parser.add_argument('--verify-only', action='store_true', help='Validate public source hashes without creating archives.')
    parser.add_argument('--verify-executable', action='store_true', help='Inspect the built runtime archive (requires PyInstaller).')
    parser.add_argument('--output', type=Path, help='New release output directory (default: release).')
    arguments = parser.parse_args()
    if arguments.version:
        print(version())
    elif arguments.executable_path:
        print(executable_path())
    elif arguments.bundle_path:
        print(runtime_directory())
    elif arguments.standalone_path:
        print(standalone_executable_path())
    elif arguments.cli_path:
        print(cli_executable_path())
    elif arguments.verify_cli:
        print(f'Verified {verify_cli()} CLI archive entries and the complete embedded runtime.')
    elif arguments.verify_standalone:
        print(f'Verified {verify_standalone()} standalone archive entries and the complete embedded runtime.')
    elif arguments.verify_executable:
        print(f'Verified the portable runtime and {verify_executable()} launcher archive entries.')
    elif arguments.verify_only:
        release_version, sources = verified_sources()
        print(f'v{release_version}: verified {len(sources) - 1} public source files.')
    else:
        for path in package(output=arguments.output):
            print(path.name)


if __name__ == '__main__':
    main()
