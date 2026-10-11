"""Non-playable format fixtures, plus separately selected public native gameplay."""
from dataclasses import replace
from functools import lru_cache
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.ryza3_dx_pc import parser as p


def node(name, body):
    name = name.encode() + b'\0'
    return struct.pack('<I',4 + len(name) + len(body)) + name + body


def unknown(size, salt=11):
    data = bytearray(size)
    for position in (0,size // 2,max(0,size - 8)):
        for index in range(min(4,size - position)):
            data[position + index] = (salt + index * 17) & 255
    return bytes(data)


def filled(name, size, body):
    remaining = size - len(node(name,body))
    if remaining:
        body += node('unmapped',unknown(remaining - 13))
    result = node(name,body)
    assert len(result) == size
    return result


@lru_cache(maxsize=1)
def generated_payload():
    # These are independent procedural construction facts, never player bytes.
    bodies = {'info':node('app_ver',struct.pack('<II',1,1)),
              'fieldmap':b'_I_SECRETBASE_01\0_T_SECRETBASE_02\0_T_RASEN\0'}
    empty = bytearray(unknown(128,37))
    struct.pack_into('<H',empty,0,0xffff)
    struct.pack_into('<H',empty,4,0xffff)
    item = node('version',b'\2\0')
    for label,name,count in p.POOLS:
        records = bytearray(empty * count)
        if name == 'item_container_units':
            struct.pack_into('<6H',records,0,71,1,692,75,75,0x2424)
        item += node(name,struct.pack('<I',len(records)) + records)
    item += node('limitSize',struct.pack('<II',700,15000))
    item += node('mix_gem',struct.pack('<II',4,300))
    bodies['item'] = item
    members = b''.join(node('Party',struct.pack('<i',i) + unknown(1586,i + 1)) for i in range(14))
    bodies['party'] = node('version',b'\1\0') + struct.pack('<I',14) + members
    bodies['AlchemyTree'] = (node('version',struct.pack('<IH',2,0))
                              + node('skill_point',struct.pack('<II',4,500))
                              + node('skill_state',struct.pack('<I',758) + bytes((i * 7) & 255 for i in range(758))))
    bodies['SecretKey'] = (node('version',b'\1\0')
                          + node('secretkey_general',struct.pack('<I',1280) + empty * 10)
                          + node('secretkey_innocent',struct.pack('<I',1280) + empty * 10))
    roots = b''.join(filled(name,size,bodies[name]) if name in bodies else
                     node(name,unknown(size - len(node(name,b''))))
                     for name,size in p.ROOT_PROFILE)
    terminal = (struct.pack('<I',830) + b'order_switch\0'
                + node('version',b'\1\0')
                + struct.pack('<I',799) + b'order_data\0' + struct.pack('<I',780)
                + bytes((i * 19 + 23) & 255 for i in range(772)))
    payload = struct.pack('<I',20150730) + bytes(28) + roots + terminal
    assert len(payload) == 2480654
    return payload


def encoded(payload, revision=4):
    header = bytearray((i * 11 + 31) & 255 for i in range(256))
    header[:48] = struct.pack('<I',revision) + bytes(36) + struct.pack('<II',1,1)
    return p.codec.encode_file(bytes(header),payload,0x12345678,b'\x13\x57\x9b')


@lru_cache(maxsize=1)
def raw():
    return encoded(generated_payload())


class Ryza3DXPCFormatTests(unittest.TestCase):
    def setUp(self):
        self.doc = p.decode(raw())

    def test_noop_native_integrity_and_strict_platform_identity(self):
        self.assertEqual(p.serialize(self.doc,{}),raw())
        for game in ('atelier_ryza2','atelier_ryza3','atelier_ryza3_switch',None):
            with self.subTest(game=game), self.assertRaises(SaveError):
                p.decode(raw(),game)
        for offset in (0,40,44,256,len(raw()) - 12):
            damaged = bytearray(raw()); damaged[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(SaveError):
                p.decode(damaged)
        with self.assertRaises(SaveError):
            p.decode(encoded(self.doc.payload,1))

    def test_only_two_explicit_resources_and_surgical_deductions(self):
        fields = p.field_map(self.doc)
        self.assertEqual(set(fields),{'skill_points','synthesis_gems'})
        changes = {key:field.value(self.doc.payload) - 1 for key,field in fields.items()}
        edited = p.decode(p.serialize(self.doc,changes))
        allowed = {offset for f in fields.values() for offset in range(f.offset,f.offset + 4)}
        touched = {i for i,(a,b) in enumerate(zip(self.doc.payload,edited.payload)) if a != b}
        self.assertTrue(touched)
        self.assertLessEqual(touched,allowed)
        self.assertEqual(len(edited.payload),len(self.doc.payload))
        self.assertEqual(edited.payload[p.TAIL_START:],self.doc.payload[p.TAIL_START:])
        self.assertEqual((edited.header,edited.seed,edited.footer,edited.trailer),
                         (self.doc.header,self.doc.seed,self.doc.footer,self.doc.trailer))
        self.assertEqual(p.maximums(self.doc,changes),changes)
        for key,f in fields.items():
            self.assertFalse(f.maxable)
            pending = p.stage(self.doc,{},key,0)
            self.assertEqual(p.stage(self.doc,pending,key,f.value(self.doc.payload)),{})
            self.assertEqual([(r.id,before,after) for r,before,after in p.review(self.doc,pending)],
                             [(key,f.value(self.doc.payload),0)])
            for value in (-1,f.maximum + 1,True,'0'):
                with self.subTest(key=key,value=value), self.assertRaises(SaveError):
                    p.serialize(self.doc,{key:value})
        for key in ('money','quality','skill_state','order_data'):
            with self.assertRaises(SaveError):
                p.stage(self.doc,{},key,1)

    def test_exact_tail_elision_never_allows_arbitrary_truncation_or_repair(self):
        payload = self.doc.payload
        bad = []
        for delta in (-8,-1,1,8):
            bad.append(payload[:delta] if delta < 0 else payload + bytes(delta))
        wrong_size = bytearray(payload);struct.pack_into('<I',wrong_size,p.TAIL_START,829);bad.append(wrong_size)
        wrong_prefix = bytearray(payload);wrong_prefix[p.TAIL_START + 4] = ord('x');bad.append(wrong_prefix)
        wrong_array = bytearray(payload);struct.pack_into('<I',wrong_array,p.TAIL_START + 46,772);bad.append(wrong_array)
        bad.append(payload[:p.TAIL_START] + payload[p.TAIL_START:] + node('after_tail',b''))
        # A prior root must still frame completely, even if envelope checks pass.
        wrong_root = bytearray(payload);struct.pack_into('<I',wrong_root,32,30);bad.append(wrong_root)
        wrong_marker = payload.replace(b'_T_RASEN\0',b'_T_WRONG\0');bad.append(wrong_marker)
        for index,data in enumerate(bad):
            with self.subTest(index=index), self.assertRaises(SaveError):
                p.decode(encoded(bytes(data)))

    def test_negative_unknown_scalar_or_duplicate_tag_never_grants_writes(self):
        f = p.field_map(self.doc)['skill_points']
        for offset,value in ((f.offset - 4,struct.pack('<I',2)),(f.offset,bytes.fromhex('ffffffff'))):
            payload = bytearray(self.doc.payload);payload[offset:offset + 4] = value
            doc = p.decode(encoded(bytes(payload)))
            self.assertNotIn('skill_points',p.field_map(doc))
            self.assertEqual(p.serialize(doc,{}),doc.raw)
        # Duplicate name by renaming a same-width unused tag, retaining geometry.
        tree = p._unique(p._structure(self.doc.payload)[0],'AlchemyTree')
        point = p._unique(p._children(self.doc.payload,tree),'skill_point')
        damaged = bytearray(self.doc.payload)
        damaged[point.start + 4:point.start + 15] = b'skill_state'
        with self.assertRaises(SaveError):
            p.decode(encoded(bytes(damaged)))

    def test_forged_snapshot_and_pending_mappings_rejected(self):
        for key,value in (('payload',self.doc.payload[:-1]),('raw',bytearray(self.doc.raw)),
                          ('header',bytes(256)),('seed',self.doc.seed + 1),
                          ('format',replace(self.doc.format,id='foreign'))):
            with self.subTest(key=key), self.assertRaises(SaveError):
                p.serialize(replace(self.doc,**{key:value}),{})
        for changes in ([],{'missing':0},{'skill_points':True}):
            with self.assertRaises(SaveError):
                p.maximums(self.doc,changes)
        with self.assertRaises(SaveError):
            p.limit_values(self.doc,{},['unknown'])

    def test_inventory_party_and_section_inspection_does_not_add_fields(self):
        inventory,party,sections = p.inspection_rows(self.doc)
        self.assertEqual(inventory,(('Container',1,71,1,692,75,75,0x2424),))
        self.assertEqual(len(party),14)
        self.assertEqual(len(sections),41)
        self.assertEqual(set(p.field_map(self.doc)),{'skill_points','synthesis_gems'})

    def test_safe_saves_backups_restore_aliases_and_source_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);source = root / 'copy.dat';source.write_bytes(raw())
            doc = p.read_save(source)
            pending = p.stage(doc,{},'synthesis_gems',0)
            edited = p.save_as(doc,pending,root / 'edited.dat')
            self.assertEqual(p.field_map(edited)['synthesis_gems'].value(edited.payload),0)
            self.assertEqual(source.read_bytes(),raw())
            snapshot = p.backup(doc)
            p.restore(snapshot,root / 'restored.dat')
            self.assertEqual((root / 'restored.dat').read_bytes(),raw())
            with self.assertRaises(FileExistsError):
                p.save_as(doc,{},source)
            source.write_bytes(b'changed')
            for action in (lambda:p.backup(doc),lambda:p.save_as(doc,pending,root / 'changed.dat')):
                with self.assertRaises(SaveError):action()
            self.assertFalse((root / 'changed.dat').exists())
            invalid = p.snapshot_backup(raw()[:-16],root / 'invalid.dat',p.GAME_ID,root / 'InvalidBackups')
            with self.assertRaises(SaveError):
                p.restore(invalid,root / 'invalid-restored.dat')
            self.assertFalse((root / 'invalid-restored.dat').exists())
            with self.assertRaises(SaveError):
                p.read_save(root / 'KoeiTecmo' / 'Atelier Ryza 3 DX' / 'copy.dat')

    def test_source_changed_after_backup_never_publishes_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root / 'copy.dat';source.write_bytes(raw());doc=p.read_save(source)
            real_backup=p.backup
            def mutate(document):
                result=real_backup(document);source.write_bytes(b'external change');return result
            with patch.object(p,'backup',side_effect=mutate),self.assertRaises(SaveError):
                p.save_as(doc,{'skill_points':0},root / 'edited.dat')
            self.assertFalse((root / 'edited.dat').exists())

    @unittest.skipUnless(os.environ.get('RYZA3_DX_PC_SAVE_COPY'),'Private native Ryza 3 DX PC gameplay not selected')
    def test_public_native_gameplay_noop_all_edits_and_storage(self):
        native=Path(os.environ['RYZA3_DX_PC_SAVE_COPY']).read_bytes();doc=p.decode(native)
        self.assertEqual(p.serialize(doc,{}),native)
        self.assertEqual(p.codec.encode_file(doc.header,doc.payload,doc.seed,doc.footer) + doc.trailer,native)
        fields=p.field_map(doc);self.assertEqual(set(fields),{'skill_points','synthesis_gems'})
        self.assertEqual({key:f.value(doc.payload) for key,f in fields.items()},
                         {'skill_points':99999,'synthesis_gems':1324241})
        changed=p.decode(p.serialize(doc,{key:0 for key in fields}))
        allowed={i for f in fields.values() for i in range(f.offset,f.offset + 4)}
        self.assertLessEqual({i for i,(a,b) in enumerate(zip(doc.payload,changed.payload)) if a!=b},allowed)
        self.assertEqual(changed.payload[p.TAIL_START:],doc.payload[p.TAIL_START:])
        self.assertGreater(len(p.inspection_rows(doc)[0]),1)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root / 'copy.dat';source.write_bytes(native)
            copied=p.read_save(source);p.save_as(copied,{'skill_points':0},root / 'edited.dat')
            snapshot=p.backup(copied);p.restore(snapshot,root / 'restored.dat')
            self.assertEqual((root / 'restored.dat').read_bytes(),native)
            self.assertEqual(source.read_bytes(),native)


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'),'Graphical display required')
class Ryza3DXPCGuiTests(unittest.TestCase):
    def test_open_inspect_search_edit_undo_review_save_and_restore(self):
        import tkinter as tk
        from koei_editor.games.ryza3_dx_pc.editor import Editor
        root=tk.Tk();root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as directory:
                directory=Path(directory);source=directory / 'copy.dat';target=directory / 'edited.dat'
                native=os.environ.get('RYZA3_DX_PC_SAVE_COPY')
                data=Path(native).read_bytes() if native else raw();source.write_bytes(data)
                editor=Editor(root)
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename',return_value=str(source)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.open();errors.assert_not_called()
                self.assertEqual(len(editor.presentation.inspection_tables(editor.document)),3)
                editor.show_inspector();root.update()
                for window in root.winfo_children():
                    if isinstance(window,tk.Toplevel):window.destroy()
                editor.search.set('gems');root.update()
                self.assertEqual(editor.fields.get_children(),('synthesis_gems',))
                editor.fields.selection_set('synthesis_gems');editor.value.set('0');editor.apply_selected()
                self.assertEqual(editor.changes,{'synthesis_gems':0})
                editor.undo();self.assertEqual(editor.changes,{})
                editor.value.set('0');editor.apply_selected();editor.review()
                for window in root.winfo_children():
                    if isinstance(window,tk.Toplevel):window.destroy()
                editor.apply_theme('Dark')
                with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename',return_value=str(target)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.save_as();errors.assert_not_called()
                self.assertEqual(p.field_map(p.read_save(target))['synthesis_gems'].value(editor.document.payload),0)
                snapshot=next((directory / 'WarriorsEditorBackups').glob('*.dat'))
                restored=directory / 'restored.dat'
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename',return_value=str(snapshot)), \
                     patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename',return_value=str(restored)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.restore();errors.assert_not_called()
                self.assertEqual(restored.read_bytes(),data)
                self.assertEqual(source.read_bytes(),data)
        finally:root.destroy()
