"""Preset data cannot bypass native final-batch, source or read-back validation."""
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from koei_editor.shared import edit_presets as presets
from koei_editor.shared.verified_editor import Field


@dataclass(frozen=True)
class TextField:
    id: str = 'nickname'
    label: str = 'Plan name'
    offset: int = 3
    size: int = 8
    minimum: int = 0
    maximum: int = 8
    group: str = 'Names'
    slot: int = 0
    kind: str = 'text'
    encoding: str = 'ascii'
    maxable: bool = False

    def value(self, payload):
        return payload[self.offset:self.offset + self.size].rstrip(b'\0').decode('ascii')

    def validate(self, value):
        if type(value) is not str or len(value) > self.size or any(not 32 <= ord(c) <= 126 for c in value):
            raise SaveError('The name must fit its verified ASCII storage.')


@dataclass(frozen=True)
class PresetDocument:
    format: object
    source: Path
    raw: bytes
    payload: bytes

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def fixture_backend():
    """Deliberately tiny native-like format with an equipped-reference dependency."""
    fields = (
        Field('left', 'Left hand', 0, 1, 100, 'Loadout', 1, experimental=False),
        Field('right', 'Right hand', 1, 1, 100, 'Loadout', 1, experimental=False),
        Field('gold', 'Gold', 2, 1, 100), TextField(),
    )
    layout = SimpleNamespace(id='preset_fixture', title='Preset contract fixture', fields=fields, size=15)

    def encode(payload):
        body = b'P' + bytes(payload)
        return body + bytes([sum(body) % 256])

    def decode(raw, game_id='preset_fixture', source=Path('copy.dat')):
        if (game_id != layout.id or type(raw) is not bytes or len(raw) != 15
                or raw[:1] != b'P' or sum(raw[:-1]) % 256 != raw[-1]):
            raise SaveError('Fixture identity or integrity is invalid.')
        return PresetDocument(layout, Path(source), raw, raw[1:-1])

    def validate(document):
        if decode(document.raw, layout.id, document.source) != document:
            raise SaveError('The fixture document changed.')

    def changed(document, changes):
        result = bytearray(document.payload)
        mapping = {field.id: field for field in fields}
        for key, value in changes.items():
            field = mapping[key]
            if value != field.value(document.payload) or type(value) is not type(field.value(document.payload)):
                field.validate(value)
            result[field.offset:field.offset + field.size] = (
                value.encode('ascii').ljust(field.size, b'\0') if type(value) is str
                else value.to_bytes(field.size, 'little'))
        if result[0] and result[0] == result[1]:
            raise SaveError('The same physical weapon cannot occupy both hands.')
        return bytes(result)

    def stage(document, changes, key, value):
        result = dict(changes)
        result[key] = value
        changed(document, result)
        return result

    def review(document, changes):
        changed(document, changes)
        return tuple((field, field.value(document.payload), changes[field.id])
                     for field in fields if field.id in changes)

    def unavailable(*_args, **_kwargs):
        raise AssertionError('Preset operations must not invoke save/backup/restore/Max.')

    backend = SimpleNamespace(
        get_format=lambda _game_id: layout,
        read_save=lambda path, game_id: decode(Path(path).read_bytes(), game_id, Path(path)),
        decode=decode, validate_document=validate, fields_for=lambda _doc: fields,
        field_map=lambda _doc: {field.id: field for field in fields}, stage=stage,
        limit_values=unavailable, maximums=unavailable, review=review,
        changed_payload=changed, serialize=lambda document, changes: encode(changed(document, changes)),
        backup=unavailable, save_as=unavailable, restore=unavailable,
    )
    raw = encode(bytes([10, 20, 50]) + b'Original' + b'\xab\xcd')
    return backend, raw


