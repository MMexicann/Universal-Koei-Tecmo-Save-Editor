"""Original SW4 PS4 source safeguards; all public inputs are procedural."""
from dataclasses import replace
from pathlib import Path
import hashlib
import os
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.sw4dx import ps4_export as p
from koei_editor.games.p5strikers_ps4.context import title_only_sfo


def seal(raw):
    """Procedural fixture helper, deliberately not an application writer."""
    result = bytearray(raw)
    for offset, value in zip(p.CHECKSUM_OFFSETS, p.checksums(result)):
        result[offset:offset + 4] = value.to_bytes(4, 'little')
    return bytes(result)


def fixture(gold=123456):
    raw = bytearray((index * 37 + 11) & 255 for index in range(p.SAVE_SIZE))
    raw[:4] = p.REVISION
    start, end = p.ZERO_REGION
    raw[start:end] = bytes(end - start)
    for index in range(p.OFFICER_COUNT):
        offset = p.OFFICER_BASE + index * p.OFFICER_STRIDE
        raw[offset:offset + 4] = index.to_bytes(4, 'little')
    raw[0x7842:0x7846] = gold.to_bytes(4, 'little')
    return seal(raw)


def context():
    return title_only_sfo().replace(b'CUSA19640', p.TITLE_ID.encode())


