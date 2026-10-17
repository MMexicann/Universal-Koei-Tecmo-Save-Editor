"""Availability gates protect inactive inventory and unranked attributes."""
import struct
import unittest
from pathlib import Path
from koei_editor.shared.koei_codec import byte_cipher, mix_word, word_cipher, word_sum
from koei_editor.games.dw3.models import SaveError
import koei_editor.shared.verified_editor as backend
from koei_editor.games.dw3.game_content import record_label
from test_verified_editors import synthetic_raw


def with_payload(document, payload):
    inner = byte_cipher(payload, document.format.inner_seed)
    raw = struct.pack('<HH', word_sum(inner), document.seed) + word_cipher(inner, document.seed)
    raw += bytes([(sum(payload) & 255) ^ (mix_word(document.seed) & 255)])
    return backend.decode(raw, 'dw8xl')


class PCContentMappingTests(unittest.TestCase):
    def setUp(self):
        original = backend.decode(synthetic_raw('dw8xl'), 'dw8xl')
        payload = bytearray(original.payload)
        for slot, state, identity in ((0,1,123), (1,0,123), (2,3,321), (3,2,123), (4,1,65535)):
            offset = backend.DW8_WEAPON_BASE + slot * 24
            payload[offset:offset+18] = bytes([state,0]) + identity.to_bytes(2,'little') + bytes(
                [2,40,7,1,255,200,41,0,3,1,0,2,9,25])
        payload[0x7fe0] = 149
        payload[0x7fe5:0x7fe9] = (358700).to_bytes(4,'little')
        payload[0x7fe1:0x7fe5] = (98).to_bytes(4,'little')
        payload[0x7fe9:0x7fed] = (1827).to_bytes(4,'little')
        self.document = with_payload(original, payload)

    def test_only_existing_supported_ranked_attributes_are_editable(self):
        keys = {key for key in backend.field_map(self.document)
                if key.startswith('weapon_') and '_attribute_' in key}
        ranks = {f'weapon_{slot}_attribute_{attribute}_rank'
                 for slot in (0, 2) for attribute in (0, 4, 5)}
        identities = {f'weapon_{slot}_attribute_{attribute}_identity'
                      for slot in (0, 2) for attribute in (0, 4)}
        self.assertEqual({key for key in keys if key.endswith('_rank')}, ranks)
        self.assertEqual({key for key in keys if key.endswith('_identity')}, identities)
        self.assertEqual(keys, ranks | identities)
        # Identity replacement requires an original ordinary ranked slot; the
        # existing rank editor separately preserves/permits edits of rank 25.
        protected = {f'weapon_{slot}_attribute_{attribute}_identity'
                     for slot in (1, 3, 4) for attribute in range(6)}
        protected.update(f'weapon_{slot}_attribute_{attribute}_identity'
                         for slot in (0, 2) for attribute in (1, 2, 3, 5))
        for key in protected:
            self.assertNotIn(key, backend.field_map(self.document))
            with self.subTest(protected_identity=key), self.assertRaises(SaveError):
                backend.serialize(self.document, {key: 7})
        self.assertEqual(backend.limit_values(self.document, {}, identities), {})
        self.assertIn('Velocity',backend.field_map(self.document)['weapon_0_attribute_0_rank'].label)
        self.assertIn('Comet',backend.field_map(self.document)['weapon_0_attribute_4_rank'].label)
        for key in ('weapon_1_attribute_0_rank','weapon_3_attribute_0_rank','weapon_4_attribute_0_rank',
                    'weapon_0_attribute_1_rank','weapon_0_attribute_2_rank','weapon_0_attribute_3_rank',
                    'weapon_0_id','weapon_0_attack'):
            with self.assertRaises(SaveError):backend.serialize(self.document,{key:10})

    def test_bulk_ranks_preserve_inactive_empty_unranked_unknown_and_higher_values(self):
        changes = backend.maximums(self.document,{},'Weapon attributes')
        self.assertEqual(len(changes),4)
        after = backend.decode(backend.serialize(self.document,changes),'dw8xl')
        allowed = {backend.field_map(self.document)[key].offset for key in changes}
        changed = {i for i,(a,b) in enumerate(zip(self.document.payload,after.payload)) if a!=b}
        self.assertEqual(changed,allowed)
        self.assertEqual(backend.weapon(after,1)['attributes'][-1],(0,25))
        self.assertEqual(backend.serialize(self.document,{}),self.document.raw)
        for value in (0,11,True):
            with self.assertRaises(SaveError):backend.stage(self.document,{},'weapon_0_attribute_0_rank',value)

    def test_progression_is_read_only_and_has_correct_widths(self):
        progress = backend.progression(self.document,1)
        self.assertEqual((progress['level'],progress['experience'],progress['leadership'],progress['leadership_experience']),
                         (150,358700,99,1827))
        self.assertEqual(len(backend.progressions(self.document)),82)
        for key in ('officer_0_level','officer_0_experience','officer_0_leadership'):
            with self.assertRaises(SaveError):backend.serialize(self.document,{key:1})
        for slot in (0,83,True):
            with self.assertRaises(SaveError):backend.progression(self.document,slot)

    def test_gem_limit_uses_corroborated_normal_cap_and_preserves_higher_values(self):
        self.assertEqual(backend.field_map(self.document)['gems'].maximum,9999)
        payload = bytearray(self.document.payload)
        payload[0x1d43:0x1d45] = (65535).to_bytes(2,'little')
        high = with_payload(self.document,payload)
        self.assertNotIn('gems',backend.maximums(high,{}))
        with self.assertRaises(SaveError):backend.stage(high,{},'gems',10000)

    def test_pw3_identity_and_costume_inspection_never_grant_unlocks(self):
        document = backend.decode(synthetic_raw('pw3'),'pw3')
        self.assertIn('Luffy',record_label('pw3',1,'Characters'))
        self.assertIn('post-timeskip',record_label('pw3',40,'Characters'))
        self.assertEqual(record_label('pw3',42,'Characters'),'Character slot 42')
        rows = backend.costume_associations(document)
        self.assertEqual(len(rows),28)
        for row in rows:
            offset = 0x650+(row['slot']-1)*0x1f0+0x2f+row['local_slot']
            self.assertEqual(row['stored_id'],document.payload[offset])
        with self.assertRaises(SaveError):backend.serialize(document,{'costume_0':1})
        self.assertEqual(backend.serialize(document,{}),document.raw)


if __name__ == '__main__':unittest.main()
