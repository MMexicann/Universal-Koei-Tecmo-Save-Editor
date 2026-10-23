"""Collect only the pinned AES ECB/CBC native libraries used by Linux saves."""
from pathlib import Path

from PyInstaller.utils.hooks import get_package_paths

_base, _package = get_package_paths('Crypto')
binaries = []
for _relative in ('Cipher/_raw_aes.abi3.so', 'Cipher/_raw_aesni.abi3.so',
                  'Cipher/_raw_cbc.abi3.so', 'Cipher/_raw_ecb.abi3.so',
                  'Util/_cpuid_c.abi3.so'):
    _source = Path(_package) / _relative
    if not _source.is_file() or _source.is_symlink():
        raise ValueError('The reviewed Linux AES native provider is incomplete.')
    binaries.append((str(_source), 'Crypto/' + str(Path(_relative).parent)))
