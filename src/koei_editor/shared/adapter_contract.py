"""Shared adapter contracts; format logic remains in explicit game backends.

Scalar backends retain the existing module API. BoundScalarAdapter checks the
selected identity before delegating, without probing another parser. DW3 uses
only EditorSession and keeps its tagged document and patch workflow.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from koei_editor.games.dw3.models import SaveError


class ScalarField(Protocol):
    id: str
    label: str
    offset: int
    size: int
    minimum: int
    maximum: int
    group: str
    slot: int

    def value(self, payload: bytes) -> int | str: ...
    def validate(self, value: int | str) -> None: ...


class ScalarFormat(Protocol):
    id: str
    title: str
    size: int
    fields: Sequence[ScalarField]


class ScalarDocument(Protocol):
    format: ScalarFormat
    source: Path
    raw: bytes
    payload: bytes
    sha256: str


class ScalarBackend(Protocol):
    def get_format(self, game_id: str) -> ScalarFormat: ...
    def read_save(self, path, game_id: str) -> ScalarDocument: ...
    def decode(self, raw: bytes, game_id: str, source: Path) -> ScalarDocument: ...
    def validate_document(self, document: ScalarDocument) -> None: ...
    def fields_for(self, document: ScalarDocument) -> Sequence[ScalarField]: ...
    def field_map(self, document: ScalarDocument) -> Mapping[str, ScalarField]: ...
    def stage(self, document, changes, key: str, value: int | str) -> dict: ...
    def limit_values(self, document, changes, keys) -> dict: ...
    def maximums(self, document, changes, group=None) -> dict: ...
    def review(self, document, changes) -> Sequence[tuple]: ...
    def changed_payload(self, document, changes) -> bytes: ...
    def serialize(self, document, changes) -> bytes: ...
    def backup(self, document) -> Path: ...
    def save_as(self, document, changes, destination) -> ScalarDocument: ...
    def restore(self, backup_path, destination, game_id: str) -> Path: ...


SESSION_ACTIONS = ('open', 'save_changes', 'save_as', 'undo', 'review', 'dirty_ok')
SCALAR_OPERATIONS = ('get_format', 'read_save', 'decode', 'validate_document',
                     'fields_for', 'field_map', 'stage', 'limit_values',
                     'maximums', 'review', 'changed_payload', 'serialize',
                     'backup', 'save_as', 'restore')


class EditorSession(Protocol):
    """The launcher contract, shared by scalar, research and bespoke editors."""
    document: object
    changes: object
    theme_name: object  # Tk variable with set(), owned by the editor.

    def open(self) -> None: ...
    def save_changes(self) -> None: ...
    def save_as(self) -> None: ...
    def undo(self) -> None: ...
    def review(self) -> None: ...
    def dirty_ok(self) -> bool: ...


def is_opened_value(document, field, value):
    """Whether a value exactly reassigns the immutable opened field value."""
    opened = field.value(document.payload)
    return (type(value) in (int, str) and type(value) is type(opened)
            and value == opened)


def validate_pending_values(document, changes, fields):
    """Validate a complete scalar change map while preserving original values.

    A game's editing bound must not make an otherwise readable, unusual opened
    value prevent unrelated edits. Only the exact value with the exact type is
    accepted as unchanged; every new value still passes the field validator.
    """
    if not isinstance(changes, Mapping):
        raise SaveError('Pending edits must be a mapping of verified fields and values.')
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('A requested field is not verified for this game.')
        field = fields[key]
        if not is_opened_value(document, field, value):
            field.validate(value)
    return fields


def normalize_pending_values(document, changes, fields):
    """Validate a change map and remove exact assignments of opened values."""
    validate_pending_values(document, changes, fields)
    return {key: value for key, value in changes.items()
            if not is_opened_value(document, fields[key], value)}


def validate_session(editor, game_id):
    missing = [name for name in SESSION_ACTIONS if not callable(getattr(editor, name, None))]
    missing += [name for name in ('document', 'changes', 'theme_name') if not hasattr(editor, name)]
    if not callable(getattr(getattr(editor, 'theme_name', None), 'set', None)):
        missing.append('theme_name.set')
    if missing:
        raise SaveError(f'{game_id}: editor does not implement the session contract ({", ".join(missing)}).')
    identity = getattr(editor, 'game_id', game_id)
    if identity != game_id:
        raise SaveError(f'{game_id}: editor belongs to a different game.')
    return editor


@dataclass(frozen=True)
class BoundScalarAdapter:
    """Bind one backend to one game/platform before reading or writing data."""
    game_id: str
    extension: str
    backend: ScalarBackend

    def __post_init__(self):
        missing = [name for name in SCALAR_OPERATIONS if not callable(getattr(self.backend, name, None))]
        if missing:
            raise SaveError(f'{self.game_id}: incomplete scalar backend ({", ".join(missing)}).')
        self.get_format()

    def _identity(self, game_id):
        if game_id is not None and game_id != self.game_id:
            raise SaveError('The selected adapter belongs to a different game/platform.')

    def _path(self, path):
        if Path(path).suffix.lower() != self.extension:
            raise SaveError(f'{self.game_id} requires an explicit {self.extension} copy.')

    def get_format(self, game_id=None):
        self._identity(game_id)
        layout = self.backend.get_format(self.game_id)
        if getattr(layout, 'id', None) != self.game_id:
            raise SaveError('The registered backend returned a different game/platform format.')
        return layout

    def _document_identity(self, document):
        layout = getattr(document, 'format', None)
        if getattr(layout, 'id', None) != self.game_id or layout is not self.get_format():
            raise SaveError('This document belongs to a different game/platform adapter.')

    def validate_document(self, document):
        self._document_identity(document)
        self.backend.validate_document(document)

    def read_save(self, path, game_id=None):
        self._identity(game_id)
        self._path(path)
        document = self.backend.read_save(path, self.game_id)
        self.validate_document(document)
        return document

    def decode(self, raw, game_id=None, source=None):
        self._identity(game_id)
        source = Path('copy' + self.extension) if source is None else Path(source)
        self._path(source)
        document = self.backend.decode(raw, self.game_id, source)
        self.validate_document(document)
        return document

    def _call(self, operation, document, *args):
        # Frozen snapshots were validated on read/decode. Writers keep their
        # own full integrity checks; decoding every staged field would make a
        # bulk GUI operation repeat the entire native cipher hundreds of times.
        self._document_identity(document)
        return getattr(self.backend, operation)(document, *args)

    def fields_for(self, document):
        return self._call('fields_for', document)

    def field_map(self, document):
        return self._call('field_map', document)

    @staticmethod
    def _pending_value(document, field, value):
        if not is_opened_value(document, field, value):
            field.validate(value)

    def _pending_fields(self, document, changes):
        self._document_identity(document)
        fields = self.backend.field_map(document)
        return validate_pending_values(document, changes, fields)

    def _normalized_changes(self, document, changes):
        fields = self._pending_fields(document, changes)
        return {key: value for key, value in changes.items()
                if not is_opened_value(document, fields[key], value)}

    def _verify_serialized(self, document, changes, raw, expected_payload):
        if type(raw) is not bytes:
            raise SaveError(f'{self.game_id}: serializer did not return save bytes.')
        if not changes:
            if raw != document.raw:
                raise SaveError(f'{self.game_id}: an unchanged save must remain byte-identical.')
            return document
        try:
            original_fields = self.backend.field_map(document)
            result = self.backend.decode(raw, self.game_id, document.source)
            self.validate_document(result)
            if (type(expected_payload) is not bytes or type(result.payload) is not bytes
                    or not self._payload_matches_expected(expected_payload, result.payload)):
                raise SaveError(f'{self.game_id}: edited save did not preserve every requested value.')
            result_fields = self.backend.field_map(result)
            for key, value in changes.items():
                original_field = original_fields.get(key)
                field = result_fields.get(key) or original_field
                reader = getattr(self.backend, 'read_back_value', None)
                applied = (reader(result, key) if callable(reader) else
                           field.value(result.payload) if field is not None else None)
                if (original_field is None or type(applied) is not type(value) or applied != value):
                    raise SaveError(f'{self.game_id}: edited field {key} did not apply in the saved copy.')
        except SaveError:
            raise
        except Exception as error:
            raise SaveError(f'{self.game_id}: edited save failed read-back validation.') from error
        return result

    def _payload_matches_expected(self, expected, actual):
        """Allow a backend to declare only its recalculated native integrity words."""
        if len(expected) != len(actual):
            return False
        ranges = getattr(self.backend, 'SERIALIZED_INTEGRITY_RANGES', ())
        try:
            ranges = tuple(ranges)
        except TypeError as error:
            raise SaveError(f'{self.game_id}: invalid serialized-integrity range declaration.') from error
        ignored = set()
        for item in ranges:
            if (type(item) is not tuple or len(item) != 2
                    or type(item[0]) is not int or type(item[1]) is not int
                    or item[0] < 0 or item[1] <= item[0] or item[1] > len(expected)):
                raise SaveError(f'{self.game_id}: invalid serialized-integrity range declaration.')
            ignored.update(range(*item))
        return all(before == after or offset in ignored
                   for offset, (before, after) in enumerate(zip(expected, actual)))

    def stage(self, document, changes, key, value):
        pending = self._normalized_changes(document, changes)
        fields = self.backend.field_map(document)
        if type(key) is not str or key not in fields:
            raise SaveError('A requested field is not verified for this game.')
        field = fields[key]
        self._pending_value(document, field, value)
        if is_opened_value(document, field, value):
            pending.pop(key, None)
            return pending
        result = self._call('stage', document, pending, key, value)
        return self._normalized_changes(document, result)

    def limit_values(self, document, changes, keys):
        pending = self._normalized_changes(document, changes)
        fields = self.backend.field_map(document)
        try:
            keys = tuple(keys)
        except TypeError as error:
            raise SaveError('Choose verified field IDs for the Max action.') from error
        for key in keys:
            if type(key) is not str or key not in fields:
                raise SaveError('A requested field is not verified for this game.')
        result = self._call('limit_values', document, pending, keys)
        return self._normalized_changes(document, result)

    def maximums(self, document, changes, group=None):
        pending = self._normalized_changes(document, changes)
        result = self._call('maximums', document, pending, group)
        return self._normalized_changes(document, result)

    def review(self, document, changes):
        pending = self._normalized_changes(document, changes)
        return self._call('review', document, pending)

    def changed_payload(self, document, changes):
        pending = self._normalized_changes(document, changes)
        payload = self._call('changed_payload', document, pending)
        if type(payload) is not bytes:
            raise SaveError(f'{self.game_id}: backend did not return an encoded payload.')
        return payload

    def serialize(self, document, changes):
        self.validate_document(document)
        pending = self._normalized_changes(document, changes)
        raw, _expected_payload = self._serialize_checked(document, pending)
        return raw

    def _serialize_checked(self, document, pending):
        if not pending:
            return document.raw, document.payload
        expected_payload = self._call('changed_payload', document, pending)
        if type(expected_payload) is not bytes:
            raise SaveError(f'{self.game_id}: backend did not return an encoded payload.')
        raw = self._call('serialize', document, pending)
        self._verify_serialized(document, pending, raw, expected_payload)
        return raw, expected_payload

    def backup(self, document):
        return self._call('backup', document)

    def save_as(self, document, changes, destination):
        self._path(destination)
        self.validate_document(document)
        pending = self._normalized_changes(document, changes)
        expected_raw, expected_payload = self._serialize_checked(document, pending)
        result = self._call('save_as', document, pending, destination)
        self.validate_document(result)
        try:
            saved = self.backend.read_save(destination, self.game_id)
            self.validate_document(saved)
        except SaveError as error:
            raise SaveError(f'{self.game_id}: the saved file failed on-disk read-back validation.') from error
        except Exception as error:
            raise SaveError(f'{self.game_id}: the saved file could not be reopened for verification.') from error
        if saved.raw != result.raw:
            raise SaveError(f'{self.game_id}: the saved file differs from the backend result.')
        if not self._payload_matches_expected(expected_payload, saved.payload):
            raise SaveError(f'{self.game_id}: the saved copy differs from the verified edit.')
        if not pending and saved.raw != expected_raw:
            raise SaveError(f'{self.game_id}: an unchanged saved copy must remain byte-identical.')
        if pending:
            # Prefer descriptors from the reopened output because serializers
            # may move later fields when an earlier text token changes length.
            # Fall back to an opened descriptor when a valid reduction makes a
            # record ineligible for rediscovery (for example a stack of one).
            original_fields = self.backend.field_map(document)
            saved_fields = self.backend.field_map(saved)
            reader = getattr(self.backend, 'read_back_value', None)
            for key, value in pending.items():
                original_field = original_fields.get(key)
                field = saved_fields.get(key) or original_field
                applied = (reader(saved, key) if callable(reader) else
                           field.value(saved.payload) if field is not None else None)
                if (original_field is None or type(applied) is not type(value)
                        or applied != value):
                    raise SaveError(f'{self.game_id}: edited field {key} did not apply in the saved copy.')
        return saved

    def restore(self, backup_path, destination, game_id=None):
        self._identity(game_id)
        self._path(backup_path)
        self._path(destination)
        return self.backend.restore(backup_path, destination, self.game_id)
