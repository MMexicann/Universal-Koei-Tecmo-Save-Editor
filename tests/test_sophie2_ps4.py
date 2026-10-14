"""Procedural exact-profile checks and private genuine PS4 codec/storage/Tk tests."""

from dataclasses import replace
from functools import lru_cache
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.sophie2_ps4 import parser as p
from koei_editor.games.sophie2_ps4.context import title_only_sfo, title_id
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from koei_editor.shared.verified_self_test import _run


def node(name, body):
    name = name.encode() + b"\0"
    return struct.pack("<I", 4 + len(name) + len(body)) + name + body


def pool(name, count, occupied=False):
    records = bytearray(count * 44)
    for index in range(count):
        off = index * 44
        records[off + 4 : off + 6] = b"\xff\xff"
    if occupied:
        struct.pack_into("<IhH", records, 0, 101, 37, 40)
        records[36:38] = b"\1\1"
        records[12:14] = b"\x8f\x02"
        struct.pack_into(
            "<IhH", records, 44, 102, 30000, 50
        )  # unknown item remains readonly
        records[80:82] = b"\1\1"
    return node(name, struct.pack(">I", len(records)) + records)


@lru_cache(maxsize=1)
def payload():
    """Published/observed geometry with sparse distinctive unknown bytes; not playable."""
    records = []
    for i in range(10):
        body = bytearray(778)
        struct.pack_into(">iII", body, 0, i if i < 6 else -1, 10 + i, 456 + i)
        body[100:108] = b"Unknown!"
        # source equipment offset relative to Party name start, then record44
        for slot in range(8):
            off = 0x17A - 10 + slot * 44
            body[off + 4 : off + 6] = b"\xff\xff"
        if i == 0:
            off = 0x17A - 10 + 4 * 44
            struct.pack_into("<IhH", body, off, 900, 295, 90)
            body[off + 36 : off + 38] = bytes((3, 7))
        records.append(node("Party", body))
    remaining = 8056 - 10 - 14 - 4 - 10 * 788
    special = {
        "info": node("info", node("app_ver", struct.pack(">II", 1, 0))),
        "money": node("money", node("money", struct.pack(">III", 1000, 0, 21))),
        "party": node(
            "party",
            node("version", b"\0\3")
            + struct.pack(">I", 10)
            + b"".join(records)
            + node("m_squad", bytes(remaining - 12)),
        ),
        "item": node(
            "item",
            node("version", b"\0\2")
            + pool("m_unitBasket", 400)
            + pool("m_unitBasketImportant", 150)
            + pool("m_unitContainer", 9999, True)
            + pool("m_unitContainerImportant", 150)
            + pool("m_unitContainerExpendable", 50)
            + node("limitSize", struct.pack(">II", 400, 9999))
            + node("ID", b"\x90\x91\x92\x93")
            + node("m_mixGem", bytes(8))
            + node("m_mixMistList", bytes(24)),
        ),
        "mix_lv": node(
            "mix_lv",
            node("lv", struct.pack(">I", 20))
            + node("exp", struct.pack(">I", 1000))
            + node("plachta_lv", struct.pack(">I", 21))
            + node("plachta_exp", struct.pack(">I", 1100)),
        ),
        "explore_equip": node(
            "explore_equip",
            node("version", b"\0\1")
            + pool("explore_equip_item", 15)
            + pool("adventure_equip_item", 25),
        ),
    }
    raw = bytearray(bytes.fromhex("013379c9") + bytes(28))
    for name, size in p.ROOT_PROFILE:
        if name in special:
            block = special[name]
        else:
            body = bytearray(size - 5 - len(name))
            if len(body) >= 16:
                body[3:11] = b"Preserve"
            block = node(name, body)
        assert len(block) == size, (name, len(block), size)
        raw += block
    assert len(raw) == 629622
    return bytes(raw)


