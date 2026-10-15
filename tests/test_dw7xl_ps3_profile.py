"""Exact original XL PS3 framing, mandatory context and copied-snapshot safety."""
from dataclasses import replace
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw7xl_ps3 import parser as backend
from koei_editor.shared import ps3_copy
from tests import test_ps3_expansion as ps3_context


@lru_cache(maxsize=2)
def profile_fixture(salt=0):
    """Procedural plaintext, independently bounded; not a genuine game fixture."""
    raw = bytearray((index * 37 + salt * 59) & 255 for index in range(470303))
    raw[:4] = bytes.fromhex('11080200')
    return bytes(raw)


def write_copy(folder, directory='BLUS30873-SAVEDATA', salt=0):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'APP.BIN'
    path.write_bytes(profile_fixture(salt))
    (folder / 'PARAM.SFO').write_bytes(ps3_context.PS3ContextTests.metadata(directory))
    return path


class DW7XLPS3ProfileTests(unittest.TestCase):
    def test_exact_xl_framing_refuses_base_pc_encrypted_padding_and_other_revisions(self):
        raw = profile_fixture()
        document = backend.decode(raw)
        self.assertEqual(backend.serialize(document, {}), raw)
        self.assertEqual(document.payload, raw)
        self.assertEqual(document.sha256, hashlib.sha256(raw).hexdigest())
        base = bytes.fromhex('11011200') + bytes(453560)
        wrong_pc_payload = bytes.fromhex('00020811') + raw[4:]
        for foreign in (base, wrong_pc_payload, raw[:-1], raw + b'\0', raw + bytes(4),
                        bytes(len(raw)), bytearray(raw), memoryview(raw)):
            with self.subTest(length=len(foreign)), self.assertRaises(SaveError):
                backend.decode(foreign)
        for game_id in (None, '', 'dw7_ps3', 'dw7xl', 'dw7e_ps3', 'dw8xl_ps3'):
            with self.subTest(game_id=game_id), self.assertRaises(SaveError):
                backend.decode(raw, game_id)
            with patch.object(Path, 'open') as opened, self.assertRaises(SaveError):
                backend.read_save(Path('missing.bin'), game_id)
            opened.assert_not_called()

    def test_frozen_snapshot_identity_payload_source_and_empty_only_serialization(self):
        raw = profile_fixture()
        document = backend.decode(raw)
        for fake in (None, object(), replace(document, format=backend.Format()),
                     replace(document, raw=bytearray(raw)), replace(document, payload=bytearray(raw)),
                     replace(document, payload=profile_fixture(1)),
                     replace(document, raw=raw[:-1], payload=raw[:-1]),
                     replace(document, source='APP.BIN'), replace(document, context_digest=None)):
            with self.subTest(type=type(fake).__name__), self.assertRaises(SaveError):
                backend.validate_document(fake)
        for changes in (None, [], (), {'gold': 123}, {'officer_0_health': 1000}):
            with self.subTest(changes=changes), self.assertRaises(SaveError):
                backend.serialize(document, changes)
        self.assertFalse(hasattr(backend, 'fields_for'))

    def test_both_native_regional_contexts_are_required_exact_and_fully_bound(self):
        for directory in ('BLUS30873-SAVEDATA', 'BLES01496-SAVEDATA'):
            with self.subTest(directory=directory), tempfile.TemporaryDirectory() as temporary:
                path = write_copy(Path(temporary), directory)
                document = backend.read_save(path)
                original_context = (path.parent / 'PARAM.SFO').read_bytes()
                self.assertEqual(document.context_digest, hashlib.sha256(original_context).hexdigest())
                self.assertEqual(backend.context_raw(path), original_context)
                self.assertEqual(backend.serialize(document, {}), path.read_bytes())
                for foreign in ('BLUS30690-SAVEDATA', 'BLES01149-SAVEDATA',
                                'BLUS31123-SAVEDATA', 'BLUS30873', 'BLUS30873-SAVEDATA-1',
                                'BLJM61000-SAVEDATA'):
                    (path.parent / 'PARAM.SFO').write_bytes(ps3_context.PS3ContextTests.metadata(foreign))
                    with self.subTest(foreign=foreign), self.assertRaises(SaveError):
                        backend.read_save(path)
                metadata_path = path.parent / 'PARAM.SFO'
                metadata_path.unlink()
                with self.assertRaises(SaveError):
                    backend.read_save(path)
                metadata_path.write_bytes(original_context + bytes(4097))
                with self.assertRaises(SaveError):
                    backend.read_save(path)
                metadata_path.write_bytes(original_context)
                with self.assertRaises(SaveError):
                    backend.read_save(path.with_suffix('.dat'))

    def test_metadata_drift_while_opening_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = write_copy(Path(temporary))
            original_decode = backend.decode

            def change_metadata(*args, **kwargs):
                document = original_decode(*args, **kwargs)
                metadata = path.parent / 'PARAM.SFO'
                metadata.write_bytes(metadata.read_bytes() + b'changed opaque metadata')
                return document

            with patch.object(backend, 'decode', side_effect=change_metadata), self.assertRaises(SaveError):
                backend.read_save(path)

    def test_backups_bind_snapshot_context_recheck_races_and_retain_completed_bytes(self):
        for changed in ('source', 'context'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as temporary:
                path = write_copy(Path(temporary))
                document = backend.read_save(path)
                original_context = (path.parent / 'PARAM.SFO').read_bytes()
                snapshot = backend.backup(document)
                self.assertEqual(snapshot.read_bytes(), document.raw)
                manifest = json.loads(snapshot.with_name(snapshot.name + '.context.json').read_bytes())
                self.assertEqual(manifest['context_sha256'], hashlib.sha256(original_context).hexdigest())
                self.assertEqual(manifest['save_sha256'], document.sha256)
                real_snapshot = ps3_copy.snapshot_backup

                def mutate(*args, **kwargs):
                    result = real_snapshot(*args, **kwargs)
                    if changed == 'source':
                        path.write_bytes(profile_fixture(1))
                    else:
                        (path.parent / 'PARAM.SFO').write_bytes(original_context + b'changed opaque metadata')
                    return result

                with patch.object(ps3_copy, 'snapshot_backup', side_effect=mutate), self.assertRaises(SaveError):
                    backend.backup(document)
                self.assertEqual(snapshot.read_bytes(), document.raw)
                backups = tuple((path.parent / 'UniversalEditorBackups').glob('*.BIN'))
                self.assertEqual(len(backups), 2)
                self.assertTrue(all(item.read_bytes() == document.raw for item in backups))
                with self.assertRaises(SaveError):
                    backend.backup(document)

    def test_native_copied_xl_exports_when_supplied(self):
        value = os.environ.get('DW7XL_PS3_SAVE_COPIES')
        if not value:
            self.skipTest('Set DW7XL_PS3_SAVE_COPIES to decrypted XL APP.BIN copies with original PARAM.SFO.')
        paths = tuple(Path(item) for item in value.split(os.pathsep) if item)
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(reference=path.parent.name):
                original = path.read_bytes()
                context = (path.parent / 'PARAM.SFO').read_bytes()
                document = backend.read_save(path)
                self.assertEqual(backend.serialize(document, {}), original)
                self.assertEqual(document.context_digest, hashlib.sha256(context).hexdigest())
                with tempfile.TemporaryDirectory() as temporary:
                    copy = Path(temporary) / 'APP.BIN'
                    copy.write_bytes(original)
                    (copy.parent / 'PARAM.SFO').write_bytes(context)
                    snapshot = backend.backup(backend.read_save(copy))
                    self.assertEqual(snapshot.read_bytes(), original)
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual((path.parent / 'PARAM.SFO').read_bytes(), context)


if __name__ == '__main__':
    unittest.main()
