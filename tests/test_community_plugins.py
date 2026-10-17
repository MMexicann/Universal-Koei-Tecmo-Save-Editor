"""Untrusted manifest admission, immutable approvals and inert command dispatch."""
import hashlib
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.shared import community_plugins as plugins


def manifest():
    return {
        'schema': 1, 'api': '1', 'id': 'community.example', 'title': 'Copy guide',
        'version': '1.0.0', 'author': 'Example contributor', 'description': 'Data-only copy guidance.',
        'capabilities': ['help', 'workflows', 'commands'],
        'contributions': [
            {'kind': 'help', 'id': 'copy-help', 'title': 'Copied saves', 'locale': 'en',
             'game_ids': ['dw8xl'], 'body': 'Keep the original save and its companion metadata.'},
            {'kind': 'workflows', 'id': 'copy-steps', 'title': 'Prepare an export', 'locale': 'de',
             'game_ids': [], 'platforms': ['Windows PC'], 'steps': ['Original sichern.', 'Kopie öffnen.']},
            {'kind': 'commands', 'id': 'open-help', 'title': 'Open copy guidance', 'locale': 'en',
             'game_ids': ['dw8xl'], 'target': 'copy-help'},
        ],
    }


def raw(value=None):
    return json.dumps(value if value is not None else manifest(), ensure_ascii=False).encode('utf-8')


