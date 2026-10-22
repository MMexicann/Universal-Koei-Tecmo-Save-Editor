"""Immutable copy tools. No operation here overwrites an existing file."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import uuid
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.save_safety import reserved_windows_path, safe_path


def atomic_new(data, destination, *, mode=0o666):
    destination = safe_path(destination)
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name('.' + destination.name + '.' + uuid.uuid4().hex + '.tmp')
    identity = None
    try:
        # Keep verification on our owned handle. A replacement of the staging
        # pathname must not redirect verification into somebody else's file.
        with open(temporary, 'x+b', opener=lambda name, flags: os.open(
                name, flags | getattr(os, 'O_NOFOLLOW', 0), mode)) as stream:
            owned = os.fstat(stream.fileno())
            identity = (owned.st_dev, owned.st_ino)
            if stream.write(data) != len(data):
                raise SaveError('Temporary copy write was incomplete.')
            stream.flush()
            os.fsync(stream.fileno())
            stream.seek(0)
            if stream.read(len(data) + 1) != data:
                raise SaveError('Temporary copy verification failed.')
            current = temporary.lstat()
            if (not stat.S_ISREG(current.st_mode)
                    or (current.st_dev, current.st_ino) != identity):
                raise SaveError('Temporary copy changed before publication.')
        if os.name == 'nt':
            os.rename(temporary, destination)
        else:
            os.link(temporary, destination, follow_symlinks=False)
    finally:
        if identity is not None:
            try:
                current = temporary.lstat()
                if stat.S_ISREG(current.st_mode) and (current.st_dev, current.st_ino) == identity:
                    temporary.unlink()
            except FileNotFoundError:
                pass
    return destination


def new_child_bound(data, directory, name, expected_identity):
    """Create a new ordinary child while writes stay bound to its directory.

    This is for generated files inside freshly-created private directories.
    On systems with descriptor-relative opens, the open directory descriptor
    prevents a renamed or symlink-replaced path from redirecting the write.
    The Windows implementation uses an NT relative open rooted at a pinned
    directory handle for the same reason.
    """
    if type(name) is not str:
        raise SaveError('A new private child needs bytes and one ordinary file name.')
    try:
        encoded_name = name.encode('utf-16-le')
        name_length = len(encoded_name) // 2
    except UnicodeError as error:
        raise SaveError('A new private child name must be valid Unicode.') from error
    if (type(data) is not bytes or not name or Path(name).name != name
            or name in ('.', '..') or '\\' in name or '/' in name
            or name_length > 255 or reserved_windows_path(name)):
        raise SaveError('A new private child needs bytes and one ordinary file name.')
    directory = Path(directory)
    if os.name == 'nt':
        return _new_child_windows(data, directory, name, expected_identity)
    return _new_child_posix(data, directory, name, expected_identity)


class ChildPublishedUncertainError(SaveError):
    """A child was linked, but a later durability or identity check failed."""

    def __init__(self, destination):
        self.destination = Path(destination)
        super().__init__(f'The new private output may already be published at {self.destination}.')


def publish_new_child_bound(data, directory, name, expected_identity):
    """Write, verify, then publish a new child without exposing partial bytes."""
    if type(data) is not bytes:
        raise SaveError('A published private child must contain bytes.')
    _validate_child_name(name)
    directory = Path(directory)
    if os.name == 'nt':
        temporary_name = '.pending-' + uuid.uuid4().hex + '.tmp'
        # Keep the created child owned through verification and exclusive rename.
        return _new_child_windows(data, directory, temporary_name, expected_identity,
                                  _publish_name=name)
    if sys.platform.startswith('linux'):
        return _publish_new_child_linux(data, directory, name, expected_identity)
    raise SaveError('This system has no safe handle-bound no-replace publication for private manifests.')


def _validate_child_name(name):
    if type(name) is not str:
        raise SaveError('A private child needs one ordinary file name.')
    try:
        name_length = len(name.encode('utf-16-le')) // 2
    except UnicodeError as error:
        raise SaveError('A private child name must be valid Unicode.') from error
    if (not name or Path(name).name != name or name in ('.', '..')
            or '\\' in name or '/' in name or name_length > 255
            or reserved_windows_path(name)):
        raise SaveError('A private child needs one ordinary file name.')
    return name_length


def _publish_new_child_linux(data, directory, name, expected_identity):
    """Publish from an unnamed inode so no path can replace the verified source."""
    import ctypes
    import errno

    if not hasattr(os, 'O_TMPFILE'):
        raise SaveError('This system cannot create an unnamed private staging file.')
    flags = (os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0)
             | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0))
    try:
        directory_fd = os.open(directory, flags)
    except OSError as error:
        raise SaveError('The private output directory changed or became linked.') from error
    published = False
    publication_attempted = False
    try:
        directory_info = os.fstat(directory_fd)
        identity = (directory_info.st_dev, directory_info.st_ino)
        if not stat.S_ISDIR(directory_info.st_mode) or identity != expected_identity:
            raise SaveError('The private output directory changed identity.')

        try:
            output_fd = os.open('.', os.O_RDWR | os.O_TMPFILE | getattr(os, 'O_CLOEXEC', 0),
                                0o600, dir_fd=directory_fd)
        except OSError as error:
            raise SaveError('This filesystem cannot create a private unnamed staging file.') from error
        try:
            written = 0
            while written < len(data):
                count = os.write(output_fd, data[written:written + 65536])
                if not count:
                    raise SaveError('The private output file could not be completed.')
                written += count
            os.fsync(output_fd)
            os.lseek(output_fd, 0, os.SEEK_SET)
            source_info = os.fstat(output_fd)
            source_identity = (source_info.st_dev, source_info.st_ino)
            if (not stat.S_ISREG(source_info.st_mode) or source_info.st_nlink != 0
                    or _read_descriptor(output_fd, len(data)) != data):
                raise SaveError('The private output failed handle-bound read-back.')

            libc = ctypes.CDLL(None, use_errno=True)
            linkat = libc.linkat
            linkat.argtypes = [ctypes.c_int, ctypes.c_char_p,
                               ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
            linkat.restype = ctypes.c_int
            destination = os.fsencode(name)
            source_path = os.fsencode(f'/proc/self/fd/{output_fd}')
            # AT_SYMLINK_FOLLOW makes /proc/self/fd/N resolve to the open inode.
            publication_attempted = True
            result = linkat(-100, source_path, directory_fd, destination, 0x400)
            if result != 0:
                publication_attempted = False  # A negative native result did not link.
                error_number = ctypes.get_errno()
                if error_number == errno.EEXIST:
                    raise SaveError('The private output name already exists.')
                raise SaveError('The verified private output could not be published without replacement.')
            published = True

            final_fd = os.open(name, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                               | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_CLOEXEC', 0),
                               dir_fd=directory_fd)
            try:
                final_info = os.fstat(final_fd)
                if (not stat.S_ISREG(final_info.st_mode) or final_info.st_nlink != 1
                        or (final_info.st_dev, final_info.st_ino) != source_identity
                        or _read_descriptor(final_fd, len(data)) != data):
                    raise SaveError('The published private output failed handle-bound verification.')
            finally:
                os.close(final_fd)
            os.fsync(directory_fd)
            named_info = os.stat(directory, follow_symlinks=False)
            if (not stat.S_ISDIR(named_info.st_mode)
                    or (named_info.st_dev, named_info.st_ino) != identity):
                raise SaveError('The private output directory path changed during publication.')
            return directory / name
        except BaseException as error:
            if published or publication_attempted:
                raise ChildPublishedUncertainError(directory / name) from error
            raise
        finally:
            try:
                os.close(output_fd)
            except BaseException as error:
                if published or publication_attempted:
                    raise ChildPublishedUncertainError(directory / name) from error
                raise
    finally:
        try:
            os.close(directory_fd)
        except BaseException as error:
            if published or publication_attempted:
                raise ChildPublishedUncertainError(directory / name) from error
            raise


def _read_descriptor(file_descriptor, maximum):
    blocks, length = [], 0
    while length <= maximum:
        block = os.read(file_descriptor, min(65536, maximum + 1 - length))
        if not block:
            break
        blocks.append(block)
        length += len(block)
    return b''.join(blocks)


def _rename_verified_child_windows(ntdll, child, parent, name):
    """Publish the still-owned child handle relative to the pinned directory."""
    import ctypes
    from ctypes import wintypes

    class IO_STATUS_BLOCK_UNION(ctypes.Union):
        _fields_ = [('Status', ctypes.c_long), ('Pointer', wintypes.LPVOID)]

    class IO_STATUS_BLOCK(ctypes.Structure):
        _anonymous_ = ('u',)
        _fields_ = [('u', IO_STATUS_BLOCK_UNION), ('Information', ctypes.c_size_t)]

    class FILE_RENAME_INFORMATION(ctypes.Structure):
        _fields_ = [('ReplaceIfExists', wintypes.BOOLEAN),
                    ('RootDirectory', wintypes.HANDLE),
                    ('FileNameLength', wintypes.ULONG),
                    ('FileName', wintypes.WCHAR * 1)]

    encoded_name = name.encode('utf-16-le')
    header_size = FILE_RENAME_INFORMATION.FileName.offset
    storage_size = max(ctypes.sizeof(FILE_RENAME_INFORMATION), header_size + len(encoded_name))
    storage = ctypes.create_string_buffer(storage_size)
    information = ctypes.cast(storage, ctypes.POINTER(FILE_RENAME_INFORMATION)).contents
    information.ReplaceIfExists = False
    information.RootDirectory = parent
    information.FileNameLength = len(encoded_name)
    ctypes.memmove(ctypes.addressof(storage) + header_size, encoded_name, len(encoded_name))
    iosb = IO_STATUS_BLOCK()
    ntdll.NtSetInformationFile.argtypes = [wintypes.HANDLE, ctypes.POINTER(IO_STATUS_BLOCK),
                                           wintypes.LPVOID, wintypes.ULONG, wintypes.ULONG]
    ntdll.NtSetInformationFile.restype = ctypes.c_long
    status = ntdll.NtSetInformationFile(child, ctypes.byref(iosb), storage, storage_size, 10)
    return status


def _new_child_posix(data, directory, name, expected_identity):
    flags = (os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0)
             | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0))
    try:
        directory_fd = os.open(directory, flags)
    except OSError as error:
        raise SaveError('The private output directory changed or became linked.') from error
    try:
        directory_info = os.fstat(directory_fd)
        identity = (directory_info.st_dev, directory_info.st_ino)
        if (not stat.S_ISDIR(directory_info.st_mode) or identity != expected_identity):
            raise SaveError('The private output directory changed identity.')
        try:
            output_fd = os.open(
                name, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0),
                0o600, dir_fd=directory_fd)
        except OSError as error:
            raise SaveError('The private output file already exists or cannot be created safely.') from error
        try:
            output_info = os.fstat(output_fd)
            output_identity = (output_info.st_dev, output_info.st_ino)
            view = memoryview(data)
            while view:
                count = os.write(output_fd, view)
                if count <= 0:
                    raise SaveError('The private output file could not be completed.')
                view = view[count:]
            os.fsync(output_fd)
        finally:
            os.close(output_fd)

        verify_fd = os.open(name, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                            | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_CLOEXEC', 0),
                            dir_fd=directory_fd)
        try:
            file_info = os.fstat(verify_fd)
            if (not stat.S_ISREG(file_info.st_mode) or file_info.st_nlink != 1
                    or (file_info.st_dev, file_info.st_ino) != output_identity):
                raise SaveError('The private output is not the created ordinary file.')
            blocks, length = [], 0
            while length <= len(data):
                block = os.read(verify_fd, min(65536, len(data) + 1 - length))
                if not block:
                    break
                blocks.append(block)
                length += len(block)
            if b''.join(blocks) != data:
                raise SaveError('The private output failed descriptor-bound read-back.')
        finally:
            os.close(verify_fd)
        os.fsync(directory_fd)
        try:
            named_info = os.stat(directory, follow_symlinks=False)
        except OSError as error:
            raise SaveError('The private output directory path changed during the write.') from error
        if (not stat.S_ISDIR(named_info.st_mode)
                or (named_info.st_dev, named_info.st_ino) != identity):
            raise SaveError('The private output directory path changed during the write.')
        return directory / name
    finally:
        os.close(directory_fd)


def _new_child_windows(data, directory, name, expected_identity, *, _publish_name=None):
    """Use NtCreateFile with RootDirectory so Windows writes cannot follow a raced parent."""
    import ctypes
    from ctypes import wintypes

    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    SYNCHRONIZE = 0x00100000
    FILE_LIST_DIRECTORY = 0x0001
    FILE_ADD_FILE = 0x0002
    DELETE = 0x00010000
    FILE_TRAVERSE = 0x0020
    FILE_READ_ATTRIBUTES = 0x0080
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    FILE_ATTRIBUTE_DIRECTORY = 0x00000010
    FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
    FILE_NON_DIRECTORY_FILE = 0x00000040
    FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
    FILE_CREATE = 2
    OBJ_CASE_INSENSITIVE = 0x00000040

    class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [('dwFileAttributes', wintypes.DWORD),
                    ('ftCreationTimeLow', wintypes.DWORD),
                    ('ftCreationTimeHigh', wintypes.DWORD),
                    ('ftLastAccessTimeLow', wintypes.DWORD),
                    ('ftLastAccessTimeHigh', wintypes.DWORD),
                    ('ftLastWriteTimeLow', wintypes.DWORD),
                    ('ftLastWriteTimeHigh', wintypes.DWORD),
                    ('dwVolumeSerialNumber', wintypes.DWORD),
                    ('nFileSizeHigh', wintypes.DWORD),
                    ('nFileSizeLow', wintypes.DWORD),
                    ('nNumberOfLinks', wintypes.DWORD),
                    ('nFileIndexHigh', wintypes.DWORD),
                    ('nFileIndexLow', wintypes.DWORD)]

    class UNICODE_STRING(ctypes.Structure):
        _fields_ = [('Length', wintypes.USHORT),
                    ('MaximumLength', wintypes.USHORT),
                    ('Buffer', wintypes.LPWSTR)]

    class OBJECT_ATTRIBUTES(ctypes.Structure):
        _fields_ = [('Length', wintypes.ULONG),
                    ('RootDirectory', wintypes.HANDLE),
                    ('ObjectName', ctypes.POINTER(UNICODE_STRING)),
                    ('Attributes', wintypes.ULONG),
                    ('SecurityDescriptor', wintypes.LPVOID),
                    ('SecurityQualityOfService', wintypes.LPVOID)]

    class IO_STATUS_BLOCK_UNION(ctypes.Union):
        _fields_ = [('Status', ctypes.c_long), ('Pointer', wintypes.LPVOID)]

    class IO_STATUS_BLOCK(ctypes.Structure):
        _anonymous_ = ('u',)
        _fields_ = [('u', IO_STATUS_BLOCK_UNION), ('Information', ctypes.c_size_t)]

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    ntdll = ctypes.WinDLL('ntdll')
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                     wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                     wintypes.HANDLE]
    kernel32.GetFileInformationByHandle.argtypes = [wintypes.HANDLE,
                                                     ctypes.POINTER(BY_HANDLE_FILE_INFORMATION)]
    kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                                   ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                                  ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
    kernel32.FlushFileBuffers.restype = wintypes.BOOL
    kernel32.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong,
                                          ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD]
    kernel32.SetFilePointerEx.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    parent = kernel32.CreateFileW(
        str(directory), FILE_LIST_DIRECTORY | FILE_TRAVERSE | FILE_READ_ATTRIBUTES
        | (FILE_ADD_FILE if _publish_name is not None else 0),
        FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, None)
    if parent == wintypes.HANDLE(-1).value:
        raise SaveError('The private output directory could not be opened without following links.')
    try:
        import msvcrt
        parent_fd = msvcrt.open_osfhandle(parent, os.O_RDONLY)
    except OSError as error:
        kernel32.CloseHandle(parent)
        raise SaveError('The private output directory handle could not be bound safely.') from error
    parent = msvcrt.get_osfhandle(parent_fd)
    child = wintypes.HANDLE()
    published = False
    publication_attempted = False
    try:
        parent_info = BY_HANDLE_FILE_INFORMATION()
        if (not kernel32.GetFileInformationByHandle(parent, ctypes.byref(parent_info))
                or not parent_info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY
                or parent_info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT):
            raise SaveError('The private output directory changed identity or became linked.')
        parent_stat = os.fstat(parent_fd)
        if (parent_stat.st_dev, parent_stat.st_ino) != expected_identity:
            raise SaveError('The private output directory changed identity or became linked.')

        name_buffer = ctypes.create_unicode_buffer(name)
        encoded_name = name.encode('utf-16-le')
        unicode_name = UNICODE_STRING(
            len(encoded_name), len(encoded_name) + 2,
            ctypes.cast(name_buffer, wintypes.LPWSTR))
        object_attributes = OBJECT_ATTRIBUTES(
            ctypes.sizeof(OBJECT_ATTRIBUTES), parent, ctypes.pointer(unicode_name),
            OBJ_CASE_INSENSITIVE, None, None)
        iosb = IO_STATUS_BLOCK()
        ntdll.NtCreateFile.argtypes = [ctypes.POINTER(wintypes.HANDLE), wintypes.ULONG,
                                       ctypes.POINTER(OBJECT_ATTRIBUTES),
                                       ctypes.POINTER(IO_STATUS_BLOCK), wintypes.LPVOID,
                                       wintypes.ULONG, wintypes.ULONG, wintypes.ULONG,
                                       wintypes.ULONG, wintypes.LPVOID, wintypes.ULONG]
        ntdll.NtCreateFile.restype = ctypes.c_long
        status = ntdll.NtCreateFile(
            # Required explicitly by FILE_SYNCHRONOUS_IO_NONALERT at NT entry.
            ctypes.byref(child), GENERIC_READ | GENERIC_WRITE | SYNCHRONIZE
            | (DELETE if _publish_name is not None else 0),
            ctypes.byref(object_attributes), ctypes.byref(iosb), None, 0x80,
            FILE_SHARE_READ, FILE_CREATE,
            FILE_NON_DIRECTORY_FILE | FILE_SYNCHRONOUS_IO_NONALERT
            | FILE_FLAG_OPEN_REPARSE_POINT, None, 0)
        if status < 0:
            raise SaveError(f'The private output file could not be created exclusively (NTSTATUS {status & 0xffffffff:08x}).')

        written = 0
        while written < len(data):
            block = data[written:written + 65536]
            buffer = ctypes.create_string_buffer(block)
            count = wintypes.DWORD()
            if not kernel32.WriteFile(child, buffer, len(block), ctypes.byref(count), None) or not count.value:
                raise SaveError('The private output file could not be completed.')
            written += count.value
        if not kernel32.FlushFileBuffers(child):
            raise SaveError('The private output file could not be flushed safely.')
        position = ctypes.c_longlong()
        if not kernel32.SetFilePointerEx(child, 0, ctypes.byref(position), 0):
            raise SaveError('The private output file could not be verified.')
        verified = bytearray()
        while len(verified) <= len(data):
            amount = min(65536, len(data) + 1 - len(verified))
            buffer = ctypes.create_string_buffer(amount)
            count = wintypes.DWORD()
            if not kernel32.ReadFile(child, buffer, amount, ctypes.byref(count), None):
                raise SaveError('The private output file could not be read back.')
            if not count.value:
                break
            verified.extend(buffer.raw[:count.value])
        if bytes(verified) != data:
            raise SaveError('The private output failed handle-bound read-back.')
        child_info = BY_HANDLE_FILE_INFORMATION()
        if (not kernel32.GetFileInformationByHandle(child, ctypes.byref(child_info))
                or child_info.dwFileAttributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT)
                or child_info.nNumberOfLinks != 1):
            raise SaveError('The private output is not one ordinary file.')
        if _publish_name is not None:
            publication_attempted = True
            status = _rename_verified_child_windows(ntdll, child, parent, _publish_name)
            if status < 0:
                publication_attempted = False  # Native rejection leaves the pending file.
                raise SaveError('The verified private output could not be published without replacement.')
            published = True
            if (not kernel32.GetFileInformationByHandle(child, ctypes.byref(child_info))
                    or child_info.dwFileAttributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT)
                    or child_info.nNumberOfLinks != 1):
                raise SaveError('The published private output is not one ordinary file.')
        try:
            path_info = directory.lstat()
        except OSError as error:
            raise SaveError('The private output directory path changed during the write.') from error
        if ((path_info.st_dev, path_info.st_ino) != expected_identity
                or stat.S_ISLNK(path_info.st_mode)
                or getattr(path_info, 'st_file_attributes', 0) & FILE_ATTRIBUTE_REPARSE_POINT):
            raise SaveError('The private output directory path changed during the write.')
        return directory / (_publish_name if _publish_name is not None else name)
    except BaseException as error:
        if published or publication_attempted:
            raise ChildPublishedUncertainError(directory / _publish_name) from error
        raise
    finally:
        child_close_error = None
        try:
            if child.value:
                closed = kernel32.CloseHandle(child)
                if _publish_name is not None and not closed:
                    child_close_error = SaveError('The private output handle could not be closed safely.')
        except BaseException as error:
            child_close_error = error
        try:
            os.close(parent_fd)
        except BaseException as error:
            if published or publication_attempted:
                raise ChildPublishedUncertainError(directory / _publish_name) from error
            raise
        if child_close_error is not None:
            if published or publication_attempted:
                raise ChildPublishedUncertainError(directory / _publish_name) from child_close_error
            raise child_close_error


def snapshot_backup(raw, source, game_id, folder=None):
    source = safe_path(source)
    folder = safe_path(folder if folder is not None else source.parent / 'OriginsEditorBackups')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    separator = '.' if source.suffix else '-'
    destination = folder / (source.stem + separator + stamp + separator + uuid.uuid4().hex[:8] + source.suffix)
    manifest = {'game_id': game_id, 'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw),
                'kind': 'opaque-copy', 'created_utc': stamp}
    result = atomic_new(raw, destination)
    # If manifest creation fails, keep the completed snapshot. Another app may
    # have replaced either path; failure must never delete its bytes. Restore
    # still requires a matching manifest before accepting this backup.
    atomic_new(json.dumps(manifest, indent=2).encode('utf-8'), destination.with_suffix('.json'))
    return result


def restore_snapshot(backup, destination, game_id, suffix, max_size, validate_raw=None):
    backup, destination = safe_path(backup), safe_path(destination)
    if backup.suffix.lower() != suffix or destination.suffix.lower() != suffix:
        raise SaveError(f'Choose a {suffix} backup and a new {suffix} destination.')
    manifest_path = safe_path(backup.with_suffix('.json'))
    with manifest_path.open('rb') as stream:
        metadata = stream.read(4097)
    with backup.open('rb') as stream:
        raw = stream.read(max_size + 1)
    if len(metadata) > 4096 or not 0 < len(raw) <= max_size:
        raise SaveError('Backup or manifest size is invalid.')
    try:
        manifest = json.loads(metadata)
    except (ValueError, UnicodeError) as error:
        raise SaveError('Backup manifest is damaged.') from error
    if (not isinstance(manifest, dict) or manifest.get('game_id') != game_id or
            manifest.get('kind') != 'opaque-copy' or manifest.get('size_bytes') != len(raw) or
            manifest.get('sha256') != hashlib.sha256(raw).hexdigest()):
        raise SaveError('Backup game, hash, or size does not match its manifest.')
    if validate_raw is not None:
        # Qualify the same bounded bytes that will be written, rather than a
        # separate earlier read whose backup or manifest could change.
        validate_raw(raw)
    return atomic_new(raw, destination)
