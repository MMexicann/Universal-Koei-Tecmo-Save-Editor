"""Additional ordinary consumables: generated safety and opt-in native evidence."""
import os
from pathlib import Path
import struct
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.nioh3 import codec, inventory, parser
from koei_editor.games.nioh3.editor import Editor
from tests.test_nioh3_format import procedural_raw, resign


ADDITIONS = {
    0x6514: 'Antidote', 0xFA6E: 'Antiparalytic Needle',
    0x96A7: 'Arrowproof Amulet', 0x4E22: "Daion-Jin's Sake",
    0xE7D3: 'Dung Ball', 0x4D66: 'Fireproof Amulet', 0xFC7A: 'Sacred Ash',
    0x5A51: 'Smoke Ball', 0x4C5F: 'Throwing Stone', 0x5943: 'Travel Amulet',
    0x304E: 'Water Amulet',
    0x2296: 'Yokai Water Pot', 0x683B: 'Scampuss Furball',
    0x3F5A: "Summoner's Candle", 0x140F: 'Righteous Jasper',
    0xCC42: 'Power Pill', 0x059A: 'Lantern Plant Fruit',
    0x3299: 'Steel Pill', 0xE4AA: 'Luckbringer Amulet',
    0x3A1B: 'Uchiko Powder', 0x9509: 'Fragrant Wood',
    0x65B4: 'Healing Pill', 0x5EDB: 'Tiger-Running Amulet',
    0x7EA2: 'Sacred Brush', 0xF681: 'Herbal Remedy',
}


class AdditionalConsumableTests(unittest.TestCase):
    def test_both_revisions_all_additions_surgical_reductions_and_undo(self):
        for revision in codec.SUPPORTED_REVISIONS:
            document = parser.decode(procedural_raw(revision))
            changes = {}
            allowed = set(range(codec.CHECKSUM_OFFSET, codec.CHECKSUM_OFFSET + 4))
            fields = parser.fields_for(document)
            for pool in inventory.POOLS[1:]:
                for identity, name in ADDITIONS.items():
                    matching = [f for f in fields if f.group == pool.title and f.label == name + ' quantity']
                    self.assertEqual(len(matching), 1)
                    field = matching[0]
                    self.assertEqual(int.from_bytes(document.payload[field.offset - 4:field.offset - 2], 'little'), identity)
                    changes = parser.stage(document, changes, field.id, 1)
                    allowed.update(range(field.offset, field.offset + field.size))
                    self.assertFalse(field.maxable)
                    for value in (0, field.maximum + 1, True, '1'):
                        with self.subTest(revision=revision, identity=identity, value=value), self.assertRaises(SaveError):
                            parser.stage(document, {}, field.id, value)
            self.assertEqual(len(changes), 50)
            self.assertEqual(len(parser.review(document, changes)), 50)
            self.assertEqual(parser.maximums(document, changes), changes)
            output = parser.serialize(document, changes)
            reopened = parser.decode(output)
            touched = {i for i, (before, after) in enumerate(zip(document.payload, reopened.payload)) if before != after}
            self.assertLessEqual(touched, allowed)
            for field in fields:
                if field.id in changes:
                    self.assertEqual(field.value(reopened.payload), 1)
                    changes = parser.stage(document, changes, field.id, field.value(document.payload))
            self.assertEqual(changes, {})
            self.assertEqual(parser.serialize(document, changes), document.raw)

    def test_new_ids_do_not_authorize_equipment_or_nonordinary_records(self):
        original = procedural_raw()
        pool = inventory.POOLS[1]
        slot = list(inventory.COMMON_ITEMS).index(0x6514)
        at = pool.start + slot * pool.stride
        for relative, value in ((2, 0), (4, 0), (6, 1), (8, 1), (10, 1), (0x1C, 0)):
            payload = bytearray(original)
            struct.pack_into('<H', payload, at + relative, value)
            document = parser.decode(resign(payload))
            self.assertNotIn(f'inventory_{slot}_quantity', parser.field_map(document))
            self.assertEqual(parser.serialize(document, {}), document.raw)
        payload = bytearray(original)
        equipment = inventory.POOLS[0]
        struct.pack_into('<6H', payload, equipment.start, 0x6514, 0x6514, 20, 0, 0, 0)
        document = parser.decode(resign(payload))
        self.assertFalse(any(field.group == 'Equipment' for field in parser.fields_for(document)))

    def test_refined_ids_require_ordinary_shape_and_unique_pool_identity(self):
        for identity in (0x2296, 0x683B, 0x3F5A, 0x140F, 0xCC42, 0x059A,
                         0x3299, 0xE4AA, 0x3A1B, 0x9509, 0x65B4, 0x5EDB,
                         0x7EA2, 0xF681):
            pool = inventory.POOLS[1]
            slot = list(inventory.COMMON_ITEMS).index(identity)
            at = pool.start + slot * pool.stride
            for relative, value in ((2, 0), (4, 0), (6, 1), (8, 1), (10, 1), (0x1C, 0)):
                payload = bytearray(procedural_raw())
                struct.pack_into('<H', payload, at + relative, value)
                document = parser.decode(resign(payload))
                with self.subTest(identity=identity, relative=relative):
                    self.assertNotIn(f'inventory_{slot}_quantity', parser.field_map(document))
                    self.assertEqual(parser.serialize(document, {}), document.raw)
            payload = bytearray(procedural_raw())
            duplicate = pool.start + 100 * pool.stride
            payload[duplicate:duplicate + pool.stride] = payload[at:at + pool.stride]
            with self.subTest(identity=identity), self.assertRaises(SaveError):
                parser.decode(resign(payload))

    def test_high_original_quantity_and_unknown_neighbors_remain_reversible(self):
        payload = bytearray(procedural_raw())
        pool = inventory.POOLS[1]
        slot = list(inventory.COMMON_ITEMS).index(0x6514)
        at = pool.start + slot * pool.stride
        struct.pack_into('<H', payload, at + 4, 65535)
        payload[at + 0x34:at + pool.stride] = bytes(range(180))
        document = parser.decode(resign(payload))
        field = parser.field_map(document)[f'inventory_{slot}_quantity']
        changes = parser.stage(document, {}, field.id, 2)
        reopened = parser.decode(parser.serialize(document, changes))
        self.assertEqual(reopened.payload[at + 6:at + pool.stride], document.payload[at + 6:at + pool.stride])
        self.assertEqual(parser.stage(document, changes, field.id, 65535), {})
        self.assertEqual(parser.maximums(document, {}), {})

    def test_sacred_brush_gui_search_review_undo_and_safe_save(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.addCleanup(root.destroy)
        root.withdraw()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.bin'
            source.write_bytes(procedural_raw())
            editor = Editor(root)
            errors = []
            with patch('koei_editor.shared.verified_gui.messagebox.showerror', side_effect=lambda *args: errors.append(args)), \
                    patch('koei_editor.shared.verified_gui.messagebox.showinfo'), \
                    patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                editor.open()
                editor.group.set('Item box')
                editor.search.set('Sacred Brush')
                editor.refresh()
                keys = editor.fields.get_children()
                self.assertEqual(len(keys), 1)
                key = keys[0]
                editor.fields.selection_set(key)
                editor.value.set('2')
                editor.apply_selected()
                self.assertEqual(editor.changes, {key: 2})
                editor.review()
                editor.undo()
                self.assertEqual(editor.changes, {})
                editor.fields.selection_set(key)
                editor.value.set('2')
                editor.apply_selected()
                destination = Path(directory) / 'edited.bin'
                with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(destination)):
                    editor.save_as()
                self.assertEqual(errors, [])
                self.assertEqual(source.read_bytes(), procedural_raw())
                reopened = parser.read_save(destination)
                self.assertEqual(parser.field_map(reopened)[key].value(reopened.payload), 2)
                self.assertTrue(list((source.parent / 'WarriorsEditorBackups').glob('*.bin')))


