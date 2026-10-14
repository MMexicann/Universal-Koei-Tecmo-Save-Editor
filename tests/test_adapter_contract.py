"""Shared contracts exercise real backends and explicit dispatch/session safety."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from koei_editor.shared.adapter_contract import BoundScalarAdapter, SESSION_ACTIONS, validate_session
from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from tests.scalar_contract import ScalarContractTests
from tests.test_verified_editors import synthetic_raw
from tests.test_dw4hyper_format import procedural_raw as hyper_raw
from tests.test_dw4xl_format import procedural_psu
from tests.test_atelier_sophie2_format import procedural_raw as sophie_raw


class DW8ContractTests(ScalarContractTests, unittest.TestCase):
    game_id = 'dw8xl'
    fixture_bytes = staticmethod(lambda: synthetic_raw('dw8xl'))


class PW3ContractTests(ScalarContractTests, unittest.TestCase):
    game_id = 'pw3'
    fixture_bytes = staticmethod(lambda: synthetic_raw('pw3'))


class HyperContractTests(ScalarContractTests, unittest.TestCase):
    game_id = 'dw4hyper'
    fixture_bytes = staticmethod(hyper_raw)


class PS2ContractTests(ScalarContractTests, unittest.TestCase):
    game_id = 'dw4xl_ps2'
    fixture_bytes = staticmethod(procedural_psu)
    payload_integrity_offsets = frozenset((0, 1))


class SophieContractTests(ScalarContractTests, unittest.TestCase):
    game_id = 'atelier_sophie2'
    fixture_bytes = staticmethod(sophie_raw)


class AdapterDispatchTests(unittest.TestCase):
    def test_save_as_reopens_destination_instead_of_trusting_backend_return(self):
        adapter = get_game('dw8xl').get_scalar_adapter()
        original = synthetic_raw('dw8xl')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.dat'
            destination = Path(directory) / 'edited.dat'
            source.write_bytes(original)
            document = adapter.read_save(source)
            field = adapter.fields_for(document)[0]
            opened = field.value(document.payload)
            target = field.maximum if opened != field.maximum else field.minimum
            changes = adapter.stage(document, {}, field.id, target)

            def return_good_but_write_old_copy(document, changes, path):
                expected = adapter.backend.serialize(document, changes)
                Path(path).write_bytes(document.raw)
                return adapter.backend.decode(expected, adapter.game_id, Path(path))

            with patch.object(adapter.backend, 'save_as', side_effect=return_good_but_write_old_copy):
                with self.assertRaisesRegex(SaveError, 'saved file differs from the backend result'):
                    adapter.save_as(document, changes, destination)

    def test_declared_integrity_ranges_only_allow_exact_payload_bytes(self):
        adapter = get_game('dw8xl').get_scalar_adapter()
        with patch.object(adapter.backend, 'SERIALIZED_INTEGRITY_RANGES', ((1, 2),), create=True):
            self.assertTrue(adapter._payload_matches_expected(b'abc', b'aXc'))
            self.assertFalse(adapter._payload_matches_expected(b'abc', b'aXd'))
            self.assertFalse(adapter._payload_matches_expected(b'abc', b'abc!'))
        with patch.object(adapter.backend, 'SERIALIZED_INTEGRITY_RANGES', ((2, 4),), create=True):
            with self.assertRaisesRegex(SaveError, 'invalid serialized-integrity range'):
                adapter._payload_matches_expected(b'abc', b'aXc')

    def test_save_as_reopens_checksums_and_fields_that_leave_the_editor_map(self):
        # These serializers recalculate native checksums or stop rediscovering
        # a field after a valid reduction. Exercise the shared on-disk contract
        # directly so it is covered on hosts without a Tk display.
        from tests.test_ayesha_ps3 import procedural_save
        from tests.test_nobu6_pk_pc import generated_raw
        from tests.test_samurai4dx_format import procedural_raw
        from tests.test_tecmo_super_bowl_nes import generated_raw as tecmo_raw
        from tests.test_wolong_expansion import named_battle_set_payload

        cases = (
            ('tecmo_super_bowl_nes', tecmo_raw(), {'team_9_play_0': 3}),
            ('samurai4dx', procedural_raw(),
             {'weapon_0_0_skill_0_rank': 5, 'weapon_0_0_skill_0_active': 1}),
            ('nobu6_pk_pc', generated_raw(), {'slot_0_district_0_gold': 0}),
            ('ayesha_ps3', procedural_save(), {'container_1_quantity': 1}),
            ('wolong', named_battle_set_payload(),
             {'sen': 123, 'battle_set_3_name': 'Short', 'storage_items_8_num': 1}),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for game_id, raw, changes in cases:
                with self.subTest(game_id=game_id):
                    adapter = get_game(game_id).get_scalar_adapter()
                    source = root / (game_id + adapter.extension)
                    destination = root / ('edited-' + game_id + adapter.extension)
                    source.write_bytes(raw)
                    document = adapter.read_save(source)
                    original_fields = adapter.field_map(document)
                    saved = adapter.save_as(document, changes, destination)
                    self.assertEqual(saved.raw, destination.read_bytes())
                    saved_fields = adapter.field_map(saved)
                    reader = getattr(adapter.backend, 'read_back_value', None)
                    for key, value in changes.items():
                        field = saved_fields.get(key) or original_fields[key]
                        applied = reader(saved, key) if callable(reader) else field.value(saved.payload)
                        self.assertIs(type(applied), type(value))
                        self.assertEqual(applied, value)
                    if game_id in ('nobu6_pk_pc', 'ayesha_ps3', 'wolong'):
                        removed_key = ('storage_items_8_num' if game_id == 'wolong'
                                       else next(iter(changes)))
                        self.assertNotIn(removed_key, saved_fields)

    def test_bound_adapter_keeps_noop_exact_and_rejects_serializer_that_drops_edit(self):
        class Format:
            id = 'contract_stub'

        layout = Format()

        class Document:
            def __init__(self, raw):
                self.format = layout
                self.source = Path('copy.dat')
                self.raw = bytes(raw)
                self.payload = bytes(raw)

        class Field:
            id = 'value'
            label = 'Value'
            offset = 0
            size = 1
            minimum = 0
            maximum = 255
            group = 'Test'
            slot = 0

            def value(self, payload):
                return payload[0]

            def validate(self, value):
                if type(value) is not int or not 0 <= value <= 255:
                    raise SaveError('Invalid test value.')

        field = Field()

        class Backend:
            def __init__(self):
                self.serialize_calls = 0

            def get_format(self, _game_id):
                return layout

            def read_save(self, *_args):
                raise AssertionError('Not used in this contract test.')

            def decode(self, raw, _game_id, _source):
                return Document(raw)

            def validate_document(self, document):
                if type(document.raw) is not bytes or document.payload != document.raw:
                    raise SaveError('Invalid test snapshot.')

            def fields_for(self, _document):
                return (field,)

            def field_map(self, _document):
                return {'value': field}

            def stage(self, _document, changes, key, value):
                return {**changes, key: value}

            def limit_values(self, _document, changes, _keys):
                return changes

            def maximums(self, _document, changes, _group=None):
                return changes

            def review(self, _document, changes):
                return [(field, 1, value) for value in changes.values()]

            def changed_payload(self, document, changes):
                result = bytearray(document.payload)
                if 'value' in changes:
                    result[0] = changes['value']
                return bytes(result)

            def serialize(self, document, _changes):
                self.serialize_calls += 1
                return document.raw  # Simulate a buggy writer that silently drops edits.

            def backup(self, _document):
                return Path('backup.dat')

            def save_as(self, *_args):
                raise AssertionError('Not used in this contract test.')

            def restore(self, *_args):
                raise AssertionError('Not used in this contract test.')

        backend = Backend()
        adapter = BoundScalarAdapter('contract_stub', '.dat', backend)
        document = Document(b'\x01')
        self.assertEqual(adapter.serialize(document, {'value': 1}), document.raw)
        self.assertEqual(backend.serialize_calls, 0)
        with self.assertRaisesRegex(SaveError, 'did not preserve every requested value'):
            adapter.serialize(document, {'value': 2})
        self.assertEqual(backend.serialize_calls, 1)

    def test_wrong_extension_and_game_never_invoke_backend_read(self):
        adapter = get_game('dw8xl').get_scalar_adapter()
        with patch.object(adapter.backend, 'read_save') as read:
            for path, identity in (('copy.psu', None), ('copy.dat', 'pw3')):
                with self.assertRaises(SaveError):
                    adapter.read_save(path, identity)
            read.assert_not_called()

    def test_snapshot_profile_identity_rejects_equal_and_permissive_metadata(self):
        adapter = get_game('dw8xl').get_scalar_adapter()
        document = adapter.decode(synthetic_raw('dw8xl'))
        class PermissiveProfile:
            id = 'dw8xl'
            def __eq__(self, _other): return True
        for layout in (replace(document.format), PermissiveProfile()):
            with self.subTest(profile=type(layout).__name__), \
                    patch.object(adapter.backend, 'fields_for') as fields:
                with self.assertRaises(SaveError):
                    adapter.fields_for(replace(document, format=layout))
                fields.assert_not_called()

    def test_bulk_staging_keeps_snapshot_and_does_not_repeat_native_cipher(self):
        adapter = get_game('dw8xl').get_scalar_adapter()
        document = adapter.decode(synthetic_raw('dw8xl'))
        changes = {}
        with patch.object(adapter.backend, 'decode', wraps=adapter.backend.decode) as decode:
            for field in adapter.fields_for(document):
                changes = adapter.stage(document, changes, field.id, field.maximum)
        self.assertGreater(len(changes), 100)
        self.assertEqual(document.raw, synthetic_raw('dw8xl'))
        # A full decode per field makes Max Visible block the UI for seconds.
        self.assertLessEqual(decode.call_count, 1)

    def test_incomplete_or_mismatched_backend_rejected_before_read(self):
        with self.assertRaisesRegex(SaveError, 'incomplete scalar backend'):
            BoundScalarAdapter('dw8xl', '.dat', SimpleNamespace())
        adapter = get_game('dw8xl').get_scalar_adapter()
        with patch.object(adapter.backend, 'get_format', return_value=SimpleNamespace(id='pw3')):
            with self.assertRaisesRegex(SaveError, 'different game/platform format'):
                BoundScalarAdapter('dw8xl', '.dat', adapter.backend)

    def test_new_scalar_registration_dispatches_self_test_without_game_branch(self):
        import koei_editor.game_registry as game_registry
        import koei_editor.shared.verified_self_test as verified_self_test
        import koei_editor.games.dw4hyper.dw4hyper_parser as dw4hyper_parser
        new = replace(get_game('dw4hyper'), id='contributor_example')
        layout = replace(dw4hyper_parser.FORMAT, id=new.id)
        with patch.object(game_registry, 'ALL_ADAPTERS', game_registry.ALL_ADAPTERS + (new,)), \
                patch.object(dw4hyper_parser, 'get_format', return_value=layout), \
                patch.object(verified_self_test, '_run', return_value={'success': True}) as run:
            self.assertEqual(verified_self_test.run(new.id, 'copy.dat', 'output'), {'success': True})
        bound, identity, source, output = run.call_args.args
        self.assertEqual(bound.game_id, new.id)
        self.assertIs(bound.backend, dw4hyper_parser)
        self.assertEqual((identity, source, output), (new.id, 'copy.dat', 'output'))

    def test_registered_editor_mismatch_rejected_before_constructor(self):
        game = get_game('pw3')
        constructor = Mock(game_id='dw8xl')
        with patch('koei_editor.game_registry.import_module', return_value=SimpleNamespace(Editor=constructor)):
            with self.assertRaises(SaveError):
                game.create_editor(None, None)
        constructor.assert_not_called()

    def test_editor_backend_or_extension_mismatch_rejected_before_constructor(self):
        game = get_game('pw3')
        backend = game.get_scalar_adapter().backend
        for declared_backend, extension in ((object(), '.dat'), (backend, '.psu')):
            constructor = Mock(game_id=game.id, backend=declared_backend, save_extension=extension)
            editor_module = SimpleNamespace(Editor=constructor)
            with patch('koei_editor.game_registry.import_module', side_effect=lambda name: editor_module if name == game.editor_module else backend):
                with self.assertRaises(SaveError):
                    game.create_editor(None, None)
            constructor.assert_not_called()

    def test_cli_uses_declared_scalar_capability_for_new_registration(self):
        import koei_editor.application as application
        import koei_editor.game_registry as game_registry
        new = replace(get_game('dw4hyper'), id='contributor_cli')
        report = {'format_sample_verified': False, 'fields_checked': 3}
        arguments = ['application.py', '--game', new.id, '--self-test', 'copy.dat', 'output']
        with patch.object(game_registry, 'ALL_ADAPTERS', game_registry.ALL_ADAPTERS + (new,)), \
                patch.object(application, 'ALL_ADAPTERS', application.ALL_ADAPTERS + (new,)), \
                patch.object(sys, 'argv', arguments), patch('koei_editor.shared.verified_self_test.run', return_value=report) as run, \
                patch.object(application.tk, 'Tk') as tk_root, patch('builtins.print'):
            application.main()
        run.assert_called_once_with(new.id, 'copy.dat', 'output')
        tk_root.assert_not_called()

    def test_session_validation_and_active_only_dispatch_hidden_close_cancel(self):
        from koei_editor.application import Application
        def session(game_id):
            values = {name: Mock(return_value=True) for name in SESSION_ACTIONS}
            return SimpleNamespace(game_id=game_id, document=None, changes={}, theme_name=Mock(), **values)
        first, second = session('first'), session('second')
        validate_session(first, 'first')
        with self.assertRaises(SaveError):
            validate_session(first, 'second')
        invalid = session('invalid')
        invalid.undo = None
        with self.assertRaises(SaveError):
            validate_session(invalid, 'invalid')
        app = Application.__new__(Application)
        app.sessions = {'first': (None, first), 'second': (None, second)}
        app.converter = None
        app.active_game = 'second'
        app.root = Mock()
        self.assertEqual(app.dispatch('undo'), 'break')
        first.undo.assert_not_called()
        second.undo.assert_called_once()
        app.active_game = None
        app.dispatch('undo')
        self.assertEqual(second.undo.call_count, 1)
        first.changes['pending'] = 123
        first.dirty_ok.return_value = False
        app.close()
        app.root.destroy.assert_not_called()
        self.assertEqual(first.changes, {'pending': 123})
