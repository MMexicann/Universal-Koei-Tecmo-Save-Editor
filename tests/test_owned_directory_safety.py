"""Real unsupported-platform refusals; no owned-directory contract double.

Positive native ownership workflows run in the Vault/Profile tests on Windows.
These cases exercise actual non-Windows production dispatch and require no
new payload, lock, directory or cleanup side effects on refusal.
"""
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import copy_storage, playthrough_profiles as profiles
from koei_editor.shared import save_vault as vault


@unittest.skipIf(os.name == 'nt', 'Actual unsupported-platform refusal contract.')
class UnsupportedOwnedDirectoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'private-source.dat'
        self.source.write_bytes(b'preserve exact private source')

    def tree(self):
        return tuple((str(path.relative_to(self.root)),
                      path.read_bytes() if path.is_file() else None)
                     for path in sorted(self.root.rglob('*')))

    def assert_refuses_without_writes(self, operation):
        before = self.tree()
        with patch.object(os, 'mkdir', side_effect=AssertionError('Unsupported operation attempted mkdir')):
            with self.assertRaisesRegex(SaveError, '(?i)(owned|atomic|support|Windows)'):
                operation()
        self.assertEqual(self.tree(), before)
        self.assertEqual(self.source.read_bytes(), b'preserve exact private source')

    def seed_vault(self):
        root = self.root / 'existing-vault'
        root.mkdir()
        objects = root / 'objects'
        objects.mkdir()
        payload = {'schema_version': 1, 'snapshots': [], 'branches': {}}
        (root / 'index.json').write_bytes(vault._json(
            {'payload': payload, 'sha256': vault._digest(vault._json(payload))}))
        # Fixture constructs an already selected ordinary store without calling
        # its lock-requiring constructor. The tested methods/guards are real.
        store = object.__new__(vault.SaveVault)
        store.root, store.objects = root, objects
        store._root_identity = root.stat().st_dev, root.stat().st_ino
        store._objects_identity = objects.stat().st_dev, objects.stat().st_ino
        return store

    def test_actual_creator_refuses_before_any_directory_or_payload(self):
        identity = self.root.stat().st_dev, self.root.stat().st_ino

        def create():
            with copy_storage.new_directory_child_bound(self.root, 'output', identity):
                self.fail('Unsupported native creator yielded ownership.')

        self.assert_refuses_without_writes(create)

    def test_vault_create_refuses_without_leaving_root_objects_or_index(self):
        self.assert_refuses_without_writes(lambda: vault.SaveVault.create(self.root / 'new-vault'))

    def test_opening_existing_vault_refuses_lock_without_altering_store(self):
        store = self.seed_vault()
        self.assert_refuses_without_writes(lambda: vault.SaveVault(store.root))

    def test_existing_vault_lock_and_restore_refuse_without_cleanup_or_output(self):
        store = self.seed_vault()
        self.assert_refuses_without_writes(store.list_snapshots)
        self.assert_refuses_without_writes(lambda: store.snapshot('wo1', self.source))
        self.assert_refuses_without_writes(
            lambda: store.restore('a' * 32, self.root / 'restore-output'))

    def test_profile_store_creation_refuses_before_manifest_or_lock(self):
        root = self.root / 'existing-vault'
        root.mkdir()
        selected_vault = SimpleNamespace(root=root, list_snapshots=lambda **_: (), verify=lambda _: (),
                                         _root_identity=(root.stat().st_dev, root.stat().st_ino))
        store = profiles.PlaythroughProfileStore(selected_vault)
        # Isolate the real missing profile-directory path after snapshot
        # qualification; this stubs no OS result or directory-creation guard.
        with patch.object(store, '_snapshot', return_value=SimpleNamespace(filename='save.dat')):
            self.assert_refuses_without_writes(
                lambda: store.create_profile('profile', 'wo1', '1.0', 'a' * 32))

    def test_profile_lock_refuses_without_deleting_foreign_entries(self):
        directory = self.root / 'existing-profiles'
        directory.mkdir()
        (directory / 'preserved.json').write_bytes(b'private existing record')

        def lock():
            with profiles._store_lock(directory, (directory.stat().st_dev, directory.stat().st_ino)):
                self.fail('Unsupported lock yielded ownership.')

        self.assert_refuses_without_writes(lock)

    def test_existing_profile_read_and_prepare_fail_before_lock_or_output(self):
        selected_vault = self.seed_vault()
        directory = selected_vault.root / 'playthrough_profiles'
        directory.mkdir()
        (directory / ('a' * 32 + '.json')).write_bytes(b'preserve existing private record')
        store = profiles.PlaythroughProfileStore(selected_vault)
        self.assert_refuses_without_writes(store.list_profiles)
        self.assert_refuses_without_writes(lambda: store.load('a' * 32))
        self.assert_refuses_without_writes(
            lambda: store.prepare_environment('a' * 32, self.root / 'environment', '1.0'))

    def test_nested_materialization_refuses_before_first_flat_payload(self):
        directory = self.root / 'selected-output'
        directory.mkdir()
        identity = directory.stat().st_dev, directory.stat().st_ino
        bundle = {'save.dat': b'no partial flat payload', 'sce_sys/param.sfo': b'private context'}
        self.assert_refuses_without_writes(
            lambda: vault.SaveVault._materialize(bundle, directory, expected_identity=identity))
