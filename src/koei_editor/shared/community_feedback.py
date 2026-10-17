"""Reviewable, offline community reports with a closed diagnostic allowlist."""
import json

from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.validation_toolkit import (
    ReportError, ValidationRecord, _choice, _game, strict_json,
)

CATEGORIES = ('navigation', 'accessibility', 'localization', 'compatibility', 'save_workflow', 'other')
ERROR_CODES = ('none', 'input_rejected', 'operation_failed', 'ui_unresponsive', 'unexpected_result')
DIAGNOSTIC_OPTIONS = {
    'os_family': ('unknown', 'windows', 'linux', 'macos', 'other'),
    'ui_scale': ('unknown', '100', '125', '150', '175', '200', 'above_200'),
    'theme': ('unknown', 'light', 'dark', 'system'),
}


def build_bug_report(*, game_id=None, category='other', error_code='none',
                     locale='en', diagnostics=None, validation=None):
    """Return a fresh allowlisted dict; callers must show it before local export.

    No environment collection, exception messages, save bytes, filenames, free
    text, hashes, account IDs, machine IDs or network operations are supported.
    Unknown keys are rejected rather than silently included or interpolated.
    """
    _choice(category, CATEGORIES)
    _choice(error_code, ERROR_CODES)
    _choice(locale, ('en', 'de'))
    game = None if game_id is None else _game(game_id)
    if diagnostics is None:
        diagnostics = {}
    if type(diagnostics) is not dict or not set(diagnostics).issubset(DIAGNOSTIC_OPTIONS):
        raise ReportError('Only documented diagnostic fields are accepted.')
    cleaned = {key: _choice(value, DIAGNOSTIC_OPTIONS[key]) for key, value in diagnostics.items()}
    if validation is not None:
        if type(validation) is not ValidationRecord:
            raise ReportError('Use a validated structured workflow report.')
        # Revalidate even a mutated or manually constructed Python object.
        validation = ValidationRecord.from_json(validation.to_json())
        if game is None or validation.game_id != game.id:
            raise ReportError('Validation and feedback must use the same game profile.')
    return {
        'schema_version': 1, 'kind': 'community_bug_report', 'app_version': '2.7',
        'category': category, 'error_code': error_code, 'locale': locale,
        'game_id': None if game is None else game.id,
        'platform': None if game is None else game.platform,
        'diagnostics': cleaned,
        'validation': None if validation is None else validation.to_dict(),
        'transmission': 'local_review_only',
    }


def review_json(report):
    """Validate again before rendering or export; no arbitrary dict serialization."""
    if type(report) is not dict or set(report) != {
            'schema_version', 'kind', 'app_version', 'category', 'error_code', 'locale',
            'game_id', 'platform', 'diagnostics', 'validation', 'transmission'}:
        raise ReportError('Report fields do not match the supported feedback schema.')
    if (type(report['schema_version']) is not int or report['schema_version'] != 1
            or report['kind'] != 'community_bug_report' or report['app_version'] != '2.7'
            or report['transmission'] != 'local_review_only'):
        raise ReportError('Unsupported feedback report identity.')
    validation = report['validation']
    if validation is not None:
        validation = ValidationRecord.from_json(json.dumps(validation))
    cleaned = build_bug_report(game_id=report['game_id'], category=report['category'],
                               error_code=report['error_code'], locale=report['locale'],
                               diagnostics=report['diagnostics'], validation=validation)
    if report['platform'] != cleaned['platform']:
        raise ReportError('Feedback platform does not match its registered game.')
    return json.dumps(cleaned, indent=2, ensure_ascii=False) + '\n'


def import_bug_report(data):
    """Strict bounded import for callers that choose to review existing reports."""
    report = strict_json(data)
    return json.loads(review_json(report))


def export_bug_report(report, destination):
    return atomic_new(review_json(report).encode('utf-8'), destination)
