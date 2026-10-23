"""Verify and package the complete native Linux portable GUI and CLI folders."""
import argparse
import gzip
import hashlib
import io
import os
from pathlib import Path
import re
import stat
import tarfile
import zlib

from tools.build_linux import ROOT, LINUX_LICENSES, artifact_name
from tools.linux_build_review import AES_NATIVE_FILES, verify_linux_lock
from tools import package_release as release
from koei_editor.shared.copy_storage import publish_new_child_bound
from koei_editor.shared.save_safety import safe_path

# Distribution system libraries are deliberately excluded during Analysis.
# CPython's lib-dynload extensions and pinned wheel libraries are retained.
STDLIB_EXTENSIONS = release.STDLIB_EXTENSIONS | frozenset({
    '_posixsubprocess', '_posixshmem', '_resource', 'resource', 'fcntl', 'grp',
    'pwd', 'syslog', 'termios', '_curses', '_curses_panel', '_crypt', '_uuid',
    '_codecs_cn', '_codecs_hk', '_codecs_iso2022', '_codecs_jp', '_codecs_kr',
    '_codecs_tw', '_contextvars', '_multibytecodec', 'mmap', 'readline',
})
NATIVE_RUNTIME = re.compile(r'lib(?:python3\.13(?:\.so(?:\.1\.0)?)?|tcl(?:8\.6|9\.0|9tk9\.0)?\.so(?:\.[\d.]+)?|tk(?:8\.6|9\.0)?\.so(?:\.[\d.]+)?)\Z')
EXTENSION = re.compile(r'([A-Za-z_]\w*)\.(?:cpython-313-[\w-]+|abi3)\.so\Z')
TCL_COMPRESSED = frozenset({'_tcl_data/cookiejar0.2/public_suffix_list.dat.gz'})
TCL_MODULE = re.compile(r'tcl(?:8/8\.[456]|9/9\.0)/[A-Za-z0-9_./-]+\.tm\Z')
TK_IMAGES = frozenset('_tk_data/images/' + name for name in (
    'logo100.gif', 'tai-ku.gif', 'pwrdLogo.eps', 'pwrdLogo75.gif', 'pwrdLogo175.gif',
    'pwrdLogo150.gif', 'logoLarge.gif', 'logoMed.gif', 'pwrdLogo100.gif', 'logo.eps',
    'pwrdLogo200.gif', 'logo64.gif'))


def runtime_directory(root=ROOT, *, cli=False):
    return Path(root) / 'dist-linux' / artifact_name(root, cli=cli)


def _elf(data):
    return len(data) >= 20 and data[:6] == b'\x7fELF\x02\x01' and int.from_bytes(data[18:20], 'little') == 62


def _native_allowed(name, data, review):
    if not _elf(data):
        return False
    if name in review['native_wheel_files']:
        return hashlib.sha256(data).hexdigest() == review['native_wheel_files'][name]
    aliases = [digest for member, digest in review['native_wheel_files'].items()
               if '/' not in name and Path(member).name == name]
    if aliases:
        return len(aliases) == 1 and hashlib.sha256(data).hexdigest() == aliases[0]
    path = Path(name)
    if len(path.parts) == 1 and NATIVE_RUNTIME.fullmatch(name):
        return True
    match = EXTENSION.fullmatch(path.name)
    return bool(match and match[1] in STDLIB_EXTENSIONS and (
        len(path.parts) == 1 or path.parts[:-1] == ('python3.13', 'lib-dynload')))


def _tcl_resource(name, data):
    if name in TCL_COMPRESSED:
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        try:
            content = decoder.decompress(data, 32 * 1024 * 1024 + 1)
        except zlib.error:
            raise ValueError('Invalid compressed Tcl runtime resource.') from None
        if len(content) > 32 * 1024 * 1024 or not decoder.eof or decoder.unused_data:
            raise ValueError('Unbounded compressed Tcl runtime resource.')
        release.scan_bundled_data(name, content)
        return True
    return bool(name in TK_IMAGES or TCL_MODULE.fullmatch(name) or (
        Path(name).parts[0] in {'_tcl_data', '_tk_data'}
        and Path(name).suffix.casefold() in release.TCL_RESOURCE_SUFFIXES))


def _verify_modules(executable, sources):
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(executable))
    modules = set()
    for name, entry in archive.toc.items():
        release._bundled_path(name)
        data = archive.extract(name)
        release.scan_bundled_data(name, data)
        if entry[-1] == 'z':
            pyz = archive.open_embedded_archive(name)
            for module in pyz.toc:
                parts = module.split('.')
                if any(p.casefold() in {'tests', 'fixtures', 'source-fixtures'} for p in parts):
                    raise ValueError('Private test modules in the Linux executable.')
                if parts[0] == 'koei_editor':
                    prefix = 'src/' + module.replace('.', '/')
                    if prefix + '.py' not in sources and prefix + '/__init__.py' not in sources:
                        raise ValueError('Unreviewed application module in Linux executable.')
                release.scan_bundled_data(module, pyz.extract(module, raw=True))
                modules.add(module)
        elif entry[-1] not in {'m', 'M', 's', 'o'}:
            raise ValueError('Unexpected embedded Linux runtime payload.')
    if not {'koei_editor.application', 'koei_editor.cli', 'Crypto.Cipher.AES'} <= modules:
        raise ValueError('Linux executable is missing required application/provider modules.')


