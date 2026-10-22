"""Published profile IDs survive failures leaving an owned directory scope."""
from contextlib import contextmanager
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import playthrough_profiles as profiles, save_vault
from tests import test_playthrough_profiles as fixtures


class OwnedDirectoryProfileUncertaintyTests(unittest.TestCase):
    def setUp(self):
        # Explicit platform contract fixture on Linux; native creator on Windows.
        self.fixture = fixtures.PlaythroughProfileIntegrationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def assert_scope_failure_reports_retained_profile(self, failed_name):
        original = profiles.new_directory_child_bound
        injected = []

        @contextmanager
        def fail_after_published_scope(directory, name, expected_identity, **kwargs):
            with original(directory, name, expected_identity, **kwargs) as owned:
                yield owned
            store = self.fixture.vault.root / 'playthrough_profiles'
            if name == failed_name and tuple(store.glob('*.json')):
                injected.append(True)
                raise SaveError('Injected owned directory scope completion failure.')

        with patch.object(profiles, 'new_directory_child_bound', fail_after_published_scope):
            with self.assertRaises(profiles.ProfilePublicationUncertainError) as caught:
                self.fixture.make_profile()
        self.assertEqual(injected, [True])
        profile_id = caught.exception.profile_id
        self.assertRegex(profile_id, r'^[0-9a-f]{32}$')
        loaded = self.fixture.store.load(profile_id)
        self.assertEqual(loaded.id, profile_id)
        self.assertEqual(self.fixture.store.list_profiles(), (loaded,))
        directory = self.fixture.vault.root / 'playthrough_profiles'
        self.assertEqual({path.name for path in directory.iterdir()}, {profile_id + '.json'})
        self.assertEqual(self.fixture.source.read_bytes(), self.fixture.raw)
        self.assertEqual((self.fixture.source.parent / 'PARAM.SFO').read_bytes(), self.fixture.context)

    def test_outer_created_store_scope_failure_preserves_published_profile_id(self):
        self.assert_scope_failure_reports_retained_profile('playthrough_profiles')

    def test_inner_lock_scope_failure_preserves_published_profile_id(self):
        self.assert_scope_failure_reports_retained_profile('.lock')

    def test_prepared_child_directories_stay_owned_through_report_validation(self):
        profile = self.fixture.make_profile()
        destination = self.fixture.root / 'held-environment'
        expected = {destination, destination / 'save-copy', destination / 'components'}
        active, observations = set(), []
        original_create = profiles.new_directory_child_bound
        original_publish = profiles.new_child_bound
        original_read = profiles._read

        @contextmanager
        def track_created_scope(directory, name, expected_identity, **kwargs):
            with original_create(directory, name, expected_identity, **kwargs) as owned:
                path, _info = owned
                active.add(path)
                try:
                    yield owned
                finally:
                    active.remove(path)

        def publish_report(data, directory, name, expected_identity):
            if name == 'playthrough-report.json':
                self.assertTrue(expected <= active)
                observations.append('report-publication')
            return original_publish(data, directory, name, expected_identity)

        def read_report(path, *args, **kwargs):
            if path.name == 'playthrough-report.json':
                self.assertTrue(expected <= active)
                observations.append('report-readback')
            return original_read(path, *args, **kwargs)

        with patch.object(profiles, 'new_directory_child_bound', track_created_scope), \
                patch.object(save_vault, 'new_directory_child_bound', track_created_scope), \
                patch.object(profiles, 'new_child_bound', side_effect=publish_report), \
                patch.object(profiles, '_read', side_effect=read_report):
            result = self.fixture.store.prepare_environment(profile.id, destination, '1.02')
        self.assertEqual(observations, ['report-publication', 'report-readback'])
        self.assertEqual(active, set())
        self.assertEqual(result.save_path.read_bytes(), self.fixture.raw)
        self.assertEqual(self.fixture.source.read_bytes(), self.fixture.raw)