@lru_cache(maxsize=1)
def raw():
    header = bytearray(256)
    header[:4] = struct.pack("<I", 2)
    header[64:68] = struct.pack("<I", 1000)
    header[200:216] = b"UnknownHeader123"
    return p.codec.encode_file(bytes(header), payload(), 12345, b"XYZ")


def add_context(root, metadata=None):
    companion = root / "sce_sys" / "param.sfo"
    companion.parent.mkdir(exist_ok=True)
    companion.write_bytes(title_only_sfo() if metadata is None else metadata)
    return companion


def source(root, data=None, metadata=None):
    path = root / "copy.dat"
    path.write_bytes(raw() if data is None else data)
    add_context(root, metadata)
    return path


class Sophie2PS4Tests(unittest.TestCase):
    def test_additional_source_qualified_materials_preserve_native_dependencies(self):
        """Each newly named kind uses the same bounded, owned-record gate."""
        d = p.decode(raw())
        original = p.field_map(d)["materials_0_quality"]
        offset = original.offset - 6
        added = {3, 4, 9, 11, 14, 21, 22, 36, 45, 59, 69, 70, 71, 89}
        self.assertTrue(added <= p.MATERIAL_NAMES.keys())
        for identity in sorted(added):
            with self.subTest(item_id=identity):
                body = bytearray(d.payload)
                struct.pack_into("<h", body, offset + 4, identity)
                modified = p.decode(p.codec.encode_file(d.header, bytes(body), d.seed, d.footer))
                f = p.field_map(modified)[original.id]
                self.assertIn(p.MATERIAL_NAMES[identity], f.label)
                self.assertFalse(f.maxable)
                intended = p.changed_payload(modified, {f.id: 1})
                self.assertEqual(intended[:f.offset], modified.payload[:f.offset])
                self.assertEqual(intended[f.offset + 2:], modified.payload[f.offset + 2:])
                reopened = p.decode(p.serialize(modified, {f.id: 1}))
                self.assertEqual(reopened.payload, intended)
                self.assertEqual(p.serialize(modified, {f.id: 40}), modified.raw)
                self.assertEqual(p.stage(modified, {f.id: 1}, f.id, 40), {})
                with self.assertRaises(SaveError):
                    p.serialize(modified, {f.id: 41})
                # Stat bonuses still make a known material read-only.
                body[offset + 0x27] = 1
                bounded = p.decode(p.codec.encode_file(d.header, bytes(body), d.seed, d.footer))
                self.assertNotIn(f.id, p.field_map(bounded))

    def test_noop_identity_complete_codec_and_surgical_bounded_edits(self):
        adapter = BoundScalarAdapter(p.GAME_ID, ".dat", p)
        d = adapter.decode(raw())
        self.assertEqual(p.serialize(d, {}), raw())
        self.assertEqual(
            p.codec.encode_file(d.header, d.payload, d.seed, d.footer) + d.trailer,
            raw(),
        )
        fields = p.field_map(d)
        self.assertEqual(set(fields), {"materials_0_quality", "character_0_4_uses"})
        self.assertEqual(fields["materials_0_quality"].maximum, 40)
        self.assertEqual(fields["character_0_4_uses"].maximum, 7)
        pending = {}
        for key, value in (("materials_0_quality", 1), ("character_0_4_uses", 7)):
            pending = p.stage(d, pending, key, value)
        intended = p.changed_payload(d, pending)
        edited = p.decode(p.serialize(d, pending))
        allowed = {
            index
            for f in fields.values()
            for index in range(f.offset, f.offset + f.size)
        }
        self.assertLessEqual(
            {i for i, (a, b) in enumerate(zip(d.payload, intended)) if a != b}, allowed
        )
        self.assertEqual(edited.payload, intended)
        self.assertEqual(edited.header, d.header)
        self.assertEqual(edited.footer, b"XYZ")
        self.assertEqual(
            p.stage(
                d, p.stage(d, {}, "materials_0_quality", 1), "materials_0_quality", 40
            ),
            {},
        )
        self.assertEqual(p.maximums(d, pending), pending)
        self.assertEqual(p.limit_values(d, pending, list(fields)), {})
        self.assertEqual(len(p.inspection_rows(d)[1]), 6)
        self.assertEqual(len(p.inspection_rows(d)[3]), 36)
        self.assertNotIn("UnknownHeader", repr(d))

    def test_corrupt_envelope_and_exact_title_platform_root_revision_arrays(self):
        original = raw()
        for offset in (256, len(original) // 2, len(original) - 8, len(original) - 1):
            damaged = bytearray(original)
            damaged[offset] ^= 1
            with self.assertRaises(SaveError):
                p.decode(bytes(damaged))
        for bad in (
            original[:-1],
            original + b"\0",
            bytearray(original),
            bytes(256),
            bytes(p.MAX_FILE_SIZE + 1),
        ):
            with self.assertRaises(SaveError):
                p.decode(bad)
        d = p.decode(original)
        roots = p._structure(d.payload)[2]
        party = p._structure(d.payload)[1]
        app = p._node(p._children(d.payload, p._node(roots, "info")), "app_ver")
        cases = [
            (0, b"\0"),
            (32, b"\0"),
            (app.body, b"\1"),
            (party[6].body, b"\0"),
            (party[1].body + 3, b"\0"),
            (party[0].start, b"\0"),
        ]
        for off, value in cases:
            body = bytearray(d.payload)
            body[off : off + 1] = value
            with self.assertRaises(SaveError):
                p.decode(p.codec.encode_file(d.header, bytes(body), d.seed, d.footer))
        header = bytearray(d.header)
        header[0] = 3
        with self.assertRaises(SaveError):
            p.decode(p.codec.encode_file(bytes(header), d.payload, d.seed, d.footer))
        with self.assertRaises(SaveError):
            p.decode(original, "atelier_sophie2")
        meta = title_only_sfo()
        for bad in (meta.replace(b"CUSA28451", b"CUSA19640"), meta[:-1], bytes(4097)):
            with self.assertRaises(SaveError):
                title_id(bad)

    def test_unknown_item_dependencies_higher_values_forged_snapshots_and_types(self):
        d = p.decode(raw())
        fields = p.field_map(d)
        for key, f in fields.items():
            for value in (True, 1.0, "1", -1, f.maximum + 1):
                with self.assertRaises(SaveError):
                    p.serialize(d, {key: value})
        for key in (
            "cole",
            "level",
            "alchemy_exp",
            "traits",
            "story",
            "materials_1_quality",
            None,
            [],
        ):
            with self.assertRaises(SaveError):
                p.stage(d, {}, key, 1)
            with self.assertRaises(SaveError):
                p.field_hint(d, key)
        for bad in (
            replace(d, payload=d.payload[:-1]),
            replace(d, header=bytes(256)),
            replace(d, seed=d.seed + 1),
            replace(d, trailer=b"fake"),
            replace(d, raw=bytearray(d.raw)),
            replace(d, source=None),
            replace(d, format=replace(p.FORMAT, id="other")),
        ):
            with self.assertRaises(SaveError):
                p.serialize(bad, {})
        f = fields["materials_0_quality"]
        for off, value in (
            (f.offset, b"\xff\xff"),
            (f.offset + 33, b"\1"),
            (f.offset + 31, b"\2"),
        ):
            body = bytearray(d.payload)
            body[off : off + len(value)] = value
            modified = p.decode(
                p.codec.encode_file(d.header, bytes(body), d.seed, d.footer)
            )
            self.assertNotIn(f.id, p.field_map(modified))
            self.assertEqual(p.serialize(modified, {}), modified.raw)

    def test_duplicate_instance_and_unknown_battle_records_are_read_only(self):
        d = p.decode(raw())
        material = p.field_map(d)["materials_0_quality"]
        uses = p.field_map(d)["character_0_4_uses"]
        start = material.offset - 6
        unknown_start = start + 44
        for target in (unknown_start, uses.offset - 36):
            body = bytearray(d.payload)
            body[target : target + 2] = body[start : start + 2]
            body[target + 2 : target + 4] = b"\xca\xfe"
            modified = p.decode(
                p.codec.encode_file(d.header, bytes(body), d.seed, d.footer)
            )
            self.assertNotIn(material.id, p.field_map(modified))
            if target == uses.offset - 36:
                self.assertNotIn(uses.id, p.field_map(modified))
            self.assertEqual(p.serialize(modified, {}), modified.raw)
        body = bytearray(d.payload)
        struct.pack_into("<h", body, uses.offset - 32, 30000)
        modified = p.decode(
            p.codec.encode_file(d.header, bytes(body), d.seed, d.footer)
        )
        self.assertNotIn(uses.id, p.field_map(modified))
        self.assertEqual(p.serialize(modified, {}), modified.raw)

    def test_save_restore_metadata_races_and_real_diagnostic_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = source(root)
            d = p.read_save(path)
            meta = (root / "sce_sys" / "param.sfo").read_bytes()
            edited = p.save_as(d, {"materials_0_quality": 1}, root / "edited.dat")
            self.assertEqual(
                p.field_map(edited)["materials_0_quality"].value(edited.payload), 1
            )
            snapshot = p.backup(d)
            p.restore(snapshot, root / "restored.dat")
            self.assertEqual((root / "restored.dat").read_bytes(), d.raw)
            with self.assertRaises(FileExistsError):
                p.save_as(d, {}, root / "edited.dat")
            add_context(root, meta + b"\0")
            with self.assertRaises(SaveError):
                p.save_as(d, {}, root / "bad.dat")
            with self.assertRaises(SaveError):
                p.restore(snapshot, root / "badrestore.dat")
            add_context(root, meta)
            original = p.backup

            def mutate(doc):
                result = original(doc)
                add_context(root, meta + b"\0")
                return result

            with patch.object(p, "backup", side_effect=mutate):
                with self.assertRaises(SaveError):
                    p.save_as(d, {"materials_0_quality": 1}, root / "race.dat")
            self.assertFalse((root / "race.dat").exists())
            add_context(root, meta)
            snapshot.with_name(snapshot.name + ".context.json").write_bytes(bytes(1025))
            with self.assertRaises(SaveError):
                p.restore(snapshot, root / "oversized.dat")
            report = _run(
                BoundScalarAdapter(p.GAME_ID, ".dat", p),
                p.GAME_ID,
                path,
                root / "diagnostic",
            )
            self.assertTrue(report["success"])
            self.assertTrue(report["native_integrity_verified"])
            self.assertFalse(report["in_game_load_tested"])
            self.assertEqual(
                (root / "diagnostic" / "sce_sys" / "param.sfo").read_bytes(), meta
            )
            self.assertEqual(path.read_bytes(), d.raw)
            path.write_bytes(d.raw[:-1] + bytes([d.raw[-1] ^ 1]))
            with self.assertRaises(SaveError):
                p.backup(d)

    def test_genuine_export_full_codec_all_field_masks_combined_edit_storage(self):
        configured = os.environ.get("SOPHIE2_PS4_SAVE_COPY")
        if not configured:
            self.skipTest("Private genuine PS4 gameplay export not configured")
        native = Path(configured)
        metadata = (native.parent / "sce_sys" / "param.sfo").read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = source(root, native.read_bytes(), metadata)
            d = p.read_save(path)
            self.assertEqual(p.serialize(d, {}), native.read_bytes())
            self.assertEqual(
                p.codec.encode_file(d.header, d.payload, d.seed, d.footer) + d.trailer,
                d.raw,
            )
            fields = p.fields_for(d)
            self.assertGreater(len(fields), 400)
            pending = {}
            for f in fields:
                value = f.minimum if f.value(d.payload) != f.minimum else f.maximum
                # Direct staging checks exercise each mapped extent without
                # redundant hundreds of whole-file native encryptions.
                single = p.changed_payload(d, {f.id: value})
                self.assertEqual(single[: f.offset], d.payload[: f.offset])
                self.assertEqual(
                    single[f.offset + f.size :], d.payload[f.offset + f.size :]
                )
                self.assertEqual(f.value(single), value)
                pending[f.id] = value
            edited = p.save_as(d, pending, root / "edited.dat")
            self.assertEqual(edited.payload, p.changed_payload(d, pending))
            allowed = {i for f in fields for i in range(f.offset, f.offset + f.size)}
            self.assertLessEqual(
                {
                    i
                    for i, (a, b) in enumerate(zip(d.payload, edited.payload))
                    if a != b
                },
                allowed,
            )
            self.assertEqual(edited.header, d.header)
            self.assertEqual(edited.footer, d.footer)
            self.assertEqual(edited.trailer, d.trailer)
            snapshot = p.backup(d)
            p.restore(snapshot, root / "restored.dat")
            self.assertEqual((root / "restored.dat").read_bytes(), d.raw)
            self.assertEqual(path.read_bytes(), native.read_bytes())


@unittest.skipUnless(
    os.name == "nt" or os.environ.get("DISPLAY"), "Graphical display required"
)
class Sophie2PS4GUI(unittest.TestCase):
    def test_open_search_stage_undo_review_inspector_theme_save_and_restore(self):
        import tkinter as tk
        from koei_editor.games.sophie2_ps4.editor import Editor

        root = tk.Tk()
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                native = os.environ.get("SOPHIE2_PS4_SAVE_COPY")
                path = source(
                    folder,
                    Path(native).read_bytes() if native else None,
                    (
                        (Path(native).parent / "sce_sys" / "param.sfo").read_bytes()
                        if native
                        else None
                    ),
                )
                editor = Editor(root)
                with (
                    patch(
                        "koei_editor.shared.verified_gui.filedialog.askopenfilename",
                        return_value=str(path),
                    ),
                    patch(
                        "koei_editor.shared.verified_gui.messagebox.showerror"
                    ) as errors,
                ):
                    editor.open()
                    errors.assert_not_called()
                fields = p.fields_for(editor.document)
                f = next(f for f in fields if "Tall Taun" in f.label)
                editor.search.set("Tall Taun")
                root.update()
                self.assertIn(f.id, editor.fields.get_children())
                editor.fields.selection_set(f.id)
                editor.value.set("1")
                editor.apply_selected()
                self.assertEqual(editor.changes, {f.id: 1})
                editor.undo()
                self.assertEqual(editor.changes, {})
                editor.value.set("1")
                editor.apply_selected()
                editor.review()
                editor.show_inspector()
                root.update()
                for window in root.winfo_children():
                    if isinstance(window, tk.Toplevel):
                        window.destroy()
                editor.apply_theme("Dark")
                target = folder / "gui-edited.dat"
                with (
                    patch(
                        "koei_editor.shared.verified_gui.filedialog.asksaveasfilename",
                        return_value=str(target),
                    ),
                    patch(
                        "koei_editor.shared.verified_gui.messagebox.showerror"
                    ) as errors,
                ):
                    editor.save_as()
                    errors.assert_not_called()
                self.assertEqual(
                    p.field_map(p.read_save(target))[f.id].value(
                        editor.document.payload
                    ),
                    1,
                )
                snapshot = next((folder / "UniversalEditorBackups").glob("*.dat"))
                restored = folder / "gui-restored.dat"
                with (
                    patch(
                        "koei_editor.shared.verified_gui.filedialog.askopenfilename",
                        return_value=str(snapshot),
                    ),
                    patch(
                        "koei_editor.shared.verified_gui.filedialog.asksaveasfilename",
                        return_value=str(restored),
                    ),
                    patch(
                        "koei_editor.shared.verified_gui.messagebox.showerror"
                    ) as errors,
                ):
                    editor.restore()
                    errors.assert_not_called()
                self.assertEqual(restored.read_bytes(), path.read_bytes())
        finally:
            root.destroy()
