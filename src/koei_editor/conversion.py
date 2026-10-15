"""Explicit, lossless platform routes and transactional copied-save exports.

Conversion is separate from scalar editing: complete known gameplay spans move
unchanged, while a qualified destination template supplies its native framing.
No console signing metadata is generated or interpreted.
"""
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import verified_editor as dw8_pc
from koei_editor.games.dw8xl_ps3 import parser as dw8_ps3
from koei_editor.games.dw8xl_vita import parser as dw8_vita
from koei_editor.games.p5strikers_pc import parser as p5_pc
from koei_editor.games.p5strikers_ps4 import parser as p5_ps4
from koei_editor.games.p5strikers_switch import parser as p5_switch
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.save_safety import safe_path
from koei_editor.games.dw8xl import converter as dw8_conversion
from koei_editor.games.dw8xl import ps4_export as dw8_ps4
from koei_editor.games.dw6 import converter as dw6_conversion
from koei_editor.games.dw6 import progression_conversion as dw6_progression
from koei_editor.games.dw6 import dw6_parser as dw6_pc
from koei_editor.games.dw6_ps3 import parser as dw6_ps3
from koei_editor.games.dw6_ps3 import japanese_export as dw6_ps3_jp
from koei_editor.games.p5strikers_pc import converter as p5_conversion

_FAMILIES = MappingProxyType({'dw8xl': dw8_conversion, 'p5s': p5_conversion, 'dw6': dw6_conversion})
_VARIANTS = MappingProxyType({('dw6', 'progress'): dw6_progression})


def _transform(route):
    family = ENDPOINTS[route.source_id].family
    return _VARIANTS[(family, route.variant)] if route.variant else _FAMILIES[family]


@dataclass(frozen=True)
class Endpoint:
    id: str
    family: str
    label: str
    filename: str
    backend: object = field(repr=False)
    companion: str = ''
    companion_limit: int = 0
    import_note: str = ''
    conversion_only: bool = False


ENDPOINTS = MappingProxyType({endpoint.id: endpoint for endpoint in (
    Endpoint('dw8xl', 'dw8xl', 'DW8 XL · PC', 'save.dat', dw8_pc),
    Endpoint('dw8xl_ps3', 'dw8xl', 'DW8 XL · US PS3 PSN', 'APP.BIN', dw8_ps3,
             'PARAM.SFO', 4096,
             'PFD-decrypted NPUB31449 export. Reimport and resign with Apollo Save Tool.'),
    Endpoint('dw8xl_vita', 'dw8xl', 'DW8 XL · Vita', 'MainData00.dat', dw8_vita,
             import_note='Reimport the plaintext file with your Vita save manager.'),
    Endpoint('dw8xl_ps4', 'dw8xl', 'DW8 XL · US PS4 zero-extension profile', 'APP.BIN', dw8_ps4,
             'sce_sys/param.sfo', 4096,
             'Decrypted CUSA00397 export. Reimport and resign with your PS4 save manager.', True),
    Endpoint('p5strikers_pc', 'p5s', 'Persona 5 Strikers · PC English', 'SAVEDATA.BIN', p5_pc),
    Endpoint('p5strikers_ps4', 'p5s', 'Persona 5 Strikers · PS4 English', 'APP.BIN', p5_ps4,
             'sce_sys/param.sfo', 4096,
             'Decrypted CUSA19640 export. Reimport and resign with your PS4 save manager.'),
    Endpoint('p5strikers_switch', 'p5s', 'Persona 5 Strikers · Switch English', 'savedata', p5_switch,
             import_note='Reimport the exported file with your Switch save manager.'),
    Endpoint('dw6', 'dw6', 'DW6 · PC', 'save.dat', dw6_pc),
    Endpoint('dw6_ps3', 'dw6', 'DW6 · US PS3', 'APP.BIN', dw6_ps3,
             'PARAM.SFO', 4096,
             'PFD-decrypted BLUS30110 export. Reimport and resign with Apollo Save Tool.'),
    Endpoint('dw6_ps3_jp', 'dw6', 'DW6 · Japanese PS3', 'APP.BIN', dw6_ps3_jp,
             'PARAM.SFO', 4096,
             'PFD-decrypted BLJM60041 export. Reimport and resign with Apollo Save Tool.', True),
)})


@dataclass(frozen=True)
class Route:
    source_id: str
    target_id: str
    variant: str = ''

    @property
    def id(self):
        return self.source_id + '-to-' + self.target_id + ('-' + self.variant if self.variant else '')

    @property
    def label(self):
        label = ENDPOINTS[self.source_id].label + ' → ' + ENDPOINTS[self.target_id].label
        if self.transfer_scope == 'roster-and-horses':
            label += ' (roster and horses)'
        elif getattr(_transform(self), 'ROUTE_LABEL', ''):
            label += ' (' + _transform(self).ROUTE_LABEL + ')'
        return label

    @property
    def transfer_scope(self):
        return _transform(self).TRANSFER_SCOPE

    @property
    def scope_description(self):
        return _transform(self).SCOPE_DESCRIPTION


