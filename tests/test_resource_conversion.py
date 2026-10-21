"""Resource-only routes: semantic values and complete retained payload checks.

Generated inputs establish software behavior, not converted in-game loading.
"""
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
import os
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from koei_editor import conversion as c
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import experimental_limits


@lru_cache(maxsize=8)
def fixture(endpoint_id, variant=0):
    if endpoint_id == 'wo3u':
        from tests.test_wo3u_format import procedural_raw
        raw = procedural_raw()
    elif endpoint_id == 'wo3u_ps3':
        from tests.test_wo3u_ps3 import fixture as ps3_fixture
        raw = ps3_fixture()
    elif endpoint_id == 'samurai4dx':
        from tests.test_samurai4dx_format import procedural_raw
        raw = procedural_raw()
    elif endpoint_id == 'sw4_ps3':
        from tests.test_ps3_expansion import fixture as ps3_fixture
        raw = ps3_fixture(c.ENDPOINTS[endpoint_id].backend)
    else:
        raise AssertionError(endpoint_id)
    backend = c.ENDPOINTS[endpoint_id].backend
    document = backend.decode(raw)
    transfer = c._FAMILIES[c.ENDPOINTS[endpoint_id].family]
    values = {'growth_points': 7654321 - variant, 'gems': 654321 - variant,
              'gold': 654321 - variant, **{f'gem_{i}': 12 + 7 * i + variant for i in range(8)}}
    return backend.serialize(document, {key: values[key] for key in transfer.keys})


class ResourceConversionTests(unittest.TestCase):
    def test_all_directions_numeric_values_and_complete_destination_remainder(self):
        from tests.test_conversion import write_copy
        routes = [route for route in c.ROUTES if route.transfer_scope == 'mapped-resources-only']
        self.assertEqual(len(routes), 4)
        for route in routes:
            with self.subTest(route=route.id), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                source = write_copy(folder / 'source', route.source_id)
                template = write_copy(folder / 'template', route.target_id, 1)
                plan = c.prepare(route.id, source, template)
                transfer = c._transform(route)
                backend = c.ENDPOINTS[route.target_id].backend
                output, backups, receipt = c.export(plan, folder / 'converted')
                reopened = backend.read_save(output)
                original = plan.template.document
                allowed = set()
                for key in transfer.keys:
                    source_field = c.ENDPOINTS[route.source_id].backend.field_map(plan.source.document)[key]
                    target_field = backend.field_map(reopened)[key]
                    self.assertEqual(target_field.value(reopened.payload), source_field.value(plan.source.document.payload))
                    allowed.update(range(target_field.offset, target_field.offset + target_field.size))
                integrity = getattr(backend, 'SERIALIZED_INTEGRITY_RANGES', ())
                if not integrity:
                    integrity = tuple((offset, offset + 4) for offset in getattr(backend, 'CHECKSUM_OFFSETS', ()))
                for start, end in integrity:
                    allowed.update(range(start, end))
                touched = {i for i, (a, b) in enumerate(zip(original.payload, reopened.payload)) if a != b}
                self.assertTrue(touched)
                self.assertLessEqual(touched, allowed)
                self.assertEqual(len(original.payload), len(reopened.payload))
                if route.target_id == 'samurai4dx':
                    self.assertEqual(reopened.raw[:0x20C], original.raw[:0x20C])
                    self.assertEqual(reopened.seed, original.seed)
                self.assertEqual([path.read_bytes() for path in backups],
                                 [source.read_bytes(), template.read_bytes()])
                self.assertEqual(receipt['transfer_scope'], 'mapped-resources-only')
                self.assertEqual(receipt['gameplay_bytes'], 8 if route.source_id.startswith('wo3u') else 4)
                self.assertTrue(any('→' in note for note in plan.notes))
                reverse = c.prepare(route.target_id + '-to-' + route.source_id, output, source)
                self.assertEqual(reverse.raw, source.read_bytes())

    def test_higher_opened_balances_use_destination_limits_and_preserve_exact_noops(self):
        pc, ps3 = c.ENDPOINTS['wo3u'].backend, c.ENDPOINTS['wo3u_ps3'].backend
        source = pc.decode(pc.serialize(pc.decode(fixture('wo3u')), {'gems': 1000000}))
        target_raw = bytearray(fixture('wo3u_ps3'))
        target_raw[0x137C:0x1380] = (1000000).to_bytes(4, 'little')
        transfer = c._FAMILIES['wo3u']
        with experimental_limits(True), self.assertRaises(SaveError):
            transfer.encode(source, ps3.decode(fixture('wo3u_ps3')))
        target = ps3.decode(bytes(target_raw))
        self.assertEqual(transfer.encode(source, target), target.raw)
        raw = transfer.encode(target, pc.decode(fixture('wo3u')))
        self.assertEqual(pc.field_map(pc.decode(raw))['gems'].value(pc.decode(raw).payload), 1000000)
        self.assertEqual(source.payload[0x137C:0x1380], (1000000).to_bytes(4, 'little'))
        with self.assertRaises(SaveError):
            transfer.encode(source, c.ENDPOINTS['sw4_ps3'].backend.decode(fixture('sw4_ps3')))

    def test_native_corruption_foreign_metadata_stale_reviews_and_races_block_exports(self):
        from tests.test_conversion import write_copy
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = write_copy(folder / 'source', 'sw4_ps3')
            template = write_copy(folder / 'template', 'samurai4dx')
            raw = source.read_bytes()
            damaged = bytearray(raw)
            damaged[0x7842] ^= 1
            source.write_bytes(damaged)
            with self.assertRaises(SaveError):
                c.prepare('sw4_ps3-to-samurai4dx', source, template)

            source.write_bytes(raw)
            plan = c.prepare('sw4_ps3-to-samurai4dx', source, template)
            with self.assertRaises(SaveError):
                c.export(replace(plan, notes=()), folder / 'forged')
            backend = c.ENDPOINTS['sw4_ps3'].backend
            original_backup = backend.backup
            def race(document):
                result = original_backup(document)
                context = source.parent / 'PARAM.SFO'
                context.write_bytes(context.read_bytes() + b'\0')
                return result
            with patch.object(backend, 'backup', side_effect=race), self.assertRaises(SaveError):
                c.export(plan, folder / 'raced')
            self.assertFalse((folder / 'raced').exists())
            context = source.parent / 'PARAM.SFO'
            context.write_bytes(context.read_bytes().replace(b'NPUB31564', b'NPUB31505'))
            with self.assertRaises(SaveError):
                c.prepare('sw4_ps3-to-samurai4dx', source, template)

    def test_cli_dry_run_and_mixed_family_batch_export(self):
        from tests.test_conversion import write_copy
        from koei_editor.shared import batch_conversion as batch
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            pairs = (('wo3u_ps3', 'wo3u', ''), ('samurai4dx', 'sw4_ps3', ''),
                     ('dw8xl_ps4', 'dw8xl_vita', ''), ('wo3u_ps4', 'wo3u', 'ps4-materials'),
                     ('wo3u_ps4', 'wo3u', 'ps4-stats-materials'))
            specs = []
            for index, (source_id, target_id, variant) in enumerate(pairs):
                source = write_copy(folder / str(index) / 'source', source_id)
                template = write_copy(folder / str(index) / 'template', target_id, 1)
                specs.append(batch.JobSpec(str(index), source_id + '-to-' + target_id + ('-' + variant if variant else ''),
                                           source, template, folder / ('out' + str(index))))
            spec = specs[0]
            result = subprocess.run([sys.executable, '-m', 'koei_editor', '--convert', spec.route,
                                     '--source', str(spec.source), '--template', str(spec.template), '--dry-run'],
                                    capture_output=True, text=True, cwd=folder, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['dry_run'])
            self.assertFalse(any(folder.rglob('UniversalEditorBackups')))
            prepared = batch.prepare_specs(tuple(specs))
            outcomes = batch.execute(prepared)
            report = batch.outcome_report(prepared, outcomes)
            self.assertTrue(report['success'])
            self.assertEqual(report['completed'], 5)



