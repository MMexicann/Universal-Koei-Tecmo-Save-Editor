"""Source-qualified SYSTEM tests; optional genuine STORY codec is not SYSTEM evidence."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.ninja_gaiden_black_xbox import codec, owner, parser
from koei_editor.research.ninja_gaiden_black_xbox import parser as story
from koei_editor.shared.adapter_contract import BoundScalarAdapter


def procedural(directory, payload=None):
    directory.mkdir(parents=True, exist_ok=True)
    protected = bytes(range(28))
    eeprom = bytearray(256)
    digest = owner._xhash(protected, owner.STATES[2])
    eeprom[:20] = digest
    eeprom[20:48] = owner._rc4(protected, owner._xhash(digest, owner.STATES[2]))
    (directory / 'eeprom.bin').write_bytes(eeprom)
    if payload is None:
        payload = bytearray(codec.SYSTEM_DECODED_SIZE)
        payload[:6] = codec.MARKER
        payload[27:41] = b'TeamNINJA 2003'
        struct.pack_into('<I', payload, parser.MAGIC, 0x20030730)
        struct.pack_into('<30I', payload, 46, *range(100, 130))
        payload[parser.COUNT] = 3
        payload[parser.ORDER:parser.ORDER + 30] = bytes([4, 1, 7] + [n for n in range(30) if n not in (4, 1, 7)])
        payload[42 + 0x1e5] = 7
    stream = codec.pack(bytes(payload), None)
    plain = stream + bytes(codec.SYSTEM_PLAIN_SIZE - len(stream) - 6) + codec.MARKER
    raw = bytes(20) + struct.pack('<I', 12345) + codec.transform(plain, 12345)
    raw = owner.signature(raw, protected[8:24]) + raw[20:]
    source = directory / 'system.dat'
    source.write_bytes(raw)
    return source


class NinjaGaidenBlackSystemTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.source = procedural(self.folder / 'original')
        self.document = parser.read_save(self.source)

    def test_published_provenance_and_exact_order_scope(self):
        self.assertFalse(parser.FORMAT.sample_verified)
        self.assertTrue(parser.FORMAT.published_format)
        self.assertFalse(parser.FORMAT.game_load_verified)
        original = self.document
        self.assertEqual(parser.serialize(original, {}), original.raw)
        changes = parser.stage(original, {}, 'numeric_slot_order', 1)
        self.assertEqual(parser.stage(original, changes, 'numeric_slot_order', 0), {})
        self.assertEqual(parser.maximums(original, changes), changes)
        self.assertEqual(parser.limit_values(original, changes, iter(['numeric_slot_order'])), {})
        result = parser.decode(parser.serialize(original, changes), source=self.source)
        self.assertEqual(result.payload[parser.COUNT:parser.ORDER + 30], bytes([30]) + bytes(range(30)))
        self.assertEqual(original.payload[:parser.COUNT], result.payload[:parser.COUNT])
        self.assertEqual(original.payload[parser.ORDER + 30:], result.payload[parser.ORDER + 30:])
        self.assertEqual(parser.serialize(result, {'numeric_slot_order': 1}), result.raw)
        with self.assertRaises(SaveError):
            parser.stage(result, {}, 'numeric_slot_order', 0)
        self.assertEqual(len(parser.inspection_rows(original)), 30)

    def test_true_cipher_range_reconstruction_and_residue(self):
        plain, payload, extent, counts = codec.decrypt(self.document.raw)
        stream = codec.pack(payload, counts)
        self.assertEqual(plain[:len(stream)], stream)
        self.assertEqual(codec.transform(plain, 12345), self.document.raw[24:])
        edited = parser.serialize(self.document, {'numeric_slot_order': 1})
        changed_plain, changed_payload, _, _ = codec.decrypt(edited)
        changed_stream = codec.pack(changed_payload, counts)
        self.assertEqual(changed_plain[len(changed_stream):], plain[len(changed_stream):])
        self.assertEqual(edited[20:24], self.document.raw[20:24])
        self.assertEqual(edited[:20], owner.signature(edited, self.document.context.key))
        self.assertLess(extent, codec.SYSTEM_PLAIN_SIZE)
        self.assertEqual(codec._Blowfish(bytes(8)).block(0, 0), (0x4ef99745, 0x6198dd78))
        self.assertEqual(owner._rc4(b'Plaintext', b'Key'), bytes.fromhex('bbf316e8d940af0ad3'))

    def test_sparse_table_and_unknown_order_tail_preserve_on_noop(self):
        payload = bytearray(self.document.payload)
        payload[parser.ORDER + 15] = 250  # Outside active entries: opaque native tail.
        source = procedural(self.folder / 'sparse', payload)
        original = parser.read_save(source)
        plain, decoded, _, counts = codec.decrypt(original.raw)
        full = codec.pack(decoded, counts)
        pairs = [(symbol, count) for symbol, count in enumerate(counts) if count]
        self.assertLessEqual(len(pairs), 127)
        sparse = bytes([len(pairs)]) + bytes(n for pair in pairs for n in pair) + full[257:]
        new_plain = sparse + plain[len(sparse):]
        raw = original.raw[:24] + codec.transform(new_plain, 12345)
        raw = owner.signature(raw, original.context.key) + raw[20:]
        source.write_bytes(raw)
        opened = parser.read_save(source)
        self.assertEqual(opened.payload, decoded)
        self.assertEqual(parser.serialize(opened, {}), raw)
        edited = parser.decode(parser.serialize(opened, {'numeric_slot_order': 1}), source=source)
        self.assertEqual(edited.payload[:parser.COUNT], decoded[:parser.COUNT])
        self.assertEqual(edited.payload[parser.ORDER + 30:], decoded[parser.ORDER + 30:])
        for invalid in [None, bytearray(raw), raw[:-1]]:
            with self.assertRaises(SaveError): codec.decrypt(invalid)
        for invalid_counts in [(), (0,) * 256, [1] * 256, (300,) * 256]:
            with self.assertRaises(SaveError): codec.pack(decoded, invalid_counts)

    def test_source_format_structure_rejections(self):
        raw = self.document.raw
        for malformed in [raw[:-1], raw + b'X', bytearray(raw), bytes(len(raw)),
                          raw[:700] + bytes([raw[700] ^ 1]) + raw[701:]]:
            with self.assertRaises(SaveError):
                parser.decode(malformed, source=self.source)
        for offset, value in [(parser.COUNT, 31), (parser.ORDER, 30), (parser.ORDER + 1, 4), (parser.MAGIC, 1)]:
            payload = bytearray(self.document.payload)
            payload[offset] = value
            bad = procedural(self.folder / f'bad-{offset}', payload)
            with self.assertRaises(SaveError):
                parser.read_save(bad)
        for key, value in [('karma_score', 1), ('frames', 0), ('numeric_slot_order', True),
                           ('numeric_slot_order', -1), ('numeric_slot_order', 2), ([], 1)]:
            with self.assertRaises(SaveError):
                parser.stage(self.document, {}, key, value)
        for keys in [None, [['numeric_slot_order']], ['karma_score']]:
            with self.assertRaises(SaveError):
                parser.limit_values(self.document, {}, keys)

    def test_malformed_immutable_snapshot_and_context_fail_closed(self):
        doc, ctx = self.document, self.document.context
        for badctx in [None, replace(ctx, key=None), replace(ctx, key=b''),
                       replace(ctx, eeprom=None), replace(ctx, directory='bad'),
                       replace(ctx, metadata=None), replace(ctx, basename='../eeprom.bin')]:
            with self.assertRaises(SaveError):
                parser.serialize(replace(doc, context=badctx), {})
        for bad in [replace(doc, source=None), replace(doc, source=Path('relative.dat')),
                    replace(doc, raw=bytearray(doc.raw)), replace(doc, payload=doc.payload[:-1]),
                    replace(doc, format=replace(doc.format))]:
            with self.assertRaises(SaveError):
                parser.serialize(bad, {})
        for raw in [None, bytearray(doc.raw)]:
            with self.assertRaises(SaveError):
                owner.signature(raw, ctx.key)
        self.assertNotIn(ctx.key.hex(), repr(ctx))
        self.assertNotIn(ctx.key.hex(), repr(doc))
        self.assertNotIn(str(doc.source), repr(doc))

    def test_storage_adapter_original_context_and_exact_restore(self):
        adapter = BoundScalarAdapter(parser.GAME_ID, '.dat', parser)
        doc = adapter.read_save(self.source)
        self.assertEqual(adapter.decode(doc.raw, source=self.source).payload, doc.payload)
        target = self.folder / 'private-output' / 'edited.dat'
        parser.prepare_self_test_copy(doc, target)
        result = adapter.save_as(doc, adapter.stage(doc, {}, 'numeric_slot_order', 1), target)
        self.assertEqual(parser.SORT.value(result.payload), 1)
        snapshot = adapter.backup(doc)
        restored = target.with_name('restored.dat')
        adapter.restore(snapshot, restored)
        self.assertEqual(restored.read_bytes(), doc.raw)
        self.assertEqual(self.source.read_bytes(), doc.raw)
        binding = json.loads(snapshot.with_name(snapshot.name + '.context.json').read_text())
        self.assertNotIn(doc.context.key.hex(), json.dumps(binding))
        with self.assertRaises(FileExistsError):
            adapter.save_as(doc, {}, target)
        with self.assertRaises(FileExistsError):
            adapter.restore(snapshot, restored)
        damaged = bytearray(snapshot.read_bytes()); damaged[500] ^= 1
        snapshot.write_bytes(damaged)
        manifest = json.loads(snapshot.with_suffix('.json').read_text())
        manifest['sha256'] = hashlib.sha256(damaged).hexdigest()
        snapshot.with_suffix('.json').write_text(json.dumps(manifest))
        binding['native_sha256'] = manifest['sha256']
        snapshot.with_name(snapshot.name + '.context.json').write_text(json.dumps(binding))
        with self.assertRaises(SaveError):
            adapter.restore(snapshot, target.with_name('damaged.dat'))

    def test_original_source_owner_alias_and_race_guards(self):
        doc = self.document
        for name in ['system.dat', 'eeprom.bin']:
            path = self.source.parent / name; original = path.read_bytes()
            path.write_bytes(original + b'X')
            with self.assertRaises(SaveError): parser.backup(doc)
            with self.assertRaises(SaveError): parser.save_as(doc, {}, self.source.parent / 'blocked.dat')
            path.write_bytes(original)
        backup = parser.backup
        def race(document):
            snapshot = backup(document); self.source.unlink(); return snapshot
        with patch.object(parser, 'backup', side_effect=race):
            with self.assertRaises(SaveError): parser.save_as(doc, {'numeric_slot_order': 1}, self.source.parent / 'race.dat')
        self.assertFalse((self.source.parent / 'race.dat').exists())
        self.source.write_bytes(doc.raw)
        for path in [None, [], self.folder / 'UDATA' / '5443000d' / 'system.dat',
                     self.folder / 'TDATA' / '5443000D' / 'system.dat']:
            with self.assertRaises(SaveError): parser.read_save(path)
        alias = self.folder / 'alias.dat'
        try: alias.symlink_to(self.source)
        except OSError: return
        with self.assertRaises(SaveError): parser.read_save(alias)

    def test_context_not_conflated_with_english_story_metadata(self):
        (self.source.parent / 'SaveMeta.xbx').write_bytes(b'unrelated japanese story metadata')
        self.assertEqual(parser.read_save(self.source).payload, self.document.payload)
        (self.source.parent / 'factory_eeprom.bin').write_bytes(self.document.context.eeprom)
        with self.assertRaises(SaveError): parser.read_save(self.source)

    def test_actual_tk_named_choices_sort_undo_review_save(self):
        import tkinter as tk
        from koei_editor.games.ninja_gaiden_black_xbox.editor import Editor
        try: root = tk.Tk()
        except tk.TclError: self.skipTest('A real Tk display is required')
        self.addCleanup(root.destroy); root.withdraw()
        editor = Editor(root)
        with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(self.source)):
            editor.open()
        root.update()
        self.assertIsNotNone(editor.document)
        editor.fields.selection_set('numeric_slot_order'); editor.selected()
        self.assertTrue(editor.value_choice.cget('values'))
        editor.value.set('1'); editor.apply_selected()
        self.assertEqual(editor.changes, {'numeric_slot_order': 1})
        with patch('koei_editor.shared.verified_gui.messagebox.showinfo'): editor.review()
        editor.undo(); self.assertEqual(editor.changes, {})
        editor.fields.selection_set('numeric_slot_order'); editor.value.set('1'); editor.apply_selected()
        target = self.source.parent / 'gui-edited.dat'
        with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(target)), patch('koei_editor.shared.verified_gui.messagebox.showinfo'):
            editor.save_as()
        self.assertEqual(parser.SORT.value(parser.read_save(target).payload), 1)


@unittest.skipUnless(os.environ.get('NGB_XBOX_NATIVE_DIRECTORY'), 'Private genuine STORY reference not supplied')
class NativeStoryCipherReferenceTests(unittest.TestCase):
    def test_genuine_story_reference_crypto_and_readonly_quarantine(self):
        path = Path(os.environ['NGB_XBOX_NATIVE_DIRECTORY']) / 'save000.dat'
        doc = story.read_story(path)
        plain, payload, extent, counts = codec.decrypt(doc.raw)
        stream = codec.pack(payload, counts)
        self.assertEqual(stream, plain[:len(stream)])
        self.assertEqual(codec.transform(plain, int.from_bytes(doc.raw[20:24], 'little')), doc.raw[24:])
        self.assertEqual(owner.signature(doc.raw, doc.context.key), doc.raw[:20])
        self.assertGreater(story.records(doc)['karma_score'], 0)
        self.assertFalse(hasattr(story, 'save_as'))
        with self.assertRaises(SaveError): parser.decode(doc.raw, source=path)


@unittest.skipUnless(os.environ.get('NGB_XBOX_SYSTEM_DIRECTORY'), 'No genuine owner-bound SYSTEM fixture acquired')
class OptionalNativeSystemTests(unittest.TestCase):
    def test_genuine_system_noop_and_exact_order_scope(self):
        path = Path(os.environ['NGB_XBOX_SYSTEM_DIRECTORY']) / 'system.dat'
        doc = parser.read_save(path)
        self.assertEqual(parser.serialize(doc, {}), doc.raw)
        original = path.read_bytes()
        edited = parser.decode(parser.serialize(doc, {'numeric_slot_order': 1}), source=path)
        self.assertEqual(edited.payload[:parser.COUNT], doc.payload[:parser.COUNT])
        self.assertEqual(edited.payload[parser.ORDER + 30:], doc.payload[parser.ORDER + 30:])
        self.assertEqual(path.read_bytes(), original)
