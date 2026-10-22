"""The custom pre-import hook preserves explicit compiler exclusions."""
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import build_windows as build
from tools import package_release as release

PROJECT = Path(__file__).resolve().parents[1]
HOOK = 'tools/pyinstaller_hooks/pre_safe_import_module/hook-distutils.py'
ROOTS = ('setuptools', 'distutils', 'pkg_resources')


class CompilerExclusionHookTests(unittest.TestCase):
    def setUp(self):
        # The ordinary test suite does not require the platform build tool.
        # A separate real pinned-PyInstaller Analysis qualifies the integration.
        class ExcludedModule:
            pass

        self.nodes = {name: ExcludedModule() for name in ROOTS}
        self.api = SimpleNamespace(
            module_name='distutils',
            module_graph=SimpleNamespace(find_node=Mock(side_effect=self.nodes.get)),
            add_alias_module=Mock(side_effect=AssertionError('Excluded compiler alias created')),
        )
        module = SimpleNamespace(ExcludedModule=ExcludedModule)
        imported = patch.dict(sys.modules, {'PyInstaller.lib.modulegraph.modulegraph': module})
        imported.start()
        self.addCleanup(imported.stop)
        self.hook = runpy.run_path(str(PROJECT / HOOK))['pre_safe_import_module']

    def test_excluded_roots_are_retained_without_creating_any_alias(self):
        self.hook(self.api)
        self.assertEqual([call.args[0] for call in self.api.module_graph.find_node.call_args_list], list(ROOTS))
        self.api.add_alias_module.assert_not_called()

    def test_missing_or_nonexcluded_compiler_root_blocks_build(self):
        original = dict(self.nodes)
        for root in ROOTS:
            for replacement in (None, object()):
                self.nodes.update(original)
                self.nodes[root] = replacement
                with self.subTest(root=root, replacement=type(replacement).__name__), \
                        self.assertRaisesRegex(ValueError, 'compiler exclusion is missing: ' + root):
                    self.hook(self.api)
                self.api.add_alias_module.assert_not_called()

    def test_other_hook_target_is_rejected(self):
        self.api.module_name = 'another_module'
        with self.assertRaisesRegex(ValueError, 'Unexpected compiler-exclusion hook target'):
            self.hook(self.api)
        self.api.module_graph.find_node.assert_not_called()
        self.api.add_alias_module.assert_not_called()

    def test_both_builds_supply_reviewed_hook_and_exact_exclusions(self):
        self.assertIn(HOOK, release.TOOL_FILES)
        for standalone in (False, True):
            args = build.build_args(standalone=standalone)
            self.assertEqual(args[args.index('--additional-hooks-dir') + 1],
                             str(build.ROOT / 'tools/pyinstaller_hooks'))
            excluded = {args[index + 1] for index, value in enumerate(args) if value == '--exclude-module'}
            self.assertEqual(excluded, set(ROOTS))


if __name__ == '__main__':
    unittest.main()