@unittest.skipUnless(os.environ.get('NIOH3_NATIVE_DIR'), 'Private native copies unavailable.')
class AdditionalNativeConsumableTests(unittest.TestCase):
    def test_both_native_revisions_existing_additional_consumables_only(self):
        revisions = set()
        refined_identities = set()
        for path in Path(os.environ['NIOH3_NATIVE_DIR']).iterdir():
            if not path.is_file():
                continue
            raw = path.read_bytes()
            try:
                document = parser.decode(raw)
            except SaveError:
                continue
            revisions.add(document.revision)
            self.assertEqual(parser.serialize(document, {}), raw)
            selected = [field for field in parser.fields_for(document)
                        if field.label in {name + ' quantity' for name in ADDITIONS.values()} and field.maximum > 1]
            refined_identities.update(int.from_bytes(document.payload[field.offset - 4:field.offset - 2], 'little')
                                      for field in selected)
            self.assertGreater(len(selected), 0)
            changes = {field.id: 1 for field in selected}
            output = parser.serialize(document, changes)
            reopened = parser.decode(output)
            allowed = set(range(codec.CHECKSUM_OFFSET, codec.CHECKSUM_OFFSET + 4))
            for field in selected:
                allowed.update(range(field.offset, field.offset + field.size))
                self.assertEqual(field.value(reopened.payload), 1)
            touched = {i for i, (a, b) in enumerate(zip(document.payload, reopened.payload)) if a != b}
            self.assertLessEqual(touched, allowed)
            self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(revisions, set(codec.SUPPORTED_REVISIONS))
        # Every newly advertised identity must have a positive native reduction
        # in the reviewed corpus, not just a procedural record or catalog name.
        self.assertLessEqual({0x2296, 0x683B, 0x3F5A, 0x140F, 0xCC42, 0x059A,
                              0x3299, 0xE4AA, 0x3A1B, 0x9509, 0x65B4, 0x5EDB,
                              0x7EA2, 0xF681}, refined_identities)
