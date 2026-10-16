"""Read-only diagnostics for one explicitly selected registered save profile.

Native validators remain authoritative. A generic rejection never proves
corruption, a checksum failure, a foreign title, or repairability. No operation
backs up, stages, repairs, or saves gameplay data. Public reports contain only
catalogued guidance and aggregate counts, never parser error text or paths.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from koei_editor.game_registry import GAMES, get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import save_library as library
from koei_editor.shared.copy_storage import atomic_new


MAX_FILE_BYTES = 32 * 1024 * 1024
DOCTOR_GAMES = GAMES


@dataclass(frozen=True)
class Finding:
    code: str
    state: str
    title: str
    detail: str
    guidance: str = ''


def _finding(code, state, title, detail, guidance=''):
    return Finding(code, state, title, detail, guidance)


# Report text is deliberately a closed catalogue, not native exception text.
FINDINGS = {item.code: item for item in (
    _finding('path.safe', 'passed', 'Separate ordinary copy',
             'The selected file and its ancestors passed copy-only path checks.'),
    _finding('path.unsafe', 'failed', 'Unsafe or linked path',
             'The selection did not pass ordinary-file or copy-only path checks.',
             'Use an ordinary separate copy outside live game and Steam Cloud folders; avoid links and hard links.'),
    _finding('read.missing', 'failed', 'Copy not found',
             'The selected file or one of its parent directories does not exist.',
             'Select an existing copied gameplay file.'),
    _finding('read.unreadable', 'unknown', 'Copy could not be read',
             'The operating system could not complete the file check.',
             'Check access permissions and availability, then retry. This does not establish corruption.'),
    _finding('read.bounded', 'passed', 'Bounded file read',
             'The complete selected file was fingerprinted within the fixed size limit.'),
    _finding('read.empty', 'failed', 'Empty file',
             'The selected file contains no bytes.',
             'Restore an untouched original or export a fresh copy. Save Doctor cannot reconstruct missing bytes.'),
    _finding('read.oversized', 'failed', 'File exceeds the diagnostic limit',
             'The selected file exceeds the requested bounded read limit.',
             'Select the supported gameplay file instead of an archive, memory card, or whole container.'),
    _finding('profile.extension', 'passed', 'Explicit profile and extension',
             'The file extension matches the explicitly selected game/platform profile. This alone does not identify its contents.'),
    _finding('profile.extension_mismatch', 'failed', 'Extension does not match',
             'The selected profile requires a different gameplay-file extension.',
             'Select the correct profile and its documented copied file. Renaming a foreign save does not convert it.'),
    _finding('native.accepted', 'passed', 'Native validator accepted this snapshot',
             'The selected registered parser accepted this exact copy and any context it requires. This is file-level qualification, not a game-load test.'),
    _finding('native.checksum_rejected', 'failed', 'Native checksum check failed',
             'The selected native validator explicitly reported a checksum failure.',
             'Confirm the exact title/platform/revision and obtain a fresh original export or known-good backup. No checksum repair is attempted.'),
    _finding('native.identity_revision_rejected', 'failed', 'Native identity or revision rejected',
             'The validator explicitly rejected a title, revision, or serialized layout marker; it did not isolate which edition or revision this file belongs to.',
             'Check the documented game/platform and revision. Save Doctor never tries another parser automatically.'),
    _finding('native.context_rejected', 'failed', 'Required original context rejected',
             'The native validator explicitly rejected required original companion metadata or its availability.',
             'Keep the complete original export and its original companion files together. Do not synthesize account or signing metadata.'),
    _finding('native.structure_rejected', 'failed', 'Native structure or size rejected',
             'The native validator explicitly rejected a required size, structure, or truncation condition.',
             'Check that the file is a complete supported gameplay export. This does not prove how it became incompatible.'),
    _finding('native.rejected', 'failed', 'Copy did not qualify',
             'The selected validator rejected this copy without an isolated diagnostic category. Damage, foreign input, an unsupported revision, or missing context remain possible.',
             'Check the exact game/platform and required original export context, then try an untouched copy. No repairability is inferred.'),
    _finding('native.unavailable', 'unknown', 'Native validation could not finish',
             'A runtime or I/O error prevented the native check from completing.',
             'Retry in the official Windows application. This is not evidence that the save is damaged.'),
    _finding('integrity.unreported', 'unknown', 'Individual checksum result unavailable',
             'The generic adapter contract does not expose separate successful integrity checks. Native acceptance is reported as a combined result; no independent checksum claim is made.'),
    _finding('revision.unreported', 'unknown', 'Individual revision result unavailable',
             'The adapter does not expose an independent revision-verification result. No revision number is guessed from filenames or file sizes.'),
    _finding('roundtrip.exact', 'passed', 'Unchanged roundtrip is byte exact',
             'The normal in-memory serializer returned the exact opened bytes with no edits. Nothing was written to the save.'),
    _finding('roundtrip.mismatch', 'failed', 'Unchanged roundtrip did not match',
             'The serializer did not reproduce the exact opened bytes. This copy is not offered for opening from this diagnostic result.',
             'Keep the original untouched and report the selected profile with this privacy-safe diagnostic report.'),
    _finding('roundtrip.unavailable', 'unknown', 'Unchanged roundtrip unavailable',
             'The serializer could not finish its no-edit check; no repaired or normalized bytes are accepted.'),
    _finding('source.fixed', 'passed', 'Source stayed unchanged',
             'The file identity and complete bounded fingerprint matched before and after diagnostic operations.'),
    _finding('source.changed', 'failed', 'Source changed during checking',
             'File identity, content, or copied-folder identity changed during checking. Earlier native results are historical and cannot authorize opening.',
             'Finish copying or synchronizing the separate export, then diagnose the stable copy again.'),
    _finding('context.fixed', 'passed', 'Context stayed unchanged',
             'Observed original-context identities and the native snapshot metadata matched across two fresh native reads.'),
    _finding('context.changed', 'failed', 'Original context changed',
             'Observed original companion context or native snapshot metadata changed while checking.',
             'Use one stable complete original export and diagnose again.'),
    _finding('compatibility.clear', 'passed', 'No parser compatibility warnings',
             'This parser exposes compatibility warnings and reported none for the opened snapshot.'),
    _finding('compatibility.warnings', 'warning', 'Preserved compatibility warnings',
             'The parser accepted the copy with compatibility warnings. The report includes only their count; private saved values and names are omitted.',
             'Read the existing editor warnings before considering any edits. Unrecognized or unusual values must be preserved.'),
    _finding('compatibility.unreported', 'unknown', 'Compatibility warning list unavailable',
             'This adapter does not expose a separate compatibility-warning list; acceptance is not a claim that every gameplay value is understood.'),
    _finding('operation.cancelled', 'cancelled', 'Check cancelled',
             'Checking stopped before a complete result could be established. No partial result authorizes opening.'),
    _finding('game_load.unverified', 'unknown', 'In-game loading remains unverified',
             'Save Doctor cannot run the destination game, verify account signing, or prove that an edited or converted save loads and re-saves.'),
)}


@dataclass(frozen=True)
class DoctorResult:
    game_id: str
    status: str
    findings: tuple[Finding, ...]
    size_bytes: int = 0
    mapped_fields: int | None = None
    compatibility_warnings: int | None = None
    created_utc: str = ''
    # Private freshness material: never included by report(). No save retained.
    source: Path | None = field(default=None, repr=False)
    identity: tuple = field(default=(), repr=False)
    sha256: str = field(default='', repr=False)
    snapshot_digest: str = field(default='', repr=False)
    folder_identity: tuple = field(default=(), repr=False)
    context_identity: tuple = field(default=(), repr=False)
    max_file_bytes: int = field(default=MAX_FILE_BYTES, repr=False)

    @property
    def qualified(self):
        return self.status in ('qualified', 'attention')


@dataclass(frozen=True)
class _TaggedSnapshot:
    source: Path
    raw: bytes
    payload: bytes
    warning_count: int


class _TaggedReader:
    """DW3 keeps its tagged parser and writer, never a scalar fallback."""
    def __init__(self, game):
        self.game = game

    def read_save(self, path):
        document = self.game.read_save(path)
        return _TaggedSnapshot(Path(document.source), document.encrypted,
                               document.plaintext, len(document.compatibility_warnings))

    @staticmethod
    def fields_for(document):
        return ()  # Tagged properties are not scalar editable-field counts.

    @staticmethod
    def serialize(document, changes):
        from koei_editor.games.dw3 import save_parser, save_writer
        if changes:
            raise SaveError('Save Doctor only permits a no-edit roundtrip.')
        opened = save_parser.parse_bytes(document.raw, document.source)
        return save_writer.serialize(opened)[0]


_TAGGED_READERS = {'dw3': _TaggedReader}


def _adapter(game):
    if game.scalar_backend is not None:
        return game.get_scalar_adapter()
    factory = _TAGGED_READERS.get(game.id)
    if factory is None:
        raise SaveError('No read-only diagnostic workflow is registered for this profile.')
    return factory(game)


def _native_finding(error):
    """Conservative categories from explicit validator statements only.

    Never publish the error text. Ambiguous combined errors and generic
    rejections deliberately remain unclassified rather than guessing damage.
    """
    message = str(error).casefold().strip()
    if (' or ' not in message and re.search(
            r'\b(?:checksum|crc32|crc16) (?:failed|mismatch|does not match|is invalid)\b', message)):
        return 'native.checksum_rejected'
    if (message.startswith('keep the original param.sfo alongside')
            or message.startswith('keep the original param.sfo beside')
            or message.startswith('original param.sfo is required')
            or message.startswith('the original param.sfo is required')):
        return 'native.context_rejected'
    if (' or ' not in message and ('title/revision marker' in message
            or message == 'this save version is not supported yet.'
            or message == 'game identity or save revision does not match the selected pc editor.'
            or re.fullmatch(r'unsupported [a-z0-9 .-]+ serialized record revision\.', message))):
        return 'native.identity_revision_rejected'
    if (' or ' not in message and (message.startswith('truncated ')
            or message.startswith('incomplete ')
            or message.startswith('invalid save size')
            or re.fullmatch(r'[a-z0-9 .-]+ save must contain exactly [0-9,]+ bytes\.', message))):
        return 'native.structure_rejected'
    return 'native.rejected'


def _warning_count(document):
    if isinstance(document, _TaggedSnapshot):
        return document.warning_count
    warnings = getattr(document, 'compatibility_warnings', None)
    return len(warnings) if isinstance(warnings, (tuple, list)) else None


def diagnose(game_id, path, *, cancel=None, max_file_bytes=MAX_FILE_BYTES):
    """Check a copied file with one explicit native parser, without file writes.

    Call from a worker thread. Cancellation is cooperative between bounded I/O
    and parser operations; an already-running native codec cannot be interrupted.
    Invalid profile IDs/limits are caller errors. File problems become findings.
    """
    game = get_game(game_id)
    if type(max_file_bytes) is not int or not 1 <= max_file_bytes <= MAX_FILE_BYTES:
        raise SaveError('Save Doctor read limits must be within 1 byte and 32 MiB.')
    adapter = _adapter(game)
    codes = []
    source, identity, digest, snapshot, parent_id, context = None, (), '', '', (), ()
    size, mapped, warnings = 0, None, None

    def add(code):
        if code not in codes:
            codes.append(code)

    def result(status):
        add('game_load.unverified')
        return DoctorResult(game.id, status, tuple(FINDINGS[code] for code in codes),
                            size, mapped, warnings, datetime.now(timezone.utc).isoformat(),
                            source, identity, digest, snapshot, parent_id, context, max_file_bytes)

    try:
        library._check_cancel(cancel)
        try:
            source, info = library._checked_path(path)
            _, parent_info = library._checked_path(source.parent, directory=True)
            parent_id = library._directory_identity(parent_info)
        except FileNotFoundError:
            add('read.missing')
            return result('unreadable')
        except OSError:
            add('read.unreadable')
            return result('unreadable')
        except SaveError:
            add('path.unsafe')
            return result('unsafe')
        add('path.safe')
        identity, size = library._identity(info), info.st_size
        if source.suffix.casefold() != game.extension:
            add('profile.extension_mismatch')
            return result('rejected')
        add('profile.extension')
        if not size:
            add('read.empty')
            return result('rejected')
        if size > max_file_bytes:
            add('read.oversized')
            return result('rejected')
        try:
            digest = library._capture(source, identity, max_file_bytes, cancel)
            context = library._context_guard(source)
        except SaveError:
            add('source.changed')
            return result('changed')
        except OSError:
            add('read.unreadable')
            return result('unreadable')
        add('read.bounded')
        accepted = False
        try:
            document, native_digest, snapshot, count = library._qualify(
                adapter, source, info, max_file_bytes, cancel)
            if native_digest != digest:
                raise SaveError('The selected copy changed during native qualification.')
            accepted = True
            mapped = count if game.scalar_backend else None
            warnings = _warning_count(document)
            add('native.accepted')
        except SaveError as error:
            if str(error) in (
                    'The selected file changed before its bounded read.',
                    'The selected file changed during its bounded read.',
                    'The selected copy changed during native qualification.',
                    'The selected copy changed after native qualification.'):
                add('source.changed')
            else:
                add(_native_finding(error))
        except (OSError, RuntimeError, ImportError):
            add('native.unavailable')
        except Exception:
            # An adapter bug is not proof of save corruption. Do not leak its
            # exception (which can contain player values or account paths).
            add('native.unavailable')
        library._check_cancel(cancel)
        if accepted:
            try:
                unchanged = adapter.serialize(document, {})
                # BoundScalarAdapter deliberately returns the original bytes
                # immediately for an empty pending map. Exercise the backend's
                # actual no-edit serializer as well, rather than reporting that
                # safe shortcut as independent codec roundtrip evidence.
                native_backend = getattr(adapter, 'backend', None)
                native_unchanged = (native_backend.serialize(document, {})
                                    if native_backend is not None else unchanged)
                add('roundtrip.exact' if (type(unchanged) is bytes and unchanged == document.raw
                    and type(native_unchanged) is bytes and native_unchanged == document.raw)
                    else 'roundtrip.mismatch')
            except Exception:
                add('roundtrip.unavailable')
            library._check_cancel(cancel)
            try:
                _, again_digest, again_snapshot, again_count = library._qualify(
                    adapter, source, info, max_file_bytes, cancel)
                if (again_digest != digest or again_snapshot != snapshot or again_count != count):
                    add('context.changed')
                else:
                    add('context.fixed')
            except library._Cancelled:
                raise
            except Exception:
                add('context.changed')
        try:
            _, final_info = library._checked_path(source)
            _, final_parent = library._checked_path(source.parent, directory=True)
            if (library._identity(final_info) != identity
                    or library._directory_identity(final_parent) != parent_id
                    or library._capture(source, identity, max_file_bytes, cancel) != digest):
                add('source.changed')
            else:
                add('source.fixed')
            if library._context_guard(source) != context:
                add('context.changed')
        except (OSError, SaveError):
            add('source.changed')
        library._check_cancel(cancel)
        if 'native.checksum_rejected' not in codes:
            add('integrity.unreported')
        add('revision.unreported')
        if accepted:
            add('compatibility.unreported' if warnings is None else
                'compatibility.warnings' if warnings else 'compatibility.clear')
        if 'source.changed' in codes or 'context.changed' in codes:
            return result('changed')
        if not accepted:
            return result('incomplete' if 'native.unavailable' in codes else 'rejected')
        if 'roundtrip.exact' not in codes:
            return result('incomplete')
        return result('attention' if warnings else 'qualified')
    except library._Cancelled:
        add('operation.cancelled')
        return result('cancelled')


def _validate(result):
    if (type(result) is not DoctorResult or result.game_id not in {game.id for game in DOCTOR_GAMES}
            or result.status not in ('qualified', 'attention', 'rejected', 'unsafe', 'unreadable', 'changed', 'cancelled', 'incomplete')
            or type(result.findings) is not tuple or not result.findings
            or any(type(item) is not Finding or FINDINGS.get(item.code) != item for item in result.findings)
            or len({item.code for item in result.findings}) != len(result.findings)
            or type(result.size_bytes) is not int or not 0 <= result.size_bytes
            or any(value is not None and (type(value) is not int or not 0 <= value <= 1_000_000)
                   for value in (result.mapped_fields, result.compatibility_warnings))
            or type(result.created_utc) is not str):
        raise SaveError('Use an unmodified Save Doctor result.')
    try:
        datetime.fromisoformat(result.created_utc)
    except ValueError as error:
        raise SaveError('The diagnostic timestamp is invalid.') from error
    if result.qualified:
        codes = {item.code for item in result.findings}
        if (not {'native.accepted', 'roundtrip.exact', 'source.fixed', 'context.fixed'} <= codes
                or any(item.state in ('failed', 'cancelled') for item in result.findings)):
            raise SaveError('A qualified result requires complete native and freshness checks.')


def requalify(result, *, cancel=None):
    """Return a path only after a complete fresh check matches this snapshot.

    The owning application must still use the normal editor open path. A Doctor
    result is never permission to skip the editor's own validation or backups.
    """
    _validate(result)
    if not result.qualified or result.source is None:
        raise SaveError('Diagnose a stable qualified copied save before opening it.')
    fresh = diagnose(result.game_id, result.source, cancel=cancel, max_file_bytes=result.max_file_bytes)
    if (not fresh.qualified or fresh.identity != result.identity or fresh.sha256 != result.sha256
            or fresh.snapshot_digest != result.snapshot_digest or fresh.folder_identity != result.folder_identity
            or fresh.context_identity != result.context_identity or fresh.mapped_fields != result.mapped_fields):
        raise SaveError('This save or its original context changed. Diagnose it again before opening.')
    return fresh.source


def report(result):
    """Privacy-safe historical report, with no filenames, hashes or save bytes."""
    _validate(result)
    game = get_game(result.game_id)
    return {'schema_version': 1, 'tool': 'Save Doctor', 'read_only': True,
            'historical_snapshot': True, 'created_utc': result.created_utc,
            'game_id': game.id, 'title': game.title, 'platform': game.platform,
            'status': result.status, 'qualified_at_check': result.qualified,
            'size_bytes': result.size_bytes, 'mapped_scalar_fields': result.mapped_fields,
            'compatibility_warning_count': result.compatibility_warnings,
            'repairs_attempted': False, 'game_load_verified': False,
            'findings': [{'code': item.code, 'state': item.state, 'title': item.title,
                          'detail': item.detail, 'guidance': item.guidance}
                         for item in result.findings]}


def export_report(result, destination):
    """Atomically create a new .doctor.json report; never replace any file."""
    encoded = (json.dumps(report(result), indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    selected = Path(destination).absolute()
    if not selected.name.casefold().endswith('.doctor.json'):
        raise SaveError('Choose a new .doctor.json diagnostic report file.')
    parent, _ = library._checked_path(selected.parent, directory=True)
    target = parent / selected.name
    if target != selected.resolve():
        raise SaveError('Choose an ordinary diagnostic report destination.')
    # atomic_new refuses existing names and writes only this metadata snapshot.
    created = atomic_new(encoded, target)
    checked, info = library._checked_path(target)
    if (checked != target or info.st_size != len(encoded)
            or library._capture(target, library._identity(info), len(encoded), None)
                != hashlib.sha256(encoded).hexdigest()):
        raise SaveError('The diagnostic report changed after atomic creation.')
    return created
