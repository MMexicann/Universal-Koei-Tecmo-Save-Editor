"""Independent Win64 native-directory contract, simulated without Windows binaries."""
import ctypes
from ctypes import wintypes
from contextlib import ExitStack
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from koei_editor.shared import copy_storage as storage

class Win64DirectoryAPI:

    def __init__(self, root, case, lock):
        self.directory = root
        self.name = '新🔒' if case == 'unicode_success' else 'created'
        self.path = root / self.name
        self.case = case
        self.lock = lock
        self.parent_info = root.stat()
        self.child_info = None
        self.events = []
        self.fdhandles = {}
        self.raw_closed = []
        self.dispositions = []
        self.live_descriptor = False
        self.functions = {name: Mock(side_effect=getattr(self, name)) for name in ('CreateFileW', 'GetFileInformationByHandle', 'CloseHandle', 'NtCreateFile', 'SetFileInformationByHandle', 'ConvertStringSecurityDescriptorToSecurityDescriptorW', 'LocalFree')}

    def CreateFileW(self, path, access, share, security, disposition, options, template):
        assert path == str(self.directory)
        assert access == 165
        assert share == 3
        assert disposition == 3 and options == 35651584
        self.events.append('parent_open')
        return 256

    def GetFileInformationByHandle(self, handle, output):
        value = handle.value if hasattr(handle, 'value') else handle
        if self.case == 'parent_information_failure' and value == 256:
            return 0
        if self.case == 'child_information_failure' and value == 512:
            return 0
        output._obj.dwFileAttributes = 1040 if self.case == 'reparse_child' and value == 512 else 16
        assert ctypes.sizeof(type(output._obj)) == 52
        return 1

    def CloseHandle(self, handle):
        value = handle.value if hasattr(handle, 'value') else handle
        self.raw_closed.append(value)
        self.events.append('close_raw_' + str(value))
        return not (self.case == 'raw_child_close_false' and value == 512 or (self.case == 'raw_parent_close_false' and value == 256))

    def ConvertStringSecurityDescriptorToSecurityDescriptorW(self, policy, revision, output, length):
        assert policy == 'D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)' and revision == 1
        if self.case == 'acl_failure':
            return 0
        ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = 20817
        ctypes.cast(length, ctypes.POINTER(ctypes.c_uint32))[0] = 128
        self.live_descriptor = True
        return 1

    def LocalFree(self, pointer):
        assert pointer.value == 20817 and self.live_descriptor
        self.live_descriptor = False
        self.events.append('acl_free')
        return 20817 if self.case == 'acl_release_failure' else None

    def NtCreateFile(self, out, access, attributes, iosb, allocation, flags, share, disposition, options, ea, ealen):
        self.events.append('create')
        assert self.live_descriptor
        obj = attributes._obj
        u = obj.ObjectName.contents
        assert ctypes.sizeof(type(obj)) == 48 and obj.RootDirectory == 256
        assert obj.SecurityDescriptor == 20817 and obj.Attributes == 64
        assert type(obj).RootDirectory.offset == 8 and type(obj).SecurityDescriptor.offset == 32
        assert ctypes.sizeof(type(u)) == 16 and type(u).Buffer.offset == 8
        assert u.Length == len(self.name.encode('utf-16-le')) and u.MaximumLength == u.Length + 2
        assert ctypes.string_at(u.Buffer, u.Length) == self.name.encode('utf-16-le')
        assert ctypes.sizeof(type(iosb._obj)) == 16 and type(iosb._obj).Information.offset == 8
        assert access == 1048705 + (65536 if self.lock else 0)
        assert flags == 16 and share == 3 and (disposition == 2) and (options == 2097185)
        if self.case == 'collision':
            return -1073741771
        self.path.mkdir()
        self.child_info = self.path.stat()
        ctypes.cast(out, ctypes.POINTER(ctypes.c_void_p))[0] = 512
        iosb._obj.Information = 1 if self.case == 'opened_existing' else 2
        if self.case == 'creation_interrupt':
            raise KeyboardInterrupt()
        if self.case == 'missing_child':
            self.path.rmdir()
        if self.case == 'foreign_child':
            self.path.rename(self.directory / 'owned-retained')
            self.path.mkdir()
            (self.path / 'foreign.txt').write_text('foreign')
        if self.case == 'return_pending':
            return 259
        if self.case == 'return_informational':
            return 1073741824
        if self.case == 'ntstatus_error_with_handle':
            return -1073741790
        return 0

    def SetFileInformationByHandle(self, handle, information, buffer, length):
        assert handle == 512 and information == 4 and (length == 1)
        assert ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))[0] == 1
        self.dispositions.append(handle)
        self.events.append('dispose_owned')
        return self.case != 'dispose_failure'

    def open_osfhandle(self, handle, flags):
        if self.case in {'parent_conversion_fail', 'raw_parent_close_false'} and handle == 256:
            raise OSError('conversion failed')
        if self.case in {'raw_child_close_false', 'child_conversion_fail'} and handle == 512:
            raise OSError('child conversion failed')
        fd = 1001 if handle == 256 else 1002
        self.fdhandles[fd] = handle
        return fd

    def get_osfhandle(self, fd):
        if self.case == 'parent_gethandle_fail' and fd == 1001:
            raise OSError('lookup failed')
        return self.fdhandles[fd]

    def fstat(self, fd):
        if self.case == 'wrong_parent_identity' and fd == 1001:
            return SimpleNamespace(st_dev=-1, st_ino=-1)
        if self.case == 'wrong_child_type' and fd == 1002:
            return SimpleNamespace(st_mode=stat.S_IFREG)
        return self.parent_info if fd == 1001 else self.child_info

    def close(self, fd):
        self.events.append('close_fd_' + str(fd))
        self.fdhandles.pop(fd)
        if self.case == 'child_close_fail' and fd == 1002:
            raise OSError('child close failed')
        if self.case == 'parent_close_fail' and fd == 1001:
            raise OSError('parent close failed')


