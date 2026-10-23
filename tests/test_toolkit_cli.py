"""First-class headless commands preserve the real engines' copy protections."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import stat
import tempfile
import unittest
from unittest.mock import patch

from koei_editor import application, cli, conversion
from koei_editor.game_registry import get_game
from koei_editor.shared import automation
from koei_editor.supported_games import SUPPORTED_GAMES
from tests.test_conversion import write_copy
from tests.test_dw4hyper_format import procedural_raw


class ToolkitCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def invoke(self, *arguments):
        output, errors = io.StringIO(), io.StringIO()
        # The CLI entry must never reach the GUI, including empty/invalid inputs.
        with patch.object(application.tk, 'Tk', side_effect=AssertionError('CLI opened Tk')), \
                redirect_stdout(output), redirect_stderr(errors):
            try:
                code = cli.main(list(map(str, arguments)))
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def process(self, *arguments, ascii_output=False):
        environment = dict(os.environ, DISPLAY='')
        if ascii_output:
            environment['PYTHONIOENCODING'] = 'ascii'
        return subprocess.run([sys.executable, '-m', 'koei_editor.cli', *map(str, arguments)],
                              env=environment, capture_output=True, text=True,
                              encoding='utf-8', timeout=60)

    def copy(self, name='private-source.dat'):
        source = self.folder / name
        source.write_bytes(procedural_raw())
        return source

    def files(self):
        return {path.relative_to(self.folder).as_posix(): path.read_bytes()
                for path in self.folder.rglob('*') if path.is_file()}

    def test_no_arguments_help_version_and_automation_help_are_headless(self):
        for arguments in ((), ('--help',), ('automation', '--help')):
            with self.subTest(arguments=arguments):
                process = self.process(*arguments)
                self.assertEqual((process.returncode, process.stderr), (0, ''))
                self.assertIn('usage:', process.stdout)
        process = self.process('--version')
        self.assertEqual((process.returncode, process.stderr), (0, ''))
        self.assertEqual(process.stdout, 'Universal Koei Tecmo Game Toolkit ' + application.VERSION + '\n')
        self.assertFalse(self.files())

    def test_json_inventories_are_exact_scoped_and_have_no_input_paths(self):
        for name in ('games', 'routes'):
            process = self.process(name, '--json')
            self.assertEqual((process.returncode, process.stderr), (0, ''))
            data = json.loads(process.stdout)
            self.assertEqual(data['schema'], 'koei-toolkit-' + name)
            self.assertEqual(data['schema_version'], 1)
            self.assertTrue(data['read_only'])
            self.assertFalse(data['in_game_verified'])
            self.assertNotIn(str(self.folder), process.stdout)
            self.assertEqual(len({item['id'] for item in data[name]}), len(data[name]))
            if name == 'games':
                self.assertEqual({item['id'] for item in data[name]}, {game.id for game in SUPPORTED_GAMES})
                self.assertEqual(data['profile_count'], len(SUPPORTED_GAMES))
                self.assertEqual(data['platform_count'], len({game.platform for game in SUPPORTED_GAMES}))
                self.assertEqual(data['profile_count'], 98)
                self.assertEqual(data['platform_count'], 15)
            else:
                self.assertEqual({item['id'] for item in data[name]}, {route.id for route in conversion.ROUTES})
                self.assertEqual(data['route_count'], len(conversion.ROUTES))
                self.assertEqual(data['route_count'], 145)
                self.assertTrue(all(item['scope_description'] for item in data[name]))

    def test_human_inventories_work_with_a_strict_ascii_terminal(self):
        for name in ('games', 'routes'):
            process = self.process(name, ascii_output=True)
            self.assertEqual((process.returncode, process.stderr), (0, ''))
            self.assertTrue(process.stdout)
            self.assertTrue(process.stdout.isascii())

    def test_bad_or_empty_commands_and_mixed_options_cannot_open_gui(self):
        for arguments in (('unknown',), ('--game', 'dw3'), ('batch-convert', ''),
                          ('scan', '--game', 'dw4hyper', ''),
                          ('compare', '--game', 'dw4hyper', 'one'),
                          ('convert', 'dw6-to-dw6_ps3', '--source', 'one', '--template', 'two'),
                          ('games', '--dry-run'), ('discover', '--steam-root', ''),
                          ('fields', '--game', '', 'copy'),
                          ('convert', '', '--source', 'one', '--template', 'two', '--dry-run')):
            with self.subTest(arguments=arguments):
                code, output, errors = self.invoke(*arguments)
                self.assertEqual(code, 2)
                self.assertEqual(output, '')
                self.assertIn('usage:', errors)
        self.assertFalse(self.files())

    def test_empty_repeated_discovery_root_is_rejected_before_filesystem_access(self):
        with patch('koei_editor.shared.save_discovery.discover_saves',
                   side_effect=AssertionError('Invalid roots reached discovery')) as discover:
            code, output, errors = self.invoke('discover', '--steam-root', self.folder,
                                               '--steam-root', '')
        self.assertEqual((code, output), (2, ''))
        self.assertIn('must not be empty', errors)
        discover.assert_not_called()
        self.assertFalse(self.files())

    def test_option_like_values_cannot_become_another_command(self):
        source = self.copy()
        before = self.files()
        code, output, errors = self.invoke('fields', '--game=--help', source)
        self.assertEqual((code, errors), (2, ''))
        self.assertFalse(json.loads(output)['success'])
        for arguments in (('doctor', '--game=--help', source),
                          ('batch-convert', '--report=--help', source),
                          ('scan', '--game', 'dw4hyper', '--', '--smoke-test')):
            code, output, errors = self.invoke(*arguments)
            self.assertNotEqual(code, 0)
            self.assertNotIn('usage:', output)
        self.assertEqual(self.files(), before)

    def test_fields_inspection_is_json_read_only_and_wrong_profiles_reject(self):
        source = self.copy()
        before = self.files()
        process = self.process('fields', '--game', 'dw4hyper', source)
        self.assertEqual((process.returncode, process.stderr), (0, ''))
        report = json.loads(process.stdout)
        self.assertTrue(report['success'])
        self.assertEqual(report['game_id'], 'dw4hyper')
        self.assertEqual(report['source_sha256'], hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertTrue(any(row['field'] == 'officer_0_attack' and row['value'] == 50 for row in report['fields']))
        code, output, errors = self.invoke('fields', '--game', 'dw6', source)
        self.assertEqual((code, errors), (2, ''))
        self.assertFalse(json.loads(output)['success'])
        self.assertEqual(self.files(), before)

    def test_compare_and_scan_preserve_inputs_and_refuse_report_overwrite(self):
        source = self.copy()
        adapter = get_game('dw4hyper').get_scalar_adapter()
        other = self.folder / 'private-other.dat'
        other.write_bytes(adapter.serialize(adapter.read_save(source), {'officer_0_attack': 123}))
        before = self.files()
        code, output, errors = self.invoke('compare', '--game', 'dw4hyper', source, other)
        self.assertEqual((code, errors), (0, ''))
        self.assertTrue(json.loads(output)['read_only'])
        self.assertEqual(json.loads(output)['different_fields'], 1)
        code, output, errors = self.invoke('scan', '--game', 'dw4hyper', self.folder)
        self.assertEqual((code, errors), (0, ''))
        scanned = json.loads(output)
        self.assertTrue(scanned['read_only'])
        self.assertEqual(scanned['statuses']['qualified'], 2)
        self.assertNotIn(str(self.folder), output)
        self.assertNotIn(source.name, output)
        self.assertEqual(self.files(), before)
        report = self.folder / 'review.json'
        code, output, errors = self.invoke('compare', '--game', 'dw4hyper', source, other, '--report', report)
        self.assertEqual((code, errors), (0, ''))
        self.assertEqual(json.loads(report.read_text()), json.loads(output))
        report_before = report.read_bytes()
        self.assertEqual(self.invoke('compare', '--game', 'dw4hyper', source, other, '--report', report)[0], 1)
        self.assertEqual(report.read_bytes(), report_before)
        for name, raw in before.items():
            self.assertEqual((self.folder / name).read_bytes(), raw)

    def test_doctor_reads_without_repair_and_bad_sources_exit_nonzero(self):
        source = self.copy()
        before = self.files()
        code, output, errors = self.invoke('doctor', '--game', 'dw4hyper', source)
        self.assertEqual((code, errors), (0, ''))
        self.assertTrue(json.loads(output)['read_only'])
        self.assertEqual(self.files(), before)
        for command in ('scan', 'doctor', 'compare'):
            arguments = [command, '--game', 'dw4hyper', self.folder / 'missing']
            if command == 'compare':
                arguments.append(source)
            code, output, errors = self.invoke(*arguments)
            self.assertNotEqual(code, 0)
            if output:
                self.assertIsInstance(json.loads(output), dict)
        self.assertEqual(self.files(), before)

    def test_conversion_dry_run_is_no_write_and_export_never_overwrites(self):
        source = write_copy(self.folder / 'pc', 'dw6')
        template = write_copy(self.folder / 'ps3', 'dw6_ps3', 1)
        before = self.files()
        destination = self.folder / 'converted'
        arguments = ('convert', 'dw6-to-dw6_ps3', '--source', source, '--template', template,
                     '--output-dir', destination)
        process = self.process(*arguments, '--dry-run')
        self.assertEqual((process.returncode, process.stderr), (0, ''))
        report = json.loads(process.stdout)
        self.assertTrue(report['dry_run'])
        self.assertFalse(report['game_load_verified'])
        self.assertEqual(self.files(), before)
        process = self.process(*arguments)
        self.assertEqual((process.returncode, process.stderr), (0, ''))
        report = json.loads(process.stdout)
        exported = destination / report['output_file']
        self.assertTrue(exported.is_file())
        after = self.files()
        process = self.process(*arguments)
        self.assertEqual(process.returncode, 1)
        self.assertEqual(self.files(), after)
        for name, raw in before.items():
            self.assertEqual((self.folder / name).read_bytes(), raw)

    def test_batch_conversion_dry_run_preserves_all_files(self):
        source = write_copy(self.folder / 'pc', 'dw6')
        template = write_copy(self.folder / 'ps3', 'dw6_ps3', 1)
        output = self.folder / 'converted'
        plan = self.folder / 'queue.json'
        plan.write_text(json.dumps({'schema_version': 1, 'jobs': [{
            'id': 'save', 'route': 'dw6-to-dw6_ps3', 'source': str(source),
            'template': str(template), 'output_dir': str(output)}]}))
        before = self.files()
        code, text, errors = self.invoke('batch-convert', plan, '--dry-run')
        self.assertEqual((code, errors), (0, ''))
        self.assertTrue(json.loads(text)['dry_run'])
        self.assertEqual(self.files(), before)

    def test_workflow_review_dry_run_token_and_journal_gates_survive_frontend(self):
        source = self.copy()
        destination = self.folder / 'edited.dat'
        workflow = automation.Workflow('Reviewed attack', 'dw4hyper', (
            automation.Operation('assert', (('officer_0_attack', 50),)),
            automation.Operation('set', (('officer_0_attack', 123),))))
        plan = self.folder / 'plan.json'
        plan.write_text(json.dumps({'schema_version': 1, 'workflow': automation.workflow_data(workflow),
                                   'jobs': [{'id': 'save', 'source': source.name, 'destination': destination.name}]}))
        before = self.files()
        process = self.process('automation', 'preview', plan)
        self.assertEqual((process.returncode, process.stderr), (0, ''))
        preview = json.loads(process.stdout)
        self.assertEqual(preview['status'], 'prepared')
        code, text, errors = self.invoke('automation', 'apply', plan, '--dry-run')
        self.assertEqual((code, errors), (0, ''))
        self.assertEqual(json.loads(text)['review_token'], preview['review_token'])
        for options in (('--review-token', 'wrong'), ('--review-token', preview['review_token'])):
            code, text, errors = self.invoke('automation', 'apply', plan, *options)
            self.assertEqual((code, errors), (2, ''))
            self.assertFalse(json.loads(text)['success'])
        self.assertEqual(self.files(), before)
        journal = self.folder / 'journal'
        code, text, errors = self.invoke('automation', 'apply', plan,
                                        '--review-token', preview['review_token'], '--journal', journal)
        self.assertEqual((code, errors), (0, ''))
        self.assertTrue(json.loads(text)['success'])
        adapter = get_game('dw4hyper').get_scalar_adapter()
        restored = adapter.read_save(destination)
        self.assertEqual(adapter.field_map(restored)['officer_0_attack'].value(restored.payload), 123)
        self.assertEqual(source.read_bytes(), before[source.name])
        self.assertTrue(journal.is_dir())

    def test_invalid_automation_retains_structured_json_exit_contract(self):
        process = self.process('automation', 'not-a-command')
        self.assertEqual((process.returncode, process.stderr), (2, ''))
        data = json.loads(process.stdout)
        self.assertFalse(data['success'])
        self.assertEqual(data['error_code'], 'invalid_arguments')

    def test_catalog_filters_are_case_insensitive_ordered_and_truthful_about_totals(self):
        first = self.process('games', '--query', 'NIOH 3', '--platform', 'Windows PC', '--json')
        second = self.process('games', '--query', 'nioh 3', '--platform', 'Windows PC', '--json')
        self.assertEqual((first.returncode, first.stderr), (0, ''))
        self.assertEqual((first.returncode, first.stdout), (second.returncode, second.stdout))
        report = json.loads(first.stdout)
        self.assertEqual([item['id'] for item in report['games']], ['nioh3'])
        self.assertEqual((report['profile_count'], report['full_profile_count']), (1, 98))
        self.assertEqual((report['platform_count'], report['full_platform_count']), (1, 15))
        self.assertEqual(report['filters'], {'query_applied': True, 'platform': 'Windows PC'})
        report = json.loads(self.process('games', '--platform', 'Nintendo Switch', '--json').stdout)
        expected = [game.id for game in SUPPORTED_GAMES if game.platform == 'Nintendo Switch']
        self.assertEqual([item['id'] for item in report['games']], expected)
        self.assertEqual(report['profile_count'], len(expected))
        self.assertEqual(report['full_profile_count'], 98)
        self.assertEqual(report['full_platform_count'], 15)
        report = json.loads(self.process('games', '--platform', 'Nintendo Switch',
                                         '--query', 'nioh 3', '--json').stdout)
        self.assertEqual(report['games'], [])
        self.assertEqual((report['profile_count'], report['platform_count']), (0, 0))
        self.assertEqual((report['full_profile_count'], report['full_platform_count']), (98, 15))
        code, text, errors = self.invoke('games', '--platform', 'Nintendo Switch', '--query', 'nioh 3')
        self.assertEqual((code, errors), (0, ''))
        self.assertEqual(text, '0 matching save profiles (98 total).\n')

    def test_route_endpoint_and_query_filters_preserve_distinct_transfer_scopes(self):
        result = self.process('routes', '--from-game', 'dw6', '--to-game', 'dw6_ps3', '--json')
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        report = json.loads(result.stdout)
        expected = [route.id for route in conversion.ROUTES
                    if route.source_id == 'dw6' and route.target_id == 'dw6_ps3']
        self.assertEqual([item['id'] for item in report['routes']], expected)
        self.assertEqual(report['route_count'], 4)
        self.assertEqual(report['full_route_count'], 145)
        self.assertEqual(report['filters'], {'query_applied': False, 'from_game': 'dw6', 'to_game': 'dw6_ps3'})
        result = self.process('routes', '--from-game', 'dw6', '--to-game', 'dw6_ps3',
                              '--query', 'CAMPAIGNS', '--json')
        report = json.loads(result.stdout)
        self.assertEqual(report['route_count'], 1)
        self.assertEqual(report['routes'][0]['id'], 'dw6-to-dw6_ps3-campaigns')
        self.assertEqual(report['full_route_count'], 145)
        self.assertTrue(report['filters']['query_applied'])

    def test_bad_selectors_fail_before_export_and_queries_are_not_echoed(self):
        destination = self.folder / 'not-created.json'
        for arguments in (('games', '--platform', 'windows'),
                          ('routes', '--from-game', 'dw6_typo'),
                          ('routes', '--to-game', 'dw6_ps33'),
                          ('games', '--query', ''), ('routes', '--query', '')):
            with self.subTest(arguments=arguments):
                code, output, errors = self.invoke(*arguments, '--output', destination, '--json')
                self.assertEqual((code, output), (2, ''))
                self.assertTrue(errors)
                self.assertFalse(destination.exists())
        private = str(self.folder / 'personal-name-query')
        for command in ('games', 'routes'):
            code, output, errors = self.invoke(command, '--query', private, '--json')
            self.assertEqual((code, errors), (0, ''))
            self.assertNotIn(private, output)
            self.assertNotIn('personal-name', output)
            self.assertTrue(json.loads(output)['filters']['query_applied'])
            self.assertEqual(json.loads(output)[command], [])

    def test_inventory_output_is_exact_new_private_json_and_never_overwrites(self):
        output = self.folder / 'new-inventory.json'
        code, text, errors = self.invoke('games', '--query', 'nioh 3', '--json', '--output', output)
        self.assertEqual((code, errors), (0, ''))
        self.assertEqual(output.read_text(), text)
        self.assertNotIn(str(output), text)
        if os.name != 'nt':
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        original = output.read_bytes()
        for command in ('games', 'routes'):
            for mode in ((), ('--json',)):
                code, text, errors = self.invoke(command, '--output', output, *mode)
                self.assertEqual((code, text), (1, ''))
                self.assertIn('export failed', errors)
                self.assertEqual(output.read_bytes(), original)
        self.assertEqual({p.name for p in self.folder.iterdir()}, {output.name})

    def test_inventory_export_error_never_prints_success_or_private_error_paths(self):
        output = self.folder / 'new-report.json'
        with patch('koei_editor.shared.report_export.write_report_bytes',
                   side_effect=OSError('secret-local-user-path')):
            code, text, errors = self.invoke('routes', '--json', '--output', output)
        self.assertEqual((code, text), (1, ''))
        self.assertNotIn('secret-local-user-path', errors)
        self.assertFalse(output.exists())

    def test_inventory_concurrent_destination_creation_preserves_foreign_bytes(self):
        from koei_editor.shared import report_export
        source = self.copy()
        source_before = source.read_bytes()
        output = self.folder / 'contended.json'
        original = report_export.publish_new_child_bound
        injected = []

        def occupy_before_native_publication(data, directory, name, identity, **options):
            # Exercise the actual exclusive publisher after the helper's initial
            # absence check, rather than simulating a publisher failure.
            self.assertEqual(Path(directory) / name, output)
            output.write_bytes(b'foreign-writer-report')
            injected.append(True)
            return original(data, directory, name, identity, **options)

        with patch.object(report_export, 'publish_new_child_bound',
                          side_effect=occupy_before_native_publication):
            code, text, errors = self.invoke('routes', '--json', '--output', output)
        self.assertEqual((code, text), (1, ''))
        self.assertEqual(injected, [True])
        self.assertEqual(output.read_bytes(), b'foreign-writer-report')
        self.assertEqual(source.read_bytes(), source_before)
        self.assertNotIn(str(self.folder), errors)

    def test_inventory_refuses_hardlinked_existing_reports(self):
        source = self.folder / 'retained.json'
        source.write_bytes(b'original-user-report')
        alias = self.folder / 'hardlink.json'
        try:
            os.link(source, alias)
        except OSError as error:
            self.skipTest('Host cannot create a hardlink: ' + type(error).__name__)
        before = self.files()
        code, text, errors = self.invoke('games', '--json', '--output', alias)
        self.assertEqual((code, text), (1, ''))
        self.assertEqual(self.files(), before)

    def test_inventory_refuses_dangling_links_and_aliased_output_parents(self):
        destination = self.folder / 'not-created.json'
        alias = self.folder / 'dangling.json'
        try:
            alias.symlink_to(destination)
        except OSError as error:
            self.skipTest('Host cannot create a symlink: ' + type(error).__name__)
        code, text, errors = self.invoke('games', '--json', '--output', alias)
        self.assertEqual((code, text), (1, ''))
        self.assertFalse(destination.exists())
        self.assertTrue(alias.is_symlink())
        ordinary = self.folder / 'ordinary'
        ordinary.mkdir()
        linked = self.folder / 'linked-parent'
        linked.symlink_to(ordinary, target_is_directory=True)
        code, text, errors = self.invoke('routes', '--json', '--output', linked / 'new.json')
        self.assertEqual((code, text), (1, ''))
        self.assertFalse((ordinary / 'new.json').exists())

    def test_diagnostics_are_headless_path_free_and_truthful_about_platform(self):
        process = self.process('diagnostics', '--json')
        self.assertEqual((process.returncode, process.stderr), (0, ''))
        report = json.loads(process.stdout)
        self.assertEqual(report['schema'], 'koei-toolkit-diagnostics')
        self.assertEqual(report['schema_version'], 1)
        self.assertEqual(report['application']['version'], application.VERSION)
        self.assertEqual(report['application']['mode'], 'source')
        self.assertEqual(report['catalog'], {'profiles': 98, 'platforms': 15,
                                              'conversion_routes': 145, 'in_game_verified': False})
        self.assertNotIn(str(self.folder), process.stdout)
        vault = report['capabilities']['save_vault_profiles']
        self.assertEqual(vault['supported_platform'], os.name == 'nt')
        if os.name != 'nt':
            self.assertEqual(vault['status'], 'requires_windows')
        self.assertTrue(all(item['status'] in ('metadata_available', 'not_installed',
                                             'unavailable', 'version_unrecognized')
                            for item in report['dependencies']))
        with patch('koei_editor.shared.save_discovery.discover_saves',
                   side_effect=AssertionError('Support report scanned game folders')) as discovery, \
                patch.dict(os.environ, {'HOME': 'private-home-sentinel',
                                        'USERNAME': 'private-user-sentinel',
                                        'COMPUTERNAME': 'private-host-sentinel'}):
            code, text, errors = self.invoke('diagnostics', '--json')
        self.assertEqual((code, errors), (0, ''))
        for sentinel in ('private-home-sentinel', 'private-user-sentinel', 'private-host-sentinel'):
            self.assertNotIn(sentinel, text)
        discovery.assert_not_called()
        code, text, errors = self.invoke('diagnostics')
        self.assertEqual((code, errors), (0, ''))
        self.assertIn('Dependency metadata:', text)
        if os.name != 'nt':
            self.assertIn('require Windows.', text)

    def test_diagnostics_export_is_new_only_and_failures_keep_stdout_empty(self):
        output = self.folder / 'support.json'
        code, text, errors = self.invoke('diagnostics', '--json', '--output', output)
        self.assertEqual((code, errors), (0, ''))
        self.assertEqual(output.read_text(), text)
        original = output.read_bytes()
        code, text, errors = self.invoke('diagnostics', '--json', '--output', output)
        self.assertEqual((code, text), (1, ''))
        self.assertEqual(output.read_bytes(), original)
        with patch('koei_editor.shared.toolkit_diagnostics.report_json',
                   side_effect=ValueError('private-invalid-report')):
            code, text, errors = self.invoke('diagnostics', '--json')
        self.assertEqual((code, text), (1, ''))
        self.assertNotIn('private-invalid-report', errors)


if __name__ == '__main__':
    unittest.main()
