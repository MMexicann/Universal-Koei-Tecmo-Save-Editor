"""Native PS3 DW8 XL regression; private player exports are never published."""

from dataclasses import replace
import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw8xl_ps3 import parser as p
from koei_editor.games.dw8xl_ps3.editor import Editor
from koei_editor.shared.koei_codec import byte_cipher
from tests import test_ps3_expansion as ps3_context


def encode(payload):
    return byte_cipher(bytes(payload), 0x13100200) + bytes([sum(payload) & 255])


def fixture():
    payload = bytearray((i * 17 + 9) % 256 for i in range(p.PAYLOAD_SIZE))
    payload[:5] = p.SIGNATURE
    for i in range(p.WEAPON_COUNT):
        off = p.WEAPON_BASE + i * p.WEAPON_STRIDE
        payload[off] = 0
        payload[off + 2 : off + 4] = b"\xff\xff"
    off = p.WEAPON_BASE
    payload[off] = 1
    payload[off + 2 : off + 4] = b"\x03\x00"
    payload[off + 6 : off + 12] = bytes((0, 2, 255, 3, 4, 5))
    payload[off + 12 : off + 18] = bytes((2, 7, 5, 0, 99, 10))
    for field in p.BASE_FIELDS:
        value = 50 if "_compatibility_" in field.id else min(123, field.maximum)
        payload[field.offset : field.offset + field.size] = value.to_bytes(
            field.size, "little"
        )
    return encode(payload)


def context(folder, title=p.TITLE_DIRECTORY):
    (Path(folder) / "PARAM.SFO").write_bytes(
        ps3_context.PS3ContextTests.metadata(title)
    )