class OwnedDirectoryNativeWindowsTests(unittest.TestCase):
    def test_exclusive_creation_unicode_and_held_handle_lifetime(self):
        for case, lock in (('success', False), ('success', True), ('unicode_success', False)):
            with self.subTest(case=case, lock=lock):
                self._run_case(case, lock)

    def test_rejected_native_outcomes_never_adopt_or_dispose_existing_directories(self):
        cases = ('collision', 'opened_existing', 'acl_failure', 'wrong_parent_identity',
                 'reparse_child', 'missing_child', 'foreign_child', 'return_pending',
                 'return_informational', 'ntstatus_error_with_handle',
                 'parent_information_failure', 'child_information_failure', 'wrong_child_type')
        for case in cases:
            with self.subTest(case=case):
                self._run_case(case, case in {'opened_existing', 'return_pending',
                                              'return_informational', 'ntstatus_error_with_handle'})

    def test_interruption_and_replaced_or_missing_names_preserve_foreign_content(self):
        for case in ('creation_interrupt', 'body_interrupt', 'foreign_after_body', 'missing_after_body'):
            with self.subTest(case=case):
                self._run_case(case, True)

    def test_conversion_disposition_and_final_close_errors_never_report_success(self):
        cases = ('parent_conversion_fail', 'parent_gethandle_fail', 'dispose_failure',
                 'child_close_fail', 'parent_close_fail', 'raw_child_close_false',
                 'raw_parent_close_false', 'child_conversion_fail', 'acl_release_failure')
        for case in cases:
            with self.subTest(case=case):
                self._run_case(case, case in {'dispose_failure', 'acl_release_failure'})

    def _run_case(self, case, lock):
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as patches:
            root = Path(temporary)
            api = Win64DirectoryAPI(root, case, lock)
            types = {'DWORD': ctypes.c_uint32, 'ULONG': ctypes.c_uint32, 'USHORT': ctypes.c_uint16, 'BOOL': ctypes.c_int32, 'BOOLEAN': ctypes.c_ubyte, 'HANDLE': ctypes.c_void_p, 'LPVOID': ctypes.c_void_p, 'HLOCAL': ctypes.c_void_p, 'LPWSTR': ctypes.c_void_p}
            for name, kind in types.items():
                patches.enter_context(patch.object(wintypes, name, kind))
            patches.enter_context(patch.object(ctypes, 'c_long', ctypes.c_int32))

            def unicode_buffer(value):
                raw = value.encode('utf-16-le') + b'\x00\x00'
                return (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
            patches.enter_context(patch.object(ctypes, 'create_unicode_buffer', side_effect=unicode_buffer))
            libraries = {'kernel32': SimpleNamespace(**{n: f for n, f in api.functions.items() if n not in ('NtCreateFile', 'ConvertStringSecurityDescriptorToSecurityDescriptorW')}), 'ntdll': SimpleNamespace(NtCreateFile=api.functions['NtCreateFile']), 'advapi32': SimpleNamespace(ConvertStringSecurityDescriptorToSecurityDescriptorToSecurityDescriptorW=None, ConvertStringSecurityDescriptorToSecurityDescriptorW=api.functions['ConvertStringSecurityDescriptorToSecurityDescriptorW'])}
            patches.enter_context(patch.object(ctypes, 'WinDLL', side_effect=lambda name, **kwargs: libraries[name], create=True))
            patches.enter_context(patch.dict(sys.modules, {'msvcrt': SimpleNamespace(open_osfhandle=api.open_osfhandle, get_osfhandle=api.get_osfhandle)}))
            patches.enter_context(patch.object(storage.os, 'fstat', side_effect=api.fstat))
            patches.enter_context(patch.object(storage.os, 'close', side_effect=api.close))
            entered = False
            error = None
            try:
                with storage._new_directory_child_windows(root, api.name, (api.parent_info.st_dev, api.parent_info.st_ino), remove_on_close=lock) as (path, info):
                    entered = True
                    assert path == api.path and info is api.child_info
                    assert set(api.fdhandles) == {1001, 1002}
                    if case == 'body_interrupt':
                        raise KeyboardInterrupt()
                    if case == 'missing_after_body':
                        path.rmdir()
                    if case == 'foreign_after_body':
                        path.rename(root / 'owned-retained')
                        path.mkdir()
                        (path / 'foreign.txt').write_text('foreign')
            except BaseException as caught:
                error = caught
            if case in {'success', 'unicode_success'}:
                assert error is None, (case, error)
            else:
                assert error is not None, (case, 'unexpected success')
            if case in {'acl_failure', 'collision', 'opened_existing', 'wrong_parent_identity', 'reparse_child', 'missing_child', 'foreign_child', 'parent_conversion_fail', 'parent_gethandle_fail', 'creation_interrupt', 'raw_child_close_false', 'return_pending', 'return_informational', 'ntstatus_error_with_handle', 'raw_parent_close_false', 'parent_information_failure', 'child_information_failure', 'child_conversion_fail', 'acl_release_failure', 'wrong_child_type'}:
                assert not entered, case
            assert not api.fdhandles, (case, 'leaked descriptors', api.fdhandles)
            assert api.dispositions == ([512] if lock and entered else []), (case, api.dispositions)
            if case in {'foreign_child', 'foreign_after_body'}:
                assert (api.path / 'foreign.txt').read_text() == 'foreign'
            if case == 'creation_interrupt':
                assert api.path.exists() and api.raw_closed == [512]


if __name__ == "__main__":
    unittest.main()
