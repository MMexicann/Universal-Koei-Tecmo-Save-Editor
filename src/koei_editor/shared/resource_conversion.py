"""Explicit scalar-resource transfers using each endpoint's native writer.

Game packages select the endpoints and fields. No offsets, edition discovery,
numeric coercion, clamping or inventory/progression inference belongs here.
"""
from dataclasses import dataclass
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import experimental_limits


@dataclass(frozen=True)
class ResourceTransfer:
    backends: object
    keys: tuple[str, ...]
    SCOPE_DESCRIPTION: str
    NOTES: tuple[str, ...]
    TRANSFER_SCOPE: str = 'mapped-resources-only'
    ROUTE_LABEL: str = 'resources only'
    directions: frozenset[tuple[str, str]] | None = None

    def __post_init__(self):
        object.__setattr__(self, 'backends', MappingProxyType(dict(self.backends)))

    @property
    def SUPPORTED_DIRECTIONS(self):
        if self.directions is not None:
            return self.directions
        return frozenset((source, target) for source in self.backends
                         for target in self.backends if source != target)

    def _fields(self, document):
        backend = self.backends.get(getattr(getattr(document, 'format', None), 'id', None))
        if backend is None:
            raise SaveError('Choose the exact resource-transfer game/platform endpoints.')
        backend.validate_document(document)
        mapping = backend.field_map(document)
        if any(key not in mapping for key in self.keys):
            raise SaveError('A required mapped resource is unavailable in this revision.')
        return backend, tuple(mapping[key] for key in self.keys)

    def gameplay(self, document):
        # Conversion never inherits an editor's experimental numeric policy.
        with experimental_limits(False):
            _backend, fields = self._fields(document)
            result = []
            for field in fields:
                value = field.value(document.payload)
                # A native reader may admit unusual opened balances above its
                # manual editing bounds. Reading them does not assign a value.
                result.append(value.to_bytes(field.size, 'little'))
            return b''.join(result)

    def encode(self, source, template):
        if (source.format.id, template.format.id) not in self.SUPPORTED_DIRECTIONS:
            raise SaveError('Choose a supported resource-transfer direction.')
        with experimental_limits(False):
            self.gameplay(source)
            _source_backend, source_fields = self._fields(source)
            backend, target_fields = self._fields(template)
            changes = {}
            for original, target in zip(source_fields, target_fields):
                value = original.value(source.payload)
                # Preserve an exact unusual opened destination as a no-op;
                # every changed assignment must pass the target's own limits.
                if value != target.value(template.payload):
                    target.validate(value)
                if original.size != target.size:
                    raise SaveError('The resource-transfer storage widths do not agree.')
                changes[target.id] = value
            return backend.serialize(template, changes)

    def preview_notes(self, source, template):
        _source_backend, source_fields = self._fields(source)
        _target_backend, target_fields = self._fields(template)
        return tuple(f'{target.label}: {target.value(template.payload):,} → '
                     f'{original.value(source.payload):,}'
                     for original, target in zip(source_fields, target_fields))
