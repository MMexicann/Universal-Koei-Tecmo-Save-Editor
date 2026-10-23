"""Install the exact reviewed Linux build interpreter into a new work directory.

This bootstrap uses only the host Python standard library. It never installs a
global launcher, modifies a supplied archive or accepts an arbitrary download.
"""
import argparse
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import platform
import posixpath
import stat
import sys
import tarfile
import urllib.request
import zlib

ROOT = Path(__file__).resolve().parents[1]
PYTHON_VERSION = '3.13.13'
ARCHIVE_URL = ('https://github.com/astral-sh/python-build-standalone/releases/download/20260602/'
               'cpython-3.13.13%2B20260602-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz')
ARCHIVE_SHA256 = 'c249d2b96af6912c3910f234b96aa8d20d30e8b0c46d0584fa956d7a77036ea9'
ARCHIVE_BYTES = 34904739
ARCHIVE_NAME = 'cpython-3.13.13-linux-x86_64.tar.gz'
MAX_TAR_BYTES = 160 * 1024 * 1024
MAX_MEMBERS = 10000
MAX_FILE_BYTES = 64 * 1024 * 1024


def _ordinary(path):
    for parent in (path, *path.parents):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise ValueError('Build interpreter folders must be ordinary directories.')


def _work_path(path):
    selected = Path(os.path.abspath(path))
    root = ROOT.resolve(strict=True)
    _ordinary(root)
    work = root / 'work'
    if not selected.is_relative_to(work) or selected == work or selected.resolve() != selected:
        raise ValueError('Choose an ordinary new build folder inside the checkout work directory.')
    return selected


