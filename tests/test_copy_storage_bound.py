"""Directory-bound output: native Windows checks plus portable API-flow regressions.

The fake kernel exercises Python/ctypes control flow, not the Windows ABI or
filesystem. Native checks run without mocks on the release workflow's Windows
shards and require exclusive creation, unchanged existing bytes and read-back.
"""
import ctypes
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import copy_storage


class _Function:
    def __init__(self, operation):
        self.operation = operation

    def __call__(self, *args):
        return self.operation(*args)


class _WindowsKernel:
    def __init__(self, expected_name):
        self.expected_name = expected_name
        self.data = bytearray()
        self.position = 0
        self.created = False
        self.closed = []
        self.directory_flags = None
        self.CreateFileW = _Function(self.open_parent)
        self.GetFileInformationByHandle = _Function(self.info)
        self.WriteFile = _Function(self.write)
        self.ReadFile = _Function(self.read)
        self.FlushFileBuffers = _Function(lambda handle: True)
        self.SetFilePointerEx = _Function(self.seek)
        self.CloseHandle = _Function(lambda handle: self.closed.append(handle.value))
        self.NtCreateFile = _Function(self.create)

    def open_parent(self, path, access, share, security, disposition, flags, template):
        self.directory_flags = flags
        return 101

    def info(self, handle, pointer):
        pointer._obj.dwFileAttributes = 0x10 if handle == 101 else 0x80
        pointer._obj.nNumberOfLinks = 1
        return True

    def create(self, handle, access, attributes, status, allocation, flags, share,
               disposition, options, ea, ea_length):
        attrs = attributes._obj
        name = attrs.ObjectName.contents
        assert attrs.RootDirectory == 101
        assert name.Buffer == self.expected_name
        assert name.Length == len(self.expected_name.encode('utf-16-le'))
        assert name.MaximumLength == name.Length + 2
        assert disposition == 2  # FILE_CREATE must reject an existing child.
        assert options & 0x40 and options & 0x200000
        if self.created:
            return -1073741771  # STATUS_OBJECT_NAME_COLLISION
        self.created = True
        handle._obj.value = 202
        return 0

    def write(self, handle, buffer, size, count, overlapped):
        # Partial writes must be completed without duplicating data.
        size = min(size, 40001)
        self.data.extend(ctypes.string_at(buffer, size))
        count._obj.value = size
        return True

    def seek(self, handle, offset, position, origin):
        self.position = offset
        return True

    def read(self, handle, buffer, amount, count, overlapped):
        block = bytes(self.data[self.position:self.position + amount])
        ctypes.memmove(buffer, block, len(block))
        self.position += len(block)
        count._obj.value = len(block)
        return True


class WindowsBoundApiFlowTests(unittest.TestCase):
    def run_branch(self, kernel, directory, identity):
        fake_crt = SimpleNamespace(open_osfhandle=lambda handle, flags: 303,
                                   get_osfhandle=lambda fd: 101)
        libraries = lambda name, **kw: kernel
        info = SimpleNamespace(st_dev=self.identity[0], st_ino=self.identity[1])
        with patch.object(ctypes, 'WinDLL', libraries, create=True), \
                patch.dict('sys.modules', {'msvcrt': fake_crt}), \
                patch.object(copy_storage.os, 'fstat', return_value=info), \
                patch.object(copy_storage.os, 'close') as close:
            result = copy_storage._new_child_windows(
                self.payload, directory, kernel.expected_name, identity)
        close.assert_called_once_with(303)
        return result

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        info = self.directory.stat()
        self.identity = (info.st_dev, info.st_ino)
        self.payload = bytes(range(256)) * 600

    def test_windows_branch_constructs_unicode_relative_name_and_reads_back(self):
        kernel = _WindowsKernel('r\u00e9sum\u00e9-\U0001f3ae.json')
        result = self.run_branch(kernel, self.directory, self.identity)
        self.assertEqual(result, self.directory / kernel.expected_name)
        self.assertEqual(bytes(kernel.data), self.payload)
        self.assertEqual(kernel.closed, [202])
        self.assertTrue(kernel.directory_flags & 0x200000)

    def test_windows_branch_rejects_existing_child_without_writing(self):
        kernel = _WindowsKernel('component.json')
        kernel.created = True
        kernel.data.extend(b'preserve existing')
        with self.assertRaisesRegex(SaveError, 'exclusively'):
            self.run_branch(kernel, self.directory, self.identity)
        self.assertEqual(bytes(kernel.data), b'preserve existing')

    def test_windows_branch_rejects_changed_parent_before_child_creation(self):
        kernel = _WindowsKernel('component.json')
        with self.assertRaisesRegex(SaveError, 'changed identity'):
            self.run_branch(kernel, self.directory, (self.identity[0], self.identity[1] + 1))
        self.assertFalse(kernel.created)
        self.assertEqual(kernel.data, b'')

    def test_windows_branch_rejects_path_replacement_after_handle_bound_write(self):
        kernel = _WindowsKernel('component.json')
        replaced = SimpleNamespace(st_dev=self.identity[0], st_ino=self.identity[1] + 1,
                                   st_mode=0o40700, st_file_attributes=0)
        with patch.object(Path, 'lstat', return_value=replaced), \
                self.assertRaisesRegex(SaveError, 'path changed during'):
            self.run_branch(kernel, self.directory, self.identity)
        self.assertEqual(bytes(kernel.data), self.payload)
        self.assertEqual(kernel.closed, [202])


@unittest.skipUnless(os.name == 'nt', 'Native Windows filesystem qualification')
class WindowsBoundNativeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        info = self.directory.stat()
        self.identity = (info.st_dev, info.st_ino)

    def test_native_unicode_large_write_and_existing_child_preservation(self):
        name = 'r\u00e9sum\u00e9-\U0001f3ae.json'
        data = bytes(range(256)) * 600
        result = copy_storage.new_child_bound(data, self.directory, name, self.identity)
        self.assertEqual(result.read_bytes(), data)
        self.assertEqual(result.stat().st_nlink, 1)
        with self.assertRaises(SaveError):
            copy_storage.new_child_bound(b'replacement', self.directory, name, self.identity)
        self.assertEqual(result.read_bytes(), data)

    def test_native_changed_directory_identity_rejected_before_output(self):
        with self.assertRaisesRegex(SaveError, 'changed identity'):
            copy_storage.new_child_bound(
                b'new', self.directory, 'component.json',
                (self.identity[0], self.identity[1] + 1))
        self.assertEqual(tuple(self.directory.iterdir()), ())


if __name__ == '__main__':
    unittest.main()
