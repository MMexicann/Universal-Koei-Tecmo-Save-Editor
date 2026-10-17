"""Research correlations remain read-only, natively qualified and bounded."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.deception4_ps3 import parser
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import research_lab as lab
from koei_editor.shared import save_comparison
from tests.test_ps3_new_families import fixture
from tests import test_ps3_expansion


class ResearchLabTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.first, self.second = self.folder / 'first.bin', self.folder / 'second.bin'
        self.first.write_bytes(fixture(parser))
        raw = bytearray(parser.serialize(parser.decode(self.first.read_bytes()), {'warl': 0x10203}))
        raw[-2] ^= 1
        self.second.write_bytes(raw)
        self.metadata = self.folder / 'PARAM.SFO'
        self.metadata.write_bytes(test_ps3_expansion.PS3ContextTests.metadata('NPUB31442-GAMEDATA-10'))
        self.comparison = save_comparison.prepare(parser.GAME_ID, self.first, self.second)

    def test_decoded_runs_windows_and_native_overlap_preserve_every_source_byte(self):
        result = lab.changed_runs(self.comparison)
        self.assertEqual(result['total_runs'], 2)
        self.assertEqual(result['runs'][0]['offset'], 0x20)
        self.assertEqual(result['runs'][0]['length'], 3)
        self.assertEqual({row['id'] for row in result['runs'][0]['mapped_spans']}, {'warl'})
        self.assertEqual(result['runs'][1]['mapped_spans'], [])
        limited = lab.changed_runs(self.comparison, 1)
        self.assertTrue(limited['truncated']); self.assertEqual(limited['total_runs'], 2)
        rows = lab.byte_window(self.comparison, 0x20, 17)
        self.assertEqual(rows[0]['changed_indexes'], [0, 1, 2])
        self.assertEqual(rows[1]['offset'], 0x30)
        self.assertEqual(self.first.read_bytes(), fixture(parser))
        self.assertFalse((self.folder / 'UniversalEditorBackups').exists())

    def test_offset_interpretation_both_endian_signed_float_and_exact_xor(self):
        result = lab.inspect_offset(self.comparison, 0x20, 8)
        row = next(row for row in result['interpretations'] if
                   (row['side'], row['width'], row['byteorder']) == ('second', 4, 'big'))
        self.assertEqual(row['unsigned'], 0x03020100)
        little = next(row for row in result['interpretations'] if
                   (row['side'], row['width'], row['byteorder']) == ('second', 4, 'little'))
        self.assertEqual(little['unsigned'], 0x10203)
        self.assertEqual(result['xor_hex'].split()[:3], ['8a', '02', '01'])
        self.assertGreater(result['changed_bits'], 0)
        self.assertIn('float', little)

    def test_exact_candidate_query_keeps_encoding_ambiguity_and_requires_pair_match(self):
        query = lab.CandidateQuery(137, 0x10203, widths=(4,), byteorder='little')
        result = lab.discover_candidates(self.comparison, query)
        self.assertEqual(result['total_candidates'], 1)
        self.assertEqual(result['candidates'][0]['offset'], 0x20)
        self.assertEqual(result['candidates'][0]['status'], 'unverified_hypothesis')
        self.assertEqual(lab.discover_candidates(self.comparison, replace(query, before=138))['total_candidates'], 0)
        self.assertEqual(lab.discover_candidates(self.comparison, replace(query, byteorder='big'))['total_candidates'], 0)
        self.assertEqual(lab.discover_candidates(self.comparison, replace(query, alignment=3))['total_candidates'], 0)
        self.assertEqual(lab.discover_candidates(self.comparison, replace(query, start=0x21))['total_candidates'], 0)

    def test_signed_candidates_and_truncated_hypotheses_are_explicit(self):
        first, second = bytearray(self.first.read_bytes()), bytearray(self.first.read_bytes())
        for offset in range(0x40, 0x50, 2):
            first[offset:offset + 2] = (-7).to_bytes(2, 'big', signed=True)
            second[offset:offset + 2] = (-6).to_bytes(2, 'big', signed=True)
        self.first.write_bytes(first); self.second.write_bytes(second)
        comparison = save_comparison.prepare(parser.GAME_ID, self.first, self.second)
        query = lab.CandidateQuery(-7, -6, (2,), 'big', True, start=0x40, end=0x50, alignment=2)
        result = lab.discover_candidates(comparison, query, limit=2)
        self.assertEqual(result['total_candidates'], 8)
        self.assertEqual([row['offset'] for row in result['candidates']], [0x40, 0x42])
        self.assertTrue(result['truncated'])

    def test_candidate_validation_rejects_silent_coercions_and_invalid_spans(self):
        query = lab.CandidateQuery(137, 140)
        invalid = (replace(query, before=True), replace(query, after='140'), replace(query, after=137),
                   replace(query, widths=(3,)), replace(query, widths=(1, 1)), replace(query, widths=[4]),
                   replace(query, signed=1), replace(query, byteorder='native'), replace(query, start=-1),
                   replace(query, end=10**9), replace(query, end=True), replace(query, alignment=0),
                   replace(query, before=10**40, after=10**41), replace(query, start=200, end=100))
        for item in invalid:
            with self.subTest(query=item), self.assertRaises(SaveError):
                lab.discover_candidates(self.comparison, item)
        for offset, length in ((-1, 8), (True, 8), (0, 0), (0, 4097), (10**9, 1)):
            with self.subTest(span=(offset, length)), self.assertRaises(SaveError):
                lab.byte_window(self.comparison, offset, length)

    def test_annotations_require_bounded_spans_text_and_exact_types(self):
        note = lab.Annotation(0x20, 4, 'Controlled currency action', 'Known resource changed', 'Repeat in game')
        self.assertEqual(lab.validate_annotations(self.comparison, (note,)), (note,))
        for notes in ([note], (None,), (replace(note, offset=True),), (replace(note, length=0),),
                      (replace(note, title=''),), (replace(note, observation='\0'),),
                      (replace(note, evidence='x' * 4097),), (note,) * 201):
            with self.subTest(notes=str(notes)[:80]), self.assertRaises(SaveError):
                lab.validate_annotations(self.comparison, notes)

    def test_report_is_structured_private_research_without_paths_or_companion_metadata(self):
        destination = self.folder / 'research.json'
        query = lab.CandidateQuery(137, 0x10203, (4,))
        note = lab.Annotation(0x20, 4, 'Observation', 'Resource correlation', 'Controlled pair')
        self.assertEqual(lab.export(self.comparison, destination, annotations=(note,),
                         action='One controlled purchase', query=query, offset=0x20), destination.resolve())
        text = destination.read_text(encoding='utf-8'); result = json.loads(text)
        self.assertEqual(result['schema'], 'koei-save-research')
        self.assertEqual(result['offset_space'], 'decoded_payload')
        self.assertTrue(result['read_only'])
        self.assertEqual(result['candidate_search']['total_candidates'], 1)
        self.assertEqual(result['annotations'][0]['evidence'], 'Controlled pair')
        for private in (str(self.folder), 'PARAM.SFO', 'NPUB31442', self.first.name, 'context_digest'):
            self.assertNotIn(private, text)
        self.assertNotIn('raw', result)

    def test_forged_snapshots_rows_and_unqualified_profiles_cannot_be_researched(self):
        for forged in (replace(self.comparison, changed_payload_bytes=0),
                       replace(self.comparison, game_id='dw3'),
                       replace(self.comparison, left=replace(self.comparison.left, payload=b'broken'))):
            for operation in (lab.changed_runs, lab.byte_window, lab.report):
                with self.subTest(operation=operation, forged=forged.game_id), self.assertRaises(SaveError):
                    operation(forged)

    def test_stale_sources_metadata_existing_outputs_and_non_json_never_write(self):
        output = self.folder / 'research.json'; output.write_text('existing', encoding='utf-8')
        with self.assertRaises(FileExistsError): lab.export(self.comparison, output)
        self.assertEqual(output.read_text(encoding='utf-8'), 'existing')
        with self.assertRaises(SaveError): lab.export(self.comparison, self.folder / 'research.bin')
        for source in (self.first, self.metadata):
            raw = source.read_bytes(); source.write_bytes(raw + b'changed')
            with self.assertRaises(SaveError): lab.export(self.comparison, self.folder / 'stale.json')
            self.assertFalse((self.folder / 'stale.json').exists()); source.write_bytes(raw)

    def test_source_race_removes_only_unchanged_report_and_keeps_foreign_replacement(self):
        for replace_report in (False, True):
            output = self.folder / ('replaced.json' if replace_report else 'race.json')
            original, source = lab.atomic_new, self.second.read_bytes()
            def changed(raw, destination):
                original(raw, destination); self.second.write_bytes(b'changed')
                if replace_report: destination.write_bytes(b'foreign replacement')
            with patch.object(lab, 'atomic_new', side_effect=changed), self.assertRaises(SaveError):
                lab.export(self.comparison, output)
            if replace_report:
                self.assertEqual(output.read_bytes(), b'foreign replacement')
            else:
                self.assertFalse(output.exists())
            self.second.write_bytes(source)
