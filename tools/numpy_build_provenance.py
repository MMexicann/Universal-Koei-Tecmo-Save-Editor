"""Narrow build-time edits for two exact members of the locked NumPy wheel."""
import ast
import hashlib
from pathlib import Path
import sys

from tools.package_release import verify_dependency_metadata_lock

REVIEWED_SOURCES = {
    'numpy.__config__': '7484592aa3f8dc04c44d13ab7520d27429ee47b03090a49b6a6c7a221cf52130',
    'numpy.lib._datasource': 'dbbf26c57ccd4d2dc435304f4418f967411261230fa2f9850e1788f57db7ea1f',
}
MAX_SOURCE_BYTES = 65536
CONFIG_PATHS = (
    ('Build Dependencies', 'blas', 'include directory'),
    ('Build Dependencies', 'blas', 'lib directory'),
    ('Build Dependencies', 'lapack', 'include directory'),
    ('Build Dependencies', 'lapack', 'lib directory'),
    ('Python Information', 'path'),
)


def _dictionary_value(node, key):
    if not isinstance(node, ast.Dict):
        raise ValueError('Unexpected reviewed NumPy configuration structure.')
    matches = [value for candidate, value in zip(node.keys, node.values)
               if isinstance(candidate, ast.Constant) and candidate.value == key]
    if len(matches) != 1:
        raise ValueError('Unexpected reviewed NumPy configuration key.')
    return matches[0]


def reviewed_numpy_code(module, source, filename):
    """Compile exact reviewed source, changing only declared provenance/docs."""
    if (module not in REVIEWED_SOURCES or type(source) is not bytes
            or len(source) > MAX_SOURCE_BYTES
            or hashlib.sha256(source).hexdigest() != REVIEWED_SOURCES[module]):
        raise ValueError('Unreviewed NumPy source; repeat the locked-wheel provenance review.')
    tree = ast.parse(source, filename=filename)
    if module == 'numpy.__config__':
        assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                       and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                       and node.targets[0].id == 'CONFIG']
        if (len(assignments) != 1 or not isinstance(assignments[0].value, ast.Call)
                or not isinstance(assignments[0].value.func, ast.Name)
                or assignments[0].value.func.id != '_cleanup' or len(assignments[0].value.args) != 1):
            raise ValueError('Unexpected reviewed NumPy CONFIG assignment.')
        config = assignments[0].value.args[0]
        for path in CONFIG_PATHS:
            value = config
            for key in path:
                value = _dictionary_value(value, key)
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str) or not value.value:
                raise ValueError('Unexpected reviewed NumPy build path.')
            value.value = '<upstream build ' + ('Python' if path[0] == 'Python Information' else path[-1]) + '>'
    else:
        # Only these three docstrings contain historical absolute-path examples.
        # Comments and every executable statement/constant are left untouched.
        scopes = [(tree, 'guido', 1)]
        for name, owner, count in (('DataSource', 'guido', 6), ('Repository', 'user', 1)):
            classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name]
            if len(classes) != 1:
                raise ValueError('Unexpected reviewed NumPy documentation scope.')
            scopes.append((classes[0], owner, count))
        for scope, owner, count in scopes:
            text = ast.get_docstring(scope, clean=False)
            prefix = '/'.join(('', 'home', owner))
            if text is None or text.count(prefix) != count:
                raise ValueError('Unexpected reviewed NumPy documentation examples.')
            scope.body[0].value.value = text.replace(prefix, '/example/data')
    return compile(tree, filename, 'exec', dont_inherit=True, optimize=0)


def sanitize_numpy_hook(api):
    """Use PyInstaller's graph code object so its normal PYZ writer sees edits."""
    if api.analysis.optimize != 0 or sys.flags.optimize != 0:
        raise ValueError('Reviewed NumPy provenance requires unoptimized build/code-cache mode.')
    verify_dependency_metadata_lock()
    with Path(api.__file__).open('rb') as stream:
        source = stream.read(MAX_SOURCE_BYTES + 1)
    api.module.code = reviewed_numpy_code(api.__name__, source, api.__file__)
    api.set_module_collection_mode(None, 'pyz')
