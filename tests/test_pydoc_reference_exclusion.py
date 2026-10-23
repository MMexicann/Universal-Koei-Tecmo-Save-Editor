"""Omit unused topic-reference data while preserving object documentation."""
import marshal
import pydoc
import sys
import unittest
from unittest.mock import patch

from tools import build_windows as build
from tools.package_release import scan_bundled_data


def documented_function(value):
    """Return the supplied value for the ordinary object-documentation check."""
    return value


class PydocReferenceExclusionTests(unittest.TestCase):
    def test_both_builds_exclude_only_the_unused_topic_package_in_addition_to_compilers(self):
        for standalone in (False, True):
            args = build.build_args(standalone=standalone)
            excluded = [args[index + 1] for index, arg in enumerate(args) if arg == '--exclude-module']
            self.assertEqual(set(excluded), {'setuptools', 'distutils', 'pkg_resources', 'pydoc_data'})
            self.assertEqual(excluded.count('pydoc_data'), 1)
            self.assertNotIn('pydoc', excluded)

    def test_normal_pydoc_introspection_works_with_all_topic_imports_blocked(self):
        with patch.dict(sys.modules, {'pydoc_data': None, 'pydoc_data.topics': None}):
            self.assertEqual(documented_function(123), 123)
            self.assertIn('ordinary object-documentation check', pydoc.getdoc(documented_function))
            rendered = pydoc.plain(pydoc.render_doc(documented_function))
            self.assertIn('documented_function', rendered)
            self.assertIn('Return the supplied value', rendered)
            self.assertIn('class dict', pydoc.plain(pydoc.render_doc(dict)))
            self.assertIsNone(sys.modules['pydoc_data'])
            self.assertIsNone(sys.modules['pydoc_data.topics'])

    def test_privacy_scanner_still_rejects_personal_paths_in_topic_bytes(self):
        value = '/'.join(('', 'home', 'example-owner', 'reference'))
        code = compile('topics = ' + repr({'example': value}), 'pydoc_data/topics.py', 'exec')
        with self.assertRaisesRegex(ValueError, 'Personal home path'):
            scan_bundled_data('pydoc_data.topics', marshal.dumps(code))


if __name__ == '__main__':
    unittest.main()
