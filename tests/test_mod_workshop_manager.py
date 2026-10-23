"""Procedural Workshop-to-Manager packages, including review and path guards."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from koei_editor.shared.mod_manager import ModManager, ModManagerError
from koei_editor.shared.mod_workshop.asset_explorer import register_replacement
from koei_editor.shared.mod_workshop.manager_export import export_manager_package, review_manager_package
from koei_editor.shared.mod_workshop.models import Dependency, ModManifest
from koei_editor.shared.mod_workshop.project_manager import initialize_project, load_project, save_manifest
from koei_editor.shared.mod_workshop.validation import CompatibilityContext


def make_workshop(root, game_id='nioh2_pc'):
    manifest = ModManifest('workshop.test', 'Workshop Test', '1.0.0', 'Test Creator',
                           'Procedural author-provided mod, not a game asset.',
                           game_id, '1.0.0', 'Windows PC', 'MIT')
    project = initialize_project(root / 'project', manifest, 'blank')
    records = []
    targets = ('MyMod/mod.ini', 'MyMod/model.dds') if game_id == 'nioh2_pc' else ('1234abcd.g1t',)
    for number, target in enumerate(targets):
        source = project / 'assets' / f'replacement-{number}.bin'
        source.write_bytes(b'[Mod]\nName=Test\n' if target.endswith('.ini') else b'procedural texture bytes')
        records.append(register_replacement(project, source, target, license='MIT', rights_status='creator-owned'))
    save_manifest(project, replace(manifest, replacements=tuple(records)))
    return project, CompatibilityContext(game_id, '1.0.0', 'Windows PC')


class WorkshopManagerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.project, self.context = make_workshop(self.root)

    def export(self, output, token=None):
        token = token or review_manager_package(self.project, self.context)['review_token']
        return export_manager_package(self.project, output, self.context, review_token=token)

    def test_review_export_import_preserve_sources_and_all_payloads(self):
        snapshot = {item: item.read_bytes() for item in self.project.rglob('*') if item.is_file()}
        review = review_manager_package(self.project, self.context)
        self.assertTrue(review['read_only'])
        self.assertFalse(review['in_game_verified'])
        self.assertEqual(len(review['package_review']['files']), 2)
        output = self.root / 'managed.zip'
        exported = self.export(output, review['review_token'])
        self.assertEqual(exported['status'], 'exported')
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(set(archive.namelist()), {'koei-mod.json', 'README.md', 'MyMod/mod.ini', 'MyMod/model.dds'})
            self.assertNotIn(str(self.project).encode(), archive.read('README.md'))
        manager = ModManager(self.root / 'library', game_id='nioh2_pc')
        mod = manager.import_archive(output)
        self.assertEqual(mod.id, 'workshop.test')
        self.assertFalse(mod.installed)
        self.assertEqual(len(mod.files), 2)
        for source, data in snapshot.items():
            self.assertEqual(source.read_bytes(), data)

    def test_export_is_reproducible_and_refuses_stale_metadata_review(self):
        first, second = self.root / 'first.zip', self.root / 'second.zip'
        review = review_manager_package(self.project, self.context)
        self.export(first, review['review_token'])
        self.export(second, review['review_token'])
        self.assertEqual(first.read_bytes(), second.read_bytes())
        save_manifest(self.project, replace(load_project(self.project), name='Changed after review'))
        with self.assertRaisesRegex(ValueError, 'Review it again'):
            self.export(self.root / 'stale.zip', review['review_token'])
        self.assertFalse((self.root / 'stale.zip').exists())

    def test_existing_and_dangling_aliases_never_replace_or_follow(self):
        existing = self.root / 'existing.zip'
        existing.write_bytes(b'foreign file')
        with self.assertRaises(FileExistsError):
            self.export(existing)
        self.assertEqual(existing.read_bytes(), b'foreign file')
        target, alias = self.root / 'never-created.zip', self.root / 'alias.zip'
        try:
            alias.symlink_to(target)
        except OSError as error:
            self.skipTest(str(error))
        with self.assertRaises(ValueError):
            self.export(alias)
        self.assertFalse(target.exists())

    def test_late_destination_collision_preserves_foreign_file(self):
        from koei_editor.shared.mod_workshop import manager_export
        output = self.root / 'collision.zip'
        publish = manager_export.publish_new_child_bound
        def collide(raw, parent, name, identity, **kwargs):
            output.write_bytes(b'foreign race winner')
            return publish(raw, parent, name, identity, **kwargs)
        with patch.object(manager_export, 'publish_new_child_bound', side_effect=collide):
            with self.assertRaises((ValueError, FileExistsError)):
                self.export(output)
        self.assertEqual(output.read_bytes(), b'foreign race winner')

    def test_source_change_context_and_unrepresentable_dependencies_reject(self):
        original = load_project(self.project)
        for dependency in (Dependency('other.mod', '>=1.0.0'), Dependency('other.mod', '*', True)):
            save_manifest(self.project, replace(original, dependencies=(dependency,)))
            with self.assertRaisesRegex(ValueError, 'cannot preserve'):
                review_manager_package(self.project, self.context)
        save_manifest(self.project, original)
        with self.assertRaises(ValueError):
            review_manager_package(self.project, replace(self.context, game_id='other-game'))
        review = review_manager_package(self.project, self.context)
        (self.project / original.replacements[0].source_path).write_bytes(b'changed after registration')
        with self.assertRaises(ValueError):
            self.export(self.root / 'changed.zip', review['review_token'])
        self.assertFalse((self.root / 'changed.zip').exists())

    def test_unsupported_method_or_platform_never_gets_guessed(self):
        original = load_project(self.project)
        save_manifest(self.project, replace(original, game_id='unknown-game'))
        with self.assertRaises(ModManagerError):
            review_manager_package(self.project, replace(self.context, game_id='unknown-game'))
        save_manifest(self.project, replace(original, platform='PlayStation 5'))
        with self.assertRaisesRegex(ValueError, 'Windows PC'):
            review_manager_package(self.project, replace(self.context, platform='PlayStation 5'))

    def test_document_replacement_cannot_disappear_as_manager_metadata(self):
        original = load_project(self.project)
        record = original.replacements[1]
        save_manifest(self.project, replace(original, replacements=original.replacements + (replace(record, target_path='MyMod/license.txt'),)))
        with self.assertRaisesRegex(ValueError, 'installable manager payload'):
            review_manager_package(self.project, self.context)

    def test_nioh3_uses_its_own_hash_named_payload_method(self):
        other = self.root / 'nioh3'
        other.mkdir()
        project, context = make_workshop(other, 'nioh3_pc')
        review = review_manager_package(project, context)
        self.assertEqual(review['package_review']['method_id'], 'nioh3-loose-file-loader')
        output = other / 'nioh3.zip'
        export_manager_package(project, output, context, review_token=review['review_token'])
        manager = ModManager(other / 'library', game_id='nioh3_pc')
        imported = manager.import_archive(output)
        self.assertEqual([item.path for item in imported.files], ['1234abcd.g1t'])
        self.assertFalse(imported.installed)


if __name__ == '__main__':
    unittest.main()
