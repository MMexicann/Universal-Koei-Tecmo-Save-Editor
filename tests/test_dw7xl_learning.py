"""Native negative seal-meter operation leaves ownership and reward bits intact."""
import os
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw7xl import dw7xl_codec as codec
from koei_editor.games.dw7xl import dw7xl_parser as backend
from tests.test_dw7xl_format import synthetic_raw


class DW7LearningTests(unittest.TestCase):
    def document(self, flags=1, meter=370):
        document = backend.decode(synthetic_raw())
        payload = bytearray(document.payload)
        offset = backend.WEAPON_BASE
        payload[offset + 4:offset + 6] = flags.to_bytes(2, 'little')
        payload[offset + 6:offset + 8] = meter.to_bytes(2, 'little')
        return backend.decode(codec.encode(payload, document.seed))

    def test_decrease_is_surgical_excludes_rewards_and_preserves_seed(self):
        document = self.document()
        key = 'weapon_0_seal_meter'
        field = backend.field_map(document)[key]
        self.assertFalse(field.maxable)
        for value in (0, 369):
            pending = backend.stage(document, {}, key, value)
            expected = bytearray(document.payload)
            expected[field.offset:field.offset + 2] = value.to_bytes(2, 'little')
            reopened = backend.decode(backend.serialize(document, pending))
            self.assertEqual(reopened.payload, expected)
            self.assertEqual(reopened.seed, document.seed)
            self.assertEqual(backend.stage(document, pending, key, 370), {})
            self.assertEqual(len(backend.review(document, pending)), 1)
        self.assertEqual(backend.maximums(document, {}, 'Seal learning'), {})
        self.assertEqual(backend.limit_values(document, {}, [key]), {})
        for value in (True, -1, 371, 1000):
            with self.assertRaises(SaveError):
                backend.stage(document, {}, key, value)
        with self.assertRaises(SaveError):
            backend.serialize(document, {key: 371})
        with self.assertRaises(SaveError):
            backend.stage(document, {key: 371}, key, 370)

    def test_learned_unowned_unknown_and_high_records_are_opaque(self):
        for flags, meter in ((0, 370), (5, 370), (3, 370), (0x8001, 370),
                             (1, 0), (1, 1001), (1, 65535)):
            with self.subTest(flags=flags, meter=meter):
                document = self.document(flags, meter)
                self.assertNotIn('weapon_0_seal_meter', backend.field_map(document))
                self.assertEqual(backend.serialize(document, {}), document.raw)
                saved = backend.decode(backend.serialize(document, backend.maximums(document, {})))
                start = backend.WEAPON_BASE + 4
                self.assertEqual(saved.payload[start:start + 4], document.payload[start:start + 4])

    @unittest.skipUnless(os.environ.get('DW7XL_SAVE_COPY'), 'Private native DW7 XL copy unavailable')
    def test_native_complete_inventory_does_not_revoke_learned_seals(self):
        document = backend.read_save(os.environ['DW7XL_SAVE_COPY'])
        for field in backend.fields_for(document):
            if field.group != 'Seal learning':
                continue
            flags = int.from_bytes(document.payload[field.offset - 2:field.offset], 'little')
            self.assertEqual(flags, 1)
        # The reviewed complete fixture may have no unlearned meters. This
        # verifies exclusion and reconstruction, not genuine edits of absent fields.
        self.assertEqual(backend.serialize(document, {}), document.raw)

    @unittest.skipUnless(os.environ.get('DW7XL_SAVE_COPY'), 'Private native DW7 XL copy unavailable')
    def test_native_eligible_meter_reductions_are_surgical(self):
        document = backend.read_save(os.environ['DW7XL_SAVE_COPY'])
        meters = [field for field in backend.fields_for(document) if field.group == 'Seal learning']
        if not meters:
            self.skipTest('The copied save has no owned unlearned positive seal meter.')
        for field in meters:
            with self.subTest(field=field.id):
                original = field.value(document.payload)
                for value in (0, original - 1):
                    pending = backend.stage(document, {}, field.id, value)
                    expected = bytearray(document.payload)
                    expected[field.offset:field.offset + 2] = value.to_bytes(2, 'little')
                    reopened = backend.decode(backend.serialize(document, pending))
                    self.assertEqual(reopened.payload, bytes(expected))
                    self.assertEqual(reopened.seed, document.seed)
                    # Ownership and learned flags immediately before the meter stay intact.
                    self.assertEqual(reopened.payload[field.offset - 2:field.offset],
                                     document.payload[field.offset - 2:field.offset])
                with self.assertRaises(SaveError):
                    backend.stage(document, {}, field.id, original + 1)
        self.assertEqual(backend.maximums(document, {}, 'Seal learning'), {})
        self.assertEqual(backend.serialize(document, {}), document.raw)