class SW4PS4SourceTests(unittest.TestCase):
    def test_complete_exact_profile_and_frozen_noop(self):
        raw = fixture()
        document = p.decode(raw)
        self.assertEqual(p.serialize(document, {}), raw)
        self.assertEqual(p.field_map(document)['gold'].value(document.payload), 123456)
        self.assertEqual(document.sha256, hashlib.sha256(raw).hexdigest())
        for candidate in (raw[:-1], raw + b'\0', bytearray(raw), bytes(len(raw))):
            with self.subTest(kind=type(candidate).__name__, length=len(candidate)), self.assertRaises(SaveError):
                p.decode(candidate)
        for forged in (replace(document, payload=b''), replace(document, format=replace(p.FORMAT)),
                       replace(document, context_digest='x' * 64),
                       replace(document, source='app.dat'), None):
            with self.assertRaises(SaveError):
                p.validate_document(forged)
        for changes in ({'gold': 123456}, [], None):
            with self.assertRaises(SaveError):
                p.serialize(document, changes)

    def test_all_checksums_and_each_covered_span_boundary_reject_corruption(self):
        raw = fixture()
        offsets = p.CHECKSUM_OFFSETS + (8, 0xA7, 0xAC, 0x8EB, 0x8EC, 0xC15,
                                       0xC1A, 0x78D5, 0x78D6, 0x85DD)
        for offset in offsets:
            with self.subTest(offset=hex(offset)):
                damaged = bytearray(raw)
                damaged[offset] ^= 1
                with self.assertRaises(SaveError):
                    p.decode(bytes(damaged))

    def test_nonzero_large_region_rejected_even_with_resealed_checksum(self):
        raw = fixture()
        for offset in (0x85DE, 0x58531, 0x58532, 0x80531):
            with self.subTest(offset=hex(offset)):
                damaged = bytearray(raw)
                damaged[offset] = 1
                with self.assertRaises(SaveError):
                    p.decode(seal(damaged))

    def test_resealed_foreign_identities_and_revisions_are_rejected(self):
        for offset in (0, p.OFFICER_BASE, p.OFFICER_BASE + 54 * p.OFFICER_STRIDE):
            raw = bytearray(fixture())
            raw[offset] ^= 1
            with self.subTest(offset=hex(offset)), self.assertRaises(SaveError):
                p.decode(seal(raw))
        # A PS3-style final checksum offset cannot substitute for the PS4 cell.
        raw = bytearray(fixture())
        raw[0x58532:0x58536] = raw[0x80532:0x80536]
        raw[0x80532:0x80536] = bytes(4)
        with self.assertRaises(SaveError):
            p.decode(bytes(raw))

    def test_opaque_tail_is_preserved_without_claiming_integrity(self):
        raw = bytearray(fixture())
        raw[0x80536] ^= 1
        raw[-1] ^= 1
        document = p.decode(bytes(raw))
        self.assertEqual(p.serialize(document, {}), bytes(raw))
        self.assertNotEqual(bytes(raw), fixture())

    def test_source_resource_storage_width_preserves_unusual_values(self):
        document = p.decode(fixture(0xFFFFFFFF))
        field = p.field_map(document)['gold']
        self.assertEqual(field.value(document.payload), 0xFFFFFFFF)
        field.validate(0xFFFFFFFF)
        for invalid in (-1, 0x100000000, True, 1.0):
            with self.assertRaises(SaveError):
                field.validate(invalid)

    def test_original_context_and_changed_sources_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'app.dat'
            source.write_bytes(fixture())
            with self.assertRaises(SaveError):
                p.read_save(source)
            metadata = source.parent / 'sce_sys' / 'param.sfo'
            metadata.parent.mkdir()
            metadata.write_bytes(context())
            document = p.read_save(source)
            backup = p.backup(document)
            self.assertEqual(backup.read_bytes(), document.raw)
            self.assertEqual(backup.with_name(backup.name + '.param.sfo').read_bytes(), context())
            metadata.write_bytes(context().replace(p.TITLE_ID.encode(), b'CUSA14824'))
            with self.assertRaises(SaveError):
                p.read_save(source)
            metadata.write_bytes(context())
            source.write_bytes(document.raw + b'\0')
            with self.assertRaises(SaveError):
                p.backup(document)
            source.write_bytes(document.raw)
            source.rename(source.with_suffix('.bin'))
            with self.assertRaises(SaveError):
                p.read_save(source.with_suffix('.bin'))

    def test_bounded_context_rejects_oversized_and_open_races(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'app.dat'
            source.write_bytes(fixture())
            metadata = source.parent / 'sce_sys' / 'param.sfo'
            metadata.parent.mkdir()
            metadata.write_bytes(context() + bytes(p.MAX_SFO_SIZE))
            with self.assertRaises(SaveError):
                p.read_save(source)
            metadata.write_bytes(context())
            changed = context() + b'\0'
            with patch.object(p, 'context_raw', side_effect=(context(), changed)), self.assertRaises(SaveError):
                p.read_save(source)

    def test_backup_context_race_preserves_original_and_completed_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'app.dat'
            source.write_bytes(fixture())
            metadata = source.parent / 'sce_sys' / 'param.sfo'
            metadata.parent.mkdir()
            metadata.write_bytes(context())
            document = p.read_save(source)
            original = p.snapshot_backup
            observed = []
            def raced(*args, **kwargs):
                result = original(*args, **kwargs)
                observed.append(result)
                metadata.write_bytes(context() + b'\0')
                return result
            with patch.object(p, 'snapshot_backup', side_effect=raced), self.assertRaises(SaveError):
                p.backup(document)
            self.assertEqual(source.read_bytes(), document.raw)
            self.assertEqual(observed[0].read_bytes(), document.raw)

    def test_backup_actual_readback_rejects_replacements_without_deletion(self):
        for target in ('raw', 'manifest', 'companion', 'context'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                source = Path(temporary) / 'app.dat'
                source.write_bytes(fixture())
                metadata = source.parent / 'sce_sys' / 'param.sfo'
                metadata.parent.mkdir()
                metadata.write_bytes(context())
                document = p.read_save(source)
                original = p.atomic_new
                observed = {}
                foreign = b'Another application replaced the backup.'
                def raced(raw, destination):
                    result = original(raw, destination)
                    if result.name.endswith('.context.json'):
                        backup = result.with_name(result.name.removesuffix('.context.json'))
                        observed.update(raw=backup, manifest=backup.with_suffix('.json'),
                                        companion=backup.with_name(backup.name + '.param.sfo'), context=result)
                        observed[target].write_bytes(foreign)
                    return result
                with patch.object(p, 'atomic_new', side_effect=raced), self.assertRaises(SaveError):
                    p.backup(document)
                self.assertEqual(observed[target].read_bytes(), foreign)
                self.assertTrue(all(path.is_file() for path in observed.values()))
                self.assertEqual(source.read_bytes(), document.raw)

    @unittest.skipUnless(os.environ.get('SW4_PS4_NATIVE_COPY'), 'Copied native original US SW4 PS4 save not supplied.')
    def test_optional_native_source_original_context_and_noop(self):
        document = p.read_save(Path(os.environ['SW4_PS4_NATIVE_COPY']))
        self.assertEqual(p.serialize(document, {}), document.raw)
        self.assertTrue(document.context_digest)
        self.assertEqual(len(p.field_map(document)), 1)
