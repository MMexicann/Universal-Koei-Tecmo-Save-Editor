"""Original DW6 equipment bits, own-inventory references and scoped migration."""

import os
from pathlib import Path
import tempfile
import unittest

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw6 import converter, dw6_parser as pc, equipment as e
from koei_editor.games.dw6_ps3 import parser as ps3
from koei_editor.shared.experimental_limits import experimental_limits
from tests.test_dw6_format import procedural_raw
from tests.test_dw6_ps3 import fixture, context


def equipped_fixture(backend):
    endian = "little" if backend is pc else "big"
    raw = bytearray(procedural_raw() if backend is pc else fixture())
    for officer in range(41):
        base = backend.OFFICER_BASE + officer * 168
        for slot in range(8):
            offset = base + 8 + slot * 16
            for relative, value in (
                (0, officer * 3 if slot in (0, 7) else 174),
                (8, 3),
                (12, 0),
            ):
                raw[offset + relative : offset + relative + 4] = value.to_bytes(
                    4, endian
                )
        raw[base + 160 : base + 164] = bytes(4)
    for horse in range(8):
        base = backend.HORSE_BASE + horse * 60
        raw[base + 8 : base + 16] = (3).to_bytes(4, endian) + bytes(4)
    return bytes(raw)


class EquipmentTests(unittest.TestCase):
    def test_every_named_bit_and_record_boundary_is_surgical_in_both_endians(self):
        for backend in (pc, ps3):
            adapter = get_game(backend.GAME_ID).get_scalar_adapter()
            doc = adapter.decode(equipped_fixture(backend))
            fields = [
                f for f in adapter.fields_for(doc) if isinstance(f, e.EquipmentField)
            ]
            self.assertTrue(any(f.id == "officer_40_weapon_7_skill_9" for f in fields))
            for field in fields:
                value = field.choices[-1][0] if field.choices else 1
                pending = adapter.stage(doc, {}, field.id, value)
                raw = adapter.serialize(doc, pending)
                self.assertEqual(field.value(raw), value)
                self.assertEqual(raw[: field.offset], doc.raw[: field.offset])
                self.assertEqual(raw[field.offset + 4 :], doc.raw[field.offset + 4 :])
                endian = "little" if backend is pc else "big"
                if field.bit is not None:
                    self.assertEqual(
                        int.from_bytes(raw[field.offset : field.offset + 4], endian),
                        1 << field.bit,
                    )
                    self.assertEqual(
                        backend.field_options(doc, field.id),
                        ((0, "Disabled"), (1, "Enabled")),
                    )
                self.assertEqual(
                    adapter.stage(doc, pending, field.id, field.value(doc.raw)), {}
                )
                self.assertFalse(field.maxable)

    def test_combined_capacity_validation_and_remove_then_add(self):
        for backend in (pc, ps3):
            adapter = get_game(backend.GAME_ID).get_scalar_adapter()
            doc = adapter.decode(equipped_fixture(backend))
            for prefix, limit in (("officer_0_weapon_0", 5), ("horse_0", 4)):
                changes = {f"{prefix}_skill_{bit}": 1 for bit in range(limit)}
                raw = adapter.serialize(doc, changes)
                with self.assertRaises(SaveError):
                    adapter.serialize(doc, {**changes, f"{prefix}_skill_{limit}": 1})
                with experimental_limits(True), self.assertRaises(SaveError):
                    backend.stage(doc, changes, f"{prefix}_skill_{limit}", 1)
                opened = adapter.decode(raw)
                pending = adapter.stage(opened, {}, f"{prefix}_skill_0", 0)
                pending = adapter.stage(opened, pending, f"{prefix}_skill_{limit}", 1)
                updated = adapter.serialize(opened, pending)
                self.assertEqual(
                    adapter.field_map(opened)[f"{prefix}_skill_0"].value(updated), 0
                )
                self.assertEqual(
                    adapter.field_map(opened)[f"{prefix}_skill_{limit}"].value(updated),
                    1,
                )
                for bad in (True, 2, -1, "1"):
                    with self.assertRaises(SaveError):
                        adapter.stage(doc, {}, f"{prefix}_skill_0", bad)

    def test_unknown_or_overcapacity_masks_are_read_only_and_unrelated_bytes_survive(
        self,
    ):
        for backend in (pc, ps3):
            endian = "little" if backend is pc else "big"
            for offset, prefix, masks in (
                (backend.OFFICER_BASE + 20, "officer_0_weapon_0", (1 << 31, 0x3F)),
                (backend.HORSE_BASE + 12, "horse_0", (1 << 20, 0x1F)),
            ):
                for mask in masks:
                    raw = bytearray(equipped_fixture(backend))
                    raw[offset : offset + 4] = mask.to_bytes(4, endian)
                    doc = backend.decode(bytes(raw))
                    self.assertFalse(
                        any(
                            key.startswith(prefix + "_skill_")
                            for key in backend.field_map(doc)
                        )
                    )
                    self.assertEqual(backend.serialize(doc, {}), bytes(raw))
                    updated = backend.serialize(doc, {"officer_0_unlocked": 1})
                    self.assertEqual(
                        updated[offset : offset + 4], raw[offset : offset + 4]
                    )

    def test_equipped_choices_only_from_same_officer_known_existing_pool(self):
        for backend in (pc, ps3):
            doc = backend.decode(equipped_fixture(backend))
            key = "officer_40_equipped_weapon"
            choices = backend.field_options(doc, key)
            self.assertEqual(tuple(value for value, _ in choices), (0, 7))
            self.assertIn("Emerald Dew", choices[0][1])
            self.assertIn("Yue Ying", backend.record_label(41, "Equipment"))
            for bad in (1, 6, 8, -1, True):
                with self.assertRaises(SaveError):
                    backend.stage(doc, {}, key, bad)
            raw = bytearray(doc.raw)
            off = backend.OFFICER_BASE + 40 * 168 + 160
            raw[off : off + 4] = (1).to_bytes(4, "little" if backend is pc else "big")
            self.assertNotIn(key, backend.field_map(backend.decode(bytes(raw))))

    def test_new_equipment_values_survive_pc_ps3_conversion_with_destination_remainder(
        self,
    ):
        for source_backend, target_backend in ((pc, ps3), (ps3, pc)):
            source = source_backend.decode(equipped_fixture(source_backend))
            pending = {
                "officer_40_equipped_weapon": 7,
                "officer_40_weapon_7_skill_9": 1,
                "horse_0_skill_10": 1,
                "horse_0_element": 1,
            }
            source = source_backend.decode(source_backend.serialize(source, pending))
            target = target_backend.decode(equipped_fixture(target_backend))
            encoded = converter.encode(source, target)
            reopened = target_backend.decode(encoded)
            for key, value in pending.items():
                self.assertEqual(
                    target_backend.field_map(reopened)[key].value(encoded), value
                )
            self.assertEqual(converter.gameplay(source), converter.gameplay(reopened))
            self.assertEqual(converter.encode(reopened, source), source.raw)
            start = target_backend.OFFICER_BASE
            end = target_backend.HORSE_BASE - 24 + 8 * 60
            self.assertEqual(encoded[:start], target.raw[:start])
            self.assertEqual(encoded[end:], target.raw[end:])

    def test_migration_preview_counts_semantic_changes_and_warns_about_replacement(
        self,
    ):
        left = pc.decode(equipped_fixture(pc))
        right = ps3.decode(equipped_fixture(ps3))
        right = ps3.decode(converter.encode(left, right))
        notes = converter.preview_notes(left, right)
        self.assertIn("0 of 41", notes[0])
        self.assertIn("0 of eight", notes[2])
        changed = pc.decode(
            pc.serialize(left, {"officer_40_equipped_weapon": 7, "horse_0_skill_10": 1})
        )
        notes = converter.preview_notes(changed, right)
        self.assertIn("1 of 41", notes[0])
        self.assertIn("Yue Ying", notes[1])
        self.assertIn("1 of eight", notes[2])
        self.assertIn("not an inventory merge", notes[2])

    @unittest.skipUnless(
        os.environ.get("DW6_SAVE") and os.environ.get("DW6_PS3_SAVE_COPIES"),
        "No separate native platform copies selected",
    )
    def test_independent_native_equipment_edits_reopen_and_preserve_originals(self):
        sources = [(pc, os.environ["DW6_SAVE"])] + [
            (ps3, p) for p in os.environ["DW6_PS3_SAVE_COPIES"].split(os.pathsep)
        ]
        for backend, path in sources:
            adapter = get_game(backend.GAME_ID).get_scalar_adapter()
            doc = adapter.read_save(path)
            fields = [
                f for f in adapter.fields_for(doc) if isinstance(f, e.EquipmentField)
            ]
            self.assertTrue(fields)
            # Removal cannot exceed capacity and verifies every named native bit without inventing growth.
            selected = [f for f in fields if f.bit is not None and f.value(doc.payload)]
            self.assertTrue(selected)
            pending = {f.id: 0 for f in selected}
            raw = adapter.serialize(doc, pending)
            for field in selected:
                self.assertEqual(field.value(raw), 0)
            allowed = {i for f in selected for i in range(f.offset, f.offset + 4)}
            self.assertTrue(
                all(
                    a == b or i in allowed for i, (a, b) in enumerate(zip(doc.raw, raw))
                )
            )
            with tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / (
                    "APP.BIN" if backend is ps3 else "save.dat"
                )
                if backend is ps3:
                    backend.prepare_copy_context(doc, destination.parent)
                actual = adapter.save_as(doc, pending, destination)
                self.assertEqual(actual.raw, raw)
                self.assertEqual(adapter.read_save(path), doc)
