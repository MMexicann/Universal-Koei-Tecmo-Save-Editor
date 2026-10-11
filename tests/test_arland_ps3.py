"""Original PS3 procedural framing plus private genuine export/storage/Tk tests."""

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
from koei_editor.games.totori_ps3 import parser as totori
from koei_editor.games.meruru_ps3 import parser as meruru
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from koei_editor.shared.verified_self_test import _run

PROFILES = (totori, meruru)


def sfo(title):
    key = b"SAVEDATA_DIRECTORY\0"
    value = (title + "-LIST-00").encode() + b"\0"
    data = (36 + len(key) + 3) & ~3
    return (
        struct.pack("<5I", 0x46535000, 0x101, 36, data, 1)
        + struct.pack("<HH3I", 0, 0x204, len(value), len(value), 0)
        + key
        + bytes(data - 36 - len(key))
        + value
    )


def generated(p):
    """A framed procedural case, not a genuine or playable save."""
    b = p.BACKEND
    raw = bytearray(b.SAVE_SIZE)
    raw[:4] = bytes.fromhex("0132b533")
    start = 32
    chunks = []
    for index, size in enumerate(b.sizes, 1):
        struct.pack_into(">II", raw, start, index, size)
        chunks.append(start + 8)
        # Nonzero unknown islands in every serialized body and terminal region.
        raw[start + 8 : start + min(24, size) + 8] = bytes([index]) * min(24, size)
        start += 8 + size
    struct.pack_into(">II", raw, start, 1024, len(raw) - start)
    raw[start + 8 : start + 24] = b"PreservedOpaque!"
    struct.pack_into(">I", raw, b.cole_offset, 123456)
    for i in range(len(b.names)):
        struct.pack_into(">III", raw, chunks[3] + i * b.stride, i, 12 + i, 900 + i)
    return bytes(raw)


def copied(folder, p, raw=None, metadata=None):
    source = folder / "copy.bin"
    source.write_bytes(generated(p) if raw is None else raw)
    (folder / "PARAM.SFO").write_bytes(
        sfo(p.BACKEND.title_ids[0]) if metadata is None else metadata
    )
    return source


