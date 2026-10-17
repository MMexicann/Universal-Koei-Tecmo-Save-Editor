"""Independent safety audit using procedural bytes, never Switch load evidence."""
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.three_houses import parser as backend
from tests.test_three_houses import procedural_slot, sealed


class ThreeHousesAuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.source = self.folder / 'slot-copy'
        raw = bytearray(procedural_slot())
        # A source-comment-identified ordinary weapon, not an inferred catalog.
        struct.pack_into('<h', raw, 12, 131)
        struct.pack_into('<h', raw, 12 + 0x644, 131)
        self.raw = sealed(raw)
        self.source.write_bytes(self.raw)
        self.document = backend.read_save(self.source)

    def test_unknown_positive_item_identity_is_inspected_and_preserved_read_only(self):
        raw = bytearray(self.raw)
        for offset in (12, 12 + 0x644):
            struct.pack_into('<h', raw, offset, 32767)
        document = backend.decode(sealed(raw))
        for key in ('convoy:0:durability', 'convoy:0:quantity',
                    'character:0:item:0:durability'):
            with self.subTest(key=key):
                self.assertNotIn(key, backend.field_map(document))
                with self.assertRaises(SaveError):
                    backend.serialize(document, {key: 1})
        self.assertEqual(backend.serialize(document, {}), document.raw)
        edited = backend.serialize(document, {'gold': 11999})
        self.assertEqual(edited[12:16], document.raw[12:16])
        self.assertEqual(edited[12 + 0x644:12 + 0x648], document.raw[12 + 0x644:12 + 0x648])
        self.assertEqual(sum(row['id'] == 32767 for row in backend.items(document)), 2)

    def test_unknown_positive_character_identity_does_not_qualify_held_equipment(self):
        raw = bytearray(self.raw)
        struct.pack_into('<h', raw, 12 + 0x644 + 0x24, 32767)
        document = backend.decode(sealed(raw))
        self.assertNotIn('character:0:item:0:durability', backend.field_map(document))
        self.assertEqual(backend.serialize(document, {}), document.raw)
        with self.assertRaises(SaveError):
            backend.serialize(document, {'character:0:item:0:durability': 1})

    def test_max_preserves_pending_decrease_and_rejects_malformed_key_batches(self):
        pending = {'gold': 11999}
        self.assertEqual(backend.maximums(self.document, pending), pending)
        self.assertEqual(backend.limit_values(self.document, pending, ['gold']), {})
        self.assertEqual(pending, {'gold': 11999})
        for keys in (None, 7, 'gold', [['gold']], [True], ['gold', 'unknown']):
            with self.subTest(keys=keys), self.assertRaises(SaveError):
                backend.limit_values(self.document, pending, keys)

    def test_higher_finite_durability_cannot_become_unlimited_by_decreasing(self):
        raw = bytearray(self.raw)
        raw[14] = 254
        document = backend.decode(sealed(raw))
        key = 'convoy:0:durability'
        self.assertEqual(backend.stage(document, {key: 1}, key, 254), {})
        self.assertEqual(backend.serialize(document, {key: 254}), document.raw)
        with self.assertRaises(SaveError):
            backend.serialize(document, {key: 100})

    def test_restore_checks_native_integrity_even_with_matching_forged_manifest(self):
        backup = backend.backup(self.document)
        damaged = bytearray(backup.read_bytes())
        damaged[-1] ^= 1
        damaged = bytes(damaged)
        backup.write_bytes(damaged)
        manifest_path = backup.with_suffix('.json')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['sha256'] = hashlib.sha256(damaged).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        destination = self.folder / 'restore-rejected'
        with self.assertRaises(SaveError):
            backend.restore(backup, destination)
        self.assertFalse(destination.exists())
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_source_alias_and_changed_source_never_replace_or_write_destination(self):
        alias = self.folder / 'source-alias'
        try:
            alias.symlink_to(self.source)
        except OSError as error:
            self.skipTest(f'Symlink unavailable: {error}')
        with self.assertRaises(FileExistsError):
            backend.save_as(self.document, {'gold': 11999}, alias)
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.source.write_bytes(self.raw + b'\0')
        destination = self.folder / 'changed-source-rejected'
        with self.assertRaises(SaveError):
            backend.save_as(self.document, {'gold': 11999}, destination)
        self.assertFalse(destination.exists())

    @unittest.skipUnless(os.environ.get('THREE_HOUSES_REVIEW_COPIES'),
                         'Private reviewed native Three Houses copies absent')
    def test_private_reviewed_native_copies_unchanged_surgical_backup_and_restore(self):
        sources = [Path(value) for value in os.environ['THREE_HOUSES_REVIEW_COPIES'].split(os.pathsep) if value]
        self.assertTrue(sources, 'Provide copied native files separated by the platform path separator.')
        for index, source in enumerate(sources):
            raw = source.read_bytes()
            copy = self.folder / f'native-copy-{index}'
            copy.write_bytes(raw)
            document = backend.read_save(copy)
            self.assertEqual(backend.serialize(document, {}), raw)
            self.assertEqual(sealed(raw), raw)
            for field in backend.fields_for(document):
                original = field.value(document.payload)
                target = 'Editor' if field.kind == 'text' else max(field.minimum, original - 1)
                if field.group == 'Motivation':
                    target = 0 if original else 25
                elif field.group == 'Existing ability loadout':
                    target = 240
                if target in field.forbidden:
                    target -= 1
                encoded = backend.serialize(document, {field.id: target})
                self.assertEqual(sealed(encoded), encoded)
                self.assertEqual(field.value(backend.decode(encoded).payload), target)
                allowed = set(range(4)) | set(range(field.offset, field.offset + field.size))
                self.assertLessEqual({offset for offset, (before, after) in enumerate(zip(raw, encoded))
                                      if before != after}, allowed)
            backup = backend.backup(document)
            self.assertEqual(backup.read_bytes(), raw)
            restored = backend.restore(backup, self.folder / f'native-restored-{index}')
            self.assertEqual(restored.read_bytes(), raw)
            self.assertEqual(source.read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()