class DW8XLPS3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = fixture()

    def test_noop_revision_checksums_and_foreign_inputs(self):
        doc = p.decode(self.raw)
        self.assertEqual(p.serialize(doc, {}), self.raw)
        for raw in (
            self.raw[:-1],
            self.raw + b"0",
            bytearray(self.raw),
            b"0" * len(self.raw),
        ):
            with self.assertRaises(SaveError):
                p.decode(raw)
        for offset in (0, 123, p.SAVE_SIZE - 1):
            broken = bytearray(self.raw)
            broken[offset] ^= 1
            with self.assertRaises(SaveError):
                p.decode(bytes(broken))
        foreign = bytearray(doc.payload)
        foreign[0] = 0x55
        with self.assertRaises(SaveError):
            p.decode(encode(foreign))
        with self.assertRaises(SaveError):
            p.decode(self.raw, "dw8xl")

    def test_surgical_scalars_and_attributes_unknown_preserved(self):
        doc = p.decode(self.raw)
        mapping = p.field_map(doc)
        self.assertEqual(len(mapping), 581)
        for key in (
            "weapon_0_rank_2",
            "weapon_0_rank_3",
            "weapon_0_rank_4",
            "weapon_1_rank_0",
        ):
            self.assertNotIn(key, mapping)
        for key in (
            "gold",
            "gems",
            "facility_materials",
            "weapon_materials",
            "officer_81_attack",
            "officer_81_defense",
            "officer_81_hp",
            "officer_81_compatibility_3",
            "weapon_0_rank_0",
            "weapon_0_rank_1",
            "weapon_0_rank_5",
        ):
            field = mapping[key]
            value = 100 if "_compatibility_" in key else field.minimum
            edits = p.stage(doc, {}, key, value)
            raw = p.serialize(doc, edits)
            edited = p.decode(raw)
            self.assertEqual(field.value(edited.payload), value)
            self.assertEqual(
                edited.payload[: field.offset], doc.payload[: field.offset]
            )
            self.assertEqual(
                edited.payload[field.offset + field.size :],
                doc.payload[field.offset + field.size :],
            )
            self.assertEqual(p.stage(doc, edits, key, field.value(doc.payload)), {})
            self.assertEqual(p.maximums(doc, edits), edits)
            self.assertEqual(p.limit_values(doc, edits, [key]), {})

    def test_invalid_changes_immutability_and_higher_originals(self):
        doc = p.decode(self.raw)
        for changes in (
            {"gold": True},
            {"gold": 10_000_000},
            {"officer_0_compatibility_0": 51},
            {"weapon_0_rank_0": 0},
            {"story_complete": 1},
            [],
        ):
            with self.assertRaises(SaveError):
                p.serialize(doc, changes)
        for fake in (
            replace(doc, payload=bytes(len(doc.payload))),
            replace(doc, raw=bytearray(doc.raw)),
            replace(doc, format=replace(p.FORMAT)),
        ):
            with self.assertRaises(SaveError):
                p.fields_for(fake)
        payload = bytearray(doc.payload)
        payload[0x105:0x109] = (0xFFFFFFFF).to_bytes(4, "little")
        high = p.decode(encode(payload))
        self.assertEqual(p.maximums(high, {}), {})
        edits = p.stage(high, {}, "gold", 42)
        self.assertEqual(p.stage(high, edits, "gold", 0xFFFFFFFF), {})
        self.assertEqual(p.serialize(high, {}), high.raw)

    def test_context_binding_save_backup_restore_and_changed_source(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "APP.BIN"
            source.write_bytes(self.raw)
            with self.assertRaises(SaveError):
                p.read_save(source)
            context(folder, "NPUB31449-WRONG")
            with self.assertRaises(SaveError):
                p.read_save(source)
            context(folder)
            doc = p.read_save(source)
            backup = p.backup(doc)
            destination = folder / "edited.bin"
            changed = p.save_as(doc, {"gold": 42}, destination)
            self.assertEqual(p.field_map(changed)["gold"].value(changed.payload), 42)
            self.assertEqual(source.read_bytes(), self.raw)
            restored = p.restore(backup, folder / "restored.bin")
            self.assertEqual(restored.read_bytes(), self.raw)
            with self.assertRaises(FileExistsError):
                p.save_as(doc, {}, destination)
            context(folder, "NPUB31449-WRONG")
            with self.assertRaises(SaveError):
                p.save_as(doc, {}, folder / "foreign.bin")
            context(folder)
            source.write_bytes(p.serialize(doc, {"gold": 43}))
            with self.assertRaises(SaveError):
                p.save_as(doc, {}, folder / "source-changed.bin")
            self.assertFalse((folder / "source-changed.bin").exists())

    def test_native_player_copy_noop_and_every_mapped_byte_span(self):
        path = os.environ.get("DW8XL_PS3_SAVE_COPY")
        if not path:
            self.skipTest("Private native US PS3 PSN export not supplied.")
        doc = p.read_save(path)
        self.assertEqual(p.serialize(doc, {}), doc.raw)
        for field in p.fields_for(doc):
            value = 100 if "_compatibility_" in field.id else field.minimum
            if value == field.value(doc.payload):
                value = field.maximum
            edits = p.stage(doc, {}, field.id, value)
            payload = p.changed_payload(doc, edits)
            self.assertEqual(payload[: field.offset], doc.payload[: field.offset])
            self.assertEqual(
                payload[field.offset + field.size :],
                doc.payload[field.offset + field.size :],
            )
        for key in ("gold", "gems", "officer_81_hp", "weapon_0_rank_0"):
            if key in p.field_map(doc):
                edited = p.decode(
                    p.serialize(
                        doc, p.stage(doc, {}, key, p.field_map(doc)[key].minimum)
                    )
                )
                self.assertEqual(
                    p.field_map(doc)[key].value(edited.payload),
                    p.field_map(doc)[key].minimum,
                )

    def test_gui_search_apply_review_undo_save_restore(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        root.withdraw()
        self.addCleanup(root.destroy)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "APP.BIN"
            source.write_bytes(self.raw)
            context(folder)
            editor = Editor(root)
            errors = []
            with (
                patch(
                    "koei_editor.shared.verified_gui.messagebox.showerror",
                    side_effect=lambda *x: errors.append(x),
                ),
                patch(
                    "koei_editor.shared.verified_gui.filedialog.askopenfilename",
                    return_value=str(source),
                ),
            ):
                editor.open()
                self.assertEqual(errors, [])
                editor.search.set("Gold")
                editor.refresh()
                self.assertIn("gold", editor.fields.get_children())
                editor.fields.selection_set("gold")
                editor.selected()
                editor.value.set("42")
                editor.apply_selected()
                self.assertEqual(editor.changes, {"gold": 42})
                editor.review()
                editor.undo()
                self.assertEqual(editor.changes, {})
                editor.apply_selected()
                editor.save_to(folder / "gui-edited.bin")
                self.assertEqual(errors, [])
                self.assertEqual(source.read_bytes(), self.raw)
                self.assertEqual(
                    p.restore(editor.backup, folder / "gui-restored.bin").read_bytes(),
                    self.raw,
                )
                self.assertTrue(p.inspection_rows(editor.document))

    def test_native_gui_private_copy_and_context_digest_guard(self):
        path = os.environ.get("DW8XL_PS3_SAVE_COPY")
        if not path:
            self.skipTest("Private native US PS3 PSN export not supplied.")
        original = p.read_save(path)
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        root.withdraw()
        self.addCleanup(root.destroy)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "APP.BIN"
            source.write_bytes(original.raw)
            (folder / "PARAM.SFO").write_bytes(
                (original.source.parent / "PARAM.SFO").read_bytes()
            )
            editor = Editor(root)
            errors = []
            with (
                patch(
                    "koei_editor.shared.verified_gui.messagebox.showerror",
                    side_effect=lambda *x: errors.append(x),
                ),
                patch(
                    "koei_editor.shared.verified_gui.filedialog.askopenfilename",
                    return_value=str(source),
                ),
            ):
                editor.open()
                self.assertEqual(errors, [])
                editor.fields.selection_set("gold")
                editor.selected()
                editor.value.set("12345")
                editor.apply_selected()
                self.assertEqual(editor.changes, {"gold": 12345})
                editor.review()
                editor.save_to(folder / "native-edited.bin")
                self.assertEqual(errors, [])
                edited = p.read_save(folder / "native-edited.bin")
                self.assertEqual(
                    p.field_map(edited)["gold"].value(edited.payload), 12345
                )
                self.assertEqual(edited.payload[:0x105], original.payload[:0x105])
                self.assertEqual(edited.payload[0x109:], original.payload[0x109:])
                self.assertEqual(
                    p.restore(
                        editor.backup, folder / "native-restored.bin"
                    ).read_bytes(),
                    original.raw,
                )
            doc = p.read_save(source)
            companion = folder / "PARAM.SFO"
            companion.write_bytes(companion.read_bytes() + b"\0")
            with self.assertRaises(SaveError):
                p.save_as(doc, {}, folder / "context-changed.bin")
            self.assertFalse((folder / "context-changed.bin").exists())

    def test_published_native_codec_reference_weapon_rank_surgery(self):
        path = os.environ.get("DW8XL_PS3_REFERENCE_COPY")
        if not path:
            self.skipTest("Private public converter reference not supplied.")
        doc = p.decode(Path(path).read_bytes())
        self.assertEqual(p.serialize(doc, {}), doc.raw)
        ranks = [f for f in p.fields_for(doc) if f.group == "Weapon attributes"]
        self.assertGreater(len(ranks), 0)
        for field in ranks:
            value = 1 if field.value(doc.payload) != 1 else 10
            edited = p.changed_payload(doc, p.stage(doc, {}, field.id, value))
            self.assertEqual(edited[: field.offset], doc.payload[: field.offset])
            self.assertEqual(
                edited[field.offset + 1 :], doc.payload[field.offset + 1 :]
            )
        for field in ranks[:6] + ranks[-6:]:
            value = 1 if field.value(doc.payload) != 1 else 10
            reopened = p.decode(p.serialize(doc, p.stage(doc, {}, field.id, value)))
            self.assertEqual(field.value(reopened.payload), value)
        payload = bytearray(doc.payload)
        for state in (0, 2, 255):
            start = ranks[0].offset - 12 - int(ranks[0].id.rsplit("_", 1)[-1])
            payload[start] = state
            closed = p.decode(encode(payload))
            self.assertNotIn(ranks[0].id, p.field_map(closed))

    def test_backup_source_and_context_changes_rejected_restore_context_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "APP.BIN"
            source.write_bytes(self.raw)
            context(folder)
            document = p.read_save(source)
            snapshot = p.backup(document)
            manifest = snapshot.with_name(snapshot.name + ".context.json")
            original_manifest = manifest.read_bytes()
            source.write_bytes(p.serialize(document, {"gold": 42}))
            with self.assertRaises(SaveError):
                p.backup(document)
            source.write_bytes(self.raw)
            companion = folder / "PARAM.SFO"
            original_context = companion.read_bytes()
            companion.write_bytes(original_context + b"\0")
            with self.assertRaises(SaveError):
                p.backup(document)
            with self.assertRaises(SaveError):
                p.restore(snapshot, folder / "wrong-context.bin")
            self.assertFalse((folder / "wrong-context.bin").exists())
            companion.write_bytes(original_context)
            for metadata in (b"", b"[]", b"{}", b"x" * 1025):
                manifest.write_bytes(metadata)
                with self.assertRaises(SaveError):
                    p.restore(snapshot, folder / "damaged-context.bin")
                self.assertFalse((folder / "damaged-context.bin").exists())
            manifest.unlink()
            with self.assertRaises(SaveError):
                p.restore(snapshot, folder / "missing-context.bin")
            manifest.write_bytes(original_manifest)
            self.assertEqual(
                p.restore(snapshot, folder / "same-context.bin").read_bytes(), self.raw
            )

    def test_unhashable_and_nonstring_field_ids_are_save_errors(self):
        doc = p.decode(self.raw)
        for key in ([], {}, set(), None, True, 42):
            with self.subTest(key=key):
                with self.assertRaises(SaveError):
                    p.stage(doc, {}, key, 1)
                with self.assertRaises(SaveError):
                    p.field_options(doc, key)
                with self.assertRaises(SaveError):
                    p.limit_values(doc, {}, [key])
        with self.assertRaises(SaveError):
            p.limit_values(doc, {}, None)
