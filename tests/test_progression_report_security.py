"""Adversarial report checks use display snapshots without accessing saves."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from koei_editor.shared.progression import (
    DashboardCard as Card, DashboardMetric as Metric,
    DashboardSection as Section, ProgressionDashboard as Dashboard,
)
from koei_editor.shared.progression_report import export_report, render_report
from koei_editor.shared import progression_report


class ParsedReport(HTMLParser):
    def __init__(self, document):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.snapshot = ''
        self.in_snapshot = False
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))
        self.in_snapshot = tag == 'script' and dict(attrs).get('id') == 'snapshot'

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_snapshot = False

    def handle_data(self, data):
        if self.in_snapshot:
            self.snapshot += data

    @property
    def data(self):
        return json.loads(self.snapshot)


def report_snapshot():
    return Dashboard('Snapshot', (
        Section('shown', 'Characters', (
            Card('first', 'First officer', metrics=(
                Metric('xp', 'Stored XP', '999999'),
                Metric('near', 'Mapped gallery', '999999', current=999999, total=1000000),
                Metric('small', 'Mapped count', '1', current=1, total=1000000),
                Metric('odd', 'Unusual level', '101', current=101, total=100),
            )),
            Card('second', 'Second officer', metrics=(Metric('gold', 'Gold', '42'),)),
        )),
        Section('private', 'Omitted content', (
            Card('not-shared', 'Secret character label', 'Secret subtitle', (
                Metric('hidden', 'Secret metric label', 'Secret value', note='Secret evidence note'),
            ), search_text='Secret search keywords'),
        ), 'Secret section note'),
    ))


class ProgressionReportSecurityTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'JavaScript comparison check requires optional Node.js')
    def test_report_comparison_rejects_ambiguous_labels_and_keeps_record_values(self):
        first = Card('first', 'First', metrics=(Metric('a', 'Attack', '10'),
                    Metric('b', 'Attack', '20'), Metric('hp', 'Health', '30', unit='%')))
        second = Card('second', 'Second', metrics=(Metric('c', 'Attack', '40'),
                     Metric('hp', 'Health', '50')))
        snapshot = Dashboard('Duplicates', (Section('s', 'Records', (first, second)),))
        cards = ParsedReport(render_report(snapshot, comparison_ids=('first', 'second'))).data['cards']
        self.assertEqual([m['value'] for m in cards[0]['metrics']], ['10', '20', '30'])
        function = re.search(r'(function comparisonRows.*?)(?=\nfunction renderComparison)',
                             progression_report._SCRIPT, re.S).group(1)
        program = function + '\nconsole.log(JSON.stringify(comparisonRows(JSON.parse(process.argv[1]))));'
        def rows(selected):
            result = subprocess.run([shutil.which('node'), '-e', program, json.dumps(selected)],
                                    check=True, capture_output=True, text=True, timeout=10)
            return json.loads(result.stdout)
        for selected in (cards, list(reversed(cards))):
            actual = rows(selected)
            attack = next(row for row in actual if row['label'] == 'Attack')
            self.assertTrue(attack['ambiguous'])
            self.assertEqual(attack['cells'], [{'status': 'ambiguous'}] * 2)
            for health in (row for row in actual if row['label'] == 'Health'):
                self.assertFalse(health['ambiguous'])
                self.assertEqual(sorted(cell['status'] for cell in health['cells']), ['mapped', 'missing'])
        unique = next(row for row in rows(cards[1:]) if row['label'] == 'Attack')
        self.assertFalse(unique['ambiguous'])
        self.assertEqual(unique['cells'][0]['metric']['value'], '40')

    def test_exact_endpoints_survive_float_ratio_rounding_and_underflow(self):
        metrics = (
            Metric('near', 'Large count', str(10 ** 20 - 1), current=10 ** 20 - 1, total=10 ** 20),
            Metric('tiny', 'Small range', '1e-308', current=1e-308, total=1e308),
            Metric('full', 'Full range', '1', current=1, total=1.0),
            Metric('zero', 'Zero range', '0', current=0.0, total=10),
        )
        snapshot = Dashboard('Exact ranges', (Section('s', 'Ranges', (Card('c', 'Ranges', metrics=metrics),)),))
        rendered = ParsedReport(render_report(snapshot)).data['cards'][0]['metrics']
        self.assertEqual(rendered[0]['fraction'], 1.0)
        self.assertFalse(rendered[0]['atTarget'])
        self.assertEqual(rendered[1]['fraction'], 0.0)
        self.assertFalse(rendered[1]['atZero'])
        self.assertTrue(rendered[2]['atTarget'])
        self.assertTrue(rendered[3]['atZero'])

    def test_template_markers_in_presentation_text_are_preserved_literally(self):
        title = '__TITLE__ __NOTE__ __STYLE__ __SCRIPT__ __DATA__'
        result = render_report(Dashboard(title, note=title))
        self.assertIn('<h1>' + title + '</h1>', result)
        self.assertIn('<p class="intro">' + title + '</p>', result)
        self.assertEqual(len([tag for tag, _ in ParsedReport(result).elements if tag == 'script']), 2)

    def test_every_display_string_remains_inert_even_when_it_contains_script_end_tags(self):
        hostile = '</script><img src="https://invalid.example/x" onerror="alert(1)"><script>alert(2)</script>&\u2028'
        snapshot = Dashboard(hostile, (Section(hostile, hostile, (
            Card(hostile, hostile, hostile, (Metric(hostile, hostile, hostile,
                unit=hostile, note=hostile, field_id=hostile),), search_text=hostile),
        ), hostile),), hostile)
        report = render_report(snapshot, comparison_ids=(hostile,))
        parsed = ParsedReport(report)
        self.assertEqual(len([tag for tag, _ in parsed.elements if tag == 'script']), 2)
        self.assertFalse(any(tag in ('img', 'iframe', 'object', 'embed', 'form', 'a')
                             for tag, _ in parsed.elements))
        self.assertFalse(any(key.lower().startswith('on') for _, attrs in parsed.elements for key in attrs))
        metric = parsed.data['cards'][0]['metrics'][0]
        self.assertEqual((metric['label'], metric['value'], metric['unit'], metric['note']), (hostile,) * 4)
        self.assertNotIn('field_id', metric)

    def test_omitted_sections_are_removed_from_the_embedded_payload_including_search_and_notes(self):
        report = render_report(report_snapshot(), section_ids=('shown',))
        self.assertNotIn('Secret', report)
        data = ParsedReport(report).data
        self.assertEqual([s['id'] for s in data['sections']], ['shown'])
        self.assertEqual([c['id'] for c in data['cards']], ['first', 'second'])
        with self.assertRaises(ValueError):
            render_report(report_snapshot(), section_ids=('shown',), comparison_ids=('not-shared',))

    def test_unverified_or_unusual_numbers_never_gain_chart_denominators(self):
        data = ParsedReport(render_report(report_snapshot())).data
        metrics = {m['id']: m for m in data['cards'][0]['metrics']}
        for key in ('xp', 'odd'):
            self.assertIsNone(metrics[key]['fraction'])
            self.assertIsNone(metrics[key]['current'])
            self.assertIsNone(metrics[key]['total'])
        self.assertEqual(metrics['near']['fraction'], .999999)
        self.assertEqual(metrics['small']['fraction'], .000001)
        self.assertEqual(metrics['odd']['value'], '101')

    def test_standalone_report_has_no_external_assets_or_executable_field_links(self):
        parsed = ParsedReport(render_report(report_snapshot()))
        for tag, attrs in parsed.elements:
            with self.subTest(tag=tag):
                self.assertNotIn('src', attrs)
                self.assertNotIn('href', attrs)
                self.assertNotIn('action', attrs)
        self.assertTrue(any(tag == 'meta' and attrs.get('http-equiv') == 'Content-Security-Policy'
                            for tag, attrs in parsed.elements))

    def test_unknown_selections_and_comparison_overflow_fail_explicitly(self):
        snapshot = Dashboard('Many', (Section('s', 'Records', tuple(
            Card(str(i), f'Officer {i}') for i in range(5))),))
        for options in ({'section_ids': ('missing',)}, {'comparison_ids': ('missing',)},
                        {'comparison_ids': tuple(str(i) for i in range(5))}, {'theme': 'Unknown'}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                render_report(snapshot, **options)
        data = ParsedReport(render_report(snapshot, comparison_ids=('1', '1', '2'))).data
        self.assertEqual(data['comparisons'], ['1', '2'])

    def test_export_creates_verified_html_without_replacing_an_existing_report(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'progression.html'
            result = export_report(report_snapshot(), destination, section_ids=('shown',), theme='Dark')
            self.assertEqual(result, destination.resolve())
            original = destination.read_bytes()
            self.assertEqual(ParsedReport(original.decode('utf-8')).data['theme'], 'Dark')
            with self.assertRaises(FileExistsError):
                export_report(Dashboard('Replacement'), destination)
            self.assertEqual(destination.read_bytes(), original)
            invalid = Path(directory) / 'save.dat'
            with self.assertRaises(ValueError):
                export_report(report_snapshot(), invalid)
            self.assertFalse(invalid.exists())


if __name__ == '__main__':
    unittest.main()
