"""Own-title format, bound scalar and original-context copy regressions.

All public fixtures are generated. Optional native exports remain outside Git.
"""
from dataclasses import replace
from functools import lru_cache
import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.game_registry import get_game
from koei_editor.games.deception4_ps3 import parser as deception
from koei_editor.games.escha_logy_ps3 import parser as escha
from koei_editor.games.ar_tonelico_qoga_ps3 import parser as qoga
from koei_editor.games.dw3.models import SaveError
from tests.scalar_contract import ScalarContractTests
from tests.test_ps3_expansion import PS3ContextTests

PROFILES = ((deception, 'NPUB31442-GAMEDATA-10', 'DATA.BIN', 'DECEPTION4_PS3_NATIVE_DIR'),
            (escha, 'NPEB01945-LIST-25', 'USR-DATA', 'ESCHA_LOGY_PS3_NATIVE_DIR'),
            (qoga, 'BLUS30639-LIST-08', 'USR-DATA', 'QOGA_PS3_NATIVE_DIR'))


@lru_cache(maxsize=3)
def fixture(backend):
    raw = bytearray(bytes(range(256)) * (backend.SAVE_SIZE // 256))
    raw[:8] = backend.HEADER
    for field in backend.FIELDS:
        raw[field.offset:field.offset + field.size] = (137).to_bytes(field.size, field.byteorder)
    return bytes(raw)


class ContextContract(ScalarContractTests):
    def fixture_bytes(self):
        (self.folder / 'PARAM.SFO').write_bytes(PS3ContextTests.metadata(self.directory))
        return fixture(self.backend)


class DeceptionContract(ContextContract, unittest.TestCase):
    game_id, backend, directory = deception.GAME_ID, deception, PROFILES[0][1]


class EschaContract(ContextContract, unittest.TestCase):
    game_id, backend, directory = escha.GAME_ID, escha, PROFILES[1][1]


class QogaContract(ContextContract, unittest.TestCase):
    game_id, backend, directory = qoga.GAME_ID, qoga, PROFILES[2][1]


class PS3NewFamilySafetyTests(unittest.TestCase):
    def test_each_own_title_endianness_boundaries_and_entire_unknown_tail(self):
        for backend, _, _, _ in PROFILES:
            with self.subTest(game=backend.GAME_ID):
                raw = fixture(backend); doc = backend.decode(raw)
                field = backend.FIELDS[0]
                self.assertEqual(backend.serialize(doc, {}), raw)
                for value in (0, 0x10203, field.maximum):
                    output = backend.serialize(doc, {field.id: value})
                    self.assertEqual(output[field.offset:field.offset + 4], value.to_bytes(4, field.byteorder))
                    self.assertEqual(output[:field.offset], raw[:field.offset])
                    self.assertEqual(output[field.offset + 4:], raw[field.offset + 4:])
                self.assertEqual(backend.maximums(doc, {field.id: 1}), {field.id: 1})
                self.assertEqual(backend.limit_values(doc, {}, [field.id]), {})
                self.assertFalse(field.maxable)
                self.assertFalse(backend.FORMAT.game_load_verified)
                for value in (True, -1, field.maximum + 1, '7', 1.0):
                    with self.assertRaises(SaveError): backend.stage(doc, {}, field.id, value)

    def test_wrong_profile_size_encrypted_mutable_and_forged_snapshot_rejected(self):
        for backend, _, _, _ in PROFILES:
            doc = backend.decode(fixture(backend))
            for bad in (b'', doc.raw[:-1], doc.raw + b'\0', bytes(backend.SAVE_SIZE), bytearray(doc.raw)):
                with self.subTest(game=backend.GAME_ID), self.assertRaises(SaveError): backend.decode(bad)
            for forged in (replace(doc, raw=bytearray(doc.raw)), replace(doc, payload=memoryview(doc.raw)),
                           replace(doc, source=None), replace(doc, context_digest=None),
                           replace(doc, format=replace(doc.format))):
                with self.assertRaises(SaveError): backend.serialize(forged, {})
            for changes in (None, [], {'__unknown__': 0}, {backend.FIELDS[0].id: True}):
                with self.assertRaises(SaveError): backend.serialize(doc, changes)
            for other, _, _, _ in PROFILES:
                if other is not backend:
                    with self.assertRaises(SaveError): backend.decode(fixture(other))

    def test_encoding_ceiling_is_scoped_and_higher_original_unstages(self):
        for backend, _, _, _ in PROFILES:
            field = backend.FIELDS[0]
            ordinary = get_game(backend.GAME_ID).get_scalar_adapter()
            experimental = get_game(backend.GAME_ID).get_scalar_adapter(experimental=True)
            doc = ordinary.decode(fixture(backend))
            pending = experimental.stage(doc, {}, field.id, 0xFFFFFFFF)
            encoded = experimental.serialize(doc, pending)
            self.assertEqual(field.value(experimental.decode(encoded).payload), 0xFFFFFFFF)
            with self.assertRaises(SaveError): ordinary.serialize(doc, pending)
            for value in (0x100000000, -1, True):
                with self.assertRaises(SaveError): experimental.stage(doc, {}, field.id, value)
            higher = ordinary.decode(encoded)
            self.assertEqual(ordinary.serialize(higher, {}), encoded)
            self.assertEqual(ordinary.stage(higher, {field.id: 1}, field.id, 0xFFFFFFFF), {})
            self.assertEqual(ordinary.maximums(higher, {}), {})

    def test_full_context_binding_wrong_slot_missing_changed_and_restore_alias(self):
        for backend, directory, filename, _ in PROFILES:
            with self.subTest(game=backend.GAME_ID), tempfile.TemporaryDirectory() as folder:
                root = Path(folder); source = root / filename; source.write_bytes(fixture(backend))
                metadata = root / 'PARAM.SFO'
                with self.assertRaises(SaveError): backend.read_save(source)
                for bad in ('BLUS99999-LIST-01', directory + '0', directory[:-2] + 'XX'):
                    metadata.write_bytes(PS3ContextTests.metadata(bad))
                    with self.assertRaises(SaveError): backend.read_save(source)
                original = PS3ContextTests.metadata(directory); metadata.write_bytes(original)
                doc = backend.read_save(source); backup = backend.backup(doc)
                field = backend.FIELDS[0]
                result = backend.save_as(doc, {field.id: 71}, root / ('edited' + source.suffix))
                self.assertEqual(field.value(result.payload), 71)
                self.assertEqual(source.read_bytes(), doc.raw)
                self.assertEqual(backend.restore(backup, root / ('restored' + source.suffix)).read_bytes(), doc.raw)
                with self.assertRaises(FileExistsError): backend.restore(backup, source)
                metadata.write_bytes(original + b'opaque changed')
                with self.assertRaises(SaveError): backend.backup(doc)
                with self.assertRaises(SaveError): backend.restore(backup, root / ('stale' + source.suffix))
                self.assertFalse((root / ('stale' + source.suffix)).exists())

    def test_metadata_and_source_changed_mid_serialize_prevent_destination(self):
        for backend, directory, filename, _ in PROFILES:
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder); source = root / filename; source.write_bytes(fixture(backend))
                metadata = root / 'PARAM.SFO'; original = PS3ContextTests.metadata(directory); metadata.write_bytes(original)
                doc = backend.read_save(source)
                method = backend._backend.serialize
                for kind in ('metadata', 'source'):
                    def altered(document, changes):
                        raw = method(document, changes)
                        if kind == 'metadata': metadata.write_bytes(original + b'opaque changed')
                        else: source.write_bytes(raw[:-1])
                        return raw
                    destination = root / (kind + source.suffix)
                    with patch.object(backend._backend.storage, 'serialize', side_effect=altered), self.assertRaises(SaveError):
                        backend.save_as(doc, {backend.FIELDS[0].id: 1}, destination)
                    self.assertFalse(destination.exists())
                    metadata.write_bytes(original); source.write_bytes(doc.raw)

    def test_actual_tk_open_inspection_review_undo_copy_and_restore(self):
        try: root = tk.Tk()
        except tk.TclError as error: self.skipTest(str(error))
        self.addCleanup(root.destroy); root.withdraw()
        for backend, directory, filename, _ in PROFILES:
            with self.subTest(game=backend.GAME_ID), tempfile.TemporaryDirectory() as folder:
                path = Path(folder); source = path / filename; source.write_bytes(fixture(backend))
                (path / 'PARAM.SFO').write_bytes(PS3ContextTests.metadata(directory))
                errors=[]
                with patch('koei_editor.shared.verified_gui.messagebox.showerror', side_effect=lambda *a: errors.append(a)), \
                        patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                    host = tk.Frame(root); host.pack()
                    editor = get_game(backend.GAME_ID).create_editor(root, host)
                    self.addCleanup(host.destroy)
                    editor.open(); self.assertFalse(errors)
                    field = backend.FIELDS[0]; editor.fields.selection_set(field.id); editor.value.set('31')
                    editor.apply_selected(); self.assertEqual(editor.changes, {field.id: 31})
                    editor.max_visible(); self.assertEqual(editor.changes, {field.id: 31})
                    editor.review(); editor.undo(); self.assertEqual(editor.changes, {})
                    editor.fields.selection_set(field.id); editor.value.set('31'); editor.apply_selected()
                    editor.show_inspector(); self.assertTrue(backend.inspection_rows(editor.document))
                    editor.save_to(path / ('edited' + source.suffix)); self.assertFalse(errors)
                    self.assertEqual(field.value(editor.document.payload), 31)
                    self.assertEqual(source.read_bytes(), fixture(backend))
                    self.assertEqual(backend.restore(editor.backup, path / ('restored' + source.suffix)).read_bytes(), fixture(backend))

    def test_optional_independent_complete_native_exports(self):
        found = False
        for backend, _, filename, variable in PROFILES:
            if not os.environ.get(variable): continue
            files = list(Path(os.environ[variable]).rglob(filename))
            self.assertTrue(files, 'No copied native gameplay files in the selected directory')
            found = True
            for source in files:
                with tempfile.TemporaryDirectory() as folder:
                    root=Path(folder); raw=source.read_bytes(); copied=root / filename; copied.write_bytes(raw)
                    (root / 'PARAM.SFO').write_bytes((source.parent / 'PARAM.SFO').read_bytes())
                    adapter=get_game(backend.GAME_ID).get_scalar_adapter(); doc=adapter.read_save(copied)
                    self.assertEqual(adapter.serialize(doc, {}), raw)
                    field=backend.FIELDS[0]
                    destination=adapter.save_as(doc, {field.id: 19}, root / ('edited' + copied.suffix))
                    self.assertEqual(field.value(destination.payload), 19)
                    self.assertEqual(copied.read_bytes(), raw)
                    self.assertEqual(adapter.restore(adapter.backup(doc), root / ('restored' + copied.suffix)).read_bytes(), raw)
        if not found: self.skipTest('No independent private PFD-decrypted exports selected')
