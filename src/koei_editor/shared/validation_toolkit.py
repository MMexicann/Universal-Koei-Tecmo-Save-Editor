"""Path-free, user-attested real-game validation; never a support certification.

This module does not open saves, run games or contact a service. Existing copied-save
self-tests remain authoritative for their own checks; their results are not promoted
to in-game evidence by this workflow.
"""
from dataclasses import dataclass, replace
import json
import os
import stat

from koei_editor.game_registry import GAMES
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.save_library import _checked_path, _handle_binding, _identity


MAX_REPORT_BYTES = 16384
PROVENANCES = ('unknown', 'procedural', 'genuine_file')
OUTCOMES = ('not_run', 'passed', 'failed', 'blocked')
STEPS = (
    'prepare_copy', 'identify_profile', 'unchanged_roundtrip',
    'edited_copy_reparsed', 'import_copy', 'game_load',
    'field_observed', 'game_resave', 'resaved_reload',
)
GAME_STEPS = STEPS[4:]


class ReportError(ValueError):
    """A bounded report or workflow assertion is invalid (no input in messages)."""


def _choice(value, choices):
    if type(value) is not str or value not in choices:
        raise ReportError('Choose a supported report option.')
    return value


def _game(game_id):
    if type(game_id) is not str or len(game_id) > 80:
        raise ReportError('Choose a registered game/platform profile.')
    for game in GAMES:
        if game.id == game_id:
            return game
    raise ReportError('Choose a registered game/platform profile.')


def _revision(revision):
    # Numeric parser revisions only: no build labels, paths, usernames or notes.
    if revision is not None and (type(revision) is not int or not 0 <= revision <= 0xffffffff):
        raise ReportError('Use a numeric format revision or leave it unspecified.')
    return revision


def strict_json(data):
    """Decode bounded UTF-8 JSON, rejecting duplicate keys and nonfinite numbers."""
    if type(data) not in (bytes, str):
        raise ReportError('Use a UTF-8 JSON report.')
    try:
        raw = data.encode('utf-8') if type(data) is str else data
        if not 0 < len(raw) <= MAX_REPORT_BYTES:
            raise ReportError('Report exceeds the size limit.')

        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ReportError('Duplicate report keys are not accepted.')
                result[key] = value
            return result

        def constant(_):
            raise ReportError('Nonfinite report numbers are not accepted.')

        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ReportError('Report is not valid bounded UTF-8 JSON.') from error


def read_report(path):
    """Read a bounded, unchanged ordinary file; special/linked sources fail closed."""
    try:
        source, before = _checked_path(path)
        if not 0 < before.st_size <= MAX_REPORT_BYTES:
            raise ReportError('Report source exceeds the bounded size limit.')
        flags = (os.O_RDONLY | getattr(os, 'O_BINARY', 0)
                 | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        descriptor = os.open(source, flags)
        with os.fdopen(descriptor, 'rb') as stream:
            opened = os.fstat(stream.fileno())
            if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                    or _handle_binding(opened) != _handle_binding(before)):
                raise ReportError('Report source changed before reading.')
            raw = stream.read(MAX_REPORT_BYTES + 1)
            _, after = _checked_path(source)
            if (len(raw) != before.st_size or _identity(after) != _identity(before)
                    or _identity(os.fstat(stream.fileno())) != _identity(opened)):
                raise ReportError('Report source changed during reading.')
            return raw
    except (OSError, ValueError, RuntimeError) as error:
        raise ReportError('Report requires an unchanged ordinary, bounded local file.') from error


@dataclass(frozen=True)
class ValidationRecord:
    game_id: str
    revision: int | None = None
    provenance: str = 'unknown'
    outcomes: tuple[str, ...] = ('not_run',) * len(STEPS)

    def __post_init__(self):
        _game(self.game_id)
        _revision(self.revision)
        _choice(self.provenance, PROVENANCES)
        if type(self.outcomes) is not tuple or len(self.outcomes) != len(STEPS):
            raise ReportError('The complete ordered workflow is required.')
        for index, outcome in enumerate(self.outcomes):
            _choice(outcome, OUTCOMES)
            if outcome in ('passed', 'failed'):
                if index and self.outcomes[index - 1] != 'passed':
                    raise ReportError('Complete the preceding step successfully first.')
                if index >= 4 and self.provenance != 'genuine_file':
                    raise ReportError('Actual game observations require a genuine-file source.')

    @classmethod
    def create(cls, game_id, *, revision=None, provenance='unknown'):
        return cls(game_id, revision, provenance)

    def record_step(self, step, outcome):
        _choice(step, STEPS)
        _choice(outcome, OUTCOMES)
        index = STEPS.index(step)
        if self.outcomes[index] == outcome:
            return self
        # Any changed earlier assertion invalidates all downstream observations.
        outcomes = self.outcomes[:index] + (outcome,) + ('not_run',) * (len(STEPS) - index - 1)
        return replace(self, outcomes=outcomes)

    def to_dict(self):
        game = _game(self.game_id)
        return {
            'schema_version': 1, 'kind': 'real_game_validation', 'app_version': '3.0',
            'game_id': game.id, 'platform': game.platform, 'profile_scope': game.subtitle,
            'format_revision': self.revision, 'provenance': self.provenance,
            'attestation': 'user_reported_unverified',
            'steps': dict(zip(STEPS, self.outcomes)),
        }

    def summary(self):
        """Independent evidence lanes, all explicitly self-reported."""
        qualified = self.outcomes[3] == 'passed'
        return {
            'procedural_checks_reported': qualified and self.provenance == 'procedural',
            'genuine_file_checks_reported': qualified and self.provenance == 'genuine_file',
            'game_load_reported': self.outcomes[5] == 'passed',
            'game_resave_reported': self.outcomes[7] == 'passed',
            'resaved_reload_reported': self.outcomes[8] == 'passed',
            'revision_unspecified': self.revision is None,
            'independently_verified': False,
        }

    def to_json(self):
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + '\n'

    def export(self, destination):
        return atomic_new(self.to_json().encode('utf-8'), destination)

    @classmethod
    def from_json(cls, data):
        report = strict_json(data)
        if type(report) is not dict or set(report) != {
                'schema_version', 'kind', 'app_version', 'game_id', 'platform',
                'profile_scope', 'format_revision', 'provenance', 'attestation', 'steps'}:
            raise ReportError('Report fields do not match the supported schema.')
        if type(report['schema_version']) is not int or report['schema_version'] != 1:
            raise ReportError('Unsupported report schema version.')
        if (report['kind'] != 'real_game_validation' or report['app_version'] not in ('2.7', '3.0')
                or report['attestation'] != 'user_reported_unverified'):
            raise ReportError('Unsupported report identity or evidence claim.')
        game = _game(report['game_id'])
        if report['platform'] != game.platform or report['profile_scope'] != game.subtitle:
            raise ReportError('Report does not match the registered platform/edition.')
        steps = report['steps']
        if type(steps) is not dict or set(steps) != set(STEPS):
            raise ReportError('Report must contain the exact controlled workflow.')
        return cls(game.id, report['format_revision'], report['provenance'],
                   tuple(steps[step] for step in STEPS))

    @classmethod
    def load(cls, source):
        return cls.from_json(read_report(source))
