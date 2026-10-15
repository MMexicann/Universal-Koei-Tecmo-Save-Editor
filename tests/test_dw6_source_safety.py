"""Backup and destination races must not return a successful DW6 PC copy."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw6 import dw6_parser as p
from tests.test_dw6_availability import fixture


class DW6SourceSafetyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'save.dat'
        self.source.write_bytes(fixture(p))
        self.document = p.read_save(self.source)

    def test_direct_backup_rejects_changed_source_and_race_inside_snapshot_write(self):
        original = p.snapshot_backup
        def racing(*args, **kwargs):
            result = original(*args, **kwargs)
            self.source.write_bytes(self.document.raw + b'\0')
            return result
        with patch.object(p, 'snapshot_backup', side_effect=racing), self.assertRaises(SaveError):
            p.backup(self.document)
        with self.assertRaises(SaveError):
            p.backup(self.document)

    def test_changed_source_during_backup_never_creates_destination(self):
        original = p.backup
        def racing(document):
            result = original(document)
            self.source.write_bytes(document.raw + b'\0')
            return result
        with patch.object(p, 'backup', side_effect=racing), self.assertRaises(SaveError):
            p.save_as(self.document, {'stage_0_available': 1}, self.root / 'edited.dat')
        self.assertFalse((self.root / 'edited.dat').exists())

    def test_changed_actual_destination_is_refused_and_external_bytes_preserved(self):
        destination = self.root / 'edited.dat'
        original = p.atomic_new
        changed = bytearray(self.document.raw)
        changed[0x100] ^= 0x55
        external = bytes(changed)
        def racing(data, path):
            result = original(data, path)
            # Windows temporary directories can use an 8.3 alias while the
            # guarded writer resolves its destination to the long path.
            if Path(path).resolve() == destination.resolve():
                destination.write_bytes(external)
            return result
        with patch.object(p, 'atomic_new', side_effect=racing), self.assertRaises(SaveError):
            p.save_as(self.document, {'stage_0_available': 1}, destination)
        self.assertEqual(destination.read_bytes(), external)
        self.assertEqual(self.source.read_bytes(), self.document.raw)
