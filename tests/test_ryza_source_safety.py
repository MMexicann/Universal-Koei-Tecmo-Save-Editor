"""Changed-source protection during Ryza backup and long-running Save As."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.ryza import codec, parser
from tests.test_ryza_format import procedural_raw as ryza2_raw
from tests.test_ryza_switch import raw_for as switch_raw


class RyzaSourceSafetyTests(unittest.TestCase):
    def _profiles(self):
        return (('atelier_ryza2', ryza2_raw()), ('atelier_ryza_switch', switch_raw()))

    def test_direct_backup_rejects_changed_or_missing_source(self):
        for game, raw in self._profiles():
            with self.subTest(game=game), tempfile.TemporaryDirectory() as folder:
                source = Path(folder) / 'copy.dat'
                source.write_bytes(raw)
                document = parser.read_save(source, game)
                source.write_bytes(b'externally changed')
                with self.assertRaises(SaveError):
                    parser.backup(document)
                self.assertFalse((Path(folder) / 'WarriorsEditorBackups').exists())
                source.unlink()
                with self.assertRaises(SaveError):
                    parser.backup(document)

    def test_save_rejects_source_changed_during_native_encoding(self):
        for game, raw in self._profiles():
            with self.subTest(game=game), tempfile.TemporaryDirectory() as folder:
                source, destination = Path(folder) / 'copy.dat', Path(folder) / 'edited.dat'
                source.write_bytes(raw)
                document = parser.read_save(source, game)
                field = parser.fields_for(document)[0]
                original_encode = codec.encode_file

                def concurrent_encode(*args, **kwargs):
                    encoded = original_encode(*args, **kwargs)
                    source.write_bytes(b'externally changed during encoding')
                    return encoded

                with patch.object(codec, 'encode_file', side_effect=concurrent_encode):
                    with self.assertRaises(SaveError):
                        parser.save_as(document, {field.id: 1}, destination)
                self.assertFalse(destination.exists())
                self.assertFalse((Path(folder) / 'WarriorsEditorBackups').exists())

    def test_final_source_check_rejects_mutation_after_backup(self):
        for game, raw in self._profiles():
            with self.subTest(game=game), tempfile.TemporaryDirectory() as folder:
                source, destination = Path(folder) / 'copy.dat', Path(folder) / 'edited.dat'
                source.write_bytes(raw)
                document = parser.read_save(source, game)
                field = parser.fields_for(document)[0]
                original_snapshot = parser.snapshot_backup

                def concurrent_backup(*args, **kwargs):
                    backup = original_snapshot(*args, **kwargs)
                    source.write_bytes(b'externally changed after backup')
                    return backup

                with patch.object(parser, 'snapshot_backup', side_effect=concurrent_backup):
                    with self.assertRaises(SaveError):
                        parser.save_as(document, {field.id: 1}, destination)
                self.assertFalse(destination.exists())
                backups = list((Path(folder) / 'WarriorsEditorBackups').glob('*.dat'))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_bytes(), raw)

    def test_unchanged_source_still_saves_and_restores_for_both_profiles(self):
        for game, raw in self._profiles():
            with self.subTest(game=game), tempfile.TemporaryDirectory() as folder:
                source, destination = Path(folder) / 'copy.dat', Path(folder) / 'edited.dat'
                source.write_bytes(raw)
                document = parser.read_save(source, game)
                field = parser.fields_for(document)[0]
                edited = parser.save_as(document, {field.id: 1}, destination)
                self.assertEqual(field.value(edited.payload), 1)
                self.assertEqual(source.read_bytes(), raw)
                backup = parser.backup(document)
                restored = Path(folder) / 'restored.dat'
                parser.restore(backup, restored, game)
                self.assertEqual(restored.read_bytes(), raw)
