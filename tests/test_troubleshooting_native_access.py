"""Native record bounds plus actual Windows anchored traversal qualification."""
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from koei_editor.shared import anchored_read_windows as native
from koei_editor.shared import game_troubleshooting as troubleshooting
from tests.test_game_troubleshooting import finding, snapshot_tree


def record(name='settings.json', *, identity=(1 << 100) + 17, attributes=0, size=2):
    encoded = name.encode('utf-16-le')
    data = bytearray(88 + len(encoded))
    data[24:32] = (116444736000000000 + 123456789).to_bytes(8, 'little', signed=True)
    data[40:48] = size.to_bytes(8, 'little', signed=True)
    data[56:60] = attributes.to_bytes(4, 'little')
    data[60:64] = len(encoded).to_bytes(4, 'little')
    data[72:88] = identity.to_bytes(16, 'little')
    data[88:] = encoded
    return bytes(data)


class NativeRecordTests(unittest.TestCase):
    def test_full_file_identity_and_precise_metadata_survive_without_path_lookup(self):
        with patch.object(Path, 'stat', side_effect=AssertionError('No pathname metadata')):
            item = native._decode_entry(record(attributes=0x400), 7)
        self.assertEqual(item.name, 'settings.json')
        info = item.stat(follow_symlinks=False)
        self.assertEqual((info.st_dev, info.st_ino, info.st_size), (7, (1 << 100) + 17, 2))
        self.assertEqual(info.st_mtime_ns, 12345678900)
        self.assertTrue(troubleshooting._linked(info))

    def test_truncated_ambiguous_and_unsafe_entries_are_rejected(self):
        malformed = [b'', record()[:87], record()[:-1], record(identity=0), record(size=-1)]
        for name in ('../outside.json', 'outside\\settings.json', 'disk:stream', 'trailing.', 'trailing '):
            malformed.append(record(name))
        data = bytearray(record()); data[:4] = (16).to_bytes(4, 'little'); malformed.append(bytes(data))
        data = bytearray(record()); data[60:64] = (3).to_bytes(4, 'little'); malformed.append(bytes(data))
        for raw in malformed:
            with self.subTest(length=len(raw)), self.assertRaises(OSError):
                native._decode_entry(raw, 1)
        self.assertIsNone(native._decode_entry(record('.'), 1))
        self.assertIsNone(native._decode_entry(record('..'), 1))

    def test_native_chain_never_falls_back_to_path_access_on_other_platforms(self):
        if os.name == 'nt':
            self.skipTest('Actual Windows chain is qualified by the native cases below')
        with patch.object(Path, 'open', side_effect=AssertionError('No fallback')):
            with self.assertRaises(OSError), native.directory_chain(((Path('/'), None),)):
                pass


@unittest.skipUnless(os.name == 'nt', 'Requires actual native Windows directory/file handles')
class WindowsTroubleshootingAccessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.folder = self.base / 'selected'
        self.folder.mkdir()
        (self.folder / 'game.exe').write_bytes(b'procedural marker; never executed')
        (self.folder / 'settings.json').write_bytes(b'{"private":"never exposed"}')

    def test_actual_native_scan_checks_configs_without_path_enumeration_or_open(self):
        before = snapshot_tree(self.folder)
        with patch.object(os, 'scandir', side_effect=AssertionError('Native enumeration required')), \
                patch.object(os, 'open', side_effect=AssertionError('Native relative opens required')):
            report = troubleshooting.diagnose_game('origins', self.folder, self.folder, self.folder)
        self.assertEqual(finding(report, 'installation.selected_root').status, 'passed')
        self.assertEqual(finding(report, 'configuration.syntax').status, 'passed')
        self.assertEqual(finding(report, 'mods.scan').status, 'passed')
        self.assertEqual(finding(report, 'mods.conflicts').status, 'not_checked')
        self.assertNotIn('never exposed', report.to_json())
        self.assertNotIn(str(self.folder), report.to_json())
        self.assertEqual(snapshot_tree(self.folder), before)

    def test_held_directory_cannot_be_renamed_during_native_enumeration(self):
        selected, state = troubleshooting._ordinary_root(self.folder)
        self.assertEqual(state, 'ready')
        with troubleshooting._directory(selected.bindings) as directory:
            with self.assertRaises(OSError):
                self.folder.rename(self.base / 'renamed')
            with directory.entries() as entries:
                self.assertEqual(sorted(item.name for item in entries), ['game.exe', 'settings.json'])
        self.assertTrue(self.folder.exists())

    def test_queued_directory_replacement_is_not_adopted(self):
        queued = self.folder / 'queued'; queued.mkdir()
        (queued / 'settings.json').write_bytes(b'{}')
        outside = self.base / 'outside'; outside.mkdir()
        (outside / 'private.json').write_bytes(b'{private invalid content')
        original = troubleshooting._directory
        replaced = False
        selected, _state = troubleshooting._ordinary_root(self.folder)

        @contextmanager
        def replace(bindings):
            nonlocal replaced
            if bindings[-1][0] == queued and not replaced:
                replaced = True
                queued.rename(self.base / 'held')
                outside.rename(queued)
            with original(bindings) as directory:
                yield directory

        with patch.object(troubleshooting, '_directory', replace):
            files, _visited, _links, truncated = troubleshooting._walk(selected)
        self.assertTrue(replaced)
        self.assertTrue(truncated)
        self.assertNotIn('private.json', [name for _item, name, _size in files])
        self.assertEqual((queued / 'private.json').read_bytes(), b'{private invalid content')

    def test_replaced_config_identity_is_rejected_before_read(self):
        selected, _state = troubleshooting._ordinary_root(self.folder)
        files, _visited, _links, _truncated = troubleshooting._walk(selected)
        scanned = next(item for item, name, _size in files if name == 'settings.json')
        scanned.path.rename(self.base / 'original.json')
        scanned.path.write_bytes(b'{"private":"different"}')
        real_fdopen = os.fdopen

        def forbidden_read(*_args):
            raise AssertionError('Replacement content must not be read')

        @contextmanager
        def guarded_stream(fd, mode):
            with real_fdopen(fd, mode) as stream:
                yield SimpleNamespace(fileno=stream.fileno, read=forbidden_read)

        with patch.object(os, 'fdopen', guarded_stream):
            self.assertEqual(troubleshooting._decode_config(scanned), 'changed')
        self.assertEqual((self.base / 'original.json').read_bytes(), b'{"private":"never exposed"}')

    def test_selected_and_child_symlinks_are_never_followed(self):
        outside = self.base / 'outside'; outside.mkdir()
        (outside / 'private.json').write_bytes(b'not valid json')
        link = self.folder / 'linked'
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest('Host cannot create native test symlinks: ' + type(error).__name__)
        report = troubleshooting.diagnose_game('origins', self.folder, self.folder)
        self.assertEqual(finding(report, 'configuration.syntax').status, 'passed')
        self.assertEqual(finding(report, 'installation.links_skipped').status, 'not_checked')
        root_report = troubleshooting.diagnose_game('origins', link, link)
        self.assertEqual(finding(root_report, 'installation.selected_root').status, 'unknown')
        self.assertEqual(finding(root_report, 'configuration.selected_root').status, 'unknown')


if __name__ == '__main__':
    unittest.main()
