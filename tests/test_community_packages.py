"""Strict, inert sharing formats for the Koei Tecmo Community Toolkit."""
import builtins
import copy
import importlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from koei_editor.shared import community_packages as packages


def document(kind='character_build'):
    """Fictional metadata only; these examples contain no game files or saves."""
    payloads = {
        'character_build': {
            'character_id': 'officer.example', 'level': 45,
            'stats': [{'key': 'attack', 'value': 275}, {'key': 'style', 'value': 'rapid'}],
            'skills': [{'id': 'skill.example-rush', 'rank': 2}],
            'equipment': [{'slot': 'weapon.primary', 'id': 'weapon.example'}],
        },
        'mod_list': {
            'mods': [{'id': 'mod.example-balance', 'title': 'Example balance notes',
                      'version': '1.2.0', 'source_url': 'https://mods.example.test/balance',
                      'sha256': 'a' * 64, 'enabled': True}],
            'load_order': ['mod.example-balance'],
        },
        'configuration_preset': {
            'settings': [{'key': 'display.window_mode', 'value': 'borderless'},
                         {'key': 'display.vsync', 'value': True},
                         {'key': 'display.frame_limit', 'value': 60}],
        },
        'playthrough_manifest': {
            'objectives': [
                {'id': 'chapter.one', 'title': 'Start chapter one', 'status': 'complete',
                 'order': 1, 'depends_on': []},
                {'id': 'chapter.two', 'title': 'Continue to chapter two', 'status': 'planned',
                 'order': 2, 'depends_on': ['chapter.one']},
            ],
        },
        'compatibility_report': {
            'entries': [{'component': 'mod.example-quality-of-life', 'version': '1.2.0',
                         'status': 'unknown', 'details': 'Contributor report; not independently verified.'}],
        },
    }
    return {
        'schema': packages.SCHEMA,
        'version': packages.SCHEMA_VERSION,
        'kind': kind,
        'id': 'community.example-' + kind,
        'title': 'Example ' + kind.replace('_', ' '),
        'author': 'Example contributor',
        'game_id': 'dw8xl',
        'platform': 'pc',
        'game_version': None,
        'description': 'Fictional metadata for a format test.',
        'payload': payloads[kind],
    }