ROUTES = tuple(Route(source.id, target.id) for source in ENDPOINTS.values()
               for target in ENDPOINTS.values()
               if source.family == target.family and source.id != target.id)
ROUTES += tuple(Route(route.source_id, route.target_id, variant)
                for route in ROUTES for family, variant in _VARIANTS
                if ENDPOINTS[route.source_id].family == family)
_ROUTES = MappingProxyType({route.id: route for route in ROUTES})


@dataclass(frozen=True)
class Snapshot:
    endpoint_id: str
    document: object = field(repr=False)
    companion_raw: bytes = field(default=b'', repr=False)


@dataclass(frozen=True)
class Conversion:
    route: Route
    source: Snapshot = field(repr=False)
    template: Snapshot = field(repr=False)
    raw: bytes = field(repr=False)
    gameplay_sha256: str
    gameplay_bytes: int
    notes: tuple[str, ...]


def get_route(route_id):
    if type(route_id) is not str or route_id not in _ROUTES:
        raise SaveError('Choose a supported conversion route; games and editions cannot be substituted.')
    return _ROUTES[route_id]


def _companion(endpoint, source):
    if not endpoint.companion:
        return b''
    path = safe_path(source.parent / endpoint.companion)
    with path.open('rb') as stream:
        raw = stream.read(endpoint.companion_limit + 1)
    if not 0 < len(raw) <= endpoint.companion_limit:
        raise SaveError('The original console metadata exceeds its bounded size.')
    return raw


def _read(endpoint_id, path):
    endpoint = ENDPOINTS[endpoint_id]
    path = safe_path(path)
    before = _companion(endpoint, path)
    document = endpoint.backend.read_save(path, endpoint_id)
    after = _companion(endpoint, path)
    if before != after:
        raise SaveError('Console metadata changed while opening. Reopen the copied save.')
    endpoint.backend.validate_document(document)
    if endpoint.backend.serialize(document, {}) != document.raw:
        raise SaveError('The selected save failed an unchanged native roundtrip.')
    return Snapshot(endpoint_id, document, after)


def _validate_snapshot(snapshot):
    if (type(snapshot) is not Snapshot or type(snapshot.endpoint_id) is not str
            or snapshot.endpoint_id not in ENDPOINTS):
        raise SaveError('A qualified immutable conversion snapshot is required.')
    endpoint = ENDPOINTS[snapshot.endpoint_id]
    endpoint.backend.validate_document(snapshot.document)
    if type(snapshot.companion_raw) is not bytes:
        raise SaveError('Console context must be an immutable snapshot.')
    # Validate both gameplay and mandatory title context with the actual reader.
    reopened = _read(snapshot.endpoint_id, snapshot.document.source)
    if (reopened.document.raw != snapshot.document.raw
            or reopened.companion_raw != snapshot.companion_raw):
        raise SaveError('A source, template or console metadata changed. Reopen both copies.')


def _gameplay(snapshot, route=None):
    transform = _transform(route) if route is not None else _FAMILIES[ENDPOINTS[snapshot.endpoint_id].family]
    return transform.gameplay(snapshot.document)


def _encode(source, template, route=None):
    endpoint = ENDPOINTS[template.endpoint_id]
    payload = _gameplay(source, route)
    transform = _transform(route) if route is not None else _FAMILIES[endpoint.family]
    raw = transform.encode(source.document, template.document)
    converted = endpoint.backend.decode(raw, template.endpoint_id)
    if _gameplay(Snapshot(template.endpoint_id, converted), route) != payload:
        raise SaveError('Destination reparse changed the transferred gameplay bytes.')
    return raw


def prepare(route_id, source_path, template_path):
    route = get_route(route_id)
    source = _read(route.source_id, source_path)
    template = _read(route.target_id, template_path)
    raw = _encode(source, template, route)
    payload = _gameplay(source, route)
    return Conversion(route, source, template, raw, hashlib.sha256(payload).hexdigest(), len(payload), _notes(route, source, template))


def _notes(route, source, template):
    target = ENDPOINTS[route.target_id]
    notes = [route.scope_description + '. Original copies remain unchanged.',
             'Use the same game edition and compatible updates/DLC. Test loading a separate copy in-game.',
             'In-game conversion loading has not been validated by this project.']
    if target.import_note:
        notes.append(target.import_note)
    if target.companion:
        notes.append('Original destination-template metadata is copied unchanged. This is a gameplay export, not a signed console package.')
    family = _transform(route)
    notes.extend(family.NOTES)
    preview = getattr(family, 'preview_notes', None)
    if preview is not None:
        notes.extend(preview(source.document, template.document))
    return tuple(notes)


