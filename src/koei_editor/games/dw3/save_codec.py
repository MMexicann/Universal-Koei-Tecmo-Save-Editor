"""DW3 AES envelope: Windows CNG, Linux PyCryptodome, optional other-host provider."""
import ctypes as c
import struct
import sys

SAVE_KEY=bytes.fromhex('757347635a517044474b474b676d53766b3553637a637973314e6b774d503267')
MAX_LINUX_AES_BYTES = 64 * 1024 * 1024

def validate_parameters(data: bytes, key: bytes, mode: str, iv: bytes | None,
                        direction: str) -> None:
    if mode not in ('ECB', 'CBC') or direction not in ('decrypt', 'encrypt'):
        raise ValueError('Explicit mode ECB/CBC and direction decrypt/encrypt are required.')
    if len(key) not in (16, 24, 32):
        raise ValueError('The AES key must contain exactly 16, 24, or 32 bytes.')
    if not data or len(data) % 16:
        raise ValueError('The explicitly selected payload must be nonempty and a multiple of 16 bytes.')
    if mode == 'CBC' and (iv is None or len(iv) != 16):
        raise ValueError('CBC requires an explicit 16-byte IV.')
    if mode == 'ECB' and iv is not None:
        raise ValueError('ECB does not use an IV; omit it.')


