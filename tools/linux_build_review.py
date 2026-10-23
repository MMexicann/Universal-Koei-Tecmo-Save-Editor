"""Exact Linux wheel metadata and narrowly scoped NumPy provenance review."""
import ast
import hashlib
import json
from pathlib import Path
import re
import sys

from tools import numpy_build_provenance as provenance
from tools import package_release as release

ROOT = Path(__file__).resolve().parents[1]
AES_NATIVE_FILES = frozenset({'Crypto/Cipher/_raw_aes.abi3.so',
                              'Crypto/Cipher/_raw_aesni.abi3.so',
                              'Crypto/Cipher/_raw_cbc.abi3.so',
                              'Crypto/Cipher/_raw_ecb.abi3.so',
                              'Crypto/Util/_cpuid_c.abi3.so'})


def verify_linux_lock(root=ROOT):
    root = Path(root)
    review = json.loads((root / 'tools/linux_dependency_review.json').read_text(encoding='utf-8'))
    locked, flags = {}, set()
    for line in (root / 'tools/requirements/linux-build.txt').read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line in {'--require-hashes', '--only-binary=:all:'} and line not in flags:
            flags.add(line)
            continue
        match = re.fullmatch(r'([\w-]+)==([^ ]+) --hash=sha256:([0-9a-f]{64})', line)
        if match is None:
            raise ValueError('Unreviewed Linux wheel lock syntax.')
        name, version, digest = match.groups()
        directory = name.replace('-', '_') + '-' + version + '.dist-info'
        if directory in locked:
            raise ValueError('Duplicate Linux wheel lock entry.')
        locked[directory] = digest
    if (review.get('python') != '3.13' or review.get('architecture') != 'x86_64'
            or locked != review.get('wheels') or flags != {'--require-hashes', '--only-binary=:all:'}):
        raise ValueError('Linux wheel metadata review differs from its hash lock.')
    if not AES_NATIVE_FILES <= review.get('native_wheel_files', {}).keys():
        raise ValueError('The reviewed Linux AES native provider is incomplete.')
    return review


def filter_linux_metadata(datas, root=ROOT):
    review = verify_linux_lock(root)
    retained, seen = [], set()
    for entry in datas:
        if not isinstance(entry, (tuple, list)) or len(entry) != 3:
            raise ValueError('Invalid Linux runtime data entry.')
        name, source, kind = entry
        normalized, path = release._bundled_path(name)
        if normalized in {'_tcl_data/tclAppInit.c', '_tk_data/tkAppInit.c'}:
            # Upstream sample embedding sources are not runtime scripts.
            continue
        if not release._is_distribution_metadata(path):
            retained.append(entry)
            continue
        if (kind != 'DATA' or path.parts[0] not in review['wheels']
                or any(part.endswith('.dist-info') for part in path.parts[1:])):
            raise ValueError('Unreviewed Linux dependency metadata collection.')
        if normalized in review['runtime_metadata']:
            data = Path(source).read_bytes()
            if (normalized in seen or len(data) > 65536
                    or hashlib.sha256(data).hexdigest() != review['runtime_metadata'][normalized]):
                raise ValueError('Linux dependency metadata differs from the reviewed wheel.')
            release.scan_bundled_data(normalized, data)
            retained.append(entry)
            seen.add(normalized)
    if seen != review['runtime_metadata'].keys():
        raise ValueError('Required Linux runtime dependency metadata is missing.')
    return retained


def reviewed_numpy_code(module, source, filename, root=ROOT):
    """Change only upstream build-location fields and three documentation strings."""
    review = verify_linux_lock(root)
    member = module.replace('.', '/') + '.py'
    if (member not in review['numpy_sources'] or len(source) > provenance.MAX_SOURCE_BYTES
            or hashlib.sha256(source).hexdigest() != review['numpy_sources'][member]):
        raise ValueError('Unreviewed Linux NumPy source; repeat the wheel review.')
    tree = ast.parse(source, filename=filename)
    if module == 'numpy.__config__':
        assignments = [n for n in tree.body if isinstance(n, ast.Assign)
                       and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                       and n.targets[0].id == 'CONFIG']
        if (len(assignments) != 1 or not isinstance(assignments[0].value, ast.Call)
                or not isinstance(assignments[0].value.func, ast.Name)
                or assignments[0].value.func.id != '_cleanup' or len(assignments[0].value.args) != 1):
            raise ValueError('Unexpected Linux NumPy configuration structure.')
        for path in provenance.CONFIG_PATHS + (
                ('Build Dependencies', 'blas', 'pc file directory'),
                ('Build Dependencies', 'lapack', 'pc file directory')):
            value = assignments[0].value.args[0]
            for key in path:
                value = provenance._dictionary_value(value, key)
            if not isinstance(value, ast.Constant) or type(value.value) is not str or not value.value:
                raise ValueError('Unexpected Linux NumPy provenance field.')
            value.value = '<upstream build location>'
    else:
        scopes = [(tree, 'guido', 1)]
        for name, owner, count in (('DataSource', 'guido', 6), ('Repository', 'user', 1)):
            classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name]
            if len(classes) != 1:
                raise ValueError('Unexpected Linux NumPy documentation scope.')
            scopes.append((classes[0], owner, count))
        for scope, owner, count in scopes:
            text = ast.get_docstring(scope, clean=False)
            prefix = '/'.join(('', 'home', owner))
            if text is None or text.count(prefix) != count:
                raise ValueError('Unexpected Linux NumPy documentation examples.')
            scope.body[0].value.value = text.replace(prefix, '/example/data')
    return compile(tree, filename, 'exec', dont_inherit=True, optimize=0)


def sanitize_numpy_hook(api):
    if api.analysis.optimize != 0 or sys.flags.optimize != 0:
        raise ValueError('Linux NumPy review requires unoptimized code-cache mode.')
    source = Path(api.__file__).read_bytes()
    api.module.code = reviewed_numpy_code(api.__name__, source, api.__file__)
    api.set_module_collection_mode(None, 'pyz')