class ManifestTests(unittest.TestCase):
    def validate(self, value):
        return plugins.validate_manifest(raw(value), known_game_ids=('dw8xl',))

    def test_valid_manifest_has_frozen_namespaced_scope_and_declarative_targets(self):
        item = self.validate(manifest())
        self.assertEqual(item.api, plugins.API_VERSION)
        self.assertEqual(item.capabilities, ('commands', 'help', 'workflows'))
        self.assertEqual(item.contributions[0].id, 'community.example:copy-help')
        self.assertEqual(item.contributions[2].target, item.contributions[0].id)
        with self.assertRaises(AttributeError):
            item.title = 'Changed'
        self.assertIsInstance(item.contributions, tuple)

    def test_exact_api_schema_version_namespace_and_capabilities_are_required(self):
        values = [
            ('schema', True), ('schema', 2), ('api', 1), ('api', '1.1'), ('api', '*'),
            ('id', 'example'), ('id', '../bad'), ('id', 'community.Example'),
            ('version', '2.7'), ('version', '1.0.0+run'),
            ('capabilities', ['help']), ('capabilities', ['help', 'help']),
            ('capabilities', ['filesystem']), ('capabilities', [{}]),
        ]
        for key, value in values:
            with self.subTest(key=key, value=value):
                item = manifest()
                item[key] = value
                with self.assertRaises(plugins.PluginError):
                    self.validate(item)

    def test_code_entrypoints_paths_network_and_unknown_keys_are_rejected(self):
        for key in ('entry_point', 'module', 'python', 'url', 'path', 'permissions', 'games'):
            with self.subTest(key=key):
                item = manifest()
                item[key] = 'os.system'
                with self.assertRaises(plugins.PluginError):
                    self.validate(item)
                item = manifest()
                item['contributions'][0][key] = 'evil.py'
                with self.assertRaises(plugins.PluginError):
                    self.validate(item)

    def test_reject_duplicate_properties_nonfinite_utf16_nested_and_oversized_json(self):
        cases = [b'{"schema":1,"schema":1}', b'{"x":NaN}', b'{"x":Infinity}', b'\xff',
                 raw().decode('utf-8').encode('utf-16'), b'[' * 1600 + b']' * 1600,
                 b' ' * (plugins.MAX_MANIFEST_BYTES + 1), b'[]', b'null', b'{}']
        for value in cases:
            with self.subTest(prefix=value[:40]):
                with self.assertRaises(plugins.PluginError):
                    plugins.validate_manifest(value)

    def test_bounds_text_control_characters_and_duplicate_ids_fail_closed(self):
        mutations = [
            lambda item: item.update(title='x' * 161),
            lambda item: item.update(description='\u202eSpoof'),
            lambda item: item.update(author='bad\x00name'),
            lambda item: item.update(author='Impersonator\nSHA-256: fake'),
            lambda item: item.update(title='\ud800'),
            lambda item: item.update(contributions=[]),
            lambda item: item.update(contributions=item['contributions'] * 22),
            lambda item: item['contributions'][0].update(body='x' * 8193),
            lambda item: item['contributions'][0].update(body=' '),
            lambda item: item['contributions'][1].update(id='copy-help'),
            lambda item: item['contributions'][1].update(steps=[]),
            lambda item: item['contributions'][1].update(steps=['step'] * 25),
            lambda item: item['contributions'][1].update(platforms=['PC', 'PC']),
            lambda item: item['contributions'][0].update(game_ids=['unknown']),
            lambda item: item['contributions'][0].update(game_ids=['dw8xl', 'dw8xl']),
            lambda item: item['contributions'][0].update(locale='xx'),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                item = manifest()
                mutation(item)
                # Escaped JSON also exercises lone surrogate rejection after decoding.
                value = json.dumps(item).encode('ascii')
                with self.assertRaises(plugins.PluginError):
                    plugins.validate_manifest(value, known_game_ids=('dw8xl',))

    def test_commands_cannot_call_host_functions_chain_or_escape_scope(self):
        for target in ('os.system', '../../module', 'koei.help:topic', 'open-help', 'missing'):
            with self.subTest(target=target):
                item = manifest()
                item['contributions'][2]['target'] = target
                with self.assertRaises(plugins.PluginError):
                    self.validate(item)
        for key, value in (('locale', 'de'), ('game_ids', [])):
            item = manifest()
            item['contributions'][2][key] = value
            with self.assertRaises(plugins.PluginError):
                self.validate(item)


class DiscoveryApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.path = self.folder / 'example.plugin.json'
        self.path.write_bytes(raw())

    def discover(self, **kwargs):
        return plugins.discover_plugins(self.folder, known_game_ids=('dw8xl',), **kwargs)

    def approved(self):
        catalog = plugins.PluginCatalog(self.discover())
        candidate = catalog.entries[0].candidate
        catalog.approve(candidate.manifest.id, sha256=candidate.sha256,
                        capabilities=candidate.manifest.capabilities)
        return catalog

    def test_discovery_never_imports_modules_runs_code_or_searches_subdirectories(self):
        (self.folder / 'evil.py').write_text('raise RuntimeError("must never execute")')
        subfolder = self.folder / 'nested'
        subfolder.mkdir()
        (subfolder / 'hidden.plugin.json').write_bytes(raw())
        with patch('importlib.import_module', side_effect=AssertionError('No imports')):
            candidates = self.discover()
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].sha256, hashlib.sha256(raw()).hexdigest())
        self.assertEqual(candidates[0].filename, self.path.name)

    def test_invalid_oversized_and_symlink_manifests_are_inert_visible_candidates(self):
        (self.folder / 'bad.plugin.json').write_bytes(b'not json')
        (self.folder / 'huge.plugin.json').write_bytes(b' ' * (plugins.MAX_MANIFEST_BYTES + 1))
        (self.folder / 'directory.plugin.json').mkdir()
        candidates = self.discover()
        self.assertEqual(len(candidates), 4)
        self.assertEqual(sum(item.manifest is None and bool(item.error) for item in candidates), 3)
        if hasattr(os, 'symlink'):
            try:
                (self.folder / 'link.plugin.json').symlink_to(self.path)
            except OSError:
                pass
            else:
                candidate = next(item for item in self.discover() if item.filename == 'link.plugin.json')
                self.assertIsNone(candidate.manifest)

    def test_file_reads_are_bounded_and_errors_do_not_include_private_paths(self):
        with patch.object(plugins.os, 'open', side_effect=PermissionError(str(self.folder))):
            candidate = self.discover()[0]
        self.assertIsNone(candidate.manifest)
        self.assertNotIn(str(self.folder), candidate.error)
        with self.assertRaises(plugins.PluginError) as caught:
            plugins.discover_plugins(self.folder / 'missing')
        self.assertNotIn(str(self.folder), str(caught.exception))

    def test_directory_enumeration_and_plugin_count_are_bounded(self):
        with patch.object(plugins, 'MAX_DIRECTORY_ENTRIES', 0):
            with self.assertRaises(plugins.PluginError):
                self.discover()
        with patch.object(plugins, 'MAX_PLUGINS', 0):
            with self.assertRaises(plugins.PluginError):
                self.discover()

    def test_known_game_generator_applies_to_every_manifest(self):
        item = manifest()
        item['id'] = 'community.other'
        (self.folder / 'other.plugin.json').write_bytes(raw(item))
        candidates = plugins.discover_plugins(self.folder, known_game_ids=(game for game in ('dw8xl',)))
        self.assertTrue(all(item.manifest is not None for item in candidates))

    def test_no_contributions_before_exact_hash_and_capability_approval(self):
        catalog = plugins.PluginCatalog(self.discover())
        candidate = catalog.entries[0].candidate
        self.assertEqual(catalog.contributions(), ())
        self.assertFalse(catalog.entries[0].enabled)
        with self.assertRaises(plugins.PluginError):
            catalog.resolve_command('community.example:open-help')
        for digest, capabilities in [('0' * 64, candidate.manifest.capabilities),
                                     (candidate.sha256, ['help']),
                                     (candidate.sha256, ['help', 'commands', 'filesystem']),
                                     (candidate.sha256, ['help', 'commands', 'commands'])]:
            with self.assertRaises(plugins.PluginError):
                catalog.approve(candidate.manifest.id, sha256=digest, capabilities=capabilities)
            self.assertEqual(catalog.contributions(), ())
        catalog.approve(candidate.manifest.id, sha256=candidate.sha256,
                        capabilities=candidate.manifest.capabilities)
        self.assertTrue(catalog.entries[0].enabled)
        self.assertEqual(len(catalog.contributions()), 3)

    def test_commands_resolve_only_to_inert_own_content_and_disable_revokes_immediately(self):
        catalog = self.approved()
        target = catalog.resolve_command('community.example:open-help')
        self.assertEqual(target.kind, 'help')
        self.assertIn('companion metadata', target.body)
        self.assertFalse(callable(target))
        catalog.disable('community.example')
        self.assertFalse(catalog.entries[0].enabled)
        self.assertEqual(catalog.search('copy'), ())
        with self.assertRaises(plugins.PluginError):
            catalog.resolve_command('community.example:open-help')

    def test_file_changes_cannot_mutate_approved_snapshot_and_new_discovery_is_disabled(self):
        catalog = self.approved()
        original = catalog.entries[0].candidate.sha256
        item = manifest()
        item['contributions'][0]['body'] = 'Changed after approval'
        self.path.write_bytes(raw(item))
        self.assertNotIn('Changed', catalog.contributions('help')[0].body)
        new_catalog = plugins.PluginCatalog(self.discover())
        self.assertEqual(new_catalog.contributions(), ())
        with self.assertRaises(plugins.PluginError):
            new_catalog.approve('community.example', sha256=original,
                                capabilities=('help', 'workflows', 'commands'))

    def test_duplicate_plugin_ids_quarantine_every_duplicate_and_reserved_conflicts_reject(self):
        (self.folder / 'duplicate.plugin.json').write_bytes(raw())
        catalog = plugins.PluginCatalog(self.discover())
        self.assertTrue(all(entry.error for entry in catalog.entries))
        with self.assertRaises(plugins.PluginError):
            catalog.approve('community.example', sha256=catalog.entries[0].candidate.sha256,
                            capabilities=('help', 'workflows', 'commands'))
        catalog = plugins.PluginCatalog(self.discover()[:1], reserved_ids=('community.example:copy-help',))
        self.assertTrue(catalog.entries[0].error)
        self.assertFalse(catalog.entries[0].enabled)

    def test_search_is_bounded_locale_aware_and_includes_workflow_steps(self):
        catalog = self.approved()
        self.assertEqual(len(catalog.search('ORIGINAL SICHERN', locale='de')), 1)
        self.assertEqual(catalog.search('ORIGINAL SICHERN', locale='en'), ())
        self.assertEqual(len(catalog.search('metadata', kind='help')), 1)
        with self.assertRaises(plugins.PluginError):
            catalog.search('x' * 257)

    def test_shipped_template_is_valid_but_does_not_claim_game_support(self):
        path = Path(__file__).resolve().parents[1] / 'tools' / 'community_plugin_template' / 'example.plugin.json'
        item = plugins.validate_manifest(path.read_bytes())
        self.assertTrue(item.contributions)
        self.assertTrue(all(not contribution.game_ids for contribution in item.contributions))

    def test_developer_cli_reports_rejection_and_conflicts_without_enabling_or_private_paths(self):
        from tools.check_community_plugins import main
        for invalid in (False, True):
            with self.subTest(invalid=invalid):
                if invalid:
                    (self.folder / 'duplicate.plugin.json').write_bytes(raw())
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = main([str(self.folder)])
                report = json.loads(output.getvalue())
                self.assertEqual(result, 1 if invalid else 0)
                self.assertEqual(report['valid'], not invalid)
                self.assertTrue(all(not item['enabled'] for item in report['plugins']))
                self.assertNotIn(str(self.folder), output.getvalue())

    def test_developer_cli_rejects_empty_or_unavailable_directories(self):
        from tools.check_community_plugins import main
        self.path.unlink()
        for directory in (self.folder, self.folder / 'missing'):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = main([str(directory)])
            self.assertEqual(result, 1)
            self.assertFalse(json.loads(output.getvalue())['valid'])


if __name__ == '__main__':
    unittest.main()