class CNG_AES:
    """Import-safe Windows CNG AES; no padding, inferred IV, or file operations.

    Uses the same CNG calls as the existing crypto_probes AES helper. That
    script parses arguments at import time, so it cannot safely be imported.
    """
    def __init__(self, mode: str):
        if mode not in ('ECB', 'CBC'):
            raise ValueError('Unsupported AES mode.')
        self._portable = sys.platform != 'win32'
        self._linux = sys.platform.startswith('linux')
        self.mode = mode
        if self._portable:
            from importlib import import_module
            if self._linux:
                try:
                    self._aes = import_module('Crypto.Cipher.AES')
                except ImportError as error:
                    raise RuntimeError('Linux AES needs the pycryptodome package.') from error
            else:
                # Other development hosts retain their optional provider.
                try:
                    self._ciphers = import_module('cryptography.hazmat.primitives.ciphers')
                except ImportError as error:
                    raise RuntimeError('This development host needs the optional cryptography package.') from error
            self._open = True
            return
        self.mode = mode
        self.dll = c.WinDLL('bcrypt.dll')
        signatures = {
            'BCryptOpenAlgorithmProvider': [c.POINTER(c.c_void_p), c.c_wchar_p, c.c_wchar_p, c.c_ulong],
            'BCryptSetProperty': [c.c_void_p, c.c_wchar_p, c.c_void_p, c.c_ulong, c.c_ulong],
            'BCryptGenerateSymmetricKey': [c.c_void_p, c.POINTER(c.c_void_p), c.c_void_p, c.c_ulong, c.c_void_p, c.c_ulong, c.c_ulong],
            'BCryptDecrypt': [c.c_void_p, c.c_void_p, c.c_ulong, c.c_void_p, c.c_void_p, c.c_ulong, c.c_void_p, c.c_ulong, c.POINTER(c.c_ulong), c.c_ulong],
            'BCryptEncrypt': [c.c_void_p, c.c_void_p, c.c_ulong, c.c_void_p, c.c_void_p, c.c_ulong, c.c_void_p, c.c_ulong, c.POINTER(c.c_ulong), c.c_ulong],
            'BCryptDestroyKey': [c.c_void_p],
            'BCryptCloseAlgorithmProvider': [c.c_void_p, c.c_ulong],
        }
        for name, args in signatures.items():
            fn = getattr(self.dll, name)
            fn.argtypes = args
            fn.restype = c.c_long
        self.handle = c.c_void_p()
        self._check(self.dll.BCryptOpenAlgorithmProvider(c.byref(self.handle), 'AES', None, 0))
        try:
            chaining = c.create_unicode_buffer('ChainingMode' + mode)
            self._check(self.dll.BCryptSetProperty(self.handle, 'ChainingMode', chaining,
                                                  c.sizeof(chaining), 0))
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _check(status: int) -> None:
        if status:
            raise OSError(f'CNG status 0x{status & 0xffffffff:08x}')

    def transform(self, data: bytes, key: bytes, *, direction: str,
                  iv: bytes | None = None) -> bytes:
        validate_parameters(data, key, self.mode, iv, direction)
        if self._portable:
            if not self._open:
                raise RuntimeError('AES provider is closed.')
            if self._linux:
                if len(data) > MAX_LINUX_AES_BYTES:
                    raise ValueError('Linux AES payload exceeds the 64 MiB safety bound.')
                # A fresh cipher per call prevents CBC state from leaking between
                # operations. ECB/CBC encrypt/decrypt never adds or strips padding.
                cipher = (self._aes.new(key, self._aes.MODE_ECB) if self.mode == 'ECB'
                          else self._aes.new(key, self._aes.MODE_CBC, iv=iv))
                result = cipher.decrypt(data) if direction == 'decrypt' else cipher.encrypt(data)
                if type(result) is not bytes or len(result) != len(data):
                    raise RuntimeError('Unexpected unpadded AES output size.')
                return result
            provider = self._ciphers
            mode = provider.modes.ECB() if self.mode == 'ECB' else provider.modes.CBC(iv)
            cipher = provider.Cipher(provider.algorithms.AES(key), mode)
            worker = cipher.decryptor() if direction == 'decrypt' else cipher.encryptor()
            return worker.update(data) + worker.finalize()
        if not self.handle.value:
            raise RuntimeError('AES provider is closed.')
        handle = c.c_void_p()
        keybuf = c.create_string_buffer(key)
        self._check(self.dll.BCryptGenerateSymmetricKey(self.handle, c.byref(handle),
                                                       None, 0, keybuf, len(key), 0))
        try:
            inp = c.create_string_buffer(data)
            out = c.create_string_buffer(len(data))
            # CNG may mutate its IV buffer. Never mutate the caller's IV.
            ivbuf = c.create_string_buffer(iv) if iv is not None else None
            written = c.c_ulong()
            fn = self.dll.BCryptDecrypt if direction == 'decrypt' else self.dll.BCryptEncrypt
            self._check(fn(handle, inp, len(data), None, ivbuf,
                           len(iv) if iv is not None else 0, out, len(data),
                           c.byref(written), 0))
            if written.value != len(data):
                raise RuntimeError('Unexpected unpadded AES output size.')
            return out.raw[:written.value]
        finally:
            self.dll.BCryptDestroyKey(handle)

    def close(self) -> None:
        if self._portable:
            self._open = False
            return
        if self.handle.value:
            self._check(self.dll.BCryptCloseAlgorithmProvider(self.handle, 0))
            self.handle.value = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def decrypt(raw: bytes) -> bytes:
    if not raw or len(raw)%16 or len(raw)>16*1024*1024:
        raise ValueError('Empty, truncated or oversized encrypted save.')
    with CNG_AES('ECB') as aes:
        plain=aes.transform(raw,SAVE_KEY,direction='decrypt')
    size=struct.unpack_from('>I',plain)[0]
    if not len(raw)-19<=size<=len(raw)-4 or plain[4:8]!=b'GVAS' or any(plain[4+size:]):
        raise ValueError('Unsupported or damaged save: envelope, signature or padding is invalid.')
    return plain

def encrypt(plain: bytes) -> bytes:
    if not plain or len(plain)%16 or len(plain)>16*1024*1024:
        raise ValueError('Empty, truncated or oversized plaintext save.')
    size=struct.unpack_from('>I',plain)[0]
    if not len(plain)-19<=size<=len(plain)-4 or plain[4:8]!=b'GVAS' or any(plain[4+size:]):
        raise ValueError('Invalid plaintext envelope.')
    with CNG_AES('ECB') as aes:
        return aes.transform(plain,SAVE_KEY,direction='encrypt')