class EditPresetTests(unittest.TestCase):
    def test_explicit_assignment_preview_keeps_opened_reversion_and_unrelated_edits(self):
        plan = presets.prepare_assignments(self.adapter, self.document,
                                          {'gold': 25, 'nickname': 'Changed'}, {'gold': 50}, 'Revert gold')
        self.assertEqual(tuple((edit.field, edit.value) for edit in plan.preset.edits), (('gold', 50),))
        self.assertEqual(dict(plan.result), {'nickname': 'Changed'})
        self.assertEqual({row.field.id for row in plan.rows}, {'gold', 'nickname'})
        self.assertEqual(presets.confirm(plan, self.adapter, self.document,
                                       {'gold': 25, 'nickname': 'Changed'}), {'nickname': 'Changed'})

    def test_explicit_assignment_preview_validates_final_dependencies_and_types(self):
        for assignments in ({}, {'unknown': 2}, {'gold': True}, {'left': 20}):
            with self.subTest(assignments=assignments), self.assertRaises(SaveError):
                presets.prepare_assignments(self.adapter, self.document, {}, assignments)
        # A swap may pass as a complete native map even when a sequential
        # staging operation would temporarily collide with the other hand.
        plan = presets.prepare_assignments(self.adapter, self.document, {}, {'left': 20, 'right': 10})
        self.assertEqual(dict(plan.result), {'left': 20, 'right': 10})

    def setUp(self):
        self.area = tempfile.TemporaryDirectory()
        self.addCleanup(self.area.cleanup)
        self.folder = Path(self.area.name)
        self.backend, raw = fixture_backend()
        self.adapter = BoundScalarAdapter('preset_fixture', '.dat', self.backend)
        self.source = self.folder / 'original.dat'
        self.source.write_bytes(raw)
        self.document = self.adapter.read_save(self.source)
        self.preset = presets.create(self.adapter, self.document, {'gold': 75}, 'Ordinary plan')

    def test_strict_json_roundtrip_and_new_file_suffix(self):
        self.assertEqual(presets.loads(presets.dumps(self.preset)), self.preset)
        for name, expected in (('plan', 'plan.edits.json'), ('plan.json', 'plan.edits.json'),
                               ('APP.BIN', 'APP.BIN.edits.json'), ('plan.edits', 'plan.edits.json'),
                               ('plan.EDITS.JSON', 'plan.EDITS.JSON')):
            with self.subTest(name=name):
                self.assertEqual(presets.destination_path(self.folder / name).name, expected)
        destination = presets.export(self.preset, self.adapter, self.document, self.folder / 'plan.json')
        self.assertEqual(destination.name, 'plan.edits.json')
        self.assertEqual(presets.load(destination), self.preset)
        with self.assertRaises(FileExistsError):
            presets.export(self.preset, self.adapter, self.document, self.folder / 'plan')
        self.assertEqual(self.source.read_bytes(), self.document.raw)

    def test_complete_pending_map_is_frozen_and_merged_without_a_save(self):
        pending = {'nickname': 'Build A', 'right': 30}
        before = dict(pending)
        plan = presets.prepare(self.adapter, self.document, pending, self.preset)
        self.assertEqual(pending, before)
        self.assertEqual(dict(plan.result), {'gold': 75, **pending})
        self.assertEqual({row.field.id for row in plan.rows}, {'gold', 'nickname', 'right'})
        self.assertEqual(presets.confirm(plan, self.adapter, self.document, pending), dict(plan.result))
        self.assertEqual(tuple(self.folder.iterdir()), (self.source,))
        pending['nickname'] = 'Build B'
        with self.assertRaisesRegex(SaveError, 'Pending edits changed'):
            presets.confirm(plan, self.adapter, self.document, pending)
        self.assertEqual(self.source.read_bytes(), self.document.raw)

    def test_source_binding_accepts_identical_copy_and_rejects_new_progress(self):
        identical = self.folder / 'identical.dat'
        identical.write_bytes(self.document.raw)
        copied = self.adapter.read_save(identical)
        self.assertEqual(dict(presets.prepare(self.adapter, copied, {}, self.preset).result), {'gold': 75})
        updated = self.backend.serialize(self.document, {'gold': 60})
        identical.write_bytes(updated)
        other = self.adapter.read_save(identical)
        with self.assertRaisesRegex(SaveError, 'exact original'):
            presets.prepare(self.adapter, other, {}, self.preset)

    def test_wrong_game_and_mapping_drift_fail_before_application(self):
        for preset, message in ((replace(self.preset, game_id='different_profile'), 'different game'),
                                (replace(self.preset, profile_sha256='0' * 64), 'field definitions changed')):
            with self.subTest(message=message), self.assertRaisesRegex(SaveError, message):
                presets.prepare(self.adapter, self.document, {}, preset)

    def test_source_or_companion_change_rejects_export_and_confirm(self):
        plan = presets.prepare(self.adapter, self.document, {}, self.preset)
        self.source.write_bytes(self.backend.serialize(self.document, {'gold': 55}))
        with self.assertRaises(SaveError):
            presets.confirm(plan, self.adapter, self.document, {})
        with self.assertRaises(SaveError):
            presets.export(self.preset, self.adapter, self.document, self.folder / 'never')
        self.assertFalse((self.folder / 'never.edits.json').exists())
        self.source.write_bytes(self.document.raw)
        with patch.object(self.backend, 'read_save', side_effect=SaveError('Original companion changed.')):
            with self.assertRaisesRegex(SaveError, 'companion'):
                presets.prepare(self.adapter, self.document, {}, self.preset)

    def test_late_export_failure_keeps_completed_json_and_foreign_replacement(self):
        real_atomic = presets.atomic_new
        def write_then_change_source(data, destination):
            result = real_atomic(data, destination)
            self.source.write_bytes(self.backend.serialize(self.document, {'gold': 55}))
            return result
        path = self.folder / 'retained'
        with patch.object(presets, 'atomic_new', side_effect=write_then_change_source):
            with self.assertRaisesRegex(SaveError, 'retained; do not use'):
                presets.export(self.preset, self.adapter, self.document, path)
        completed = presets.destination_path(path)
        self.assertEqual(completed.read_bytes(), presets.dumps(self.preset))
        self.source.write_bytes(self.document.raw)
        foreign = b'Another process owns this replacement.'
        def write_then_replace(data, destination):
            result = real_atomic(data, destination)
            result.write_bytes(foreign)
            return result
        path = self.folder / 'foreign'
        with patch.object(presets, 'atomic_new', side_effect=write_then_replace):
            with self.assertRaisesRegex(SaveError, 'retained; do not use'):
                presets.export(self.preset, self.adapter, self.document, path)
        self.assertEqual(presets.destination_path(path).read_bytes(), foreign)

    def test_exact_text_scalars_keep_types_and_native_encoding(self):
        text = presets.create(self.adapter, self.document, {'nickname': ''}, 'Clear name')
        self.assertIs(type(presets.loads(presets.dumps(text)).edits[0].value), str)
        plan = presets.prepare(self.adapter, self.document, {'gold': 75}, text)
        reopened = self.adapter.decode(self.adapter.serialize(self.document, dict(plan.result)))
        self.assertEqual(self.backend.field_map(reopened)['nickname'].value(reopened.payload), '')
        self.assertEqual(reopened.payload[-2:], self.document.payload[-2:])
        invalid = replace(text, edits=(presets.PresetEdit('nickname', '\u2665'),))
        with self.assertRaisesRegex(SaveError, 'ASCII'):
            presets.prepare(self.adapter, self.document, {}, invalid)

    def test_complete_native_dependency_check_includes_kept_edits(self):
        left = replace(self.preset, edits=(presets.PresetEdit('left', 30),))
        pending = {'right': 30}
        with self.assertRaisesRegex(SaveError, 'both hands'):
            presets.prepare(self.adapter, self.document, pending, left)
        self.assertEqual(pending, {'right': 30})

    def test_valid_reference_swap_is_checked_as_a_final_batch(self):
        swap = replace(self.preset, edits=(presets.PresetEdit('left', 20), presets.PresetEdit('right', 10)))
        plan = presets.prepare(self.adapter, self.document, {}, swap)
        self.assertEqual(dict(plan.result), {'left': 20, 'right': 10})
        encoded = self.adapter.serialize(self.document, dict(plan.result))
        reopened = self.adapter.decode(encoded)
        self.assertEqual(reopened.payload[:2], bytes([20, 10]))
        self.assertEqual(reopened.payload[2:], self.document.payload[2:])

    def test_explicit_original_value_unstages_but_keeps_dependency_guards(self):
        revert = replace(self.preset, edits=(presets.PresetEdit('gold', 50),))
        plan = presets.prepare(self.adapter, self.document, {'gold': 75, 'left': 30}, revert)
        self.assertEqual(dict(plan.result), {'left': 30})
        row = next(row for row in plan.rows if row.field.id == 'gold')
        self.assertEqual((row.opened, row.before, row.after), (50, 75, 50))
        left = replace(self.preset, edits=(presets.PresetEdit('left', 10),))
        with self.assertRaisesRegex(SaveError, 'both hands'):
            presets.prepare(self.adapter, self.document, {'left': 30, 'right': 10}, left)

    def test_unusual_original_value_can_be_reverted_exactly(self):
        self.source.write_bytes(self.backend.serialize(self.document, {'gold': 75}))
        payload = bytearray(self.adapter.read_save(self.source).payload)
        payload[2] = 200
        body = b'P' + payload
        self.source.write_bytes(body + bytes([sum(body) % 256]))
        document = self.adapter.read_save(self.source)
        ordinary = presets.create(self.adapter, document, {'gold': 75}, 'Reduction')
        revert = replace(ordinary, edits=(presets.PresetEdit('gold', 200),))
        plan = presets.prepare(self.adapter, document, {'gold': 75}, revert)
        self.assertEqual(plan.result, ())
        self.assertEqual(plan.experimental_count, 0)

    def test_experimental_mode_is_explicit_and_never_enabled_by_import(self):
        experimental = replace(self.adapter, experimental=True)
        higher = presets.create(experimental, self.document, {'gold': 200}, 'Experimental plan')
        self.assertTrue(higher.experimental)
        with self.assertRaises(SaveError):
            presets.prepare(self.adapter, self.document, {}, higher)
        plan = presets.prepare(experimental, self.document, {}, higher)
        self.assertEqual(plan.experimental_count, 1)
        with self.assertRaisesRegex(SaveError, 'understates'):
            presets.prepare(experimental, self.document, {}, replace(higher, experimental=False))
        with self.assertRaisesRegex(SaveError, 'session changed'):
            presets.confirm(plan, replace(experimental, experimental=False), self.document, {})
        self.assertFalse(self.adapter.experimental)

    def test_serializer_must_reparse_the_requested_values(self):
        with patch.object(self.backend, 'serialize', return_value=self.document.raw):
            with self.assertRaisesRegex(SaveError, 'requested value'):
                presets.prepare(self.adapter, self.document, {}, self.preset)

    def test_forged_plan_and_invalid_current_values_are_not_accepted(self):
        plan = presets.prepare(self.adapter, self.document, {}, self.preset)
        with self.assertRaisesRegex(SaveError, 'preview changed'):
            presets.confirm(replace(plan, result=(('gold', 99),)), self.adapter, self.document, {})
        for pending in ({'gold': True}, {'missing': 1}, [('gold', 50)], {'gold': '75'}):
            with self.subTest(pending=pending), self.assertRaises(SaveError):
                presets.prepare(self.adapter, self.document, pending, self.preset)

    def test_strict_json_rejects_extra_properties_duplicates_and_bad_types(self):
        original = json.loads(presets.dumps(self.preset))
        variants = []
        for key, value in (('version', True), ('version', 2), ('experimental', 1), ('name', ''),
                            ('name', '\ud800'), ('schema', 'review'), ('game_id', '../profile')):
            variant = dict(original)
            variant[key] = value
            variants.append(variant)
        for value in (True, 1.5, None, [], {}, 1 << 65, '\ud800'):
            variants.append({**original, 'edits': [{'field': 'gold', 'value': value}]})
        variants.extend(({**original, 'offset': 0}, {**original, 'edits': []},
                         {**original, 'edits': original['edits'] * 2},
                         {**original, 'scope': {'kind': 'portable', 'source_sha256': '0' * 64}},
                         {**original, 'scope': {'kind': 'source', 'source_sha256': 'X' * 64}},
                         {**original, 'edits': [{'field': 'gold', 'value': 75, 'offset': 2}]}))
        for variant in variants:
            with self.subTest(variant=repr(variant)), self.assertRaises(SaveError):
                presets.loads(json.dumps(variant).encode())
        for raw in (b'{"schema":1,"schema":2}', b'{"a":{"b":1,"b":2}}', b'NaN',
                    b'Infinity', b'\xff', b'[' * 2000, b'{} trailing'):
            with self.subTest(raw=raw[:60]), self.assertRaises(SaveError):
                presets.loads(raw)

    def test_bounded_reads_and_wrong_document_types(self):
        oversized = self.folder / 'oversized.edits.json'
        with oversized.open('wb') as stream:
            stream.truncate(presets.MAX_BYTES + 1)
        with self.assertRaises(SaveError):
            presets.load(oversized)
        wrong = self.folder / 'report.changes.json'
        wrong.write_bytes(presets.dumps(self.preset))
        with self.assertRaisesRegex(SaveError, 'edits.json'):
            presets.load(wrong)
        for data in (bytearray(presets.dumps(self.preset)), '', b''):
            with self.subTest(data=type(data)), self.assertRaises(SaveError):
                presets.loads(data)

    def test_source_path_alias_and_live_save_destination_are_protected(self):
        with self.assertRaises(FileExistsError):
            presets.export(
                self.preset, self.adapter, self.document, self._existing_alias_destination())
        with self.assertRaisesRegex(SaveError, 'Steam Cloud'):
            presets.export(self.preset, self.adapter, self.document,
                           self.folder / 'Steam/userdata/123/remote/test')

    def _existing_alias_destination(self):
        path = self.folder / 'original.edits.json'
        try:
            path.symlink_to(self.source)
        except OSError:
            # Windows hosts without symlink privilege still exercise an
            # existing destination; source-alias policy has its own suite.
            path.write_bytes(b'keep existing bytes')
        return path

    def test_late_source_mutation_during_create_prepare_and_confirm_is_rejected(self):
        plan = presets.prepare(self.adapter, self.document, {}, self.preset)
        serialize = self.backend.serialize
        original = self.document.raw
        for operation in ('create', 'prepare', 'confirm'):
            with self.subTest(operation=operation):
                self.source.write_bytes(original)
                mutations = []
                def mutate(document, changes):
                    raw = serialize(document, changes)
                    if changes.get('gold') == 75:
                        self.source.write_bytes(serialize(document, {'gold': 55}))
                        mutations.append(True)
                    return raw
                pending = {}
                with patch.object(self.backend, 'serialize', side_effect=mutate), self.assertRaisesRegex(SaveError, 'metadata changed'):
                    if operation == 'create':
                        presets.create(self.adapter, self.document, {'gold': 75}, 'Late mutation')
                    elif operation == 'prepare':
                        presets.prepare(self.adapter, self.document, pending, self.preset)
                    else:
                        presets.confirm(plan, self.adapter, self.document, pending)
                self.assertEqual(len(mutations), 1)
                self.assertEqual(pending, {})
        self.source.write_bytes(original)

    def test_valid_context_replacement_during_final_serialization_is_rejected(self):
        from koei_editor.game_registry import get_game
        from koei_editor.games.deception4_ps3 import parser
        from tests.test_ps3_new_families import fixture
        from tests.test_ps3_expansion import PS3ContextTests
        source = self.folder / 'DATA.BIN'
        source.write_bytes(fixture(parser))
        metadata = self.folder / 'PARAM.SFO'
        original_context = PS3ContextTests.metadata('NPUB31442-GAMEDATA-10')
        metadata.write_bytes(original_context)
        adapter = get_game(parser.GAME_ID).get_scalar_adapter()
        document = adapter.read_save(source)
        preset = presets.create(adapter, document, {'warl': 100}, 'Original context')
        plan = presets.prepare(adapter, document, {}, preset)
        serialize = parser.serialize
        def mutate(document, changes):
            raw = serialize(document, changes)
            if changes.get('warl') == 100:
                metadata.write_bytes(PS3ContextTests.metadata('NPUB31442-GAMEDATA-11'))
            return raw
        with patch.object(parser, 'serialize', side_effect=mutate), self.assertRaisesRegex(SaveError, 'metadata changed'):
            presets.confirm(plan, adapter, document, {})
        self.assertEqual(source.read_bytes(), document.raw)

    def test_fingerprint_includes_native_encoding_choices_mirrors_and_class_identity(self):
        @dataclass(frozen=True)
        class NativeField(Field):
            byteorder: str = 'little'
            storage: str = 'unsigned'
            shift: int = 0
            mirrors: tuple = ()
            choices: tuple = ()
        @dataclass(frozen=True)
        class OtherNativeField(NativeField):
            pass
        mapping = self.backend.field_map(self.document)
        original = mapping['gold']
        field = NativeField(**{key: getattr(original, key) for key in original.__dataclass_fields__})
        original_mapping = {**mapping, 'gold': field}
        with patch.object(self.backend, 'field_map', return_value=original_mapping):
            preset = presets.create(self.adapter, self.document, {'gold': 75}, 'Native metadata')
        variants = [replace(field, **{key: value}) for key, value in (
            ('byteorder', 'big'), ('storage', 'item-level'), ('shift', 1),
            ('mirrors', (4, 5)), ('choices', ((25, 'One star'), (75, 'Three stars'))))]
        variants.append(OtherNativeField(**{key: getattr(field, key) for key in field.__dataclass_fields__}))
        for changed in variants:
            with self.subTest(field=changed), patch.object(self.backend, 'field_map', return_value={**mapping, 'gold': changed}):
                with self.assertRaisesRegex(SaveError, 'field definitions changed'):
                    presets.prepare(self.adapter, self.document, {}, preset)
        self.assertEqual(self.source.read_bytes(), self.document.raw)

    def test_real_registered_backend_keeps_immutable_source_and_full_review(self):
        from koei_editor.game_registry import get_game
        from tests.test_verified_editors import synthetic_raw
        adapter = get_game('dw8xl').get_scalar_adapter()
        source = self.folder / 'dw8xl.dat'
        source.write_bytes(synthetic_raw('dw8xl'))
        document = adapter.read_save(source)
        preset = presets.create(adapter, document, {'gold': 12345, 'officer_0_attack': 100}, 'Officer build')
        plan = presets.prepare(adapter, document, {'gems': 123}, preset)
        self.assertEqual(dict(plan.result), {'gems': 123, 'gold': 12345, 'officer_0_attack': 100})
        self.assertEqual(len(plan.rows), 3)
        self.assertEqual(source.read_bytes(), document.raw)
        self.assertEqual(len(adapter.review(document, dict(plan.result))), 3)


if __name__ == '__main__':
    unittest.main()
