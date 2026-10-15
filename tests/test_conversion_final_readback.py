"""Late export replacements cannot produce a successful conversion receipt."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from dataclasses import replace

from koei_editor import conversion as c
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw6_xbox360 import stfs_context
from tests.test_conversion import fixture, write_copy
from tests.test_dw6_xbox360_conversion import context_fixture


class ConversionFinalReadbackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = write_copy(self.root / 'source', 'dw6')
        self.template = write_copy(self.root / 'template', 'dw6_xbox360_na', 1)
        self.original_source = self.source.read_bytes()
        self.original_template = self.template.read_bytes()
        self.original_context = (self.template.parent / 'ORIGINAL.CON').read_bytes()
        self.reviewed = c.prepare('dw6-to-dw6_xbox360_na-records', self.source, self.template)
        self.output = self.root / 'output'

    def test_success_matches_actual_gameplay_original_context_and_receipt(self):
        destination, _backups, receipt = c.export(self.reviewed, self.output)
        self.assertEqual(destination.read_bytes(), self.reviewed.raw)
        self.assertEqual(receipt['output_sha256'], hashlib.sha256(destination.read_bytes()).hexdigest())
        self.assertEqual(json.loads((self.output / 'conversion.json').read_bytes()), receipt)
        context = (self.output / 'ORIGINAL.CON').read_bytes()
        self.assertEqual(context, self.original_context)
        # The copied CON is intentionally unchanged. Success describes the raw
        # export, never a package with its embedded gameplay already replaced.
        embedded = stfs_context.extract_payload(context, 'dw6_xbox360_na')
        self.assertEqual(embedded, self.original_template)
        self.assertNotEqual(embedded, destination.read_bytes())
        self.assertFalse(receipt['console_signing_performed'])
        self.assertFalse(receipt['game_load_verified'])

    def _replace_when_receipt_finishes(self, target, foreign):
        original_atomic = c.atomic_new
        touched = []

        def replace_completed(data, path):
            result = original_atomic(data, path)
            if Path(path).name == 'conversion.json':
                target.write_bytes(foreign)
                touched.append(target)
            return result

        with mock.patch.object(c, 'atomic_new', side_effect=replace_completed):
            with self.assertRaises(SaveError):
                c.export(self.reviewed, self.output)
        self.assertEqual(touched, [target])
        self.assertEqual(target.read_bytes(), foreign)
        # Completed input backups remain available after a rejected export.
        backups = list((self.source.parent / 'WarriorsEditorBackups').glob('*.dat'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), self.original_source)
        self.assertEqual({path.name for path in self.output.iterdir()},
                         {'DW6_NA.dat', 'ORIGINAL.CON', 'conversion.json'})

    def test_late_raw_replacement_is_refused_and_foreign_bytes_remain(self):
        foreign = bytearray(self.reviewed.raw)
        foreign[-1] ^= 1
        self._replace_when_receipt_finishes(self.output / 'DW6_NA.dat', bytes(foreign))
        self.assertEqual(self.source.read_bytes(), self.original_source)
        self.assertEqual(self.template.read_bytes(), self.original_template)

    def test_late_valid_con_replacement_is_refused_and_preserved(self):
        foreign = context_fixture('dw6_xbox360_na', seed=7)
        self._replace_when_receipt_finishes(self.output / 'ORIGINAL.CON', foreign)
        self.assertEqual(self.source.read_bytes(), self.original_source)
        self.assertEqual((self.template.parent / 'ORIGINAL.CON').read_bytes(), self.original_context)

    def test_late_oversized_receipt_replacement_is_refused_and_preserved(self):
        foreign = b'Another application replaced this receipt.\n' + bytes(2 * 1024 * 1024)
        self._replace_when_receipt_finishes(self.output / 'conversion.json', foreign)
        self.assertEqual(self.source.read_bytes(), self.original_source)
        self.assertEqual(self.template.read_bytes(), self.original_template)

    def test_late_source_replacement_is_rechecked_before_success(self):
        self._replace_when_receipt_finishes(self.source, fixture('dw6', 2))
        self.assertEqual(self.template.read_bytes(), self.original_template)

    def test_late_original_con_replacement_is_rechecked_before_success(self):
        foreign = context_fixture('dw6_xbox360_na', seed=8)
        self._replace_when_receipt_finishes(self.template.parent / 'ORIGINAL.CON', foreign)
        self.assertEqual(self.source.read_bytes(), self.original_source)

    def test_failed_export_cannot_delete_a_replacement_between_read_and_unlink(self):
        destination = self.output / 'DW6_NA.dat'
        foreign = b'Another application replaced the raw export after the cleanup read.'
        original_atomic, original_read_bytes = c.atomic_new, Path.read_bytes
        replacement_window = []

        def fail_receipt(data, path):
            if Path(path).name == 'conversion.json':
                raise SaveError('Injected receipt creation failure.')
            return original_atomic(data, path)

        def replace_after_read(path):
            data = original_read_bytes(path)
            if path.resolve() == destination.resolve():
                path.write_bytes(foreign)
                replacement_window.append(path)
            return data

        # The former cleanup read our bytes, then deleted a foreign replacement
        # introduced here before unlink. Retention performs no such cleanup read.
        with mock.patch.object(c, 'atomic_new', side_effect=fail_receipt):
            with mock.patch.object(Path, 'read_bytes', new=replace_after_read):
                with self.assertRaisesRegex(SaveError, 'retained'):
                    c.export(self.reviewed, self.output)
        self.assertTrue(destination.is_file())
        self.assertEqual(destination.read_bytes(), foreign if replacement_window else self.reviewed.raw)
        self.assertEqual((self.output / 'ORIGINAL.CON').read_bytes(), self.original_context)
        self.assertFalse((self.output / 'conversion.json').exists())

    def test_completed_review_rejects_companion_different_from_document_digest(self):
        reverse = c.prepare('dw6_xbox360_na-to-dw6-records', self.template, self.source)
        for reviewed, field in ((self.reviewed, 'template'), (reverse, 'source')):
            with self.subTest(snapshot=field):
                snapshot = getattr(reviewed, field)
                forged = replace(reviewed, **{field: replace(snapshot, companion_raw=context_fixture('dw6_xbox360_na', seed=9))})
                with self.assertRaisesRegex(SaveError, 'context'):
                    c.validate_review_snapshot(forged)


if __name__ == '__main__':
    unittest.main()
