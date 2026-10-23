"""Linux provider parity; published NIST SP800-38A F.1/F.2 vectors, no saves."""
import importlib
import sys
import unittest
from unittest.mock import patch

from koei_editor.games.dw3 import save_codec as codec

PLAIN = bytes.fromhex('6bc1bee22e409f96e93d7e117393172aae2d8a571e03ac9c9eb76fac45af8e51')
IV = bytes(range(16))
VECTORS = (
    ('2b7e151628aed2a6abf7158809cf4f3c',
     '3ad77bb40d7a3660a89ecaf32466ef97f5d3d58503b9699de785895a96fdbaaf',
     '7649abac8119b246cee98e9b12e9197d5086cb9b507219ee95db113a917678b2'),
    ('8e73b0f7da0e6452c810f32b809079e562f8ead2522c6b7b',
     'bd334f1d6e45f25ff712a214571fa5cc974104846d0ad3ad7734ecb3ecee4eef',
     '4f021db243bc633d7178183a9fa071e8b4d9ada9ad7dedf4e5e738763f69145a'),
    ('603deb1015ca71be2b73aef0857d77811f352c073b6108d72d9810a30914dff4',
     'f3eed1bdb5d2a03c064b5a7e3db181f8591ccb10d410ed26dc5ba74a31362870',
     'f58c4c04d6e5f1ba779eabfb5f7bfbd69cfc4e967edb808d679f777bc6702c7d'),
)


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux-only audited PyCryptodome provider')
class LinuxAesProviderTests(unittest.TestCase):
    def test_nist_encrypt_and_decrypt_for_every_supported_key_size_and_mode(self):
        for key_hex, ecb, cbc in VECTORS:
            for mode, expected in (('ECB', ecb), ('CBC', cbc)):
                with self.subTest(bits=len(key_hex) * 4, mode=mode), codec.CNG_AES(mode) as aes:
                    self.assertTrue(aes._linux)
                    iv = IV if mode == 'CBC' else None
                    key, encrypted = bytes.fromhex(key_hex), bytes.fromhex(expected)
                    self.assertEqual(aes.transform(PLAIN, key, direction='encrypt', iv=iv), encrypted)
                    self.assertEqual(aes.transform(encrypted, key, direction='decrypt', iv=iv), PLAIN)

    def test_unpadded_boundaries_and_repeated_cbc_calls_keep_caller_bytes(self):
        for mode in ('ECB', 'CBC'):
            with codec.CNG_AES(mode) as aes:
                for length in (16, 32, 48, 256, 4096):
                    plain = bytes((i * 71) % 256 for i in range(length - 16)) + bytes(16)
                    key, iv = bytes(range(32)), IV if mode == 'CBC' else None
                    original = plain, key, iv
                    first = aes.transform(plain, key, direction='encrypt', iv=iv)
                    self.assertEqual(len(first), length)
                    self.assertEqual(aes.transform(plain, key, direction='encrypt', iv=iv), first)
                    self.assertEqual(aes.transform(first, key, direction='decrypt', iv=iv), plain)
                    self.assertEqual((plain, key, iv), original)

    def test_optional_independent_cryptography_parity(self):
        try:
            reference = importlib.import_module('cryptography.hazmat.primitives.ciphers')
        except ImportError:
            self.skipTest('Optional independent development reference is not installed')
        for size in (16, 24, 32):
            for mode in ('ECB', 'CBC'):
                key = bytes(range(size)); data = bytes(range(256)) * 16
                reference_mode = reference.modes.ECB() if mode == 'ECB' else reference.modes.CBC(IV)
                worker = reference.Cipher(reference.algorithms.AES(key), reference_mode).encryptor()
                expected = worker.update(data) + worker.finalize()
                with codec.CNG_AES(mode) as aes:
                    self.assertEqual(aes.transform(data, key, direction='encrypt',
                                                  iv=IV if mode == 'CBC' else None), expected)

    def test_invalid_parameters_fail_before_creating_a_cipher(self):
        for mode in ('ECB', 'CBC'):
            with codec.CNG_AES(mode) as aes, patch.object(aes._aes, 'new') as create:
                iv = IV if mode == 'CBC' else None
                for size in (0, 1, 15, 17, 23, 25, 31, 33):
                    with self.assertRaises(ValueError):
                        aes.transform(bytes(16), bytes(size), direction='encrypt', iv=iv)
                for size in (0, 1, 15, 17, 31):
                    with self.assertRaises(ValueError):
                        aes.transform(bytes(size), bytes(16), direction='encrypt', iv=iv)
                for direction in ('', 'invalid'):
                    with self.assertRaises(ValueError):
                        aes.transform(bytes(16), bytes(16), direction=direction, iv=iv)
                bad_ivs = (None, b'', bytes(15), bytes(17)) if mode == 'CBC' else (bytes(16),)
                for invalid in bad_ivs:
                    with self.assertRaises(ValueError):
                        aes.transform(bytes(16), bytes(16), direction='encrypt', iv=invalid)
                create.assert_not_called()
        with self.assertRaises(ValueError):
            codec.CNG_AES('CTR')

    def test_closed_provider_and_exception_context_reject_future_operations(self):
        aes = codec.CNG_AES('ECB')
        aes.close(); aes.close()
        for direction in ('encrypt', 'decrypt'):
            with self.assertRaises(RuntimeError):
                aes.transform(bytes(16), bytes(16), direction=direction)
        with self.assertRaises(ValueError):
            with codec.CNG_AES('CBC') as failed:
                failed.transform(b'incomplete', bytes(16), direction='encrypt', iv=IV)
        with self.assertRaises(RuntimeError):
            failed.transform(bytes(16), bytes(16), direction='decrypt', iv=IV)

    def test_safety_bound_is_checked_before_native_allocation(self):
        with codec.CNG_AES('ECB') as aes, patch.object(codec, 'MAX_LINUX_AES_BYTES', 16), \
                patch.object(aes._aes, 'new') as create:
            with self.assertRaises(ValueError):
                aes.transform(bytes(32), bytes(16), direction='encrypt')
            create.assert_not_called()

    def test_missing_linux_provider_never_falls_back_to_unqualified_crypto(self):
        calls = []
        def missing(name):
            calls.append(name)
            raise ImportError('SYNTHETIC_PRIVATE_DEPENDENCY_PATH')
        with patch.object(importlib, 'import_module', side_effect=missing):
            with self.assertRaises(RuntimeError) as error:
                codec.CNG_AES('ECB')
        self.assertEqual(calls, ['Crypto.Cipher.AES'])
        self.assertNotIn('SYNTHETIC_PRIVATE', str(error.exception))

    def test_unexpected_native_output_length_is_not_accepted(self):
        with codec.CNG_AES('ECB') as aes, patch.object(aes._aes, 'new') as create:
            create.return_value.encrypt.return_value = bytes(32)
            with self.assertRaises(RuntimeError):
                aes.transform(bytes(16), bytes(16), direction='encrypt')


if __name__ == '__main__':
    unittest.main()
