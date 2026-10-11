"""Build one standalone Windows application with all registered game interfaces."""
import argparse
import json
import os
from pathlib import Path

from koei_editor.game_registry import ALL_ADAPTERS
from tools.package_release import RUNTIME_DATA

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.7'
DATA = [(f'src/koei_editor/data/{name}', 'koei_editor/data') for name in RUNTIME_DATA] + [
    ('LICENSE', '.'), ('docs/THIRD_PARTY_NOTICES.md', '.'),
    ('licenses/atelier-sophie2-save-editor-MIT.txt', 'licenses'),
    ('licenses/katana-save-data-resigner-MIT.txt', 'licenses')]


def build_args(root=ROOT):
    args = ['--noconfirm', '--onefile', '--windowed', '--name',
            f'UniversalKoeiTecmoSaveEditor-v{VERSION}', '--paths', str(root / 'src'),
            '--distpath', str(root / 'dist'), '--workpath', str(root / 'build'),
            '--specpath', str(root / 'build')]
    for source, destination in DATA:
        args.extend(['--add-data', str(root / source) + os.pathsep + destination])
    for game in ALL_ADAPTERS:
        for module in dict.fromkeys((game.editor_module, game.parser_module, game.scalar_backend)):
            if module is not None:
                args.extend(['--hidden-import', module])
    # The thin launcher uses an absolute package import. __main__.py remains
    # the module entry point, whose relative imports need python -m context.
    args.append(str(root / 'launch.pyw'))
    return args


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--print-config', action='store_true', help='Inspect build inputs without compiling.')
    arguments = parser.parse_args()
    if arguments.print_config:
        print(json.dumps(build_args(), indent=2))
        return
    if os.name != 'nt':
        raise SystemExit('Build the Windows EXE on 64-bit Windows for the native CNG/Tk runtime.')
    from tools.package_release import verified_sources
    verified_sources(ROOT)
    from PyInstaller.__main__ import run
    run(build_args())


if __name__ == '__main__':
    main()
