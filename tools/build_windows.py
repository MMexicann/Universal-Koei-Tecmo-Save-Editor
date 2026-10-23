"""Build the portable folder or a complete standalone Windows executable."""
import argparse
import ast
import json
import os
from pathlib import Path

from koei_editor.game_registry import ALL_ADAPTERS
from koei_editor.conversion import ENDPOINTS
from koei_editor.research.imports import PROFILES as RESEARCH_PROFILES
from tools.package_release import (RUNTIME_DATA, RUNTIME_LICENSES, RUNTIME_GUIDES,
                                   RUNTIME_DEPENDENCY_METADATA)

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.0'
DATA = [(f'src/koei_editor/data/{name}', 'koei_editor/data') for name in RUNTIME_DATA] + [
    ('LICENSE', 'licenses'), ('docs/THIRD_PARTY_NOTICES.md', 'licenses'),
    ('licenses/atelier-sophie2-save-editor-MIT.txt', 'licenses'),
    ('licenses/katana-save-data-resigner-MIT.txt', 'licenses')]
DATA += [(source, 'licenses') for source in RUNTIME_LICENSES]
DATA += [(source, 'guides') for source in RUNTIME_GUIDES]


def build_args(root=ROOT, *, standalone=False, cli=False):
    if standalone and cli:
        raise ValueError("Choose either the standalone GUI or console CLI build.")
    mode = ['--onefile'] if standalone or cli else ['--onedir', '--contents-directory', '_internal']
    suffix = '-cli' if cli else '-standalone' if standalone else ''
    name = f'UniversalKoeiTecmoGameToolkit-v{VERSION}' + ('-CLI' if cli else '')
    args = ['--noconfirm', *mode, '--noupx', '--console' if cli else '--windowed', '--name',
            name, '--paths', str(root / 'src'),
            '--distpath', str(root / ('dist' + suffix)), '--workpath', str(root / ('build' + suffix)),
            '--specpath', str(root / ('build' + suffix))]
    if cli:
        args.extend(['--hidden-import', 'koei_editor.cli'])
    args.extend(['--additional-hooks-dir', str(root / 'tools' / 'pyinstaller_hooks')])
    # CFFI's optional compiler helpers reference packaging/build tools. Frozen
    # previews use precompiled decoders and never compile extensions at runtime.
    for module in ('setuptools', 'distutils', 'pkg_resources'):
        args.extend(['--exclude-module', module])
    # Interactive language-topic reference text is unused by the application.
    # Keep pydoc itself available for ordinary object documentation/introspection.
    args.extend(['--exclude-module', 'pydoc_data'])
    for name in RUNTIME_DEPENDENCY_METADATA:
        dependency = name.split('-')[0]
        args.extend(['--copy-metadata', dependency])
    for source, destination in DATA:
        args.extend(['--add-data', str(root / source) + os.pathsep + destination])
    for game in ALL_ADAPTERS:
        for module in dict.fromkeys((game.editor_module, game.parser_module,
                                     game.scalar_backend, getattr(game, 'achievement_source', None),
                                     getattr(game, 'workshop_module', None))):
            if module is not None:
                args.extend(['--hidden-import', module])
    for endpoint in ENDPOINTS.values():
        if endpoint.conversion_only:
            args.extend(['--hidden-import', endpoint.backend.__name__])
    for module in dict.fromkeys(profile.backend.__name__ for profile in RESEARCH_PROFILES.values()):
        args.extend(['--hidden-import', module])
    # These adapters are loaded on demand. Pin the dynamically selected
    # decoders/loaders so both frozen builds contain only the supported formats.
    for module in (
            'koei_editor.research.asset_explorer.gui',
            'koei_editor.research.asset_explorer.media',
            'miniaudio', '_miniaudio', 'cffi', '_cffi_backend', 'pycparser', 'numpy', 'trimesh',
            'trimesh.exchange.load',
            'trimesh.exchange.obj', 'trimesh.exchange.stl',
            'trimesh.exchange.ply', 'trimesh.exchange.gltf'):
        args.extend(['--hidden-import', module])
    # These tools are loaded only from Application's optional retained-tool route.
    args.extend(['--hidden-import', 'koei_editor.shared.configuration_manager',
                 '--hidden-import', 'koei_editor.shared.configuration_gui'])
    # The thin launcher uses an absolute package import. __main__.py remains
    # the module entry point, whose relative imports need python -m context.
    args.append(str(root / ('src/koei_editor/cli.py' if cli else 'launch.pyw')))
    return args


def filter_build_spec(spec_path, root=ROOT):
    """Insert the data review between generated Analysis and EXE/COLLECT."""
    spec_path = Path(spec_path)
    source = spec_path.read_text(encoding='utf-8')
    analyses = [node for node in ast.parse(source).body
                if isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'a'
                and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                and node.value.func.id == 'Analysis']
    if len(analyses) != 1 or 'filter_runtime_metadata' in source:
        raise ValueError('Unexpected generated PyInstaller build specification.')
    lines = source.splitlines(keepends=True)
    lines[analyses[0].end_lineno:analyses[0].end_lineno] = [
        '\nfrom tools.package_release import filter_runtime_metadata\n',
        f'a.datas = filter_runtime_metadata(a.datas, root={str(root)!r})\n',
    ]
    spec_path.write_text(''.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--print-config', action='store_true', help='Inspect build inputs without compiling.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--standalone', action='store_true',
                        help='Build the self-contained GUI EXE separately from the portable folder.')
    mode.add_argument('--cli', action='store_true', help='Build the separate self-contained console CLI EXE.')
    arguments = parser.parse_args()
    if arguments.print_config:
        print(json.dumps(build_args(standalone=arguments.standalone, cli=arguments.cli), indent=2))
        return
    if os.name != 'nt':
        raise SystemExit('Build the Windows EXE on 64-bit Windows for the native CNG/Tk runtime.')
    from tools.package_release import verified_sources, verify_dependency_metadata_lock
    verified_sources(ROOT)
    verify_dependency_metadata_lock(ROOT)
    from PyInstaller.__main__ import generate_parser, run_makespec, run
    options = vars(generate_parser().parse_args(build_args(standalone=arguments.standalone, cli=arguments.cli)))
    spec_path = run_makespec(options.pop('filenames'), **options)
    filter_build_spec(spec_path)
    run(['--noconfirm', '--distpath', options['distpath'], '--workpath', options['workpath'], spec_path])


if __name__ == '__main__':
    main()