class ArlandPS3Tests(unittest.TestCase):
    def test_every_profile_noop_unique_money_surgical_reduction_and_inspectors(self):
        for p in PROFILES:
            with self.subTest(p=p.GAME_ID):
                raw = generated(p)
                adapter = BoundScalarAdapter(p.GAME_ID, ".bin", p)
                d = adapter.decode(raw)
                self.assertEqual(adapter.serialize(d, {}), raw)
                self.assertEqual(tuple(adapter.field_map(d)), ("cole",))
                f = adapter.field_map(d)["cole"]
                pending = adapter.stage(d, {}, "cole", 5)
                edited = adapter.serialize(d, pending)
                self.assertEqual(edited[: f.offset], raw[: f.offset])
                self.assertEqual(edited[f.offset + 4 :], raw[f.offset + 4 :])
                self.assertEqual(f.value(edited), 5)
                self.assertEqual(adapter.stage(d, pending, "cole", f.value(raw)), {})
                self.assertEqual(adapter.maximums(d, pending), pending)
                self.assertEqual(adapter.limit_values(d, pending, ["cole"]), {})
                characters, systems = p.inspection_rows(d)
                self.assertEqual(len(characters), len(p.BACKEND.names))
                self.assertEqual(len(systems), len(p.BACKEND.sizes))
                self.assertTrue(
                    all(row[2] == 12 + i for i, row in enumerate(characters))
                )
                self.assertNotIn("PreservedOpaque", repr(d))
                for value in (True, 1.0, "1", -1, 123457):
                    with self.assertRaises(SaveError):
                        adapter.serialize(d, {"cole": value})
                for key in (
                    "story",
                    "date",
                    "friendship",
                    "level",
                    "quality",
                    None,
                    [],
                ):
                    with self.assertRaises(SaveError):
                        adapter.stage(d, {}, key, 0)
                    with self.assertRaises(SaveError):
                        p.field_hint(d, key)
                for bad in (
                    replace(d, payload=raw[:-1]),
                    replace(d, format=replace(p.FORMAT, id="other")),
                    replace(d, raw=bytearray(raw)),
                    replace(d, source=None),
                ):
                    with self.assertRaises(SaveError):
                        p.serialize(bad, {})

    def test_foreign_profile_regions_counts_revisions_frames_and_truncation(self):
        for p in PROFILES:
            raw = generated(p)
            for bad in (
                raw[:-1],
                raw + b"\0",
                bytes(len(raw)),
                bytearray(raw),
                generated(PROFILES[1 - PROFILES.index(p)]),
            ):
                with self.assertRaises(SaveError):
                    p.decode(bad)
            b = p.BACKEND
            chunks = b._qualify(raw)
            positions = [0, 8, *[off - 8 for _, off, _ in chunks], len(raw) - 8]
            for off in positions[:-1]:
                bad = bytearray(raw)
                bad[off] ^= 1
                with self.assertRaises(SaveError):
                    p.decode(bytes(bad))
            tail = chunks[-1][1] + chunks[-1][2]
            for off in (tail, tail + 4, chunks[3][1] + b.stride):
                bad = bytearray(raw)
                bad[off] ^= 1
                with self.assertRaises(SaveError):
                    p.decode(bytes(bad))
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = copied(root, p)
                (root / "PARAM.SFO").unlink()
                with self.assertRaises(SaveError):
                    p.read_save(source)
                (root / "PARAM.SFO").write_bytes(sfo("BLUS00000"))
                with self.assertRaises(SaveError):
                    p.read_save(source)
                (root / "PARAM.SFO").write_bytes(bytes(4097))
                with self.assertRaises(SaveError):
                    p.read_save(source)
                # Qualified regions are explicit, never a parser fallback.
                for region in b.title_ids:
                    (root / "PARAM.SFO").write_bytes(sfo(region))
                    self.assertEqual(p.read_save(source).payload, raw)

    def test_save_restore_source_metadata_binding_and_races(self):
        for p in PROFILES:
            with tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                source = copied(folder, p)
                d = p.read_save(source)
                stamp = (folder / "PARAM.SFO").read_bytes()
                target = folder / "edited.bin"
                edited = p.save_as(d, {"cole": 0}, target)
                self.assertEqual(p.field_map(edited)["cole"].value(edited.payload), 0)
                self.assertEqual(source.read_bytes(), d.raw)
                snapshot = p.backup(d)
                p.restore(snapshot, folder / "restored.bin")
                self.assertEqual((folder / "restored.bin").read_bytes(), d.raw)
                with self.assertRaises(FileExistsError):
                    p.save_as(d, {}, target)
                (folder / "PARAM.SFO").write_bytes(stamp + b"\0")
                for operation in (
                    lambda: p.backup(d),
                    lambda: p.save_as(d, {}, folder / "bad.bin"),
                    lambda: p.restore(snapshot, folder / "badrestore.bin"),
                ):
                    with self.assertRaises(SaveError):
                        operation()
                (folder / "PARAM.SFO").write_bytes(stamp)
                source.write_bytes(d.raw[:-1] + b"\x01")
                with self.assertRaises(SaveError):
                    p.save_as(d, {}, folder / "changed.bin")
                source.write_bytes(d.raw)
                original = p.BACKEND.backup

                def mutate(doc):
                    result = original(doc)
                    source.write_bytes(doc.raw[:-1] + b"\x01")
                    return result

                with patch.object(p.BACKEND, "backup", side_effect=mutate):
                    with self.assertRaises(SaveError):
                        p.save_as(d, {"cole": 0}, folder / "race.bin")
                self.assertFalse((folder / "race.bin").exists())
                source.write_bytes(d.raw)
                context_path = snapshot.with_name(snapshot.name + ".context.json")
                alternate = p.serialize(d, {"cole": 0})
                original_backup = snapshot.read_bytes()
                original_manifest = snapshot.with_suffix(".json").read_bytes()
                snapshot.write_bytes(alternate)
                ordinary = json.loads(original_manifest)
                ordinary["sha256"] = hashlib.sha256(alternate).hexdigest()
                snapshot.with_suffix(".json").write_text(json.dumps(ordinary))
                with self.assertRaises(SaveError):
                    p.restore(snapshot, folder / "replaced-native.bin")
                self.assertFalse((folder / "replaced-native.bin").exists())
                snapshot.write_bytes(original_backup)
                snapshot.with_suffix(".json").write_bytes(original_manifest)
                context_path.write_bytes(bytes(1025))
                with self.assertRaises(SaveError):
                    p.restore(snapshot, folder / "oversized.bin")
                self.assertFalse((folder / "oversized.bin").exists())
                # An attacker replacing the ordinary backup manifest cannot turn
                # a foreign framed file into a valid restore for this profile.
                forged = generated(PROFILES[1 - PROFILES.index(p)])
                snapshot.write_bytes(forged)
                manifest = json.loads(snapshot.with_suffix(".json").read_text())
                manifest["sha256"] = hashlib.sha256(forged).hexdigest()
                manifest["size"] = len(forged)
                snapshot.with_suffix(".json").write_text(json.dumps(manifest))
                context_path.write_text(
                    json.dumps(
                        {
                            "game_id": p.GAME_ID,
                            "kind": "arland-ps3-export-context",
                            "context_sha256": d.context_sha256,
                            "save_sha256": hashlib.sha256(forged).hexdigest(),
                        }
                    )
                )
                with self.assertRaises(SaveError):
                    p.restore(snapshot, folder / "forged.bin")
                self.assertFalse((folder / "forged.bin").exists())

    def test_copy_context_hook_and_actual_shared_diagnostic(self):
        for p in PROFILES:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = copied(root, p)
                adapter = BoundScalarAdapter(p.GAME_ID, ".bin", p)
                report = _run(adapter, p.GAME_ID, source, root / "output")
                self.assertTrue(report["success"])
                self.assertEqual(report["integrity_kind"], "external")
                self.assertFalse(report["native_integrity_verified"])
                self.assertEqual(
                    (root / "output" / "PARAM.SFO").read_bytes(),
                    (root / "PARAM.SFO").read_bytes(),
                )
                self.assertEqual(report["fields_changed"], 0)

    def test_higher_opened_values_are_preserved_and_unstage(self):
        for p in PROFILES:
            raw = bytearray(generated(p))
            struct.pack_into(">I", raw, p.BACKEND.cole_offset, 0xFFFFFFFF)
            d = p.decode(bytes(raw))
            pending = p.stage(d, {}, "cole", 1)
            self.assertEqual(p.stage(d, pending, "cole", 0xFFFFFFFF), {})
            self.assertEqual(p.serialize(d, {}), bytes(raw))
            self.assertEqual(p.maximums(d, {}), {})

    def test_genuine_native_corpus_all_surgical_storage_and_diagnostic(self):
        fixture_root = os.environ.get("ARLAND_PS3_NATIVE_DIRECTORY")
        if not fixture_root:
            self.skipTest("Private original PS3 exports not configured")
        root = Path(fixture_root)
        for p, folders in (
            (totori, ("totori-22454", "totori-22468", "totori-22816", "totori-eu")),
            (meruru, ("meruru-22467", "meruru-22479", "meruru-22480")),
        ):
            for name in folders:
                native = (root / name / "USR-DATA.decrypted").read_bytes()
                metadata = (root / name / "PARAM.SFO").read_bytes()
                with tempfile.TemporaryDirectory() as tmp:
                    folder = Path(tmp)
                    source = copied(folder, p, native, metadata)
                    d = p.read_save(source)
                    self.assertEqual(p.serialize(d, {}), native)
                    edited = p.save_as(d, {"cole": 0}, folder / "edited.bin")
                    offset = p.BACKEND.cole_offset
                    self.assertEqual(edited.payload[:offset], native[:offset])
                    self.assertEqual(edited.payload[offset + 4 :], native[offset + 4 :])
                    self.assertEqual(edited.payload[offset : offset + 4], bytes(4))
                    self.assertEqual(source.read_bytes(), native)
                    snapshot = p.backup(d)
                    p.restore(snapshot, folder / "restored.bin")
                    self.assertEqual((folder / "restored.bin").read_bytes(), native)
                    report = _run(
                        BoundScalarAdapter(p.GAME_ID, ".bin", p),
                        p.GAME_ID,
                        source,
                        folder / "diagnostic",
                    )
                    self.assertTrue(report["success"])
                    self.assertFalse(report["in_game_load_tested"])


