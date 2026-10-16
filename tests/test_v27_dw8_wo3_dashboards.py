"""Opened-value dashboards never infer unsupported progress or stage writes."""
from dataclasses import FrozenInstanceError, replace
import os
from pathlib import Path
import struct
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw8xl.dw8xl_editor import DW8XLPresentation
from koei_editor.games.wo3u.wo3u_editor import WO3Presentation
from koei_editor.games.wo3u import wo3u_equipment as equipment
from koei_editor.games.wo3u import wo3u_parser as wo3
from koei_editor.game_registry import get_game
from koei_editor.shared.appearance import THEMES
from koei_editor.shared import verified_editor as dw8
from tests.test_dw8_weapon_order import procedural_equipment
from tests.test_wo3u_depth import depth_raw


def sections(dashboard):
    return {section.id: section for section in dashboard.sections}


def metrics(card):
    return {metric.id: metric for metric in card.metrics}


def encode_dw8(document, payload):
    inner = dw8.byte_cipher(bytes(payload), document.format.inner_seed)
    raw = (struct.pack('<HH', dw8.word_sum(inner), document.seed)
           + dw8.word_cipher(inner, document.seed)
           + bytes([(sum(payload) & 255) ^ (dw8.mix_word(document.seed) & 255)]))
    return dw8.decode(raw, 'dw8xl')


class DW8ProgressionDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = dw8.decode(procedural_equipment(), 'dw8xl')

    def test_character_stats_equipped_references_and_only_verified_aptitude_progress(self):
        payload = bytearray(self.document.payload)
        base = 0x7fc9
        payload[base + 0x17] = 41
        struct.pack_into('<I', payload, base + 0x1c, 123456)
        payload[0x7fdb:0x7fdf] = bytes((25, 50, 100, 101))
        document = encode_dw8(self.document, payload)
        view = DW8XLPresentation(dw8, 'dw8xl').dashboard(document)
        groups = sections(view)
        self.assertEqual(len(groups['characters'].cards), 82)
        first = metrics(groups['characters'].cards[0])
        self.assertEqual(first['level'].value, '42')
        self.assertEqual(first['experience'].value, '123,456')
        self.assertIsNone(first['experience'].fraction)
        for action, expected in enumerate((0.25, 0.5, 1.0, None)):
            self.assertEqual(first[f'officer_0_compatibility_{action}'].fraction, expected)
        self.assertIn('101 stored units', first['officer_0_compatibility_3'].value)
        self.assertEqual(first['officer_0_attack'].field_id, 'officer_0_attack')
        self.assertEqual(first['equipped_0'].field_id, 'officer_0_first_weapon')
        self.assertIn('ID ', first['equipped_0'].value)
        self.assertIsNone(first['equipped_1'].field_id)

    def test_populated_weapons_unknown_ids_links_and_no_physical_pool_percentage(self):
        view = DW8XLPresentation(dw8, 'dw8xl').dashboard(self.document)
        groups = sections(view)
        native_weapons = dw8.weapons(self.document)
        self.assertEqual(len(groups['equipment'].cards), len(native_weapons))
        fields = dw8.field_map(self.document)
        for section in view.sections:
            for card in section.cards:
                for metric in card.metrics:
                    if metric.field_id is not None:
                        self.assertIn(metric.field_id, fields)
                    if metric.total is not None:
                        self.assertEqual(metric.total, 4)
                        self.assertIn('aptitude', metric.label)
        self.assertTrue(all('ownership' in card.subtitle.lower() for card in groups['allies'].cards))
        completion = metrics(groups['completion'].cards[0])
        self.assertEqual(completion['story'].value, 'Not mapped')
        self.assertTrue(all(metric.fraction is None for metric in completion.values()))

    def test_projection_is_immutable_and_never_calls_writer_or_accepts_tampering(self):
        raw = self.document.raw
        with patch.object(dw8, 'stage', side_effect=AssertionError('write attempted')), \
                patch.object(dw8, 'serialize', side_effect=AssertionError('write attempted')):
            view = DW8XLPresentation(dw8, 'dw8xl').dashboard(self.document)
        self.assertEqual(self.document.raw, raw)
        with self.assertRaises(FrozenInstanceError):
            view.sections[0].cards[0].title = 'changed'
        changed = bytearray(self.document.payload)
        changed[0x105] ^= 1
        with self.assertRaises(SaveError):
            DW8XLPresentation(dw8, 'dw8xl').dashboard(replace(self.document, payload=bytes(changed)))


