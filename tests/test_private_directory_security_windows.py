"""Windows mkdir(0700) DACL ownership, using fixed Win64 API types on any host."""
import ctypes
from ctypes import wintypes
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import _private_directory_security_windows


class PrivateDirectorySecurityWindowsTests(unittest.TestCase):
    def setUp(self):
        # Native Windows LONG/ULONG are 32-bit even when the Linux host uses LP64.
        for name, kind in {'DWORD': ctypes.c_uint32, 'ULONG': ctypes.c_uint32,
                           'BOOL': ctypes.c_int32, 'LPVOID': ctypes.c_void_p,
                           'HLOCAL': ctypes.c_void_p}.items():
            patched = patch.object(wintypes, name, kind)
            patched.start()
            self.addCleanup(patched.stop)
        self.descriptor = 0x5A5A
        self.converted = True
        self.size = 128
        self.convert = Mock(side_effect=self._convert)
        self.free = Mock(return_value=None)
        libraries = {'advapi32': SimpleNamespace(ConvertStringSecurityDescriptorToSecurityDescriptorW=self.convert),
                     'kernel32': SimpleNamespace(LocalFree=self.free)}
        patched = patch.object(ctypes, 'WinDLL', side_effect=lambda name, **kwargs: libraries[name], create=True)
        patched.start()
        self.addCleanup(patched.stop)

    def _convert(self, policy, revision, descriptor, size):
        self.assertEqual(policy, 'D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)')
        self.assertEqual(revision, 1)
        ctypes.cast(descriptor, ctypes.POINTER(ctypes.c_void_p))[0] = self.descriptor
        ctypes.cast(size, ctypes.POINTER(ctypes.c_uint32))[0] = self.size
        return self.converted

    def test_restricted_descriptor_is_live_until_native_creation_finishes_then_freed(self):
        with _private_directory_security_windows() as descriptor:
            self.assertEqual(descriptor.value, self.descriptor)
            self.free.assert_not_called()
            self.assertEqual(ctypes.sizeof(self.convert.argtypes[1]), 4)
            self.assertEqual(ctypes.sizeof(self.convert.restype), 4)
            self.assertEqual(ctypes.sizeof(self.free.restype), 8)
        self.assertEqual(self.free.call_count, 1)
        self.assertEqual(self.free.call_args.args[0].value, self.descriptor)

    def test_conversion_failure_null_or_short_descriptor_never_reaches_creation(self):
        for converted, address, size in ((False, None, 0), (True, None, 128),
                                         (True, 0x5A5A, 19), (False, 0x5A5A, 128)):
            self.converted, self.descriptor, self.size = converted, address, size
            self.free.reset_mock()
            with self.subTest(converted=converted, address=address, size=size), \
                    self.assertRaisesRegex(SaveError, 'could not be created safely'):
                with _private_directory_security_windows():
                    self.fail('A missing restricted descriptor reached directory creation.')
            self.assertEqual(self.free.call_count, int(bool(address)))

    def test_body_failure_and_interruption_release_only_the_owned_descriptor(self):
        for error in (RuntimeError('native creation failed'), KeyboardInterrupt()):
            self.free.reset_mock()
            with self.subTest(error=type(error).__name__), self.assertRaises(type(error)):
                with _private_directory_security_windows():
                    raise error
            self.assertEqual(self.free.call_count, 1)
            self.assertEqual(self.free.call_args.args[0].value, self.descriptor)

    def test_descriptor_release_failure_is_reported(self):
        self.free.return_value = self.descriptor
        with self.assertRaisesRegex(SaveError, 'could not be released safely'):
            with _private_directory_security_windows():
                pass
        self.assertEqual(self.free.call_count, 1)


if __name__ == '__main__':
    unittest.main()
