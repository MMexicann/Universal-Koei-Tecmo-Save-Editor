"""Generic dashboards retain mapped evidence without inventing progression."""
from collections import Counter
from dataclasses import dataclass
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from koei_editor.shared.progression_generic import METRICS_PER_CARD, generic_dashboard
from koei_editor.shared.scalar_presentation import ScalarPresentation


@dataclass(frozen=True)
class OpenedField:
    id: str
    label: str
    opened: int | str
    group: str = 'Resources'
    slot: int = 0
    maximum: int = 255
    minimum: int = 0

    def value(self, payload):
        if payload != b'opened':
            raise AssertionError('Only the immutable opened payload should be read.')
        return self.opened

    def validate(self, value):
        raise AssertionError('Displaying an unusual original must not validate it as an edit.')


def project(fields, *, record_label=None, layout=None):
    backend = SimpleNamespace(fields_for=Mock(return_value=tuple(fields)))
    if record_label is not None:
        backend.record_label = record_label
    document = SimpleNamespace(payload=b'opened', raw=b'original',
                               format=layout or SimpleNamespace(title='Verified title'))
    presentation = ScalarPresentation(backend, 'fixture')
    return generic_dashboard(document, backend, presentation), backend, document


def metrics(dashboard):
    return tuple(metric for section in dashboard.sections
                 for card in section.cards for metric in card.metrics)


class GenericProgressionTests(unittest.TestCase):
    def test_typed_opened_values_keep_unusual_originals_and_no_derived_bars(self):
        fields = (
            OpenedField('gold', 'Gold', 1234567),
            OpenedField('name', 'Name', '007'),
            OpenedField('negative', 'Signed native value', -500),
            OpenedField('above', 'Unusual original', 99999, maximum=99),
            OpenedField('empty', 'Empty name', ''),
        )
        dashboard, backend, document = project(fields)
        values = metrics(dashboard)
        self.assertEqual([metric.value for metric in values],
                         ['1,234,567', '007', '-500', '99,999', ''])
        self.assertEqual([metric.field_id for metric in values], [field.id for field in fields])
        self.assertTrue(all(metric.current is None and metric.total is None
                            and metric.fraction is None for metric in values))
        backend.fields_for.assert_called_once_with(document)
        self.assertEqual(document.payload, b'opened')
        self.assertEqual(document.raw, b'original')

    def test_duplicate_names_labels_and_ids_never_collapse_records_or_metrics(self):
        fields = (
            OpenedField('same', 'Attack', 10, 'Officers', 1),
            OpenedField('same', 'Attack', 20, 'Officers', 1),
            OpenedField('another', 'Attack', 30, 'Officers', 2),
            OpenedField('weapon', 'Attack', 40, 'Weapons', 1),
        )
        dashboard, _, _ = project(fields, record_label=lambda slot, group: 'Same name')
        cards = tuple(card for section in dashboard.sections for card in section.cards)
        self.assertEqual([section.title for section in dashboard.sections], ['Officers', 'Weapons'])
        self.assertEqual([len(card.metrics) for card in cards], [2, 1, 1])
        self.assertEqual(len({card.id for card in cards}), 3)
        self.assertEqual(len({metric.id for metric in metrics(dashboard)}), 4)
        self.assertEqual([metric.value for metric in metrics(dashboard)], ['10', '20', '30', '40'])
        self.assertIn('Record 2', cards[1].subtitle)

    def test_large_profiles_bound_card_height_without_losing_any_fields(self):
        fields = tuple(OpenedField(f'item-{index}', f'Quantity {index}', index,
                                   'Existing inventory') for index in range(5003))
        dashboard, _, _ = project(fields)
        cards = dashboard.sections[0].cards
        self.assertTrue(all(0 < len(card.metrics) <= METRICS_PER_CARD for card in cards))
        self.assertGreater(len(cards), 400)
        self.assertEqual([metric.field_id for metric in metrics(dashboard)],
                         [field.id for field in fields])
        self.assertEqual(cards[-1].metrics[-1].value, '5,002')
        self.assertIn('Part 1 of ', cards[0].subtitle)

    def test_all_fields_are_searchable_including_native_identity_and_opened_value(self):
        dashboard, _, _ = project((OpenedField('native-id', 'Quantity', 2450, 'Materials', 8),),
                                   record_label=lambda slot, group: 'Named item')
        card = dashboard.sections[0].cards[0]
        for text in ('Materials', 'Named item', '8', 'native-id', 'Quantity', '2,450'):
            self.assertIn(text, card.search_text)

    def test_identity_labels_with_separators_do_not_collide_and_are_stable(self):
        fields = (OpenedField('same', 'Value', 1, 'A:1', 2),
                  OpenedField('same', 'Value', 2, 'A', 12),
                  OpenedField('other', 'Value', 3, '英雄', 1))
        first, _, _ = project(fields)
        second, _, _ = project(fields)
        self.assertEqual(first, second)
        self.assertEqual(len({section.id for section in first.sections}), 3)
        self.assertEqual(len({card.id for section in first.sections for card in section.cards}), 3)

    def test_empty_qualified_document_is_a_complete_empty_dashboard(self):
        dashboard, _, _ = project(())
        self.assertEqual(dashboard.title, 'Verified title')
        self.assertEqual(dashboard.sections, ())
        self.assertIn('Read-only', dashboard.note)

    def test_layout_name_fallback_and_empty_group_are_readable(self):
        dashboard, _, _ = project((OpenedField('a', 'Value', 1, ''),),
                                   layout=SimpleNamespace(name='Native format name'))
        self.assertEqual(dashboard.title, 'Native format name')
        self.assertEqual(dashboard.sections[0].title, 'Mapped fields')

    def test_parser_rejection_propagates_without_alternative_data(self):
        backend = SimpleNamespace(fields_for=Mock(side_effect=ValueError('Wrong exact profile')))
        document = SimpleNamespace(payload=b'not validated')
        with self.assertRaisesRegex(ValueError, 'Wrong exact profile'):
            generic_dashboard(document, backend, ScalarPresentation(backend, 'fixture'))
        backend.fields_for.assert_called_once_with(document)


class RegisteredGenericProjectionTests(unittest.TestCase):
    def test_representative_registered_profiles_preserve_every_native_field(self):
        from koei_editor.game_registry import get_game
        from tests.test_atelier_sophie2_format import procedural_raw as sophie_raw
        from tests.test_dw4hyper_format import procedural_raw as hyper_raw
        from tests.test_verified_editors import synthetic_raw

        cases = (('dw8xl', lambda: synthetic_raw('dw8xl')),
                 ('pw3', lambda: synthetic_raw('pw3')),
                 ('dw4hyper', hyper_raw), ('atelier_sophie2', sophie_raw))
        for game_id, fixture in cases:
            with self.subTest(game_id=game_id):
                adapter = get_game(game_id).get_scalar_adapter()
                document = adapter.decode(fixture())
                fields = adapter.fields_for(document)
                dashboard = generic_dashboard(document, adapter.backend,
                    ScalarPresentation(adapter.backend, game_id))
                projected = metrics(dashboard)
                self.assertEqual(Counter(metric.field_id for metric in projected),
                                 Counter(field.id for field in fields))
                source = {field.id: field.value(document.payload) for field in fields}
                for metric in projected:
                    value = source[metric.field_id]
                    self.assertEqual(metric.value, f'{value:,}' if type(value) is int else str(value))
                    self.assertIsNone(metric.fraction)
                self.assertEqual(adapter.serialize(document, {}), document.raw)


if __name__ == '__main__':
    unittest.main()