class WO3ProgressionDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = bytearray(depth_raw())
        base = wo3.OFFICER_BASE
        raw[base + 17] = 34
        raw[base + 26:base + 30] = (987654).to_bytes(4, 'little')
        cls.document = wo3.decode(raw)

    def test_character_resources_and_internal_records_preserve_original_meaning(self):
        view = WO3Presentation(wo3, 'wo3u').dashboard(self.document)
        groups = sections(view)
        self.assertEqual(len(groups['characters'].cards), 145)
        self.assertEqual(len(groups['internal'].cards), 5)
        first = metrics(groups['characters'].cards[0])
        self.assertEqual(first['level'].value, '35')
        self.assertEqual(first['experience'].value, '987,654')
        self.assertEqual(first['promotions'].value, '1')
        self.assertEqual(first['upgrade_stones'].value, '50')
        self.assertEqual(first['upgrade_stones'].field_id, 'officer_0_upgrade_stones')
        self.assertEqual(first['item_0'].value, 'Item ID 0')
        self.assertEqual(first['item_0'].field_id, 'officer_0_equipped_item_0')
        self.assertTrue(all(metric.fraction is None for metric in first.values()))
        self.assertTrue(all(metric.field_id is None
                            for card in groups['internal'].cards for metric in card.metrics))
        resources = {card.id: card for card in groups['resources'].cards}
        for key in ('gems', 'growth_points', 'orb_57', 'material_6_144'):
            self.assertIn(key, resources)
            metric = resources[key].metrics[0]
            self.assertEqual(metric.field_id, key)
            self.assertIsNone(metric.fraction)

    def test_inventory_ownership_rank_references_and_scoped_coverage_are_distinct(self):
        view = WO3Presentation(wo3, 'wo3u').dashboard(self.document)
        groups = sections(view)
        cards = {card.id: card for card in groups['equipment'].cards}
        self.assertEqual(metrics(cards['item_0'])['owned'].value, 'Owned')
        self.assertIn('Officer 1', metrics(cards['item_0'])['references'].value)
        self.assertEqual(metrics(cards['item_3'])['owned'].value, 'Not owned')
        self.assertEqual(metrics(cards['item_3'])['rank'].value, '1')
        coverage = {card.id: card.metrics[0] for card in groups['completion'].cards}
        ordinary = coverage['ownership_ordinary']
        mounts = coverage['ownership_mount']
        self.assertEqual((ordinary.current, ordinary.total), (3, 60))
        self.assertEqual((mounts.current, mounts.total), (1, 4))
        self.assertIn('mapped inventory', groups['completion'].cards[0].subtitle)
        self.assertIsNone(coverage['story'].fraction)

    def test_weapons_unknown_attributes_and_unqualified_equipment_are_read_only(self):
        raw = bytearray(self.document.raw)
        raw[wo3.WEAPON_BASE + 4] = 222
        raw[wo3.OFFICER_BASE + equipment.EQUIPPED_ITEM_OFFSET] = 64
        document = wo3.decode(raw)
        view = WO3Presentation(wo3, 'wo3u').dashboard(document)
        groups = sections(view)
        weapon = next(card for card in groups['equipment'].cards if card.id == 'weapon_1')
        attribute = metrics(weapon)['attribute_0']
        self.assertEqual(attribute.label, 'Attribute ID 222')
        self.assertIsNone(attribute.field_id)
        first = metrics(groups['characters'].cards[0])
        self.assertEqual(first['item_0'].value, 'Item ID 64')
        self.assertIsNone(first['item_0'].field_id)
        self.assertIsNone(metrics(weapon)['compatibility'].fraction)
        fields = wo3.field_map(document)
        for section in view.sections:
            for card in section.cards:
                for metric in card.metrics:
                    if metric.field_id:
                        self.assertIn(metric.field_id, fields)

    def test_projection_does_not_stage_serialize_or_modify_snapshot(self):
        raw = self.document.raw
        with patch.object(wo3, 'stage', side_effect=AssertionError('write attempted')), \
                patch.object(wo3, 'serialize', side_effect=AssertionError('write attempted')):
            WO3Presentation(wo3, 'wo3u').dashboard(self.document)
        self.assertEqual(raw, self.document.raw)
        changed = bytearray(self.document.payload)
        changed[wo3.OFFICER_BASE] ^= 1
        with self.assertRaises(SaveError):
            WO3Presentation(wo3, 'wo3u').dashboard(replace(self.document, payload=bytes(changed)))


