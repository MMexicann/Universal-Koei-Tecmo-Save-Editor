"""Read-only diagnostics for one explicitly selected registered save profile.

Reports retain neither saves nor paths, field values, owner context or backend
exception text. SHA-256 verifies file bytes, not native checksums or ownership.
No operation repairs a save, creates a backup or writes to the source.
"""
from dataclasses import asdict, dataclass
import hashlib
from importlib import import_module
import json
import re

from koei_editor.game_registry import GAMES, get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared import save_library as library
from koei_editor.shared.save_safety import safe_path

# The registered Fatal Frame II remake system profile is 61,851,984 bytes.
# Keep a fixed bound that admits every existing profile, including that save.
MAX_FILE_BYTES = 64 * 1024 * 1024
NOTES = (
    'Read-only inspection of a separate save copy; no repairs or game-load test were performed.',
    'Qualification covers only the explicitly selected game/platform and the revisions implemented by its adapter.',
    'SHA-256 identifies gameplay-file bytes only; it does not verify ownership, signing, companion equality or every native integrity layer.',
    'Reports omit source paths, names, field values, companion bytes and backend exception details. File hashes can still identify a private save.',
)


@dataclass(frozen=True)
class DiagnosticCheck:
    code: str
    status: str
    message: str


@dataclass(frozen=True)
class DiagnosticReport:
    game_id: str
    title: str
    platform: str
    profile: str
    status: str
    size_bytes: int | None
    sha256: str | None
    mapped_fields: int | None
    checks: tuple[DiagnosticCheck, ...]

    @property
    def success(self):
        return self.status in ('qualified', 'warning')

    def to_dict(self):
        return {'schema_version': 1, 'read_only': True, 'success': self.success,
                **asdict(self), 'notes': list(NOTES)}

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, allow_nan=False) + '\n'

    def to_text(self):
        rows = ['Save Doctor — ' + self.title, 'Platform: ' + self.platform,
                'Profile: ' + self.profile, 'Result: ' + self.status,
                'Size: ' + (str(self.size_bytes) + ' bytes' if self.size_bytes is not None else 'unavailable'),
                'SHA-256: ' + (self.sha256 or 'unavailable')]
        if self.mapped_fields is not None:
            rows.append('Mapped fields: ' + str(self.mapped_fields))
        rows.extend('[' + check.status + '] ' + check.code + ': ' + check.message for check in self.checks)
        rows.extend(NOTES)
        return '\n'.join(rows) + '\n'


def _rejection(error):
    """Classify private backend errors without exposing their interpolated data.

    A parser rejection cannot generally distinguish damage from an unsupported
    revision. Even a checksum mismatch can result from selecting another game.
    """
    text = str(error).lower()
    if any(word in text for word in ('checksum', 'crc', 'digest', 'hmac')):
        return 'native_integrity', 'Native integrity validation failed for the selected profile; the copy may be damaged or belong to a different profile.'
    if any(word in text for word in ('companion', 'param.sfo', 'eeprom', 'owner context', 'original context', 'steam_autocloud')):
        return 'original_context', 'Required original companion/title context is missing, invalid or does not match this profile. Keep the original context with the copied save.'
    if any(word in text for word in ('truncat', 'incomplete', 'size', 'length', 'alignment', 'nonempty', 'empty', ' kib', ' mib')):
        return 'structure', 'The selected profile rejected the save size, framing or completeness; truncation, a foreign format or an unsupported revision is possible.'
    if any(word in text for word in ('version', 'revision', 'platform', 'region', 'title', 'signature', 'magic', 'identity')):
        return 'compatibility', 'The selected profile rejected the format identity or revision; verify the exact game, platform, region and copied-file type.'
    return 'qualification', 'The selected adapter rejected the copy: damaged/foreign data, an unsupported revision or missing original context is possible.'


