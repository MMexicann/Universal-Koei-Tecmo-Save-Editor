"""Real headless mod CLI subprocesses with procedural packages only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.test_mod_workshop_manager import make_workshop


class ModCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def invoke(self, *arguments):
        environment = dict(os.environ, DISPLAY='')
        return subprocess.run([sys.executable, '-m', 'koei_editor.cli', 'mods', *map(str, arguments)],
                              env=environment, text=True, encoding='utf-8', capture_output=True, timeout=30)

    def successful(self, *arguments):
        result = self.invoke(*arguments)
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        report = json.loads(result.stdout)
        self.assertTrue(report['success'])
        return report

    def test_games_and_unknown_selector_are_headless_and_explicit(self):
        report = self.successful('games')
        self.assertTrue(report['read_only'])
        self.assertIn('nioh2_pc', {item['game_id'] for item in report['games']})
        for item in report['games']:
            self.assertFalse(item['in_game_verified'])
        result = self.invoke('validate', '--game', 'typo', self.root / 'missing.zip')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertIn('Unknown mod game ID', result.stderr)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_workshop_review_export_dry_import_import_list_preserve_inputs(self):
        project, context = make_workshop(self.root)
        context_file = self.root / 'context.json'
        context_file.write_text(json.dumps({'game_id': context.game_id, 'game_version': context.game_version,
                                           'platform': context.platform, 'installed_mods': []}), encoding='utf-8')
        original = {path: path.read_bytes() for path in project.rglob('*') if path.is_file()}
        review = self.successful('workshop-review', project, '--context', context_file)
        archive = self.root / 'manager.zip'
        rejected = self.invoke('workshop-export', project, '--context', context_file,
                               '--output', archive, '--review-token', 'bad-token')
        self.assertEqual((rejected.returncode, rejected.stdout), (1, ''))
        self.assertFalse(archive.exists())
        self.successful('workshop-export', project, '--context', context_file,
                        '--output', archive, '--review-token', review['review_token'])
        archive_bytes = archive.read_bytes()
        validated = self.successful('validate', '--game', 'nioh2_pc', archive)
        self.assertEqual(validated['package_review']['id'], 'workshop.test')
        library = self.root / 'library'
        self.successful('list', '--game', 'nioh2_pc', '--library', library)
        self.assertFalse(library.exists())
        self.successful('import', '--game', 'nioh2_pc', archive, '--library', library, '--dry-run')
        self.assertFalse(library.exists())
        imported = self.successful('import', '--game', 'nioh2_pc', archive, '--library', library)
        self.assertFalse(imported['read_only'])
        self.assertFalse(imported['mod']['installed'])
        listed = self.successful('list', '--game', 'nioh2_pc', '--library', library)
        self.assertEqual([mod['id'] for mod in listed['mods']], ['workshop.test'])
        self.assertEqual(archive.read_bytes(), archive_bytes)
        for source, data in original.items():
            self.assertEqual(source.read_bytes(), data)
        rejected = self.invoke('workshop-export', project, '--context', context_file,
                               '--output', archive, '--review-token', review['review_token'])
        self.assertEqual((rejected.returncode, rejected.stdout), (1, ''))
        self.assertEqual(archive.read_bytes(), archive_bytes)

    def test_bad_package_and_empty_paths_never_create_library(self):
        bad = self.root / 'bad.zip'
        bad.write_bytes(b'not a ZIP')
        library = self.root / 'library'
        result = self.invoke('import', '--game', 'nioh2_pc', bad, '--library', library)
        self.assertEqual((result.returncode, result.stdout), (1, ''))
        self.assertFalse(library.exists())
        result = self.invoke('import', '--game', 'nioh2_pc', bad, '--library', '')
        self.assertEqual((result.returncode, result.stdout), (2, ''))
        self.assertEqual(bad.read_bytes(), b'not a ZIP')


if __name__ == '__main__':
    unittest.main()