@unittest.skipUnless(
    os.name == "nt" or os.environ.get("DISPLAY"), "Graphical display required"
)
class ArlandPS3GUI(unittest.TestCase):
    def test_both_profile_open_search_edit_undo_review_inspector_save_restore(self):
        import tkinter as tk
        from koei_editor.games.totori_ps3.editor import Editor as T
        from koei_editor.games.meruru_ps3.editor import Editor as M

        for p, Editor in ((totori, T), (meruru, M)):
            root = tk.Tk()
            root.withdraw()
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    folder = Path(tmp)
                    native_root = os.environ.get("ARLAND_PS3_NATIVE_DIRECTORY")
                    name = "totori-22454" if p is totori else "meruru-22479"
                    native_folder = Path(native_root) / name if native_root else None
                    source = copied(
                        folder,
                        p,
                        (
                            (native_folder / "USR-DATA.decrypted").read_bytes()
                            if native_folder
                            else None
                        ),
                        (
                            (native_folder / "PARAM.SFO").read_bytes()
                            if native_folder
                            else None
                        ),
                    )
                    editor = Editor(root)
                    with (
                        patch(
                            "koei_editor.shared.verified_gui.filedialog.askopenfilename",
                            return_value=str(source),
                        ),
                        patch(
                            "koei_editor.shared.verified_gui.messagebox.showerror"
                        ) as errors,
                    ):
                        editor.open()
                        errors.assert_not_called()
                    editor.search.set("Cole")
                    root.update()
                    self.assertEqual(editor.fields.get_children(), ("cole",))
                    editor.fields.selection_set("cole")
                    editor.value.set("0")
                    editor.apply_selected()
                    self.assertEqual(editor.changes, {"cole": 0})
                    editor.undo()
                    self.assertEqual(editor.changes, {})
                    editor.value.set("0")
                    editor.apply_selected()
                    editor.review()
                    editor.show_inspector()
                    root.update()
                    for window in root.winfo_children():
                        if isinstance(window, tk.Toplevel):
                            window.destroy()
                    editor.apply_theme("Dark")
                    target = folder / "gui-edited.bin"
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
                        p.field_map(p.read_save(target))["cole"].value(
                            target.read_bytes()
                        ),
                        0,
                    )
                    snapshot = next((folder / "UniversalEditorBackups").glob("*.bin"))
                    restore = folder / "gui-restored.bin"
                    with (
                        patch(
                            "koei_editor.shared.verified_gui.filedialog.askopenfilename",
                            return_value=str(snapshot),
                        ),
                        patch(
                            "koei_editor.shared.verified_gui.filedialog.asksaveasfilename",
                            return_value=str(restore),
                        ),
                        patch(
                            "koei_editor.shared.verified_gui.messagebox.showerror"
                        ) as errors,
                    ):
                        editor.restore()
                        errors.assert_not_called()
                    self.assertEqual(restore.read_bytes(), source.read_bytes())
            finally:
                root.destroy()
