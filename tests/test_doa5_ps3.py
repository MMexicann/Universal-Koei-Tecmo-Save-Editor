"""Generated DOA5 codec checks plus optional independently acquired native copies."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.doa5_ps3 import codec, parser
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from tests.scalar_contract import ScalarContractTests
from koei_editor.games.dw3.models import SaveError


def plaintext_fixture():
    """Procedural opaque bytes only; this is not a playable console save."""
    raw = bytearray((index * 17 + 103) & 255 for index in range(codec.SAVE_SIZE))
    for index, (offset, size) in enumerate(codec.BLOCKS):
        struct.pack_into('>4I', raw, offset, 0, size, 0, 0x1946AB73 + index)
    raw[16:32] = codec.REVISION_PREFIX
    return bytes(raw)


class DOA5CodecTests(unittest.TestCase):
    def test_both_native_blocks_preserve_original_seeds_and_noop(self):
        raw = codec.encode(plaintext_fixture())
        clear = codec.decode(raw)
        self.assertEqual(codec.encode(clear), raw)
        for offset, size in codec.BLOCKS:
            self.assertEqual(raw[offset:offset + 8], plaintext_fixture()[offset:offset + 8])
            self.assertEqual(raw[offset + 12:offset + 16], plaintext_fixture()[offset + 12:offset + 16])
            self.assertEqual(int.from_bytes(raw[offset + 8:offset + 12], 'big'),
                             sum(raw[offset + 16:offset + size]))
        changed = bytearray(clear)
        changed[0x30F] ^= 1
        sealed = codec.encode(bytes(changed))
        reopened = codec.decode(sealed)
        allowed = {0x30F} | set(range(8, 12))
        self.assertLessEqual({i for i, (left, right) in enumerate(zip(clear, reopened)) if left != right}, allowed)
        self.assertEqual(sealed[0x1548:], raw[0x1548:])

    def test_no_automatic_repair_or_platform_guessing(self):
        raw = codec.encode(plaintext_fixture())
        for invalid in (bytearray(raw), raw[:-1], raw + b'\0', bytes(len(raw))):
            with self.assertRaises(SaveError):
                codec.decode(invalid)
        for offset, size in codec.BLOCKS:
            for position in (offset, offset + 4, offset + 8,
                             offset + 16, offset + size - 1):
                changed = bytearray(raw)
                changed[position] ^= 1
                with self.assertRaises(SaveError):
                    codec.decode(bytes(changed))
        changed = bytearray(raw)
        changed[12] ^= 1
        with self.assertRaises(SaveError):
            codec.decode(bytes(changed))
        # Native sums cover encrypted bodies, not seed header words. The first
        # seed also has a decoded revision check; block two's opaque body has
        # no independently proved header integrity. Original seeds are preserved.
        changed = bytearray(plaintext_fixture())
        changed[16] ^= 1
        with self.assertRaises(SaveError):
            codec.encode(bytes(changed))
        # A checksum-correct foreign fingerprint must still be rejected.
        changed = bytearray(raw)
        changed[16] ^= 1
        struct.pack_into('>I', changed, 8, sum(changed[16:0x1548]))
        with self.assertRaises(SaveError):
            codec.decode(bytes(changed))

    def test_native_reference_pairs_and_independent_exports_when_provided(self):
        supplied = os.environ.get('DOA5_PS3_NATIVE_DIR')
        if not supplied:
            self.skipTest('Independent native PS3 DOA5 exports are not configured.')
        root = Path(supplied)
        for title in ('NPUB30893', 'NPEB01129', 'NPJB00242'):
            raw = (root / title / 'SAVE_SYS.DAT.decrypted').read_bytes()
            expected = (root / title / 'SAVE_SYS.DAT.native.dec').read_bytes()
            self.assertEqual(codec.decode(raw), expected)
            self.assertEqual(codec.encode(expected), raw)
        self.assertEqual(codec.decode((root / 'SAVE_SYS.DAT.PS3.enc').read_bytes()),
                         (root / 'SAVE_SYS.DAT.PS3.dec').read_bytes())
        for other in ('SAVE_SYS.DAT.vita.enc', 'SAVESYS.DAT.enc'):
            with self.assertRaises(SaveError):
                codec.decode((root / other).read_bytes())


def metadata(directory=parser.DIRECTORIES[0], extra=b''):
    key = b'SAVEDATA_DIRECTORY\0'
    value = directory.encode('ascii') + b'\0'
    return (struct.pack('<5I', 0x46535000, 0x101, 36, 36 + len(key), 1)
            + struct.pack('<HH3I', 0, 0x204, len(value), len(value), 0) + key + value + extra)


def fixture():
    clear = bytearray(plaintext_fixture())
    for field in parser.FIELDS:
        clear[field.offset] = 0
    return codec.encode(bytes(clear))


def write_context(folder, raw=None):
    path = Path(folder) / 'PARAM.SFO'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(metadata() if raw is None else raw)
    return path


class DOA5ContractTests(ScalarContractTests, unittest.TestCase):
    game_id = parser.GAME_ID
    payload_integrity_offsets = frozenset(range(8, 12))

    def fixture_bytes(self):
        return fixture()

    def setUp(self):
        from types import SimpleNamespace
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.game = SimpleNamespace(extension='.dat')
        self.adapter = BoundScalarAdapter(parser.GAME_ID, '.dat', parser)
        self.raw = fixture()
        self.source = self.folder / 'input-copy.dat'
        self.source.write_bytes(self.raw)
        write_context(self.folder)
        self.document = self.adapter.read_save(self.source)


class DOA5EditorTests(unittest.TestCase):
    def test_each_source_backed_flag_is_surgical_and_unstage_is_safe(self):
        doc = parser.decode(fixture())
        self.assertEqual(len(parser.fields_for(doc)), 63)
        for field in parser.fields_for(doc):
            pending = parser.stage(doc, {}, field.id, 1)
            self.assertEqual(parser.stage(doc, pending, field.id, 0), {})
            encoded = parser.serialize(doc, pending)
            reopened = parser.decode(encoded)
            self.assertEqual(reopened.payload, parser.changed_payload(doc, pending))
            self.assertEqual(reopened.payload[field.offset], 1)
            allowed = set(range(8, 12)) | {field.offset}
            self.assertLessEqual({i for i,(a,b) in enumerate(zip(doc.payload,reopened.payload)) if a!=b}, allowed)
            self.assertLessEqual({i for i,(a,b) in enumerate(zip(doc.raw,encoded)) if a!=b}, allowed)
            self.assertEqual(encoded[0x1548:], doc.raw[0x1548:])
        self.assertEqual(parser.maximums(doc, {}), {})
        self.assertEqual(parser.limit_values(doc, {}, [f.id for f in parser.FIELDS]), {})
        self.assertFalse(any(f.maxable for f in parser.FIELDS))
        for protected in ('title_04fb', 'story_0753', 'character_0', 'costume_03e0'):
            with self.assertRaises(SaveError):
                parser.stage(doc, {}, protected, 1)

    def test_unlocked_unknown_states_and_immutable_original_cannot_be_bypassed(self):
        clear = bytearray(codec.decode(fixture()))
        clear[parser.FIELDS[0].offset] = 1
        clear[parser.FIELDS[1].offset] = 2
        doc = parser.decode(codec.encode(bytes(clear)))
        first, second = parser.FIELDS[:2]
        self.assertEqual(parser.stage(doc, {}, first.id, 1), {})
        for changes in ({first.id: 0}, {second.id: 1}, {second.id: 0}):
            for operation in (parser.changed_payload, parser.serialize, parser.review, parser.maximums):
                with self.assertRaises(SaveError):
                    operation(doc, changes)
        for value in (True, False, '1', 2, -1, None):
            with self.assertRaises(SaveError):
                parser.stage(doc, {}, parser.FIELDS[2].id, value)
        for forged in (replace(doc, payload=doc.payload[:-1]),
                       replace(doc, raw=bytearray(doc.raw)),
                       replace(doc, format=replace(parser.FORMAT, id='doa5_vita')),
                       replace(doc, context_sha256='f'*64),
                       replace(doc, context_sha256='bad', native_directory=parser.DIRECTORIES[0])):
            with self.assertRaises(SaveError):
                parser.serialize(forged, {})
        self.assertEqual(parser.serialize(doc, {}), doc.raw)
        self.assertEqual(dict(parser.field_map(doc))[first.id].value(doc.payload), 1)
        self.assertNotIn(second.id, parser.field_map(doc))

    def test_original_metadata_destination_backup_restore_and_source_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'SAVE_SYS.DAT'
            source.write_bytes(fixture())
            companion = write_context(folder, metadata(extra=b'original opaque owner context'))
            doc = parser.read_save(source)
            edited = parser.save_as(doc, {parser.FIELDS[0].id: 1}, folder / 'edited.dat')
            self.assertEqual(edited.payload[parser.FIELDS[0].offset], 1)
            snapshot = parser.backup(doc)
            self.assertEqual(parser.restore(snapshot, folder / 'restored.dat').read_bytes(), fixture())
            other = folder / 'other';other.mkdir()
            write_context(other, companion.read_bytes())
            self.assertEqual(parser.save_as(doc, {}, other / 'copy.dat').raw, fixture())
            write_context(other, metadata(extra=b'different same-title context'))
            with self.assertRaises(SaveError):
                parser.save_as(doc, {}, other / 'wrong-context.dat')
            with self.assertRaises(SaveError):
                parser.restore(snapshot, other / 'wrong-restore.dat')
            self.assertFalse((other / 'wrong-context.dat').exists())
            original_sfo = companion.read_bytes()
            companion.write_bytes(metadata(directory='NPJB00242SYSTEM_SAVE'))
            with self.assertRaises(SaveError):parser.read_save(source)
            with self.assertRaises(SaveError):parser.save_as(doc, {}, folder / 'changed.dat')
            companion.write_bytes(original_sfo)
            damaged = bytearray(fixture());damaged[-1]^=1;source.write_bytes(damaged)
            with self.assertRaises(SaveError):parser.backup(doc)
            with self.assertRaises(SaveError):parser.save_as(doc, {}, folder / 'changed-source.dat')
            snapshot.write_bytes(damaged)
            manifest=json.loads(snapshot.with_suffix('.json').read_text())
            manifest['sha256']=hashlib.sha256(damaged).hexdigest()
            snapshot.with_suffix('.json').write_text(json.dumps(manifest))
            with self.assertRaises(SaveError):parser.restore(snapshot, folder / 'bad-restore.dat')
            self.assertFalse((folder / 'bad-restore.dat').exists())

    def test_minimal_identity_self_test_never_copies_original_owner_fields(self):
        from koei_editor.shared.verified_self_test import _run
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);source=folder/'SAVE_SYS.DAT';source.write_bytes(fixture())
            write_context(folder,metadata(extra=b'original-only owner fields'))
            adapter=BoundScalarAdapter(parser.GAME_ID,'.dat',parser)
            report=_run(adapter,parser.GAME_ID,source,folder/'self-test')
            self.assertTrue(report['success'])
            self.assertTrue(report['checksum_verified'])
            self.assertFalse(report['format_sample_verified'])
            self.assertFalse(report['native_integrity_verified'])
            self.assertFalse(report['in_game_load_tested'])
            self.assertEqual(report['fields_checked'],63)
            minimal=(folder/'self-test'/'PARAM.SFO').read_bytes()
            self.assertNotIn(b'original-only',minimal)
            self.assertEqual(struct.unpack_from('<I',minimal,16)[0],1)

    def test_independent_native_profiles_context_and_restore_when_provided(self):
        supplied=os.environ.get('DOA5_PS3_NATIVE_DIR')
        if not supplied:self.skipTest('Independent PS3 DOA5 native exports are not configured.')
        root=Path(supplied)
        for title in ('NPUB30893','NPEB01129'):
            raw=(root/title/'SAVE_SYS.DAT.decrypted').read_bytes()
            sfo=(root/title/'PARAM.SFO').read_bytes()
            with tempfile.TemporaryDirectory() as directory:
                folder=Path(directory);source=folder/'SAVE_SYS.DAT';source.write_bytes(raw);write_context(folder,sfo)
                doc=parser.read_save(source)
                self.assertEqual(parser.serialize(doc,{}),raw)
                self.assertEqual(len(parser.fields_for(doc)),63)
                for field in parser.fields_for(doc):
                    self.assertEqual(field.value(doc.payload),1)
                    with self.assertRaises(SaveError):parser.stage(doc,{},field.id,0)
                    # An explicitly labelled constructed derivative checks one
                    # native flag write without pretending it was game-generated.
                    clear=bytearray(doc.payload);clear[field.offset]=0
                    derivative=parser.decode(codec.encode(bytes(clear)))
                    self.assertEqual(parser.serialize(derivative,{field.id:1}),raw)
                self.assertEqual(parser.save_as(doc,{},folder/'edited.dat').raw,raw)
                backup=parser.backup(doc)
                self.assertEqual(parser.restore(backup,folder/'restored.dat').read_bytes(),raw)
                self.assertEqual(source.read_bytes(),raw)

    def test_actual_tk_open_search_undo_review_save_and_backup(self):
        try:
            import tkinter as tk
            root=tk.Tk()
        except Exception as error:self.skipTest('Tk display unavailable: '+type(error).__name__)
        self.addCleanup(root.destroy)
        from koei_editor.games.doa5_ps3.editor import Editor
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);source=folder/'SAVE_SYS.DAT';source.write_bytes(fixture());write_context(folder)
            editor=Editor(root,parent=root)
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename',return_value=str(source)):
                editor.open()
            root.update()
            self.assertEqual(len(editor.fields.get_children()),63)
            editor.search.set('Costume flag record 01');root.update()
            self.assertEqual(len(editor.fields.get_children()),1)
            editor.search.set('');root.update()
            changes={parser.FIELDS[0].id:1,parser.FIELDS[1].id:1}
            editor.stage_values(changes)
            self.assertEqual(len(parser.review(editor.document,editor.changes)),2)
            editor.undo();self.assertEqual(editor.changes,{})
            editor.stage_values(changes)
            children=set(root.winfo_children());editor.review();root.update()
            dialogs=[child for child in root.winfo_children()if child not in children and isinstance(child,tk.Toplevel)]
            self.assertEqual(len(dialogs),1);dialogs[0].destroy()
            destination=folder/'edited.dat'
            with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename',return_value=str(destination)):
                editor.save_as()
            edited=parser.read_save(destination)
            self.assertEqual(edited.payload[parser.FIELDS[0].offset],1)
            self.assertEqual(source.read_bytes(),fixture())
            self.assertTrue(list((folder/'UniversalEditorBackups').glob('*.context.json')))

    def test_actual_tk_independent_native_open_and_save_when_provided(self):
        supplied = os.environ.get('DOA5_PS3_NATIVE_DIR')
        if not supplied:
            self.skipTest('Independent native PS3 DOA5 exports are not configured.')
        try:
            import tkinter as tk
            root = tk.Tk()
        except Exception as error:
            self.skipTest('Tk display unavailable: ' + type(error).__name__)
        self.addCleanup(root.destroy)
        from koei_editor.games.doa5_ps3.editor import Editor
        original = Path(supplied) / 'NPUB30893'
        raw = (original / 'SAVE_SYS.DAT.decrypted').read_bytes()
        sfo = (original / 'PARAM.SFO').read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'SAVE_SYS.DAT'
            source.write_bytes(raw)
            write_context(folder, sfo)
            editor = Editor(root, parent=root)
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                editor.open()
            root.update()
            self.assertEqual(len(editor.fields.get_children()), 63)
            self.assertEqual(len(editor.presentation.inspection_tables(editor.document)[0].rows), 63)
            destination = folder / 'native-copy.dat'
            with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(destination)):
                editor.save_as()
            self.assertEqual(destination.read_bytes(), raw)
            self.assertEqual(source.read_bytes(), raw)
            snapshots = [path for path in (folder / 'UniversalEditorBackups').iterdir()
                         if path.suffix.lower() == '.dat']
            self.assertTrue(snapshots)
            self.assertEqual(parser.restore(snapshots[0], folder / 'native-restored.dat').read_bytes(), raw)
