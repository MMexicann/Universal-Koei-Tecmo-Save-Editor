"""Game dashboard summaries retain mapped scope and saved relationships."""
import unittest

from koei_editor.games.dw3 import progression_dashboard, save_writer
from koei_editor.games.dw8xl.dashboard import dashboard as dw8_dashboard
from koei_editor.games.wo3u.dashboard import dashboard as wo3_dashboard
from koei_editor.games.wo3u import wo3u_equipment, wo3u_parser
from koei_editor.games.origins import origins_codec, origins_dashboard, origins_parser, origins_weapons
from koei_editor.shared import verified_editor
from tests.test_dw8_weapon_order import procedural_equipment
from tests.test_experimental_dw3_core import equipment_document
from tests.test_origins_parser import fixture
from tests.test_origins_weapons import inventory, record
from tests.test_wo3u_depth import depth_raw


def cards(view, section):
    return {card.id: card for group in view.sections if group.id == section for card in group.cards}


def metrics(card):
    return {metric.id: metric for metric in card.metrics}


class GameDashboardContextTests(unittest.TestCase):
    def test_dw8_inventory_backlinks_preserve_duplicate_and_unresolved_references(self):
        document = verified_editor.decode(procedural_equipment(), 'dw8xl')
        view = dw8_dashboard(verified_editor, document)
        overview = metrics(cards(view, 'overview')['equipment-snapshot'])
        weapons = verified_editor.weapons(document)
        known = {row['slot'] for row in weapons}
        progressions = verified_editor.progressions(document)
        unresolved = sum(slot not in known for row in progressions for slot in row['weapon_slots'])
        self.assertEqual(overview['unresolved'].value, str(unresolved))
        self.assertTrue(all(metric.fraction is None for metric in overview.values()))
        first = cards(view, 'equipment')['weapon_1']
        references = metrics(first)['references'].value
        self.assertIn('Officer 1 · weapon 1', references)
        self.assertIn('Officer 2 · weapon 1', references)
        self.assertIn('Officer 2 · weapon 2', references)
        self.assertIn('Officer 2', first.search_text)
        self.assertEqual(verified_editor.serialize(document, {}), document.raw)

    def test_wo3_unowned_reference_keeps_rank_and_ownership_separate(self):
        raw = bytearray(depth_raw())
        raw[wo3u_parser.OFFICER_BASE + wo3u_equipment.EQUIPPED_ITEM_OFFSET] = 3
        document = wo3u_parser.decode(raw)
        view = wo3_dashboard(wo3u_parser, document)
        officer = metrics(cards(view, 'characters')['officer_1'])
        self.assertEqual(officer['item_0'].value, 'Item ID 3')
        self.assertIsNone(officer['item_0'].field_id)
        self.assertEqual(officer['item_0_state'].value, 'Not owned · stored rank 1')
        self.assertIsNone(officer['item_0_state'].fraction)
        ownership = metrics(cards(view, 'overview')['item-snapshot'])
        self.assertEqual(ownership['owned-Ordinary item'].value, '3')
        self.assertEqual(ownership['owned-Mount'].value, '1')
        self.assertEqual(wo3u_parser.serialize(document, {}), bytes(raw))

    def test_dw3_roster_scope_and_weapon_backlinks_do_not_use_stats_as_completion(self):
        document = equipment_document()
        view = progression_dashboard.dashboard(document)
        roster = metrics(cards(view, 'overview')['character-snapshot'])
        flags = document.properties['CanUseCharaArray']['value']['values']
        self.assertEqual(roster['unlocked'].total, min(len(flags), len(cards(view, 'characters'))))
        weapon = metrics(cards(view, 'equipment')['weapon-0'])
        self.assertIn(cards(view, 'characters')['officer-0'].title, weapon['references'].value)
        self.assertTrue(all(metric.fraction is None
                            for card in cards(view, 'characters').values() for metric in card.metrics))
        self.assertEqual(save_writer.serialize(document)[0], document.encrypted)

    def test_origins_copy_counts_exclude_empty_reserved_and_unknown_proficiency(self):
        original = origins_parser.decode(fixture())
        payload = bytearray(original.payload)
        weapon_payload = inventory(original.revision)
        record(weapon_payload, original.revision, 0, 1, 9)
        record(weapon_payload, original.revision, 1, 1, 255)  # Preserve unusual reinforcement.
        record(weapon_payload, original.revision, 850, 1, 99)  # Reserved, excluded.
        start = origins_weapons.BASES[original.revision]
        payload[start:len(weapon_payload)] = weapon_payload[start:]
        document = origins_parser.decode(origins_codec.encode(payload, original.seed, 'slot'))
        view = origins_dashboard.dashboard(origins_parser, document)
        snapshot = metrics(cards(view, 'overview')['equipment-snapshot'])
        self.assertEqual(snapshot['copies'].value, '2')
        self.assertEqual(snapshot['identities'].value, '1')
        self.assertEqual(snapshot['reinforcement'].value, '+255')
        self.assertIsNone(snapshot['reinforcement'].fraction)
        weapons = cards(view, 'equipment')
        self.assertEqual(metrics(weapons['weapon-0'])['copies'].value, '2')
        unusual = metrics(weapons['weapon-1'])['reinforcement']
        self.assertEqual(unusual.value, '255')
        self.assertIsNone(unusual.field_id)
        self.assertIsNone(unusual.fraction)
        self.assertEqual(metrics(cards(view, 'overview')['progression-scope'])['proficiencies'].value, 'Unavailable')
        self.assertEqual(origins_parser.serialize(document, {}), document.raw)


if __name__ == '__main__':
    unittest.main()