def _open_folder(path, *, create_work=False):
    """Retain a nofollow chain from the filesystem root before any writes."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open('/', flags)
    current = Path('/')
    try:
        for name in Path(path).parts[1:]:
            current = current / name
            try:
                child = os.open(name, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create_work or current != ROOT.resolve(strict=True) / 'work':
                    raise
                os.mkdir(name, mode=0o700, dir_fd=descriptor)
                child = os.open(name, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _name(value):
    path = PurePosixPath(value)
    if (type(value) is not str or not value or '\\' in value or ':' in value
            or any(ord(c) < 32 for c in value) or path.is_absolute()
            or any(part in ('', '.', '..') for part in value.split('/'))
            or path.parts[0] != 'python'):
        raise ValueError('Unsafe build interpreter archive path.')
    return path


def _validated_members(data):
    if type(data) is not bytes or not data or len(data) > ARCHIVE_BYTES:
        raise ValueError('Build interpreter archive exceeds its compressed bound.')
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        raw = decoder.decompress(data, MAX_TAR_BYTES + 1)
    except zlib.error:
        raise ValueError('Invalid build interpreter compression.') from None
    if len(raw) > MAX_TAR_BYTES or not decoder.eof or decoder.unused_data:
        raise ValueError('Build interpreter archive exceeds its decompression bound.')
    archive = tarfile.open(fileobj=io.BytesIO(raw), mode='r:')
    records, directories, total = {}, {''}, 0
    try:
        for member in archive:
            path = _name(member.name.rstrip('/') if member.isdir() else member.name)
            name = str(path)
            if (name in records or len(records) >= MAX_MEMBERS or member.pax_headers
                    or member.sparse is not None
                    or member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE, tarfile.SYMTYPE)
                    or not 0 <= member.size <= MAX_FILE_BYTES or member.mode & 0o7000):
                raise ValueError('Unreviewed build interpreter archive member.')
            total += member.size
            if total > MAX_TAR_BYTES:
                raise ValueError('Build interpreter members exceed the total size bound.')
            records[name] = member
            directories.update(str(parent) for parent in path.parents if str(parent) != '.')
            if member.isdir():
                directories.add(name)
        for directory in directories - {''}:
            if directory in records and not records[directory].isdir():
                raise ValueError('Archive entries cannot traverse a file or link.')
        interpreter = records.get('python/bin/python3.13')
        if interpreter is None or not interpreter.isfile() or not interpreter.mode & 0o111:
            raise ValueError('The build interpreter archive is incomplete.')
        for name, member in records.items():
            if not member.issym():
                continue
            target = member.linkname
            if (not target or target.startswith('/') or '\\' in target or ':' in target
                    or any(ord(c) < 32 for c in target)):
                raise ValueError('Build interpreter links must remain inside its tree.')
            current, visited = name, set()
            while current in records and records[current].issym():
                if current in visited or len(visited) >= 64:
                    raise ValueError('Cyclic build interpreter archive link.')
                visited.add(current)
                current = posixpath.normpath(posixpath.join(posixpath.dirname(current), records[current].linkname))
                _name(current)
            if current not in records and current not in directories:
                raise ValueError('Dangling build interpreter archive link.')
        return archive, records, directories
    except BaseException:
        archive.close()
        raise


def _extract(data, destination):
    """Validate the whole archive, then create only new fd-relative children."""
    archive, records, directories = _validated_members(data)
    descriptors = {}
    try:
        destination = _work_path(destination)
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        parent = _open_folder(destination.parent, create_work=True)
        try:
            os.mkdir(destination.name, mode=0o700, dir_fd=parent)
            descriptors[''] = os.open(destination.name, flags, dir_fd=parent)
        finally:
            os.close(parent)
        for name in sorted(directories - {''}, key=lambda n: (len(PurePosixPath(n).parts), n)):
            path = PurePosixPath(name)
            parent_name = str(path.parent) if str(path.parent) != '.' else ''
            os.mkdir(path.name, mode=0o755, dir_fd=descriptors[parent_name])
            descriptors[name] = os.open(path.name, flags, dir_fd=descriptors[parent_name])
        for name, member in records.items():
            if not member.isfile():
                continue
            path = PurePosixPath(name)
            fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=descriptors[str(path.parent)])
            with os.fdopen(fd, 'wb') as output, archive.extractfile(member) as source:
                remaining = member.size
                while remaining:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValueError('Truncated build interpreter member.')
                    output.write(chunk)
                    remaining -= len(chunk)
                output.flush()
                os.fchmod(output.fileno(), member.mode & 0o777)
        for name, member in records.items():
            if member.issym():
                path = PurePosixPath(name)
                os.symlink(member.linkname, path.name, dir_fd=descriptors[str(path.parent)])
        for name, fd in descriptors.items():
            path = destination / name
            _ordinary(path)
            current, held = path.stat(), os.fstat(fd)
            if (current.st_dev, current.st_ino) != (held.st_dev, held.st_ino):
                raise ValueError('Build interpreter folder changed during extraction.')
        return destination / 'python/bin/python3.13'
    finally:
        for fd in reversed(list(descriptors.values())):
            os.close(fd)
        archive.close()


def _verified(data):
    if len(data) != ARCHIVE_BYTES or hashlib.sha256(data).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('Build interpreter archive does not match the reviewed SHA-256.')
    return data


def install(destination, cache):
    if sys.platform != 'linux' or platform.machine().lower() not in ('x86_64', 'amd64'):
        raise ValueError('This reviewed build interpreter requires native Linux x86_64.')
    destination, cache = _work_path(destination), _work_path(cache)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('Build interpreter destination must be new.')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent_fd = _open_folder(cache.parent, create_work=True)
    try:
        try:
            os.mkdir(cache.name, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
        cache_fd = os.open(cache.name, flags, dir_fd=parent_fd)
    finally:
        os.close(parent_fd)
    try:
        try:
            fd = os.open(ARCHIVE_NAME, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=cache_fd)
        except FileNotFoundError:
            # urllib retains the host's proxy and CA configuration.
            with urllib.request.urlopen(ARCHIVE_URL, timeout=30) as response:
                data = _verified(response.read(ARCHIVE_BYTES + 1))
            fd = os.open(ARCHIVE_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=cache_fd)
            with os.fdopen(fd, 'wb') as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
        else:
            with os.fdopen(fd, 'rb') as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise ValueError('Cached build interpreter must be an ordinary file.')
                data = _verified(source.read(ARCHIVE_BYTES + 1))
        return _extract(data, destination)
    finally:
        os.close(cache_fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=ROOT / 'work/linux-python')
    parser.add_argument('--cache', type=Path, default=ROOT / 'work/linux-python-cache')
    args = parser.parse_args(argv)
    interpreter = install(args.destination, args.cache)
    print(interpreter.relative_to(ROOT.resolve()).as_posix())


if __name__ == '__main__':
    main()
