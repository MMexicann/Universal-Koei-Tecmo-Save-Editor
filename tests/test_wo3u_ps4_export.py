"""Read-only PS4 source qualification and typed resource export proof.

Procedural bytes are not genuine gameplay. The optional reference has no
original console metadata and therefore supplies payload evidence only.
"""
from dataclasses import replace
from pathlib import Path
import hashlib
import os
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.wo3u import ps4_export as p
from koei_editor.games.wo3u import wo3u_parser as pc
from koei_editor.games.wo3u.ps4_conversion import TRANSFER
from koei_editor.games.p5strikers_ps4.context import title_only_sfo
from tests.test_wo3u_format import procedural_raw


def fixture():
    raw = bytearray((i * 31 + 7) & 255 for i in range(p.SAVE_SIZE))
    raw[:4] = p.REVISION
    for base, stride, count, marker in p.MARKER_TABLES:
        for index in range(count):
            raw[base + index * stride:base + index * stride + 4] = marker
    for index, field in enumerate(p.RESOURCES):
        raw[field.offset:field.offset + field.size] = ((index * 7 + 3) % 50).to_bytes(field.size, 'little')
    return bytes(raw)


def context():
    return title_only_sfo().replace(b'CUSA19640', p.TITLE_ID.encode())


class WO3UPS4ExportTests(unittest.TestCase):
    def test_complete_profile_and_every_marker_boundary_are_required(self):
        raw = fixture()
        document = p.decode(raw)
        self.assertEqual(p.serialize(document, {}), raw)
        for candidate in (raw[:-1], raw + b'\0', bytearray(raw), bytes(len(raw))):
            with self.assertRaises(SaveError):
                p.decode(candidate)
        for base, stride, count, _marker in p.MARKER_TABLES:
            for offset in (base, base + (count - 1) * stride):
                damaged = bytearray(raw)
                damaged[offset] ^= 1
                with self.assertRaises(SaveError):
                    p.decode(bytes(damaged))
        for forged in (replace(document, payload=b''), replace(document, format=replace(p.FORMAT)),
                       replace(document, context_digest='x' * 64), None):
            with self.assertRaises(SaveError):
                p.validate_document(forged)
        for changes in ({'gems': 1}, [], None):
            with self.assertRaises(SaveError):
                p.serialize(document, changes)

    def test_exact_original_context_and_backup_race_guards(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'APP.BIN'
            source.write_bytes(fixture())
            with self.assertRaises(SaveError):
                p.read_save(source)
            metadata = source.parent / 'sce_sys' / 'param.sfo'
            metadata.parent.mkdir()
            metadata.write_bytes(context())
            document = p.read_save(source)
            snapshot = p.backup(document)
            self.assertEqual(snapshot.read_bytes(), document.raw)
            self.assertEqual(snapshot.with_name(snapshot.name + '.param.sfo').read_bytes(), context())
            original = p.snapshot_backup
            def raced(*args, **kwargs):
                result = original(*args, **kwargs)
                metadata.write_bytes(metadata.read_bytes() + b'\0')
                return result
            with patch.object(p, 'snapshot_backup', side_effect=raced), self.assertRaises(SaveError):
                p.backup(document)
            metadata.write_bytes(context().replace(p.TITLE_ID.encode(), b'CUSA00661'))
            with self.assertRaises(SaveError):
                p.read_save(source)
            metadata.write_bytes(context())
            source.write_bytes(document.raw + b'\0')
            with self.assertRaises(SaveError):
                p.backup(document)

    def test_backup_actual_readback_rejects_foreign_replacements_without_deleting_them(self):
        for target in ('raw', 'manifest', 'companion', 'context'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                source = Path(temporary) / 'APP.BIN'
                source.write_bytes(fixture())
                metadata = source.parent / 'sce_sys' / 'param.sfo'
                metadata.parent.mkdir()
                metadata.write_bytes(context())
                document = p.read_save(source)
                original = p.atomic_new
                observed = {}
                foreign = b'Another app replaced this completed backup.'
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

    def test_typed_values_transfer_and_every_other_pc_byte_is_preserved(self):
        source = p.decode(fixture())
        destination = pc.decode(procedural_raw())
        changes = {field.id: field.value(source.payload) for field in p.RESOURCES}
        raw = TRANSFER.encode(source, destination)
        reopened = pc.decode(raw)
        allowed = {offset for field in p.RESOURCES for offset in range(field.offset, field.offset + field.size)}
        self.assertEqual(len(p.RESOURCES), 354)
        self.assertEqual(len(allowed), 355)
        for offset, (before, after) in enumerate(zip(destination.raw, raw)):
            self.assertEqual(after, source.raw[offset] if offset in allowed else before)
        self.assertEqual(source.raw, fixture())
        self.assertEqual(pc.field_map(reopened)['crystals'].value(reopened.payload), 3)

    def test_direction_and_pc_bounds_reject_reverse_and_lossy_input(self):
        source = p.decode(fixture())
        destination = pc.decode(procedural_raw())
        with self.assertRaises(SaveError):
            TRANSFER.encode(destination, source)
        for key, value in (('crystals', 1000), ('orb_0', 100), ('material_0_0', 100)):
            field = p.field_map(source)[key]
            raw = bytearray(source.raw)
            raw[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
            unsupported = p.decode(bytes(raw))
            from koei_editor.shared.experimental_limits import experimental_limits
            with experimental_limits(True), self.assertRaises(SaveError):
                TRANSFER.encode(unsupported, destination)
        self.assertEqual(destination.raw, procedural_raw())
        self.assertEqual(TRANSFER.SUPPORTED_DIRECTIONS, frozenset({(p.GAME_ID, pc.GAME_ID)}))

    @unittest.skipUnless(os.environ.get('WO3U_PS4_REFERENCE'), 'Private public-origin PS4 reference not supplied.')
    def test_real_reference_payload_and_typed_pc_roundtrip(self):
        raw = Path(os.environ['WO3U_PS4_REFERENCE']).read_bytes()
        document = p.decode(raw)
        self.assertEqual(hashlib.sha256(p.serialize(document, {})).digest(), hashlib.sha256(raw).digest())
        target = pc.decode(procedural_raw())
        changes = {field.id: field.value(document.payload) for field in p.RESOURCES}
        reopened = pc.decode(TRANSFER.encode(document, target))
        for field in p.RESOURCES:
            self.assertEqual(field.value(reopened.payload), field.value(document.payload))
