"""Read-only Windows handles for an explicitly qualified local directory chain.

Every ancestor remains open without FILE_SHARE_DELETE. Enumeration uses the
held native handle and file IDs, and file reads use
single-component NT opens relative to the held parent; reparse points never pass
the handle attribute checks. No create, write, delete or repair API is used.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import stat
from types import SimpleNamespace


def _name(value):
    try:
        length = len(value.encode('utf-16-le')) if type(value) is str else 0
    except UnicodeError:
        raise OSError('An ordinary Unicode child name is required.') from None
    if (type(value) is not str or not value or value in ('.', '..')
            or any(char in value for char in ('/', '\\', ':', '\x00'))
            or value.endswith((' ', '.')) or length > 510):
        raise OSError('An ordinary single-component name is required.')
    return value


def _decode_entry(raw, device):
    """Validate one FILE_ID_EXTD_DIR_INFORMATION record; no pathname lookup."""
    if type(raw) is not bytes or len(raw) < 88:
        raise OSError('Truncated native directory entry.')
    length = int.from_bytes(raw[60:64], 'little')
    if int.from_bytes(raw[:4], 'little') or length % 2 or not 0 < length <= 510 or 88 + length > len(raw):
        raise OSError('Invalid native directory entry.')
    try:
        name = raw[88:88 + length].decode('utf-16-le')
    except UnicodeError:
        raise OSError('Invalid Unicode directory entry.') from None
    if name in ('.', '..'):
        return None
    _name(name)
    attributes = int.from_bytes(raw[56:60], 'little')
    identity = int.from_bytes(raw[72:88], 'little')
    size = int.from_bytes(raw[40:48], 'little', signed=True)
    if not identity or size < 0:
        raise OSError('A directory entry has no usable native identity.')
    info = SimpleNamespace(
        st_dev=device, st_ino=identity,
        st_mode=stat.S_IFDIR if attributes & 0x10 else stat.S_IFREG,
        st_file_attributes=attributes, st_size=size,
        st_mtime_ns=(int.from_bytes(raw[24:32], 'little', signed=True)
                      - 116444736000000000) * 100)
    return SimpleNamespace(name=name, stat=lambda *, follow_symlinks=False: info)


class WindowsDirectory:
    """Pinned chain; enumeration and child opens use its held native handles."""
    def __init__(self, bindings):
        import ctypes
        from ctypes import wintypes
        import msvcrt
        self.ctypes, self.wintypes, self.msvcrt = ctypes, wintypes, msvcrt
        self.path = Path(bindings[-1][0])
        self.descriptors = []

        class Information(ctypes.Structure):
            _fields_ = [('attributes', wintypes.DWORD), ('rest', wintypes.DWORD * 12)]
        class Unicode(ctypes.Structure):
            _fields_ = [('Length', wintypes.USHORT), ('MaximumLength', wintypes.USHORT),
                        ('Buffer', wintypes.LPWSTR)]
        class Attributes(ctypes.Structure):
            _fields_ = [('Length', wintypes.ULONG), ('RootDirectory', wintypes.HANDLE),
                        ('ObjectName', ctypes.POINTER(Unicode)), ('Attributes', wintypes.ULONG),
                        ('SecurityDescriptor', wintypes.LPVOID), ('SecurityQualityOfService', wintypes.LPVOID)]
        class StatusUnion(ctypes.Union):
            _fields_ = [('Status', ctypes.c_long), ('Pointer', wintypes.LPVOID)]
        class Status(ctypes.Structure):
            _anonymous_ = ('value',)
            _fields_ = [('value', StatusUnion), ('Information', ctypes.c_size_t)]
        self.Information, self.Unicode, self.Attributes, self.Status = Information, Unicode, Attributes, Status
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.nt = ctypes.WinDLL('ntdll')
        self.kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                            wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(Information)]
        self.kernel.GetFileInformationByHandle.restype = wintypes.BOOL
        self.nt.NtCreateFile.argtypes = [ctypes.POINTER(wintypes.HANDLE), wintypes.ULONG,
                                       ctypes.POINTER(Attributes), ctypes.POINTER(Status), wintypes.LPVOID,
                                       wintypes.ULONG, wintypes.ULONG, wintypes.ULONG, wintypes.ULONG,
                                       wintypes.LPVOID, wintypes.ULONG]
        self.nt.NtCreateFile.restype = ctypes.c_long
        self.nt.NtQueryDirectoryFile.argtypes = [wintypes.HANDLE, wintypes.HANDLE,
                                               wintypes.LPVOID, wintypes.LPVOID,
                                               ctypes.POINTER(Status), wintypes.LPVOID,
                                               wintypes.ULONG, ctypes.c_int, wintypes.BOOLEAN,
                                               wintypes.LPVOID, wintypes.BOOLEAN]
        self.nt.NtQueryDirectoryFile.restype = ctypes.c_long
        try:
            anchor = Path(bindings[0][0])
            if (not anchor.is_absolute() or not anchor.drive or anchor.drive.startswith('\\')
                    or anchor != Path(anchor.anchor)):
                raise OSError('Choose an ordinary local-drive folder.')
            # READ_DATA/LIST_DIRECTORY, READ_ATTRIBUTES, SYNCHRONIZE. No delete
            # sharing: every selected ancestor is pinned through enumeration.
            handle = self.kernel.CreateFileW(str(anchor), 0x100081, 3, None, 3,
                                             0x02000000 | 0x00200000, None)
            if handle == wintypes.HANDLE(-1).value:
                raise OSError('The root directory could not be pinned.')
            fd = self._descriptor(handle, directory=True)
            self.descriptors.append(fd)
            self._match(fd, bindings[0][1], directory=True)
            for path, expected in bindings[1:]:
                fd = self.open_child(Path(path).name, directory=True)
                self.descriptors.append(fd)
                self._match(fd, expected, directory=True)
        except BaseException:
            self.close()
            raise

    def _descriptor(self, handle, *, directory):
        c, w = self.ctypes, self.wintypes
        info = self.Information()
        try:
            if (not self.kernel.GetFileInformationByHandle(handle, c.byref(info))
                    or info.attributes & 0x400
                    or bool(info.attributes & 0x10) != directory):
                raise OSError('The opened item is linked or has the wrong type.')
            fd = self.msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        except BaseException:
            self.kernel.CloseHandle(w.HANDLE(handle))
            raise
        return fd

    @staticmethod
    def _match(fd, expected, *, directory):
        current = os.fstat(fd)
        valid_type = stat.S_ISDIR(current.st_mode) if directory else stat.S_ISREG(current.st_mode)
        if not valid_type or (current.st_dev, current.st_ino) != (expected.st_dev, expected.st_ino):
            raise OSError('The selected item changed identity.')
        return current

    def open_child(self, name, *, directory=False):
        name = _name(name)
        c, w = self.ctypes, self.wintypes
        buffer = c.create_unicode_buffer(name)
        length = len(name.encode('utf-16-le'))
        unicode_name = self.Unicode(length, length + 2, c.cast(buffer, w.LPWSTR))
        attributes = self.Attributes(c.sizeof(self.Attributes),
                                     self.msvcrt.get_osfhandle(self.descriptors[-1]),
                                     c.pointer(unicode_name), 0x40, None, None)
        status, handle = self.Status(), w.HANDLE()
        result = self.nt.NtCreateFile(c.byref(handle), 0x100081, c.byref(attributes),
                                     c.byref(status), None, 0,
                                     3 if directory else 1, 1,  # share read/write dirs; FILE_OPEN only
                                     0x00200000 | 0x20 | (1 if directory else 0x40), None, 0)
        if result != 0:
            if handle.value:
                self.kernel.CloseHandle(handle)
            raise OSError('The selected child could not be opened safely.')
        return self._descriptor(handle.value, directory=directory)

    def _entries(self):
        """FILE_ID_EXTD_DIR_INFORMATION preserves each enumerated 128-bit ID."""
        c = self.ctypes
        first = True
        while True:
            status, buffer = self.Status(), c.create_string_buffer(4096)
            result = self.nt.NtQueryDirectoryFile(
                self.msvcrt.get_osfhandle(self.descriptors[-1]), None, None, None,
                c.byref(status), buffer, len(buffer), 60, True, None, first)
            first = False
            if result & 0xffffffff == 0x80000006:  # STATUS_NO_MORE_FILES
                return
            if result != 0 or not 88 <= status.Information <= len(buffer):
                raise OSError('The selected directory could not be enumerated safely.')
            entry = _decode_entry(buffer.raw[:status.Information], os.fstat(self.descriptors[-1]).st_dev)
            if entry is not None:
                yield entry

    @contextmanager
    def entries(self):
        iterator = self._entries()
        try:
            yield iterator
        finally:
            iterator.close()

    def close(self):
        error = None
        while self.descriptors:
            try:
                os.close(self.descriptors.pop())
            except OSError as caught:
                error = caught
        if error is not None:
            raise error


@contextmanager
def directory_chain(bindings):
    if os.name != 'nt' or not bindings:
        raise OSError('Native Windows directory bindings are required.')
    directory = WindowsDirectory(bindings)
    try:
        yield directory
    finally:
        directory.close()