class NativeDashboardTests(unittest.TestCase):
    def test_optional_native_snapshots_and_all_links(self):
        configured = False
        for env, backend, game_id, presentation in (
                ('DW8XL_SAVE_COPY', dw8, 'dw8xl', DW8XLPresentation),
                ('WO3U_SAVE_COPY', wo3, 'wo3u', WO3Presentation)):
            path = os.environ.get(env)
            if not path:
                continue
            configured = True
            original = Path(path).read_bytes()
            document = backend.read_save(path, game_id)
            view = presentation(backend, game_id).dashboard(document)
            self.assertTrue(sections(view)['characters'].cards)
            fields = backend.field_map(document)
            for section in view.sections:
                for card in section.cards:
                    for metric in card.metrics:
                        if metric.field_id:
                            self.assertIn(metric.field_id, fields)
            self.assertEqual(backend.serialize(document, {}), original)
            self.assertEqual(Path(path).read_bytes(), original)
        if not configured:
            self.skipTest('Optional copied native DW8XL / WO3U saves unavailable.')


class DashboardGameGUIIntegrationTests(unittest.TestCase):
    def test_real_game_dashboard_search_theme_field_navigation_preserves_pending_and_backup(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.addCleanup(root.destroy)
        root.geometry('1400x1000')
        for game_id, raw, suffix, field_id, value, record in (
                ('dw8xl', procedural_equipment(), '.dat', 'officer_0_attack', 123, 82),
                ('wo3u', depth_raw(), '.bin', 'officer_0_attack', 321, 145)):
            with self.subTest(game_id=game_id), tempfile.TemporaryDirectory() as folder:
                source = Path(folder) / ('copy' + suffix)
                source.write_bytes(raw)
                host = ttk.Frame(root)
                host.pack(fill='both', expand=True)
                editor = get_game(game_id).create_editor(root, host)
                try:
                    with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                        self.assertTrue(editor.open_path(source))
                        root.update()
                        self.assertEqual(errors.call_count, 0)
                        self.assertEqual(editor.backup.read_bytes(), raw)
                        view = editor.dashboard_view
                        opened_dashboard = view.dashboard
                        editor.stage_values({field_id: value})
                        expected_changes = dict(editor.changes)
                        expected_history = list(editor.history)
                        editor.workspace_tabs.select(editor.dashboard_page)
                        view.section.set('characters')
                        view.search.set(f'{record}')
                        view._filter()
                        self.assertTrue(view.select_card(f'officer_{record}'))
                        self.assertIn(f'officer_{record}', {card.id for card in view._filtered_cards})
                        view.search.set('')
                        view._filter()
                        self.assertTrue(view.select_card('officer_1'))
                        card = next(card for card in view._filtered_cards if card.id == 'officer_1')
                        target = next(metric for metric in card.metrics if metric.field_id == field_id)
                        for theme in ('Dark', 'Light'):
                            editor.apply_theme(theme)
                            root.update_idletasks()
                            self.assertEqual(view.palette, THEMES[theme])
                            if game_id == 'dw8xl':
                                self.assertTrue(view.canvas.find_withtag('progress-track'))
                        view._navigate(target)
                        self.assertEqual(editor.workspace_tabs.select(), str(editor.edit_page))
                        self.assertEqual(editor.fields.selection(), (field_id,))
                        self.assertEqual(editor.changes, expected_changes)
                        self.assertEqual(editor.history, expected_history)
                        self.assertIs(view.dashboard, opened_dashboard)
                        self.assertEqual(source.read_bytes(), raw)
                        self.assertEqual(editor.backup.read_bytes(), raw)
                        self.assertEqual(errors.call_count, 0)
                finally:
                    host.destroy()
                    root.update()


if __name__ == '__main__':
    unittest.main()