def raw(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')


class CommunityPackageFormatTests(unittest.TestCase):
    def test_fictional_templates_match_the_versioned_runtime_envelope(self):
        root = Path(__file__).resolve().parents[1]
        kinds = ('character_build', 'mod_list', 'configuration_preset',
                 'playthrough_manifest', 'compatibility_report')
        for kind in kinds:
            with self.subTest(kind=kind):
                template = root / 'tools' / 'community_package_templates' / (kind + packages.SUFFIX)
                schema_path = root / 'docs' / 'schemas' / f'koei-community-{kind}-v1.schema.json'
                package = packages.loads(template.read_bytes())
                schema = json.loads(schema_path.read_text(encoding='utf-8'))
                self.assertEqual(package.kind, kind)
                self.assertEqual(schema['properties']['kind']['const'], kind)
                self.assertEqual(schema['properties']['version']['const'], packages.SCHEMA_VERSION)
                self.assertIs(schema['additionalProperties'], False)

    def test_all_five_package_kinds_load_and_round_trip(self):
        kinds = ('character_build', 'mod_list', 'configuration_preset',
                 'playthrough_manifest', 'compatibility_report')
        for kind in kinds:
            with self.subTest(kind=kind):
                source = document(kind)
                loaded = packages.loads(raw(source))
                self.assertIsInstance(loaded, packages.CommunityPackage)
                self.assertEqual(loaded.kind, kind)
                self.assertEqual(loaded.game_id, 'dw8xl')
                self.assertEqual(packages.loads(packages.dumps(loaded)), loaded)

    def test_loaded_payload_is_recursively_immutable(self):
        loaded = packages.loads(raw(document('character_build')))
        with self.assertRaises(TypeError):
            loaded.payload['character_id'] = 'changed'
        with self.assertRaises((TypeError, AttributeError)):
            loaded.payload['stats'][0]['value'] = 1
        with self.assertRaises((TypeError, AttributeError)):
            loaded.payload['skills'][0]['id'] = 'changed'

    def test_dumps_revalidates_manually_constructed_or_replaced_models(self):
        loaded = packages.loads(raw(document('configuration_preset')))
        invalid = packages.CommunityPackage(
            kind=loaded.kind, id=loaded.id, title=loaded.title, author=loaded.author,
            game_id=loaded.game_id, platform=loaded.platform, game_version=loaded.game_version,
            description=loaded.description,
            payload={'settings': [{'key': 'display.fps', 'value': 1.5}]},
        )
        with self.assertRaises(ValueError):
            packages.dumps(invalid)

    def test_dumps_is_deterministic_and_contains_metadata_only(self):
        loaded = packages.loads(raw(document('mod_list')))
        with patch('socket.create_connection', side_effect=AssertionError('No network')):
            first = packages.dumps(loaded)
            second = packages.dumps(loaded)
        self.assertEqual(first, second)
        self.assertNotIn(b'private.sav', first)
        self.assertNotIn(b'account_id', first)
        self.assertNotIn(b'file_bytes', first)

    def test_schema_and_version_are_exact(self):
        for key, value in (('schema', 'another-format'), ('version', 0), ('version', True)):
            changed = document()
            changed[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                packages.loads(raw(changed))

    def test_missing_or_extra_envelope_and_payload_properties_fail_closed(self):
        changed = document()
        changed.pop('author')
        with self.assertRaises(ValueError):
            packages.loads(raw(changed))

        changed = document()
        changed['file_path'] = '/private/example/save.sav'
        with self.assertRaises(ValueError):
            packages.loads(raw(changed))

        for kind in ('character_build', 'mod_list', 'configuration_preset',
                     'playthrough_manifest', 'compatibility_report'):
            changed = document(kind)
            changed['payload']['unexpected'] = 'must not be accepted'
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                packages.loads(raw(changed))

    def test_duplicate_properties_and_nonfinite_or_fractional_json_are_rejected(self):
        for source in (
                b'{"schema":"koei-tecmo-community-package","schema":"koei-tecmo-community-package"}',
                b'{"schema":"koei-tecmo-community-package","version":NaN}',
                b'{"schema":"koei-tecmo-community-package","version":Infinity}',
                raw({**document(), 'payload': {**document()['payload'], 'level': 12.5}}),
                raw({**document(), 'payload': {**document()['payload'],
                                                'stats': [{'key': 'attack', 'value': 1.5}]}}),
        ):
            with self.subTest(source=source[:90]), self.assertRaises(ValueError):
                packages.loads(source)

    def test_deeply_nested_json_is_rejected(self):
        deeply_nested = (b'[' * 2000) + b'0' + (b']' * 2000)
        with self.assertRaises(ValueError):
            packages.loads(deeply_nested)

    def test_boolean_values_are_not_accepted_for_integer_fields(self):
        invalid_values = [
            ('character_build', 'level', True),
            ('character_build', 'level', False),
        ]
        for kind, key, value in invalid_values:
            changed = document(kind)
            changed['payload'][key] = value
            with self.subTest(kind=kind, value=value), self.assertRaises(ValueError):
                packages.loads(raw(changed))
        changed = document('character_build')
        changed['payload']['skills'][0]['rank'] = True
        with self.assertRaises(ValueError):
            packages.loads(raw(changed))
        changed = document('playthrough_manifest')
        changed['payload']['objectives'][0]['order'] = True
        with self.assertRaises(ValueError):
            packages.loads(raw(changed))

    def test_character_build_integer_boundaries_and_unique_ids(self):
        for level in (1, 9999):
            changed = document()
            changed['payload']['level'] = level
            self.assertEqual(packages.loads(raw(changed)).payload['level'], level)
        for level in (0, 10000, -1):
            changed = document()
            changed['payload']['level'] = level
            with self.subTest(level=level), self.assertRaises(ValueError):
                packages.loads(raw(changed))

        changed = document()
        changed['payload']['stats'].append(copy.deepcopy(changed['payload']['stats'][0]))
        with self.assertRaises(ValueError):
            packages.loads(raw(changed))

        changed = document()
        changed['payload']['equipment'].append(copy.deepcopy(changed['payload']['equipment'][0]))
        with self.assertRaises(ValueError):
            packages.loads(raw(changed))

    def test_text_field_length_boundaries_are_enforced(self):
        changed = document()
        changed['title'] = 't' * packages.MAX_TITLE_LENGTH
        packages.loads(raw(changed))
        changed['title'] += 't'
        with self.assertRaises(ValueError):
            packages.loads(raw(changed))

        changed = document('configuration_preset')
        changed['payload']['settings'][0]['value'] = 'x' * packages.MAX_VALUE_TEXT_LENGTH
        packages.loads(raw(changed))
        changed['payload']['settings'][0]['value'] += 'x'
        with self.assertRaises(ValueError):
            packages.loads(raw(changed))

    def test_mod_urls_hashes_and_load_order_are_checked(self):
        mutations = (
            lambda mod: mod.update(source_url='http://mods.example.test/file'),
            lambda mod: mod.update(source_url='HTTPS://mods.example.test/file'),
            lambda mod: mod.update(source_url='javascript:alert(1)'),
            lambda mod: mod.update(source_url='https://user:pass@mods.example.test/file'),
            lambda mod: mod.update(source_url='https:///missing-host'),
            lambda mod: mod.update(sha256='A' * 64),
            lambda mod: mod.update(sha256='a' * 63),
        )
        for mutate in mutations:
            changed = document('mod_list')
            mutate(changed['payload']['mods'][0])
            with self.subTest(mod=changed['payload']['mods'][0]), self.assertRaises(ValueError):
                packages.loads(raw(changed))

        for order in ([], ['mod.missing'], ['mod.example-balance', 'mod.example-balance']):
            changed = document('mod_list')
            changed['payload']['load_order'] = order
            with self.subTest(order=order), self.assertRaises(ValueError):
                packages.loads(raw(changed))

        changed = document('mod_list')
        changed['payload']['mods'][0]['enabled'] = False
        with self.assertRaises(ValueError):
            packages.loads(raw(changed))

        changed = document('mod_list')
        changed['payload']['mods'].append(copy.deepcopy(changed['payload']['mods'][0]))
        with self.assertRaises(ValueError):
            packages.loads(raw(changed))

    def test_configuration_settings_are_unique_and_scalar(self):
        for bad in (None, 1.25, [], {}, {'command': 'run'}, 'line\ncontrol'):
            changed = document('configuration_preset')
            changed['payload']['settings'][0]['value'] = bad
            with self.subTest(value=bad), self.assertRaises(ValueError):
                packages.loads(raw(changed))
        changed = document('configuration_preset')
        changed['payload']['settings'].append(copy.deepcopy(changed['payload']['settings'][0]))
        with self.assertRaises(ValueError):
            packages.loads(raw(changed))

    def test_playthrough_references_are_unique_valid_and_acyclic(self):
        invalid_mutations = (
            lambda objectives: objectives[0].update(status='maybe'),
            lambda objectives: objectives[1].update(depends_on=['chapter.missing']),
            lambda objectives: objectives[0].update(depends_on=['chapter.one']),
            lambda objectives: objectives[0].update(depends_on=['chapter.two']),
            lambda objectives: objectives[1].update(order=1),
            lambda objectives: objectives[1].update(id='chapter.one'),
        )
        for mutate in invalid_mutations:
            changed = document('playthrough_manifest')
            mutate(changed['payload']['objectives'])
            with self.subTest(objectives=changed['payload']['objectives']), self.assertRaises(ValueError):
                packages.loads(raw(changed))

    def test_compatibility_report_status_and_version_types_are_checked(self):
        for status in ('verified', 'works', 'COMPATIBLE', ''):
            changed = document('compatibility_report')
            changed['payload']['entries'][0]['status'] = status
            with self.subTest(status=status), self.assertRaises(ValueError):
                packages.loads(raw(changed))
        for version in (False, 1, {}, []):
            changed = document('compatibility_report')
            changed['payload']['entries'][0]['version'] = version
            with self.subTest(version=version), self.assertRaises(ValueError):
                packages.loads(raw(changed))

    def test_bad_ids_and_invisible_or_control_text_are_rejected(self):
        for key, value in (
                ('id', '../example'), ('id', 'Community.Example'), ('game_id', 'dw-8-xl'),
                ('platform', 'PC'), ('title', 'looks\u202e reversed'),
                ('author', 'author\x00name'), ('description', 'has\x1b escape')):
            changed = document()
            changed[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                packages.loads(raw(changed))

    def test_invalid_byte_type_empty_bytes_size_and_list_boundaries(self):
        for invalid in (b'', 'not bytes', bytearray(b'{}'), memoryview(b'{}')):
            with self.subTest(invalid=type(invalid).__name__), self.assertRaises(ValueError):
                packages.loads(invalid)
        # Padding remains syntactically legal JSON, so this proves the byte
        # limit is enforced before parsing or allocating a decoded tree.
        valid = raw(document())
        exact_limit = valid + b' ' * (packages.MAX_BYTES - len(valid))
        packages.loads(exact_limit)
        oversized = raw(document()) + b' ' * packages.MAX_BYTES
        with self.assertRaises(ValueError):
            packages.loads(oversized)

        maximum = packages.MAX_ITEMS
        changed = document('configuration_preset')
        changed['payload']['settings'] = [
            {'key': f'video.setting-{index}', 'value': index}
            for index in range(maximum)
        ]
        packages.loads(raw(changed))
        changed['payload']['settings'].append({'key': 'video.last', 'value': 1})
        with self.assertRaises(ValueError):
            packages.loads(raw(changed))

    def test_untrusted_strings_are_inert_and_urls_are_not_fetched(self):
        sentinel = "__import__('os').system('touch /tmp/should-not-exist')"
        changed = document('compatibility_report')
        changed['payload']['entries'][0]['details'] = sentinel
        with (
                patch('socket.create_connection', side_effect=AssertionError('No network')),
                patch('subprocess.Popen', side_effect=AssertionError('No process')),
                patch('os.system', side_effect=AssertionError('No shell')),
                patch.object(builtins, 'eval', side_effect=AssertionError('No eval')),
                patch.object(builtins, 'exec', side_effect=AssertionError('No exec')),
                patch.object(importlib, 'import_module', side_effect=AssertionError('No dynamic imports'))):
            loaded = packages.loads(raw(changed))
        self.assertEqual(loaded.payload['entries'][0]['details'], sentinel)

    def test_untrusted_host_model_is_bounded_before_recursive_copy(self):
        package = packages.loads(raw(document('configuration_preset')))
        nested = [None] * packages.MAX_ITEMS
        branching = [nested] * packages.MAX_ITEMS
        over_budget = [branching] * packages.MAX_ITEMS
        forged = packages.CommunityPackage(
            kind=package.kind, id=package.id, title=package.title, author=package.author,
            game_id=package.game_id, platform=package.platform, game_version=package.game_version,
            description=package.description, payload={'settings': over_budget},
        )
        with self.assertRaisesRegex(ValueError, 'item limit'):
            packages.dumps(forged)


class CommunityPackageFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.package = packages.loads(raw(document()))

    @staticmethod
    def stat_snapshot(info, **changes):
        values = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
        values.update(changes)
        return SimpleNamespace(**values)

    def test_windows_handle_change_time_can_differ_from_path_creation_time(self):
        native_fstat = os.fstat

        def handle_stat(descriptor):
            info = native_fstat(descriptor)
            return self.stat_snapshot(info, st_ctime_ns=info.st_ctime_ns + 86_400_000_000_000)

        with patch.object(packages.os, 'fstat', side_effect=handle_stat):
            created = packages.export(self.package, self.folder / 'windows-time-semantics')
            self.assertEqual(packages.load(created), self.package)
        self.assertEqual(created.read_bytes(), packages.dumps(self.package))

    def test_shared_native_metadata_mismatch_is_rejected_before_reading(self):
        selected = self.folder / ('identity' + packages.SUFFIX)
        selected.write_bytes(packages.dumps(self.package))
        native_fstat = os.fstat
        for field in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_nlink'):
            def changed_stat(descriptor, field=field):
                info = native_fstat(descriptor)
                return self.stat_snapshot(info, **{field: getattr(info, field) + 1})

            with self.subTest(field=field), patch.object(packages.os, 'fstat', side_effect=changed_stat), \
                    patch.object(packages.os, 'read') as read:
                with self.assertRaises(packages.CommunityPackageError):
                    packages.load(selected)
                read.assert_not_called()

    def test_same_origin_freshness_still_checks_ctime_links_and_attributes(self):
        selected = self.folder / ('freshness' + packages.SUFFIX)
        selected.write_bytes(packages.dumps(self.package))
        native_fstat, native_lstat, native_read = os.fstat, Path.lstat, os.read
        for origin in ('handle', 'path'):
            for field in ('st_ctime_ns', 'st_nlink', 'st_file_attributes'):
                read_started = False

                def snapshot(info, source):
                    if read_started and origin == source:
                        return self.stat_snapshot(info, **{field: getattr(info, field, 0) + 1})
                    return info

                def read(descriptor, count):
                    nonlocal read_started
                    result = native_read(descriptor, count)
                    read_started = True
                    return result

                def lstat(path, *args, **kwargs):
                    info = native_lstat(path, *args, **kwargs)
                    return snapshot(info, 'path') if path == selected else info

                with self.subTest(origin=origin, field=field), \
                        patch.object(packages.os, 'read', side_effect=read), \
                        patch.object(packages.os, 'fstat', side_effect=lambda descriptor: snapshot(native_fstat(descriptor), 'handle')), \
                        patch.object(Path, 'lstat', lstat):
                    with self.assertRaisesRegex(packages.CommunityPackageError, 'changed while'):
                        packages.load(selected)

    def test_same_size_replacement_before_open_is_rejected_and_preserved(self):
        selected = self.folder / ('selected' + packages.SUFFIX)
        expected = packages.dumps(self.package)
        selected.write_bytes(expected)
        before = selected.stat()
        replacement = self.folder / 'foreign-replacement'
        foreign = b'X' * len(expected)
        replacement.write_bytes(foreign)
        os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
        native_open = os.open
        replaced = False

        def replace_then_open(path, flags, *args, **kwargs):
            nonlocal replaced
            if Path(path) == selected and not replaced:
                replaced = True
                os.replace(replacement, selected)
            return native_open(path, flags, *args, **kwargs)

        with patch.object(packages.os, 'open', side_effect=replace_then_open):
            with self.assertRaisesRegex(packages.CommunityPackageError, 'changed before'):
                packages.load(selected)
        self.assertTrue(replaced)
        self.assertEqual(selected.read_bytes(), foreign)

    def test_same_size_content_change_with_restored_mtime_is_rejected(self):
        selected = self.folder / ('content-change' + packages.SUFFIX)
        expected = packages.dumps(self.package)
        selected.write_bytes(expected)
        before = selected.stat()
        native_read = os.read
        changed = False

        def change_after_read(descriptor, count):
            nonlocal changed
            result = native_read(descriptor, count)
            if not changed:
                changed = True
                with selected.open('r+b') as stream:
                    stream.write(b'X' + expected[1:])
                os.utime(selected, ns=(before.st_atime_ns, before.st_mtime_ns))
            return result

        with patch.object(packages.os, 'read', side_effect=change_after_read):
            with self.assertRaisesRegex(packages.CommunityPackageError, 'changed while'):
                packages.load(selected)
        self.assertTrue(changed)
        self.assertEqual(selected.stat().st_size, before.st_size)
        self.assertEqual(selected.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(selected.read_bytes(), b'X' + expected[1:])

    def test_oversized_file_and_existing_hard_link_are_not_opened(self):
        selected = self.folder / ('bounded' + packages.SUFFIX)
        selected.write_bytes(b'X' * (packages.MAX_BYTES + 1))
        with patch.object(packages.os, 'open') as opened:
            with self.assertRaises(packages.CommunityPackageError):
                packages.load(selected)
            opened.assert_not_called()
        selected.write_bytes(packages.dumps(self.package))
        alias = self.folder / 'hard-linked-alias'
        try:
            os.link(selected, alias)
        except (AttributeError, OSError, NotImplementedError):
            self.skipTest('This filesystem cannot create hard links.')
        with patch.object(packages.os, 'open') as opened:
            with self.assertRaises(packages.CommunityPackageError):
                packages.load(selected)
            opened.assert_not_called()
        self.assertEqual(alias.read_bytes(), selected.read_bytes())

    def test_load_and_new_file_export_use_the_dedicated_suffix(self):
        destination = self.folder / ('build' + packages.SUFFIX)
        created = packages.export(self.package, destination)
        self.assertEqual(created, destination)
        self.assertEqual(packages.load(destination), self.package)
        with self.assertRaises(FileExistsError):
            packages.export(self.package, destination)
        self.assertEqual(packages.load(destination), self.package)

    def test_export_completes_the_suffix_and_never_replaces_existing_files(self):
        destination = packages.export(self.package, self.folder / 'portable-build')
        self.assertTrue(destination.name.casefold().endswith(packages.SUFFIX))
        other = self.folder / ('existing' + packages.SUFFIX)
        other.write_bytes(b'keep existing bytes')
        with self.assertRaises(FileExistsError):
            packages.export(self.package, other)
        self.assertEqual(other.read_bytes(), b'keep existing bytes')

    def test_load_rejects_wrong_suffix_and_symlink(self):
        wrong = self.folder / 'build.json'
        wrong.write_bytes(packages.dumps(self.package))
        with self.assertRaises(ValueError):
            packages.load(wrong)

        target = self.folder / ('target' + packages.SUFFIX)
        target.write_bytes(packages.dumps(self.package))
        link = self.folder / ('link' + packages.SUFFIX)
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest('Symlink creation is unavailable on this platform.')
        with self.assertRaises(ValueError):
            packages.load(link)

    def test_load_errors_do_not_echo_a_private_selected_path(self):
        private = self.folder / 'private-player-save.sav' / ('missing' + packages.SUFFIX)
        with self.assertRaises(ValueError) as caught:
            packages.load(private)
        self.assertNotIn(str(private), str(caught.exception))

    def test_load_rejects_special_files_without_blocking(self):
        if not hasattr(os, 'mkfifo'):
            self.skipTest('FIFO files are unavailable on this platform.')
        fifo = self.folder / ('pipe' + packages.SUFFIX)
        os.mkfifo(fifo)
        with self.assertRaises(ValueError):
            packages.load(fifo)

    def test_failed_export_does_not_leak_destination_path_into_package(self):
        private_path = self.folder / 'private-player-save.sav'
        self.assertNotIn(str(private_path), packages.dumps(self.package).decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
