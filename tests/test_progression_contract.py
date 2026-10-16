"""Read-only projections retain snapshots and reject unsupported progress ranges."""
from dataclasses import FrozenInstanceError
import unittest

from koei_editor.shared.progression import (
    DashboardMetric, DashboardCard, DashboardSection, ProgressionDashboard,
)


class ProgressionContractTests(unittest.TestCase):
    def test_explicit_denominator_only_and_unusual_values_are_not_clamped(self):
        self.assertIsNone(DashboardMetric('xp', 'XP', '123').fraction)
        for current, total in ((None, 10), (3, None), (-1, 10), (11, 10), (0, 0),
                               (True, 10), (1, False), (float('nan'), 1),
                               (1, float('inf')), (10 ** 1000, 10 ** 1001), ('1', 10)):
            with self.subTest(current=current, total=total):
                self.assertIsNone(DashboardMetric('m', 'Metric', str(current),
                                                current=current, total=total).fraction)
        self.assertEqual(DashboardMetric('p', 'Peace', '5000', current=5000, total=10000).fraction, .5)
        self.assertEqual(DashboardMetric('c', 'Collection', '0', current=0, total=60).fraction, 0)
        unusual = DashboardMetric('u', 'Stored XP', '999999999', current=999999999, total=10)
        self.assertEqual(unusual.value, '999999999')
        self.assertIsNone(unusual.fraction)

    def test_frozen_snapshot_does_not_retain_mutable_input_collections(self):
        metric = DashboardMetric('gold', 'Gold', '123', field_id='gold')
        metrics = [metric]
        card = DashboardCard('wallet', 'Resources', metrics=metrics)
        cards = [card]
        section = DashboardSection('r', 'Resources', cards)
        sections = [section]
        dashboard = ProgressionDashboard('Snapshot', sections)
        metrics.clear(); cards.clear(); sections.clear()
        self.assertEqual(dashboard.sections[0].cards[0].metrics, (metric,))
        with self.assertRaises(FrozenInstanceError):
            metric.value = '456'
        self.assertFalse(hasattr(dashboard, 'document'))
        self.assertFalse(hasattr(dashboard, 'backend'))
        with self.assertRaises(TypeError):
            DashboardMetric('mutable', 'Value', ['123'])
        with self.assertRaises(TypeError):
            DashboardMetric('mutable-link', 'Value', '123', field_id=['gold'])


if __name__ == '__main__':
    unittest.main()