def _native_check(backend):
    kind = getattr(backend, 'INTEGRITY_KIND', None)
    if kind == 'checksum':
        return DiagnosticCheck('native_integrity', 'passed',
            'The selected adapter accepted its implemented native checksum checks. This is not an independent audit of every integrity layer.')
    if kind == 'external':
        return DiagnosticCheck('native_integrity', 'not_assessed',
            'Native signing/integrity is external to this decrypted-export adapter and was not verified by Save Doctor.')
    if kind == 'none':
        return DiagnosticCheck('native_integrity', 'not_assessed',
            'This adapter declares no native checksum. Structure acceptance and SHA-256 are not native checksum validation.')
    return DiagnosticCheck('native_integrity', 'not_assessed',
        'This adapter does not declare standardized checksum coverage. Its implemented validation ran, but no independent native checksum claim is made.')


def inspect_save(game_id, path, *, expected_sha256=None, max_file_bytes=MAX_FILE_BYTES):
    """Inspect a bounded ordinary copy with its exact registered native reader.

    Invalid API options raise SaveError. Problems with the selected file become
    report checks. A supplied expected digest is an optional user reference,
    never a substitute for native qualification. No other parser is attempted.
    """
    game = get_game(game_id)
    if game not in GAMES:
        raise SaveError('Choose an explicitly registered game/platform for Save Doctor.')
    if type(max_file_bytes) is not int or not 1 <= max_file_bytes <= MAX_FILE_BYTES:
        raise SaveError('Save Doctor requires a bounded file limit of 1 to 64 MiB.')
    if expected_sha256 is not None:
        if type(expected_sha256) is not str or re.fullmatch('[0-9a-fA-F]{64}', expected_sha256) is None:
            raise SaveError('Expected SHA-256 must contain exactly 64 hexadecimal characters.')
        expected_sha256 = expected_sha256.lower()

    checks = []
    size = digest = count = None
    def add(code, status, message):
        checks.append(DiagnosticCheck(code, status, message))
    def result(status=None):
        if status is None:
            status = ('failed' if any(check.status == 'failed' for check in checks) else
                      'warning' if any(check.status == 'warning' for check in checks) else 'qualified')
        return DiagnosticReport(game.id, game.title, game.platform, game.subtitle,
                                status, size, digest, count, tuple(checks))

    try:
        selected, info = library._checked_path(path)
        context = library._context_guard(selected)
    except SaveError:
        add('copy_safety', 'failed', 'Use an ordinary, unaliased separate copy outside live-game and Steam Cloud folders, with ordinary original context files.')
        return result('unsafe')
    except OSError:
        add('file_access', 'failed', 'The selected copy or its original context could not be accessed.')
        return result('unreadable')
    add('copy_safety', 'passed', 'The selected path is an ordinary separate copy outside protected live/cloud paths.')
    size = info.st_size
    if selected.suffix.lower() != game.extension:
        add('compatibility', 'failed', 'The file extension does not match the explicitly selected game/platform.')
        return result()
    if size > max_file_bytes:
        add('bounded_read', 'failed', 'The save exceeds the configured diagnostic size limit; no native parser was invoked.')
        return result('oversized')
    token = library._identity(info)
    try:
        digest = library._capture(selected, token, max_file_bytes, None)
    except SaveError:
        add('source_unchanged', 'failed', 'The copy changed or became unsafe during its bounded fingerprint read.')
        return result('changed')
    except OSError:
        add('file_access', 'failed', 'The selected copy could not be read.')
        return result('unreadable')
    add('bounded_read', 'passed', 'The complete gameplay file was fingerprinted within the configured byte limit.')
    if expected_sha256 is None:
        add('expected_sha256', 'not_assessed', 'No reference SHA-256 was supplied; the reported digest identifies this inspected copy only.')
    else:
        matches = digest == expected_sha256
        add('expected_sha256', 'passed' if matches else 'failed',
            'Gameplay-file SHA-256 matches the supplied reference.' if matches else
            'Gameplay-file SHA-256 differs from the supplied reference. This establishes a byte difference, not its cause.')

    document = adapter = backend = None
    snapshot = None
    try:
        adapter = game.get_scalar_adapter() if game.scalar_backend is not None else None
        backend = adapter.backend if adapter is not None else import_module(game.parser_module)
        document = adapter.read_save(selected) if adapter is not None else game.read_save(selected)
        raw = document.raw if adapter is not None else document.encrypted
        if type(raw) is not bytes or len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            raise SaveError('Diagnostic source snapshot changed.')
        if adapter is not None:
            snapshot = library._snapshot_digest(document)
            count = len(adapter.fields_for(document))
        add('compatibility', 'passed', 'The exact selected adapter accepted its implemented game/platform, revision, structure and original-context requirements.')
        checks.append(_native_check(backend))
        warnings = getattr(document, 'compatibility_warnings', ())
        if warnings:
            add('compatibility_notes', 'warning', 'The native reader reported compatibility caveats. Inspect them privately in the game editor before editing; saved values and details are omitted here.')
    except SaveError as error:
        code, message = _rejection(error)
        add(code, 'failed', message)
        document = None
    except OSError:
        add('file_access', 'failed', 'The native reader could not access the copied save or required original context.')
        document = None
    except Exception:
        add('diagnostic_runtime', 'failed', 'The selected adapter could not complete diagnostics in this environment. This does not establish save corruption.')
        document = None

    if document is not None:
        try:
            # Call the actual native serializer: BoundScalarAdapter.serialize
            # deliberately returns raw directly for no pending edits.
            if adapter is not None:
                adapter.validate_document(document)
                unchanged = backend.serialize(document, {})
            else:
                writer = import_module('koei_editor.games.dw3.save_writer')
                unchanged, _ = writer.serialize(document, [])
            if type(unchanged) is not bytes or unchanged != raw:
                raise SaveError('Unchanged serialization differs.')
            add('unchanged_roundtrip', 'passed', 'The native no-edit serialization is byte-for-byte identical to the inspected copy; no output save was written.')
        except Exception:
            add('unchanged_roundtrip', 'failed', 'The native no-edit roundtrip failed or changed bytes. No repair or output save was written.')
    else:
        add('unchanged_roundtrip', 'not_assessed', 'A rejected or unavailable native document cannot qualify an unchanged roundtrip.')

    try:
        if library._capture(selected, token, max_file_bytes, None) != digest or library._context_guard(selected) != context:
            raise SaveError('Source or context changed.')
        if document is not None:
            # Re-read context through its owning backend, including opaque
            # metadata absent from generic companion conventions.
            current = adapter.read_save(selected) if adapter is not None else game.read_save(selected)
            if adapter is not None:
                if current.raw != raw or library._snapshot_digest(current) != snapshot:
                    raise SaveError('Original context changed.')
            elif current.encrypted != raw or current.plaintext != document.plaintext:
                raise SaveError('Native snapshot changed.')
            if library._capture(selected, token, max_file_bytes, None) != digest or library._context_guard(selected) != context:
                raise SaveError('Source or context changed after native read-back.')
    except Exception:
        add('source_unchanged', 'failed', 'The save or original context changed, became unsafe, or could not be requalified. Inspect a stable separate copy again.')
        return result('changed')
    add('source_unchanged', 'passed', 'Source bytes and required original context remained stable throughout diagnostics.')
    return result()


def export_report(report, destination):
    """Write only a new local JSON/text report through atomic copy storage."""
    if type(report) is not DiagnosticReport:
        raise SaveError('Export requires a Save Doctor diagnostic report.')
    destination = safe_path(destination)
    if destination.suffix.lower() not in ('.json', '.txt'):
        raise SaveError('Choose a new .json or .txt diagnostic report.')
    raw = (report.to_json() if destination.suffix.lower() == '.json' else report.to_text()).encode('utf-8')
    atomic_new(raw, destination)
    with destination.open('rb') as stream:
        if stream.read(len(raw) + 1) != raw:
            raise SaveError('The diagnostic report failed actual destination read-back.')
    return destination
