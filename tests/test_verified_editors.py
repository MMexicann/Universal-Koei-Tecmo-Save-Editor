"""Procedural fixtures, published cipher vectors and explicit sample validation."""
from dataclasses import replace
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import koei_editor.shared.verified_editor as editor
from koei_editor.shared.koei_codec import byte_cipher, mix_word, word_cipher, word_sum
from koei_editor.game_registry import GAMES, RESEARCH_TOOLS, get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.support_catalog import load_catalog


@lru_cache(maxsize=2)
def synthetic_raw(game_id):
    """Generated fake data, with an independently expressed reference cipher."""
    layout = editor.get_format(game_id)
    payload = bytearray(layout.size - (5 if layout.inner_seed is not None else 4))
    payload[:len(layout.magic[0])] = layout.magic[0]
    if game_id == 'pw3':
        payload[0x500:0x508] = bytes.fromhex('0000000002000000')
        payload[0x518:0x51c] = bytes.fromhex('d0000000')
    for field in layout.fields:
        value = min(50, field.maximum)
        payload[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    seed = 0xb221
    plain = bytes(payload)
    if layout.inner_seed is not None:
        state = layout.inner_seed
        for i in range(len(payload)):
            state = (1103515245 * state + 12345) % (2 ** 32)
            payload[i] ^= (state // 65536) % 256
    checksum = sum(int.from_bytes(payload[i:i+2], 'little') for i in range(0, len(payload), 2)) % 65536
    state = seed
    for i in range(0, len(payload), 4):
        for _ in range(3):
            state = (1528461393 * state + 52814) % (2 ** 32)
        payload[i:i+4] = (int.from_bytes(payload[i:i+4], 'little') ^ state).to_bytes(4, 'little')
    raw = struct.pack('<HH', checksum, seed) + payload
    if layout.inner_seed is not None:
        first = seed
        for _ in range(3):
            first = (1528461393 * first + 52814) % (2 ** 32)
        raw += bytes([(sum(plain) % 256) ^ (first % 256)])
    return bytes(raw)


class PublishedCipherTests(unittest.TestCase):
    def test_dw8_published_ps3_magic_known_answer(self):
        self.assertEqual(byte_cipher(bytes.fromhex('f0021013'), 0x13100200), bytes.fromhex('9da2dd60'))

    def test_pw3_public_pc_header_known_answer(self):
        self.assertEqual(mix_word(0xb221), 0xa953b61b)
        self.assertEqual(word_cipher(b'ONE ', 0xb221), bytes.fromhex('54f81689'))

    def test_dw8_public_pc_word_known_answer(self):
        self.assertEqual(word_cipher(bytes.fromhex('bbaf991c'), 0xd3dc), bytes.fromhex('9d87cf6a'))

    def test_word_checksum_and_alignment(self):
        self.assertEqual(word_sum(bytes.fromhex('ffff01000200')), 2)
        with self.assertRaises(ValueError):
            word_sum(b'odd')
        with self.assertRaises(ValueError):
            word_cipher(b'odd', 0)

    def test_ciphers_are_reversible(self):
        raw = bytes(range(256)) * 4
        self.assertEqual(word_cipher(word_cipher(raw, 65535), 65535), raw)
        self.assertEqual(byte_cipher(byte_cipher(raw, 0x13100200), 0x13100200), raw)


class VerifiedEditorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.documents = {}
        for game_id in ('dw8xl', 'pw3'):
            source = self.folder / (game_id + '.dat')
            source.write_bytes(synthetic_raw(game_id))
            self.documents[game_id] = editor.read_save(source, game_id)

    def tearDown(self):
        self.temporary.cleanup()

    def test_no_edit_ciphertext_roundtrip(self):
        for document in self.documents.values():
            self.assertEqual(editor.serialize(document, {}), document.raw)

    def test_single_edits_touch_only_declared_plaintext_bytes(self):
        for game_id, key in (('dw8xl', 'gold'), ('pw3', 'character_0_attack')):
            document = self.documents[game_id]
            raw = editor.serialize(document, {key:123})
            output = editor.decode(raw, game_id)
            field = editor.field_map(document)[key]
            self.assertEqual(field.value(output.payload), 123)
            allowed = set(range(field.offset, field.offset + field.size))
            changed = {i for i, (before, after) in enumerate(zip(document.payload, output.payload)) if before != after}
            self.assertTrue(changed)
            self.assertLessEqual(changed, allowed)
            self.assertEqual(output.seed, document.seed)

    def test_all_field_maximums_and_bulk_serialization(self):
        for game_id, document in self.documents.items():
            changes = editor.maximums(document, {})
            output = editor.decode(editor.serialize(document, changes), game_id)
            allowed = {i for field in document.format.fields for i in range(field.offset, field.offset + field.size)}
            for field in document.format.fields:
                self.assertEqual(field.value(output.payload), field.maximum)
            changed = {i for i, (a,b) in enumerate(zip(document.payload, output.payload)) if a != b}
            self.assertLessEqual(changed, allowed)

    def test_group_maximums_preserve_resources(self):
        document = self.documents['dw8xl']
        changes = editor.maximums(document, {}, 'Officers')
        self.assertEqual(len(changes), 246)
        self.assertNotIn('gold', changes)

    def test_staging_original_value_removes_pending_edit(self):
        document = self.documents['pw3']
        changes = editor.stage(document, {}, 'character_0_attack', 42)
        self.assertEqual(editor.stage(document, changes, 'character_0_attack', 50), {})
        self.assertEqual(changes, {'character_0_attack':42})

    def test_invalid_values_and_unverified_fields_rejected(self):
        document = self.documents['dw8xl']
        for value in (-1, 10_000_000, '7', 1.5, True, None):
            with self.assertRaises(SaveError):
                editor.stage(document, {}, 'gold', value)
        for changes in ({'experience':100}, {'officer_82_hp':999}, {'gold':-1}):
            with self.assertRaises(SaveError):
                editor.serialize(document, changes)

    def test_review_contains_only_staged_values_in_layout_order(self):
        document = self.documents['pw3']
        rows = editor.review(document, {'character_1_attack':99, 'character_0_attack':123})
        self.assertEqual([(field.id,before,after) for field,before,after in rows],
                         [('character_0_attack',50,123), ('character_1_attack',50,99)])

    def test_pw3_currency_is_read_only_and_cannot_be_staged(self):
        document = self.documents['pw3']
        self.assertEqual(editor.observed_beli(document), int.from_bytes(document.payload[0xc5d4:0xc5d8], 'little'))
        self.assertIsNone(editor.observed_beli(self.documents['dw8xl']))
        with self.assertRaises(SaveError):
            editor.stage(document, {}, 'beli', 123)
        with self.assertRaises(SaveError):
            editor.serialize(document, {'beli':123})
        after = editor.decode(editor.serialize(document, editor.maximums(document, {})), 'pw3')
        self.assertEqual(after.payload[0xc5d4:0xc5dc], document.payload[0xc5d4:0xc5dc])

    def test_read_only_progression_and_observed_health_curve(self):
        document = self.documents['pw3']
        self.assertEqual(editor.progression(document, 1)['level'], 1)
        self.assertEqual(editor.progression(document, 1)['experience'], 0)
        for index,value in ((0,2000),(16,2979),(29,3775),(33,4020),(36,4204),(49,5000),(99,6000)):
            self.assertEqual(editor.observed_health_curve(index), value)
        for index in (-1,100,True,'49'):
            self.assertIsNone(editor.observed_health_curve(index))
        for slot in (0,48,True):
            with self.assertRaises(SaveError):editor.progression(document, slot)
        for key in ('level','experience','character_0_level'):
            with self.assertRaises(SaveError):editor.stage(document, {}, key, 99)

    def test_bulk_limits_and_undo_to_original_preserve_higher_existing_values(self):
        document = self.documents['pw3']
        field = editor.field_map(document)['character_0_attack']
        payload = bytearray(document.payload)
        payload[field.offset:field.offset+field.size] = (1500).to_bytes(2,'little')
        raw = struct.pack('<HH',word_sum(payload),document.seed) + word_cipher(payload,document.seed)
        high = editor.decode(raw,'pw3')
        self.assertNotIn(field.id, editor.maximums(high, {}))
        self.assertEqual(editor.limit_values(high, {}, [field.id]), {})
        changes = editor.stage(high, {}, field.id, 500)
        self.assertEqual(editor.stage(high, changes, field.id, 1500), {})
        after = editor.decode(editor.serialize(high,editor.maximums(high,{})),'pw3')
        self.assertEqual(field.value(after.payload),1500)

    def test_bars_and_slot_writes_reject_unobserved_zero_capacity(self):
        document = self.documents['pw3']
        for key in ('character_0_special','character_0_skills'):
            with self.assertRaises(SaveError):editor.stage(document,{},key,0)

    def test_truncated_oversize_random_and_foreign_saves_rejected(self):
        for game_id, document in self.documents.items():
            other = self.documents['pw3' if game_id == 'dw8xl' else 'dw8xl']
            for raw in (b'', document.raw[:-1], document.raw+b'\0', bytes(len(document.raw)), other.raw):
                with self.assertRaises(SaveError):
                    editor.decode(raw, game_id)
        with self.assertRaises(SaveError):
            editor.decode(self.documents['pw3'].raw, 'origins')

    def test_ciphertext_corruption_rejected(self):
        for game_id, document in self.documents.items():
            for offset in (0, 2, 4, 999, len(document.raw)-1):
                raw = bytearray(document.raw)
                raw[offset] ^= 1
                with self.assertRaises(SaveError):
                    editor.decode(raw, game_id)

    def test_dw8_plaintext_checksum_failure_rejected(self):
        raw = bytearray(self.documents['dw8xl'].raw)
        raw[-1] ^= 1
        with self.assertRaisesRegex(SaveError, 'plaintext checksum'):
            editor.decode(raw, 'dw8xl')

    def test_correct_checksum_with_wrong_identity_rejected(self):
        document = self.documents['pw3']
        payload = b'WRONG GAME' + document.payload[10:]
        raw = struct.pack('<HH', word_sum(payload), document.seed) + word_cipher(payload, document.seed)
        with self.assertRaisesRegex(SaveError, 'identity'):
            editor.decode(raw, 'pw3')

    def test_tampered_document_rejected(self):
        document = self.documents['dw8xl']
        for forged in (replace(document, payload=b'bad'), replace(document, seed=0),
                       replace(document, format=replace(document.format, magic=(b'fake',)))):
            with self.assertRaises(SaveError):
                editor.serialize(forged, {})

    def test_backup_save_as_restore_and_original_preservation(self):
        for game_id, document in self.documents.items():
            snapshot = editor.backup(document)
            self.assertEqual(snapshot.read_bytes(), document.raw)
            key = 'gold' if game_id == 'dw8xl' else 'character_0_attack'
            output = editor.save_as(document, {key:123}, self.folder / (game_id+'.edited.dat'))
            self.assertEqual(editor.field_map(output)[key].value(output.payload), 123)
            restored = editor.restore(snapshot, self.folder / (game_id+'.restored.dat'), game_id)
            self.assertEqual(restored.read_bytes(), document.raw)
            self.assertEqual(document.source.read_bytes(), document.raw)

    def test_save_as_never_overwrites_any_existing_file(self):
        document = self.documents['pw3']
        for target in (document.source, self.folder/'existing.dat'):
            if not target.exists():target.write_bytes(b'keep')
            original = target.read_bytes()
            with self.assertRaises(FileExistsError):
                editor.save_as(document, {'character_0_attack':42}, target)
            self.assertEqual(target.read_bytes(), original)

    def test_changed_source_detected_without_output(self):
        document = self.documents['dw8xl']
        document.source.write_bytes(document.raw[:-1])
        destination = self.folder/'output.dat'
        with self.assertRaisesRegex(SaveError, 'changed on disk'):
            editor.save_as(document, {'gold':1}, destination)
        self.assertFalse(destination.exists())

    def test_backup_hash_and_game_checks_reject_restore(self):
        document = self.documents['pw3']
        snapshot = editor.backup(document)
        manifest = snapshot.with_suffix('.json')
        data = json.loads(manifest.read_text())
        for change in ({'game_id':'dw8xl'}, {'sha256':'0'*64}, {'size_bytes':1}):
            manifest.write_text(json.dumps(data | change))
            with self.assertRaises(SaveError):
                editor.restore(snapshot, self.folder/'restore.dat', 'pw3')
        self.assertFalse((self.folder/'restore.dat').exists())

    def test_wrong_extension_rejected_before_read(self):
        with self.assertRaises(SaveError):
            editor.read_save(self.folder/'wrong.sav', 'pw3')
        with self.assertRaises(SaveError):
            editor.save_as(self.documents['pw3'], {}, self.folder/'wrong.bin')

    def test_live_save_and_cloud_paths_rejected(self):
        for name in ('Documents/One Piece Pirate Warriors 3/SAVEDATA/OP3WIN0000.dat',
                     'Documents/KoeiTecmo/Dynasty Warriors 8/Savedata/save.dat',
                     'Documents/KoeiTecmo/Dynasty Warriors 9 for Steam/save.dat',
                     'Documents/KoeiTecmo/Dynasty Warriors 9 Empires/save.dat',
                     'Documents/KoeiTecmo/Atelier Sophie 2/AutoSave/data.dat',
                     'Documents/KoeiTecmo/NIOH2/SAVEDATA/0001/SAVEDATA.BIN',
                     'Documents/KoeiTecmo/Wolong/SAVEDATA/SAVEDATA.BIN',
                     'Documents/KOEI/Musou OROCHI Z/Savedata/save.dat',
                     'Documents/KoeiTecmo/WARRIORS ALL-STARS/Savedata/SAVEDATA.BIN',
                     r'C:\Users\Player\Documents\KoeiTecmo\Dynasty Warriors 9 for Steam\save.dat',
                     r'C:\Users\Player\Documents\KoeiTecmo\Dynasty Warriors 9 Empires\save.dat',
                     'Steam/userdata/123/456/remote/save.dat',
                     'AppData/Roaming/SEGA/Steam/P5S/example/SAVEDATA.BIN',
                     'Documents/KOEI/Shin Sangokumusou 4 Special/Savedata/save.dat',
                     'KoeiTecmo/BERSERK and the Band of the Hawk/SAVEDATA/save.dat'):
            with self.assertRaises(SaveError):
                safe_path(self.folder/name)

    def test_live_folder_symlink_rejected(self):
        live = self.folder/'One Piece Pirate Warriors 3/SAVEDATA'
        live.mkdir(parents=True)
        alias = self.folder/'alias'
        try:
            alias.symlink_to(live, target_is_directory=True)
        except OSError:
            self.skipTest('Symbolic links unavailable.')
        with self.assertRaises(SaveError):
            safe_path(alias/'save.dat')


class SupportGateTests(unittest.TestCase):
    def test_library_contains_only_verified_editing_adapters(self):
        self.assertTrue({'dw3','dw8xl','pw3','dw4hyper','dw4xl_ps2','atelier_sophie2','origins','dw7xl','wo3u','samurai4dx','pw4'}.issubset({game.id for game in GAMES}))
        self.assertTrue(all(game.editing_verified or game.published_format for game in GAMES))
        self.assertFalse(RESEARCH_TOOLS)
        self.assertTrue(get_game('origins').editing_verified)
        self.assertEqual(get_game('origins').scalar_backend, 'koei_editor.games.origins.origins_parser')

    def test_catalog_cannot_add_an_unverified_editor(self):
        entries = load_catalog()
        self.assertGreater(len(entries), 30)
        self.assertTrue(all(entry['platform'].startswith('Windows PC') or entry['platform'] in {'DOS PC', 'NES', 'SNES', 'Macintosh', 'PlayStation 2', 'PlayStation 3', 'PlayStation Vita', 'Xbox 360', 'PlayStation 4', 'PlayStation Portable', 'Xbox 360 / Xenia', 'Wii U', 'Nintendo Switch', 'Nintendo DS', 'Nintendo 3DS', 'Original Xbox'} for entry in entries))
        self.assertTrue(all(not entry['editing_verified'] for entry in entries if entry['platform'] == 'Xbox 360'))
        self.assertEqual({entry['id'] for entry in entries if entry['editing_verified']}, {game.id for game in GAMES if game.editing_verified})
        catalog = {entry['id']:entry for entry in entries}
        self.assertFalse(catalog['rotk2_dos']['editing_verified'])
        self.assertTrue(get_game('rotk2_dos').published_format)
        self.assertFalse(get_game('rotk2_dos').get_scalar_adapter().get_format().sample_verified)
        self.assertFalse(catalog['sw5']['editing_verified'])
        self.assertTrue(catalog['samurai5_pc']['editing_verified'])
        self.assertTrue(catalog['wo4_pc']['editing_verified'])
        self.assertTrue(catalog['wo4_ultimate']['editing_verified'])
        self.assertTrue(catalog['abyss_pc']['editing_verified'])
        self.assertTrue(catalog['dw6']['editing_verified'])
        self.assertEqual(get_game('dw6').platform, 'Windows PC')
        self.assertTrue(catalog['sw4ii']['editing_verified'])
        self.assertEqual(get_game('sw4ii').get_scalar_adapter().get_format().id, 'sw4ii')
        for game_id in ('berserk','dw8_empires','dw9_original','dw9_empires',
                        'dw7_definitive','sw4','sw4dx','sw5','sw_sanada','wo3','wo4',
                        'p5s','dqh1','dqh2','abyss', 'dw6_original'):
            with self.assertRaises(SaveError):get_game(game_id)

    def test_same_extension_is_not_sufficient_to_cross_game_parsers(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'save.dat'
            path.write_bytes(synthetic_raw('pw3'))
            with self.assertRaises(SaveError):get_game('dw8xl').read_save(path)
            self.assertEqual(get_game('pw3').read_save(path).format.id, 'pw3')

    def test_game_mechanics_notes_do_not_activate_research_games(self):
        before = tuple(GAMES)
        from koei_editor.games.dw3.game_knowledge import guide
        for game_id in ('dw3','dw8xl','pw3','origins','berserk','pw4','dw8_empires','sw4ii'):
            title,text = guide(game_id)
            self.assertTrue(title)
            self.assertIn('GAME_MECHANICS.md',text)
        self.assertIn('read only',guide('pw3')[1])
        self.assertEqual(tuple(GAMES), before)


class ExplicitPublicSampleTests(unittest.TestCase):
    def test_explicit_dw8_sample(self):
        self.check_sample('dw8xl', 'DW8XL_SAVE_COPY', {'gold':12345, 'officer_0_attack':1200})

    def test_explicit_pw3_sample(self):
        self.check_sample('pw3', 'PW3_SAVE_COPY', {'character_0_hp':6000, 'character_0_attack':700})

    def check_sample(self, game_id, variable, changes):
        if not os.environ.get(variable):self.skipTest('Provide an explicit copied sample using '+variable+'.')
        document = editor.read_save(os.environ[variable], game_id)
        before = document.sha256
        self.assertEqual(editor.serialize(document, {}), document.raw)
        raw = editor.serialize(document, changes)
        output = editor.decode(raw, game_id)
        for key,value in changes.items():self.assertEqual(editor.field_map(output)[key].value(output.payload), value)
        allowed = {i for key in changes for i in range(editor.field_map(document)[key].offset,
                   editor.field_map(document)[key].offset+editor.field_map(document)[key].size)}
        self.assertLessEqual({i for i,(a,b) in enumerate(zip(document.payload,output.payload)) if a!=b}, allowed)
        self.assertEqual(hashlib.sha256(document.source.read_bytes()).hexdigest(), before)


class CopiedSaveSelfTestTests(unittest.TestCase):
    def test_workflow_checks_both_formats_and_preserves_input(self):
        from koei_editor.shared.verified_self_test import run
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for game_id in ('dw8xl','pw3'):
                source = root/(game_id+'.dat')
                raw = synthetic_raw(game_id)
                source.write_bytes(raw)
                report = run(game_id, source, root/(game_id+'-output'))
                self.assertTrue(report['success'])
                self.assertTrue(report['input_preserved'])
                self.assertTrue(report['backup_restored'])
                self.assertFalse(report['in_game_load_tested'])
                self.assertEqual(source.read_bytes(), raw)

    def test_workflow_rejects_nonempty_output(self):
        from koei_editor.shared.verified_self_test import run
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root/'save.dat'
            source.write_bytes(synthetic_raw('pw3'))
            with self.assertRaisesRegex(SaveError, 'new or empty'):
                run('pw3',source,root)
            self.assertEqual(source.read_bytes(), synthetic_raw('pw3'))


if __name__ == '__main__':
    unittest.main()
