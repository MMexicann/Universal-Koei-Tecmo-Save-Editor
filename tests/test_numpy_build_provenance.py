"""Only reviewed NumPy provenance fields/docstrings may change during builds."""
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools import numpy_build_provenance as provenance


def config_source():
    data = {'Build Dependencies': {
        library: {'include directory': 'original-include', 'lib directory': 'original-lib',
                  'version': '1.2.3', 'found': True, 'pc file directory': 'original-pc'}
        for library in ('blas', 'lapack')},
        'Python Information': {'path': 'original-python', 'version': '3.14'},
        'SIMD Extensions': {'baseline': ['SSE2'], 'found': ['AVX2']}}
    return ('def _cleanup(data):\n    return data\nCONFIG = _cleanup(' + repr(data)
            + ')\ndef show_config(mode="dicts"):\n    return CONFIG\n').encode()


def datasource_source():
    prefix = '/'.join(('', 'home', 'guido'))
    other = '/'.join(('', 'home', 'user'))
    return (repr('module ' + prefix) + '\nclass DataSource:\n    '
            + repr(('example ' + prefix + '\n') * 6)
            + '\n    def unchanged(self):\n        return ' + repr(prefix)
            + '\nclass Repository:\n    ' + repr('repository ' + other)
            + '\n    def unchanged(self):\n        return 123\n').encode()


class NumpyProvenanceTests(unittest.TestCase):
    def compile_reviewed(self, module, source, filename='preserved-source.py'):
        with patch.dict(provenance.REVIEWED_SOURCES, {module: hashlib.sha256(source).hexdigest()}):
            return provenance.reviewed_numpy_code(module, source, filename)

    def test_config_changes_exactly_five_paths_and_preserves_runtime_configuration(self):
        source = config_source()
        before, after = {}, {}
        exec(compile(source, 'preserved-source.py', 'exec'), before)
        code = self.compile_reviewed('numpy.__config__', source)
        exec(code, after)
        expected = before['CONFIG']
        for path in provenance.CONFIG_PATHS:
            target = expected
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = '<upstream build ' + ('Python' if path[0] == 'Python Information' else path[-1]) + '>'
        self.assertEqual(after['show_config']('dicts'), expected)
        self.assertEqual(after['show_config'].__code__.co_code, before['show_config'].__code__.co_code)
        self.assertEqual(code.co_filename, 'preserved-source.py')

    def test_only_three_declared_docstrings_change_with_executable_values_preserved(self):
        source = datasource_source()
        before, after = {}, {}
        exec(compile(source, 'original-filename.py', 'exec'), before)
        code = self.compile_reviewed('numpy.lib._datasource', source, 'original-filename.py')
        exec(code, after)
        prefix = '/'.join(('', 'home', 'guido'))
        self.assertEqual(after['DataSource']().unchanged(), prefix)
        self.assertEqual(after['Repository']().unchanged(), 123)
        for name in ('__doc__', 'DataSource', 'Repository'):
            doc = after[name] if name == '__doc__' else after[name].__doc__
            self.assertNotIn('/'.join(('', 'home', '')), doc)
            self.assertIn('/example/data', doc)
        for name in ('DataSource', 'Repository'):
            old, new = before[name].unchanged.__code__, after[name].unchanged.__code__
            self.assertEqual((new.co_code, new.co_consts, new.co_filename),
                             (old.co_code, old.co_consts, old.co_filename))

    def test_hash_tampering_unknown_module_and_oversized_source_fail_closed(self):
        source = config_source()
        with patch.dict(provenance.REVIEWED_SOURCES, {'numpy.__config__': hashlib.sha256(source).hexdigest()}):
            for module, raw in (('numpy.__config__', source + b'\n# altered'),
                                ('numpy.unreviewed', source),
                                ('numpy.__config__', b'x' * (provenance.MAX_SOURCE_BYTES + 1))):
                with self.subTest(module=module, size=len(raw)), self.assertRaisesRegex(ValueError, 'Unreviewed NumPy source'):
                    provenance.reviewed_numpy_code(module, raw, 'unchanged.py')

    def test_even_reviewed_digest_requires_exact_declared_ast_scopes(self):
        for module, source in (('numpy.__config__', b'CONFIG = {}\n'),
                               ('numpy.lib._datasource', b'"""missing scopes"""\n')):
            with self.subTest(module=module), self.assertRaisesRegex(ValueError, 'Unexpected reviewed NumPy'):
                self.compile_reviewed(module, source)

    def test_hook_updates_only_graph_code_with_original_filename_and_source_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '__config__.py'
            source = config_source()
            path.write_bytes(source)
            api = SimpleNamespace(__name__='numpy.__config__', __file__=str(path),
                                  analysis=SimpleNamespace(optimize=0), module=SimpleNamespace(code=None),
                                  set_module_collection_mode=Mock())
            with patch.dict(provenance.REVIEWED_SOURCES, {'numpy.__config__': hashlib.sha256(source).hexdigest()}), \
                    patch.object(provenance, 'verify_dependency_metadata_lock') as lock:
                provenance.sanitize_numpy_hook(api)
            lock.assert_called_once_with()
            api.set_module_collection_mode.assert_called_once_with(None, 'pyz')
            self.assertEqual(api.module.code.co_filename, str(path))
            self.assertEqual(path.read_bytes(), source)

    def test_hook_rejects_cache_bypass_and_unreviewed_source_without_replacing_code(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '__config__.py'
            path.write_bytes(b'# not the reviewed member\n')
            original = object()
            api = SimpleNamespace(__name__='numpy.__config__', __file__=str(path),
                                  analysis=SimpleNamespace(optimize=1), module=SimpleNamespace(code=original),
                                  set_module_collection_mode=Mock())
            with self.assertRaisesRegex(ValueError, 'code-cache mode'):
                provenance.sanitize_numpy_hook(api)
            api.analysis.optimize = 0
            with patch.object(provenance, 'verify_dependency_metadata_lock'), \
                    self.assertRaisesRegex(ValueError, 'Unreviewed NumPy source'):
                provenance.sanitize_numpy_hook(api)
            self.assertIs(api.module.code, original)
            api.set_module_collection_mode.assert_not_called()


if __name__ == '__main__':
    unittest.main()
