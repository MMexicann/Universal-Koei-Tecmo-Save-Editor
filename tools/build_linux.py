"""Build the native Linux x86_64 portable GUI and command-line editions."""
import argparse
import ast
import json
import platform
from pathlib import Path
import sys

from tools import build_windows
from tools import package_release as release

ROOT = Path(__file__).resolve().parents[1]
LINUX_LICENSES = ('licenses/numpy-Linux-wheel.txt', 'licenses/pycryptodome-BSD-Public-Domain.txt')


def artifact_name(root=ROOT, *, cli=False):
    return release.artifact_name(root) + '-Linux-x86_64' + ('-CLI' if cli else '')


def build_args(root=ROOT, *, cli=False):
    """Reuse the reviewed game imports/resources, with separate native outputs."""
    root = Path(root)
    args = build_windows.build_args(root, cli=False)
    name = artifact_name(root, cli=cli)
    for flag, value in (('--name', name), ('--distpath', str(root / 'dist-linux')),
                        ('--workpath', str(root / 'work/linux-build' / name)),
                        ('--specpath', str(root / 'work/linux-build' / name))):
        args[args.index(flag) + 1] = value
    args[args.index('--windowed')] = '--console'
    # This hook directory precedes the Windows wheel's narrowly reviewed hooks.
    offset = args.index('--additional-hooks-dir')
    args[offset:offset] = ['--additional-hooks-dir', str(root / 'tools/linux_hooks')]
    for dependency in ('pycryptodome',):
        args.extend(['--copy-metadata', dependency])
    for module in ('koei_editor.cli', 'Crypto.Cipher.AES'):
        args.extend(['--hidden-import', module])
    for module in ('cryptography', 'Crypto.SelfTest', 'Crypto.Hash', 'Crypto.Math',
                   'Crypto.Protocol', 'Crypto.PublicKey', 'Crypto.Signature', 'Crypto.IO',
                   *('Crypto.Cipher._mode_' + mode for mode in (
                       'cfb', 'ofb', 'ctr', 'openpgp', 'eax', 'ccm', 'siv', 'gcm', 'ocb', 'kw', 'kwp'))):
        args.extend(['--exclude-module', module])
    for source in LINUX_LICENSES:
        args.extend(['--add-data', str(root / source) + ':licenses'])
    args.extend(['--add-data', str(root / 'docs/LINUX.md') + ':guides'])
    # Always leave the script as the final argument for PyInstaller's parser.
    script = args.pop(args.index(str(root / 'launch.pyw')))
    args.append(str(root / 'src/koei_editor/cli.py') if cli else script)
    return args


def filter_build_spec(spec_path, root=ROOT):
    spec_path = Path(spec_path)
    source = spec_path.read_text(encoding='utf-8')
    analyses = [node for node in ast.parse(source).body if isinstance(node, ast.Assign)
                and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == 'a' and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == 'Analysis']
    if len(analyses) != 1 or 'filter_linux_metadata' in source:
        raise ValueError('Unexpected Linux PyInstaller specification.')
    lines = source.splitlines(keepends=True)
    lines[analyses[0].end_lineno:analyses[0].end_lineno] = [
        '\nfrom tools.linux_build_review import filter_linux_metadata\n',
        f'a.datas = filter_linux_metadata(a.datas, root={str(Path(root))!r})\n',
        # System libraries remain supplied and patched by the Linux distribution.
        # Wheel-native libraries, lib-dynload and CPython remain self-contained.
        "a.exclude_system_libraries(list_of_exceptions=['libpython*'])\n",
    ]
    spec_path.write_text(''.join(lines), encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', action='store_true', help='Build the separate headless CLI folder.')
    parser.add_argument('--print-config', action='store_true')
    arguments = parser.parse_args(argv)
    if arguments.print_config:
        print(json.dumps(build_args(cli=arguments.cli), indent=2))
        return
    if sys.platform != 'linux' or platform.machine().lower() not in {'x86_64', 'amd64'}:
        raise SystemExit('Build on native 64-bit x86 Linux; cross-compilation is unsupported.')
    if sys.version_info[:2] != (3, 13):
        raise SystemExit('The reviewed Linux wheel lock requires CPython 3.13.')
    from tools.linux_build_review import verify_linux_lock
    release.verified_sources(ROOT)
    verify_linux_lock(ROOT)
    from PyInstaller.__main__ import generate_parser, run_makespec, run
    options = vars(generate_parser().parse_args(build_args(cli=arguments.cli)))
    spec_path = run_makespec(options.pop('filenames'), **options)
    filter_build_spec(spec_path)
    run(['--noconfirm', '--distpath', options['distpath'], '--workpath', options['workpath'], spec_path])


if __name__ == '__main__':
    main()
