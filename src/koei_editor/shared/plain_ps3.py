"""Shared immutable copied-export plumbing; game identity and fields are injected."""
from dataclasses import dataclass, replace
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.shared.ps3_copy import PS3CopyStorage
from koei_editor.shared.ps3_export import MAX_SFO_SIZE, savedata_directory
from koei_editor.shared.save_safety import safe_path


@dataclass(frozen=True)
class NativeField:
    id: str
    label: str
    offset: int
    size: int
    maximum: int
    group: str = 'Resources'
    slot: int = 0
    minimum: int = 0
    maxable: bool = False
    kind: str = 'int'
    byteorder: str = 'big'
    experimental: bool = True

    @property
    def encoding(self):
        return 'unsigned ' + self.byteorder + '-endian integer'

    @property
    def experimental_maximum(self):
        return (1 << (8 * self.size)) - 1 if self.experimental else None

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], self.byteorder)

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(value, self.minimum, self.maximum,
                storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label}: choose a whole number from {self.minimum:,} to {self.maximum:,}.')

    def encoded(self, value):
        self.validate(value)
        return value.to_bytes(self.size, self.byteorder)


@dataclass(frozen=True)
class NativeFormat:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = True
    game_load_verified: bool = False


@dataclass(frozen=True)
class NativeDocument:
    format: NativeFormat
    source: Path
    raw: bytes
    payload: bytes
    context_digest: str = ''

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


class PlainPS3Backend:
    def __init__(self, native_format, qualifier, directory_validator, extension, inspector):
        self.format = native_format
        self.qualifier, self.directory_validator = qualifier, directory_validator
        self.extension, self.inspector = extension, inspector
        self.storage = PS3CopyStorage(native_format.id, native_format.size, self.validate_document,
            self.context_raw, self.decode, self.read_save, self.serialize, extension)

    def get_format(self, game_id=None):
        if game_id is not None and game_id != self.format.id:
            raise SaveError('Select the exact ' + self.format.title + ' profile.')
        return self.format

    def decode(self, raw, game_id=None, source=Path('copied-save')):
        self.get_format(game_id)
        if type(raw) is not bytes or len(raw) != self.format.size:
            raise SaveError(f'{self.format.title} requires an immutable decrypted export of {self.format.size:,} bytes.')
        self.qualifier(raw)
        return NativeDocument(self.format, Path(source), raw, raw)

    def context_raw(self, path):
        companion = safe_path(Path(path).parent / 'PARAM.SFO')
        try:
            with companion.open('rb') as stream:
                metadata = stream.read(MAX_SFO_SIZE + 1)
        except OSError as error:
            raise SaveError('Keep the original PARAM.SFO beside this copied PS3 gameplay export.') from error
        directory = savedata_directory(metadata)
        if not self.directory_validator(directory):
            raise SaveError('The original PS3 title/slot metadata does not match ' + self.format.title + '.')
        return metadata

    def read_save(self, path, game_id=None):
        self.get_format(game_id)
        path = safe_path(path)
        if path.suffix.lower() != self.extension:
            raise SaveError('Open a separate copy with the native gameplay filename/extension.')
        metadata = self.context_raw(path)
        with path.open('rb') as stream:
            doc = self.decode(stream.read(self.format.size + 1), game_id, path)
        if self.context_raw(path) != metadata:
            raise SaveError('Original PS3 metadata changed during opening.')
        return replace(doc, context_digest=hashlib.sha256(metadata).hexdigest())

    def validate_document(self, document):
        if (type(document) is not NativeDocument or document.format is not self.format
                or type(document.raw) is not bytes or type(document.payload) is not bytes
                or document.payload != document.raw or not isinstance(document.source, Path)
                or type(document.context_digest) is not str):
            raise SaveError('A frozen exact-game native PS3 snapshot is required.')
        self.decode(document.raw)

    def fields_for(self, document):
        self.validate_document(document)
        return self.format.fields

    def field_map(self, document):
        return MappingProxyType({field.id: field for field in self.fields_for(document)})

    def stage(self, document, changes, key, value):
        mapping = self.field_map(document)
        pending = normalize_pending_values(document, changes, mapping)
        if type(key) is not str or key not in mapping:
            raise SaveError('Select an evidenced existing field.')
        pending[key] = value
        return normalize_pending_values(document, pending, mapping)

    def changed_payload(self, document, changes):
        mapping = self.field_map(document)
        pending = normalize_pending_values(document, changes, mapping)
        payload = bytearray(document.payload)
        for key, value in pending.items():
            field = mapping[key]
            payload[field.offset:field.offset + field.size] = field.encoded(value)
        result = bytes(payload)
        self.qualifier(result)
        return result

    def serialize(self, document, changes):
        return self.changed_payload(document, changes)

    def review(self, document, changes):
        pending = normalize_pending_values(document, changes, self.field_map(document))
        return [(field, field.value(document.payload), pending[field.id])
                for field in self.fields_for(document) if field.id in pending]

    def maximums(self, document, changes, group=None):
        return normalize_pending_values(document, changes, self.field_map(document))

    def limit_values(self, document, changes, keys):
        mapping = self.field_map(document)
        normalize_pending_values(document, changes, mapping)
        if isinstance(keys, (str, bytes)):
            raise SaveError('Select a sequence of evidenced field IDs.')
        try:
            keys = tuple(keys)
        except TypeError as error:
            raise SaveError('Select a sequence of evidenced field IDs.') from error
        if any(type(key) is not str or key not in mapping for key in keys):
            raise SaveError('Select only evidenced existing field IDs.')
        return {}

    def inspection_rows(self, document):
        self.validate_document(document)
        return self.inspector(document.payload)
