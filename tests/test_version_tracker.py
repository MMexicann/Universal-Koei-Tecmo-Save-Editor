"""Procedural Steam metadata and path-free version compatibility fixtures."""
from dataclasses import replace
import io
import json
from pathlib import Path
import queue
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from koei_editor.shared import save_discovery, version_tracker as tracker


class VersionTrackerTests(unittest.TestCase):
    @staticmethod
    def observation(build_id='123456789', *, game_id='atelier_sophie', app_id='527270',
                    observed_at='2026-10-22T12:00:00Z', last_updated='1761000000'):
        return tracker.BuildObservation(
            game_id=game_id,
            platform='Windows PC',
            app_id=app_id,
            build_id=build_id,
            last_updated=last_updated,
            observed_at=observed_at,
        )

    @staticmethod
    def record(build_id='123456789', *, game_id='atelier_sophie', platform='Windows PC', app_id=None,
               artifact_kind='save_editor', artifact_id='editor-a', status='verified',
               checked_at='2026-10-22T11:00:00Z', artifact_version='3.1',
               artifact_name='Reviewed editor', reason_code='exact_build_fixture',
               explanation='Procedural catalog fixture for an exact installed build.',
               evidence=('docs/HELP_AND_COMPATIBILITY.md',), next_step_ids=('evidence',)):
        if app_id is None:
            app_id = next(item.app_id for item in save_discovery.STEAM_MAPPINGS
                          if item.game_id == game_id)
        return tracker.CompatibilityRecord(
            game_id=game_id,
            platform=platform,
            app_id=app_id,
            build_id=build_id,
            artifact_kind=artifact_kind,
            artifact_id=artifact_id,
            artifact_name=artifact_name,
            artifact_version=artifact_version,
            status=status,
            reason_code=reason_code,
            explanation=explanation,
            evidence=evidence,
            checked_at=checked_at,
            next_step_ids=next_step_ids,
        )

    def test_exact_build_record_is_returned_and_unrecorded_kinds_stay_unknown(self):
        observation = self.observation()
        exact = self.record()
        results = tracker.compatibility_for(observation, records=(exact,))

        self.assertEqual(len(results), 5)
        editor = next(item for item in results if item.artifact_id == 'editor-a')
        self.assertEqual((editor.status, editor.artifact_id, editor.artifact_version),
                         ('verified', 'editor-a', '3.1'))
        self.assertEqual(editor.app_id, '527270')
        self.assertEqual(editor.evidence, ('docs/HELP_AND_COMPATIBILITY.md',))
        editor_unknown = next(item for item in results
                              if item.artifact_kind == 'save_editor' and item.status == 'unknown')
        self.assertEqual((editor_unknown.artifact_id, editor_unknown.reason_code),
                         ('unlisted_save_editor', 'incomplete_artifact_inventory'))
        self.assertIn('not a complete inventory', editor_unknown.explanation)
        unknown = [item for item in results if item.artifact_kind != 'save_editor']
        self.assertTrue(all(item.status == 'unknown' for item in unknown))
        self.assertTrue(all(item.reason_code == 'no_exact_build_record' for item in unknown))
        self.assertTrue(all('No version-specific' in item.explanation for item in unknown))

    def test_unlisted_artifact_warnings_cover_each_artifact_kind(self):
        observation = self.observation()
        records = tuple(self.record(
            artifact_kind=kind, artifact_id=f'{kind}-review', status='unknown',
            artifact_name=f'Synthetic {kind} category fixture', artifact_version=None,
            reason_code='procedural_category_fixture',
            explanation='Synthetic category coverage only; no real compatibility claim.',
            evidence=(), next_step_ids=())
                        for kind in tracker.ARTIFACT_KINDS)
        results = tracker.compatibility_for(observation, records=records)
        unlisted = {item.artifact_kind: item for item in results
                    if item.artifact_id.startswith('unlisted_')}

        self.assertEqual(set(unlisted), set(tracker.ARTIFACT_KINDS))
        for kind, item in unlisted.items():
            self.assertEqual(item.artifact_id, f'unlisted_{kind}')
            self.assertEqual(item.status, 'unknown')
            self.assertEqual(item.reason_code, 'incomplete_artifact_inventory')
            self.assertIn('not a complete inventory', item.explanation)

    def test_older_unsupported_record_does_not_mark_a_new_build_unsupported(self):
        current = self.observation('123456790')
        older = self.record('123456789', status='unsupported')
        results = tracker.compatibility_for(current, records=(older,))

        self.assertEqual({item.status for item in results}, {'unknown'})
        self.assertTrue(all(item.build_id == '123456790' for item in results))
        self.assertTrue(all(item.reason_code == 'no_exact_build_record' for item in results))
        self.assertTrue(all('compatibility record' in item.explanation.casefold() for item in results))

    def test_explicit_unsupported_status_requires_exact_game_platform_and_build(self):
        observation = self.observation()
        unsupported = self.record(status='unsupported')
        exact = tracker.compatibility_for(observation, records=(unsupported,))
        self.assertEqual(next(item.status for item in exact if item.artifact_id == 'editor-a'),
                         'unsupported')

        different_profile = self.record(game_id='dw8xl', platform='Windows PC', status='unsupported')
        results = tracker.compatibility_for(observation, records=(different_profile,))
        self.assertTrue(all(item.status == 'unknown' for item in results))

        no_detected_build = self.observation(None)
        results = tracker.compatibility_for(no_detected_build, records=(unsupported,))
        self.assertTrue(all(item.status == 'unknown' for item in results))
        self.assertTrue(all(item.build_id is None for item in results))

    def test_unsupported_records_require_resolved_help_next_steps(self):
        unsupported = self.record(status='unsupported')
        self.assertEqual(
            tracker._validate_record({**unsupported.__dict__, 'next_step_ids': ['evidence']}).next_step_ids,
            ('evidence',))
        with self.assertRaisesRegex(ValueError, 'at least one resolved next step'):
            tracker._validate_record({**unsupported.__dict__, 'next_step_ids': []})
        with self.assertRaisesRegex(ValueError, 'unresolved next-step ID'):
            tracker._validate_record({**unsupported.__dict__, 'next_step_ids': ['unknown_target']})

    def test_records_reject_blank_artifact_versions_but_unknown_may_omit_one(self):
        for status in ('verified', 'unsupported'):
            record = self.record(status=status)
            for version in ('', '   ', '\t'):
                with self.subTest(status=status, version=repr(version)):
                    with self.assertRaisesRegex(ValueError, 'invalid artifact version'):
                        tracker._validate_record({**record.__dict__, 'artifact_version': version})
            normalized = tracker._validate_record({**record.__dict__, 'artifact_version': '  3.1  '})
            self.assertEqual(normalized.artifact_version, '3.1')

        unknown = self.record(status='unknown', artifact_version=None, evidence=(), next_step_ids=())
        self.assertIsNone(tracker._validate_record(unknown.__dict__).artifact_version)

        class Resource:
            def __init__(self, raw):
                self.raw = raw

            def open(self, _mode):
                return io.BytesIO(self.raw)

        for version in ('', '   ', '\t'):
            with self.subTest(status='unknown', version=repr(version)):
                raw_record = {**unknown.__dict__, 'artifact_version': version}
                raw_catalog = json.dumps({'schema_version': 1, 'records': [raw_record]}).encode()
                with mock.patch.object(tracker, 'data_file', return_value=Resource(raw_catalog)), \
                        self.assertRaisesRegex(ValueError, 'invalid artifact version'):
                    tracker.load_catalog()

    def test_next_step_ids_render_as_localized_help_article_titles(self):
        from koei_editor.shared.version_tracker_gui import VersionTrackerPanel

        panel = object.__new__(VersionTrackerPanel)
        panel.language = 'en'
        self.assertEqual(
            panel._next_step_titles(('evidence', 'troubleshooting')),
            ('What compatibility evidence means', 'Troubleshooting rejected files and exports'))
        panel.language = 'de'
        self.assertEqual(
            panel._next_step_titles(('evidence', 'troubleshooting')),
            ('Was Kompatibilitätsnachweise bedeuten', 'Fehler bei Dateien und Exporten beheben'))

    def test_latest_reviewed_artifact_version_is_explicit_and_history_keeps_each_version(self):
        older = self.record(status='unsupported', checked_at='2026-10-20T11:00:00Z',
                            artifact_version='1.0')
        newer = self.record(status='verified', checked_at='2026-10-22T11:00:00Z',
                            artifact_version='2.0')
        latest = tracker.compatibility_for(self.observation(), records=(older, newer))
        editor = next(item for item in latest if item.artifact_id == 'editor-a')
        self.assertEqual((editor.status, editor.artifact_version), ('verified', '2.0'))
        history = tracker.compatibility_history('atelier_sophie', records=(older, newer),
                                                app_id='527270')
        self.assertEqual([item.artifact_version for item in history], ['1.0', '2.0'])

    def test_game_app_mapping_is_validated_and_app_id_participates_in_exact_join(self):
        # A registered Steam app for another profile cannot be attached to Atelier Sophie.
        with self.assertRaisesRegex(ValueError, 'reviewed game/platform/app mapping'):
            self.observation(app_id='527290')
        with self.assertRaisesRegex(ValueError, 'game/platform/app profile'):
            tracker.compatibility_for(
                self.observation(), records=(self.record(app_id='527290'),))

        # Records for another valid (game, app) pair stay unknown for this installed game.
        other_app_profile = self.record(game_id='atelier_firis_pc', app_id='527290')
        results = tracker.compatibility_for(self.observation(), records=(other_app_profile,))
        self.assertTrue(all(item.status == 'unknown' for item in results))
        self.assertTrue(all(item.app_id == '527270' for item in results))

    def test_compatibility_history_filters_profile_tool_and_orders_check_times(self):
        records = (
            self.record('123456789', checked_at='2026-10-20T09:00:00Z'),
            self.record('123456790', checked_at='2026-10-22T09:00:00Z'),
            self.record('123456789', artifact_kind='mod', artifact_id='mod-a'),
            self.record('123456789', game_id='dw8xl', artifact_id='editor-b'),
        )

        history = tracker.compatibility_history(
            'atelier_sophie', artifact_kind='save_editor', artifact_id='editor-a', records=records)
        self.assertEqual([item.build_id for item in history], ['123456789', '123456790'])
        self.assertEqual([item.checked_at for item in history],
                         ['2026-10-20T09:00:00Z', '2026-10-22T09:00:00Z'])
        app_history = tracker.compatibility_history(
            'atelier_sophie', artifact_kind='save_editor', app_id='527270', records=records)
        self.assertEqual(app_history, history)
        self.assertTrue(all(item.app_id == '527270' for item in app_history))
        with self.assertRaisesRegex(ValueError, 'reviewed Steam app mapping'):
            tracker.compatibility_history('atelier_sophie', app_id='527290', records=records)

    def test_rechecks_keep_history_and_current_view_uses_latest_status(self):
        earlier = self.record(status='verified', checked_at='2026-10-20T09:00:00Z')
        later = self.record(status='unsupported', checked_at='2026-10-22T09:00:00Z')
        records = (earlier, later)

        current = tracker.compatibility_for(self.observation(), records=records)
        editor = next(item for item in current if item.artifact_id == 'editor-a')
        self.assertEqual((editor.status, editor.checked_at),
                         ('unsupported', '2026-10-22T09:00:00Z'))
        history = tracker.compatibility_history(
            'atelier_sophie', artifact_kind='save_editor', artifact_id='editor-a', records=records)
        self.assertEqual([(item.status, item.checked_at) for item in history], [
            ('verified', '2026-10-20T09:00:00Z'),
            ('unsupported', '2026-10-22T09:00:00Z'),
        ])

    def test_catalog_rejects_duplicate_keys_wildcard_builds_and_unregistered_profiles(self):
        class Resource:
            def __init__(self, raw):
                self.raw = raw

            def open(self, _mode):
                return io.BytesIO(self.raw)

        malformed = (
            b'{"schema_version":1,"records":[],"records":[]}',
            json.dumps({'schema_version': 1, 'records': [
                {**self.record().__dict__, 'build_id': '*'}]}).encode(),
            json.dumps({'schema_version': 1, 'records': [
                {**self.record().__dict__, 'game_id': 'unregistered'}]}).encode(),
            json.dumps({'schema_version': 1, 'records': [
                {**self.record().__dict__, 'app_id': '527290'}]}).encode(),
            json.dumps({'schema_version': 1, 'records': [
                {**self.record().__dict__, 'status': 'maybe'}]}).encode(),
        )
        for raw in malformed:
            with self.subTest(raw=raw[:60]), mock.patch.object(
                    tracker, 'data_file', return_value=Resource(raw)), self.assertRaises(ValueError):
                tracker.load_catalog()

    def test_packaged_catalog_contains_only_valid_exact_build_records(self):
        records = tracker.load_catalog()
        self.assertLessEqual(len(records), tracker.MAX_CATALOG_RECORDS)
        self.assertTrue(all(item.build_id is not None and item.build_id.isdecimal() for item in records))
        self.assertTrue(all(item.status in ('verified', 'unsupported', 'unknown') for item in records))

    def test_first_seen_repeated_scan_and_build_change_are_path_free(self):
        with tempfile.TemporaryDirectory() as directory:
            history_path = Path(directory) / 'version-tracker.json'
            undetected = self.observation(None, observed_at='2026-10-22T11:00:00Z')
            self.assertEqual(tracker.record_scan((undetected,), history_path,
                                                 observed_at='2026-10-22T11:00:00Z'), ())
            self.assertEqual(tracker.load_history(history_path), ())

            first = self.observation(observed_at='2026-10-22T12:00:00Z')
            first_events = tracker.record_scan((first,), history_path,
                                               observed_at='2026-10-22T12:00:00Z')
            self.assertEqual([item.event_kind for item in first_events], ['first_seen'])
            self.assertEqual(first_events[0].previous_build_id, None)
            self.assertEqual(first_events[0].warning, '')

            repeated = replace(first, observed_at='2026-10-22T12:30:00Z')
            self.assertEqual(tracker.record_scan((repeated,), history_path,
                                                 observed_at='2026-10-22T12:30:00Z'), ())
            self.assertEqual(len(tracker.load_history(history_path)), 1)

            missing_marker = replace(first, build_id=None, last_updated=None,
                                     observed_at='2026-10-22T12:45:00Z')
            self.assertEqual(tracker.record_scan((missing_marker,), history_path,
                                                 observed_at='2026-10-22T12:45:00Z'), ())
            self.assertEqual(len(tracker.load_history(history_path)), 1)

            updated = replace(first, build_id='123456790', last_updated='1761003600',
                              observed_at='2026-10-22T13:00:00Z')
            changed = tracker.record_scan((updated,), history_path,
                                          observed_at='2026-10-22T13:00:00Z')
            self.assertEqual(len(changed), 1)
            event = changed[0]
            self.assertEqual((event.event_kind, event.previous_build_id, event.build_id),
                             ('build_changed', '123456789', '123456790'))
            self.assertIn('review exact-build compatibility entries', event.warning.casefold())
            self.assertIn('does not establish incompatibility', event.warning)

            saved = history_path.read_text(encoding='utf-8')
            self.assertEqual(len(tracker.load_history(history_path)), 2)
            self.assertNotIn(directory, saved)
            self.assertNotIn('install_path', saved)
            self.assertNotIn('private-account', saved)

    def test_malformed_or_path_bearing_local_history_is_rejected_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            history_path = Path(directory) / 'version-tracker.json'
            invalid = (
                b'{"schema_version":1,"events":[],"events":[]}',
                json.dumps({'schema_version': 1, 'events': [
                    {**tracker.BuildHistoryEvent(
                        'first_seen', 'atelier_sophie', 'Windows PC', '527270', None,
                        '123456789', '1761000000', '2026-10-22T12:00:00Z').__dict__,
                     'install_path': directory}]}).encode(),
                json.dumps({'schema_version': True, 'events': []}).encode(),
            )
            for raw in invalid:
                history_path.write_bytes(raw)
                original = history_path.read_bytes()
                with self.subTest(raw=raw[:60]), self.assertRaises(ValueError):
                    tracker.load_history(history_path)
                with self.assertRaises(ValueError):
                    tracker.record_scan((self.observation(),), history_path)
                self.assertEqual(history_path.read_bytes(), original)


class VersionTrackerPanelDiagnosticTests(unittest.TestCase):
    def test_history_error_is_appended_to_scan_diagnostics(self):
        from koei_editor.shared.version_tracker_gui import VersionTrackerPanel

        class Status:
            value = ''

            def set(self, value):
                self.value = value

            def get(self):
                return self.value

        panel = object.__new__(VersionTrackerPanel)
        panel._scan_thread = mock.Mock()
        panel._scan_thread.is_alive.return_value = False
        panel._scan_queue = queue.SimpleQueue()
        panel.scan_button = mock.Mock()
        panel.status = Status()
        panel._t = lambda key: key
        panel._render_builds = mock.Mock()
        panel._render_history = mock.Mock()
        scan = SimpleNamespace(observations=(), issues=('invalid_build_id_ignored',),
                                stop_reason='metadata_limit')
        panel._scan_queue.put(('ok', scan, (), (), True))

        panel._poll_scan()

        self.assertEqual(panel.status.get(), 'no_installs scan_issue scan_stopped history_error')


if __name__ == '__main__':
    unittest.main()
