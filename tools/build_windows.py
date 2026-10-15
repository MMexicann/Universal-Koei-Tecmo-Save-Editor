"""Build the portable folder or a complete standalone Windows executable."""
import argparse
import json
import os
from pathlib import Path

from koei_editor.game_registry import ALL_ADAPTERS
from koei_editor.conversion import ENDPOINTS
from tools.package_release import RUNTIME_DATA, RUNTIME_LICENSES, RUNTIME_GUIDES

ROOT = Path(__file__).resolve().parents[1]
VERSION = '2.5.1'
DATA = [(f'src/koei_editor/data/{name}', 'koei_editor/data') for name in RUNTIME_DATA] + [
    ('LICENSE', 'licenses'), ('docs/THIRD_PARTY_NOTICES.md', 'licenses'),
    ('licenses/atelier-sophie2-save-editor-MIT.txt', 'licenses'),
    ('licenses/katana-save-data-resigner-MIT.txt', 'licenses')]
DATA += [(source, 'licenses') for source in RUNTIME_LICENSES]
DATA += [(source, 'guides') for source in RUNTIME_GUIDES]


def build_args(root=ROOT, *, standalone=False):
    mode = ['--onefile'] if standalone else ['--onedir', '--contents-directory', '_internal']
    suffix = '-standalone' if standalone else ''
    args = ['--noconfirm', *mode, '--noupx', '--windowed', '--name',
            f'UniversalKoeiTecmoSaveEditor-v{VERSION}', '--paths', str(root / 'src'),
            '--distpath', str(root / ('dist' + suffix)), '--workpath', str(root / ('build' + suffix)),
            '--specpath', str(root / ('build' + suffix))]
    for source, destination in DATA:
        args.extend(['--add-data', str(root / source) + os.pathsep + destination])
    for game in ALL_ADAPTERS:
        for module in dict.fromkeys((game.editor_module, game.parser_module, game.scalar_backend)):
            if module is not None:
                args.extend(['--hidden-import', module])
    for endpoint in ENDPOINTS.values():
        if endpoint.conversion_only:
            args.extend(['--hidden-import', endpoint.backend.__name__])
    # The thin launcher uses an absolute package import. __main__.py remains
    # the module entry point, whose relative imports need python -m context.
    args.append(str(root / 'launch.pyw'))
    return args


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--print-config', action='store_true', help='Inspect build inputs without compiling.')
    parser.add_argument('--standalone', action='store_true',
                        help='Build the self-contained EXE separately from the portable folder.')
    arguments = parser.parse_args()
    if arguments.print_config:
        print(json.dumps(build_args(standalone=arguments.standalone), indent=2))
        return
    if os.name != 'nt':
        raise SystemExit('Build the Windows EXE on 64-bit Windows for the native CNG/Tk runtime.')
    from tools.package_release import verified_sources
    verified_sources(ROOT)
    from PyInstaller.__main__ import run
    run(build_args(standalone=arguments.standalone))


if __name__ == '__main__':
    main()