def runtime_snapshot(root, sources, *, cli=False):
    """Read only verified ordinary files; expand safe internal library aliases."""
    root = Path(root).resolve()
    folder = runtime_directory(root, cli=cli)
    if folder.is_symlink() or not folder.is_dir() or folder.resolve() != folder:
        raise ValueError('The complete ordinary Linux runtime folder is missing.')
    expected = release.embedded_metadata(sources)
    expected.update({name: sources[name] for name in LINUX_LICENSES})
    expected['guides/LINUX.md'] = sources['docs/LINUX.md']
    review = verify_linux_lock(root)
    launcher = artifact_name(root, cli=cli)
    entries, internal, seen = {}, {}, set()
    for path in sorted(folder.rglob('*')):
        name = path.relative_to(folder).as_posix()
        release._bundled_path(name)
        if name.casefold() in seen:
            raise ValueError('Duplicate Linux runtime path.')
        seen.add(name.casefold())
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(folder):
            raise ValueError('Linux runtime alias escapes its application folder.')
        if path.is_dir():
            if path.is_symlink() or (name != '_internal' and not name.startswith('_internal/')):
                raise ValueError('Unexpected Linux runtime directory.')
            continue
        if not stat.S_ISREG(resolved.stat().st_mode):
            raise ValueError('Non-regular Linux runtime file.')
        data = path.read_bytes()
        if name == launcher:
            if path.is_symlink() or not _elf(data) or not path.stat().st_mode & 0o111:
                raise ValueError('The native executable must be an executable x86_64 ELF file.')
            _verify_modules(path, sources)
        else:
            if not name.startswith('_internal/'):
                raise ValueError('Unexpected external Linux runtime file.')
            relative = name.removeprefix('_internal/')
            if relative in expected:
                if data != expected[relative]:
                    raise ValueError('Linux runtime resources differ from reviewed sources.')
            elif relative in review['runtime_metadata']:
                if hashlib.sha256(data).hexdigest() != review['runtime_metadata'][relative]:
                    raise ValueError('Linux runtime dependency metadata differs from its reviewed wheel.')
            elif relative in release.TRIMESH_RESOURCES:
                if hashlib.sha256(data).hexdigest() != release.TRIMESH_RESOURCES[relative]:
                    raise ValueError('Linux preview resource differs from its reviewed wheel.')
            elif relative == 'base_library.zip':
                release._verify_library_zip(name, data, require_stdlib=True)
            elif _native_allowed(relative, data, review):
                pass
            elif not path.is_symlink() and _tcl_resource(relative, data):
                pass
            else:
                raise ValueError('Unreviewed Linux runtime file: ' + relative)
            if path.is_symlink() and not _native_allowed(relative, data, review):
                raise ValueError('Only reviewed native library aliases may be expanded.')
            internal[relative] = data
        release.scan_bundled_data(name, data)
        entries[name] = data
    required = (set(expected) | set(review['runtime_metadata']) | set(release.TRIMESH_RESOURCES)
                | AES_NATIVE_FILES | {'base_library.zip'})
    if (launcher not in entries or required - internal.keys()
            or not any(Path(n).name.startswith('_tkinter.') for n in internal)
            or not any(Path(n).name.startswith('libpython3.13') for n in internal)):
        raise ValueError('Linux executable, Tk, Python or reviewed resources are incomplete.')
    return entries


def _new_file(path, data):
    selected = Path(os.path.abspath(path))
    if safe_path(path) != selected:
        raise ValueError('Release outputs cannot use path aliases.')
    try:
        selected.lstat()
    except FileNotFoundError:
        pass
    else:
        raise FileExistsError('Release outputs must be new files.')
    for parent in selected.parents:
        info = parent.lstat()
        if (not stat.S_ISDIR(info.st_mode) or getattr(info, 'st_file_attributes', 0)
                & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
            raise ValueError('Release outputs require an ordinary existing folder.')
    info = selected.parent.stat()
    return publish_new_child_bound(data, selected.parent, selected.name,
                                   (info.st_dev, info.st_ino), cleanup_pending_on_failure=True)


def write_tar(path, entries, top, launchers):
    """Write a reproducible archive with no owners, links, devices or timestamps."""
    release._bundled_path(top)
    if '/' in top or '\\' in top:
        raise ValueError('The archive root must be one ordinary name.')
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w', format=tarfile.USTAR_FORMAT) as archive:
            for name, data in sorted(entries.items()):
                release._bundled_path(name)
                info = tarfile.TarInfo(top + '/' + name)
                info.size = len(data)
                info.mode = 0o755 if name in launchers else 0o644
                archive.addfile(info, io.BytesIO(data))
    _new_file(path, raw.getvalue())


def package(root=ROOT, output=None, *, verify_only=False):
    root = Path(root).resolve()
    _version, sources = release.verified_sources(root)
    entries = runtime_snapshot(root, sources)
    cli_entries = runtime_snapshot(root, sources, cli=True)
    # Separate CLI tree keeps both PyInstaller launchers and their loader paths
    # intact. Compression deduplicates repeated bytes within the tar stream.
    entries.update({'cli/' + name: data for name, data in cli_entries.items()})
    if verify_only:
        return None
    output = Path(output) if output else root / 'release'
    if safe_path(output) != Path(os.path.abspath(output)):
        raise ValueError('Choose an ordinary release output folder.')
    output.mkdir(parents=True, exist_ok=True)
    name = artifact_name(root)
    archive = output / (name + '.tar.gz')
    checksums = output / (name + '.SHA256SUMS')
    if archive.exists() or archive.is_symlink() or checksums.exists() or checksums.is_symlink():
        raise FileExistsError('Linux release outputs must be new files.')
    write_tar(archive, entries, name, {name, 'cli/' + artifact_name(root, cli=True)})
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    _new_file(checksums, (digest + '  ' + archive.name + '\n').encode('ascii'))
    return archive


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--output', type=Path)
    arguments = parser.parse_args(argv)
    result = package(output=arguments.output, verify_only=arguments.verify_only)
    print(result.name if result else 'Native Linux GUI and CLI runtime verification passed.')


if __name__ == '__main__':
    main()
