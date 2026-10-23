"""Build the portable folder or a complete standalone Windows executable."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile

from koei_editor.game_registry import ALL_ADAPTERS
from koei_editor.conversion import ENDPOINTS
from koei_editor.research.imports import PROFILES as RESEARCH_PROFILES
from tools.package_release import RUNTIME_DATA, RUNTIME_LICENSES, RUNTIME_GUIDES

ROOT = Path(__file__).resolve().parents[1]
VERSION = '3.1'
DATA = [(f'src/koei_editor/data/{name}', 'koei_editor/data') for name in RUNTIME_DATA] + [
    ('LICENSE', 'licenses'), ('docs/THIRD_PARTY_NOTICES.md', 'licenses'),
    ('licenses/atelier-sophie2-save-editor-MIT.txt', 'licenses'),
    ('licenses/katana-save-data-resigner-MIT.txt', 'licenses')]
DATA += [(source, 'licenses') for source in RUNTIME_LICENSES]
DATA += [(source, 'guides') for source in RUNTIME_GUIDES]


@contextmanager
def with_numpy_metadata_only(site_packages=None):
    """Expose only NumPy's version metadata to PyInstaller, then restore its install."""
    if site_packages is None:
        import numpy
        site_packages = Path(numpy.__file__).resolve().parent.parent
    else:
        site_packages = Path(site_packages).resolve()

    candidates = tuple(site_packages.glob('numpy-*.dist-info'))
    if len(candidates) > 1:
        raise RuntimeError('Multiple NumPy distribution metadata directories found.')
    if not candidates or candidates[0].is_symlink() or not candidates[0].is_dir():
        raise RuntimeError('NumPy distribution metadata directory is missing or unsafe.')

    metadata_dir = candidates[0]
    version_metadata = metadata_dir / 'METADATA'
    if version_metadata.is_symlink() or not version_metadata.is_file():
        raise RuntimeError('NumPy version metadata is missing or unsafe.')
    # PyInstaller may copy the complete dist-info directory. Keep METADATA for
    # its build-time version lookup, but exclude runner paths, RECORD, and
    # unreviewed package data from both frozen payloads.
    with tempfile.TemporaryDirectory(prefix='koei-numpy-metadata-', dir=site_packages) as temporary:
        saved_dir = Path(temporary) / metadata_dir.name
        saved_dir.mkdir()
        hidden = []
        try:
            for entry in metadata_dir.iterdir():
                if entry.name == 'METADATA':
                    continue
                if entry.is_symlink():
                    raise RuntimeError('NumPy distribution metadata contains a symlink.')
                saved = saved_dir / entry.name
                os.replace(entry, saved)
                hidden.append((saved, entry))
            yield
        finally:
            for saved, original in reversed(hidden):
                os.replace(saved, original)


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
    with with_numpy_metadata_only():
        run(build_args(standalone=arguments.standalone))


if __name__ == '__main__':
    main()