class NativeResourceConversionTests(unittest.TestCase):
    def test_optional_native_copied_exports(self):
        pairs = (('WO3U_SAVE_COPY', 'WO3U_PS3_COPY', 'wo3u', 'wo3u_ps3'),
                 ('SW4DX_SAVE_COPY', 'SW4_PS3_US_COPY', 'samurai4dx', 'sw4_ps3'))
        available = [pair for pair in pairs if all(os.environ.get(key) for key in pair[:2])]
        if not available:
            self.skipTest('Paired native copies with original PS3 metadata not supplied.')
        for pc_key, ps3_key, pc_id, ps3_id in available:
            for source_id, target_id, source, target in (
                    (ps3_id, pc_id, os.environ[ps3_key], os.environ[pc_key]),
                    (pc_id, ps3_id, os.environ[pc_key], os.environ[ps3_key])):
                with self.subTest(route=source_id + '-to-' + target_id), tempfile.TemporaryDirectory() as temporary:
                    route_id = source_id + '-to-' + target_id
                    source_doc = c.ENDPOINTS[source_id].backend.read_save(source)
                    target_doc = c.ENDPOINTS[target_id].backend.read_save(target)
                    transform = c._transform(c.get_route(route_id))
                    source_fields = c.ENDPOINTS[source_id].backend.field_map(source_doc)
                    target_fields = c.ENDPOINTS[target_id].backend.field_map(target_doc)
                    assignments = {key: source_fields[key].value(source_doc.payload) for key in transform.keys}
                    blocked = any(value != target_fields[key].value(target_doc.payload)
                                  and not target_fields[key].minimum <= value <= target_fields[key].maximum
                                  for key, value in assignments.items())
                    if blocked:
                        with self.assertRaises(SaveError):
                            c.prepare(route_id, source, target)
                        continue
                    plan = c.prepare(source_id + '-to-' + target_id, source, target)
                    output, _backups, _receipt = c.export(plan, Path(temporary) / 'converted')
                    reverse = c.prepare(target_id + '-to-' + source_id, output, source)
                    self.assertEqual(reverse.raw, Path(source).read_bytes())