def validate_review_snapshot(conversion):
    """Verify immutable native content, including a completed export’s frozen review.

    Original disk files are checked separately before every new export. This
    content check also works after a later job has changed an original input.
    """
    if (type(conversion) is not Conversion or type(conversion.route) is not Route
            or type(conversion.route.source_id) is not str or type(conversion.route.target_id) is not str
            or type(conversion.route.variant) is not str
            or get_route(conversion.route.id) != conversion.route):
        raise SaveError('Review a prepared conversion before exporting.')
    if (type(conversion.source) is not Snapshot or type(conversion.template) is not Snapshot
            or conversion.source.endpoint_id != conversion.route.source_id
            or conversion.template.endpoint_id != conversion.route.target_id
            or type(conversion.raw) is not bytes):
        raise SaveError('Conversion snapshots do not match the chosen route.')
    for snapshot in (conversion.source, conversion.template):
        endpoint = ENDPOINTS[snapshot.endpoint_id]
        endpoint.backend.validate_document(snapshot.document)
        if (type(snapshot.companion_raw) is not bytes
                or (not endpoint.companion and snapshot.companion_raw)
                or (endpoint.companion and not 0 < len(snapshot.companion_raw) <= endpoint.companion_limit)):
            raise SaveError('Conversion context does not match its frozen endpoint.')
    payload = _gameplay(conversion.source, conversion.route)
    if (conversion.raw != _encode(conversion.source, conversion.template, conversion.route)
            or conversion.gameplay_sha256 != hashlib.sha256(payload).hexdigest()
            or conversion.gameplay_bytes != len(payload) or conversion.notes != _notes(conversion.route, conversion.source, conversion.template)):
        raise SaveError('The prepared conversion was altered. Review it again.')


def _validate_conversion(conversion):
    validate_review_snapshot(conversion)
    _validate_snapshot(conversion.source)
    _validate_snapshot(conversion.template)


def validate_review(prepared):
    """Revalidate a frozen review and both copied inputs without writing."""
    _validate_conversion(prepared)


def export(conversion, output_dir):
    """Write a new private export folder, with backups and actual native read-back."""
    _validate_conversion(conversion)
    output_dir = safe_path(output_dir)
    if output_dir.exists():
        raise FileExistsError('Choose a new output folder; existing folders are never replaced.')
    target = ENDPOINTS[conversion.route.target_id]
    # Backends preserve their own mandatory backup context and integrity rules.
    backups = [ENDPOINTS[snapshot.endpoint_id].backend.backup(snapshot.document)
               for snapshot in (conversion.source, conversion.template)]
    _validate_conversion(conversion)  # Also catches races during backups.
    receipt = {
        'schema_version': 2, 'route': conversion.route.id,
        'transfer_scope': conversion.route.transfer_scope,
        'scope_description': conversion.route.scope_description,
        'source_sha256': conversion.source.document.sha256,
        'template_sha256': conversion.template.document.sha256,
        'source_context_sha256': hashlib.sha256(conversion.source.companion_raw).hexdigest() if conversion.source.companion_raw else None,
        'template_context_sha256': hashlib.sha256(conversion.template.companion_raw).hexdigest() if conversion.template.companion_raw else None,
        'output_sha256': hashlib.sha256(conversion.raw).hexdigest(),
        'gameplay_sha256': conversion.gameplay_sha256,
        'gameplay_bytes': conversion.gameplay_bytes,
        'output_file': target.filename,
        'game_load_verified': False,
        'console_signing_performed': False,
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir()  # Exclusive reservation, including empty folders and races.
    written = []
    try:
        if target.companion:
            data = conversion.template.companion_raw
            path = atomic_new(data, output_dir / target.companion)
            written.append((path, data))
        destination = atomic_new(conversion.raw, output_dir / target.filename)
        written.append((destination, conversion.raw))
        actual = _read(target.id, destination)
        if (actual.document.raw != conversion.raw
                or actual.companion_raw != conversion.template.companion_raw
                or _gameplay(actual, conversion.route) != _gameplay(conversion.source, conversion.route)):
            raise SaveError('Saved conversion failed actual destination read-back.')
        _validate_conversion(conversion)
        data = (json.dumps(receipt, indent=2) + '\n').encode('utf-8')
        path = atomic_new(data, output_dir / 'conversion.json')
        written.append((path, data))
    except Exception:
        # Remove only our exact bytes. Never erase a file changed by another app.
        for path, data in reversed(written):
            if not path.is_symlink() and path.is_file() and path.read_bytes() == data:
                path.unlink()
        if target.companion and '/' in target.companion:
            try:
                (output_dir / Path(target.companion).parent).rmdir()
            except OSError:
                pass
        try:
            output_dir.rmdir()
        except OSError:
            pass
        raise
    return destination, tuple(backups), receipt
