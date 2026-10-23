"""Bounded, path-free Game Hub reports and installation-aware table ordering."""
from datetime import datetime, timezone
import json
import re

from koei_editor.game_registry import get_game
from koei_editor.shared.report_export import write_report_bytes
from koei_editor.shared.save_discovery import DiscoveryResult, InstalledGame, STEAM_MAPPINGS

MAX_REPORT_BYTES = 512 * 1024
_MAPPINGS = {item.app_id: item for item in STEAM_MAPPINGS}
_STOP_REASONS = frozenset(('complete', 'cancelled', 'byte_limit', 'entry_limit',
                           'root_limit', 'result_limit'))
SORT_COLUMNS = ('#0', 'status', 'build', 'updated', 'size', 'notes')


def _marker(value, maximum):
    return value if type(value) is str and re.fullmatch(r'[0-9]{1,' + str(maximum) + '}', value) else None


def _timestamp(value):
    value = _marker(value, 12)
    if value is None or int(value) <= 0:
        return None
    try:
        datetime.fromtimestamp(int(value), timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    return int(value)


def _size(value):
    return value if type(value) is int and 0 <= value <= (1 << 63) - 1 else None


def sort_rows(rows, column='#0', descending=False):
    """Sort (id, title, status, installation, note) rows; unknowns stay last.

    Numeric columns use original Steam values rather than their formatted text.
    Equal values retain the canonical title/id order in either direction.
    """
    if column not in SORT_COLUMNS or type(descending) is not bool:
        raise ValueError('Choose a supported Game Hub sort column and direction.')
    rows = sorted(rows, key=lambda row: (row[1].casefold(), row[0]))

    def value(row):
        _identity, title, status, installed, note = row
        if column == '#0':
            return title.casefold()
        if column == 'status':
            return status.casefold()
        if column == 'notes':
            return note.casefold() or None
        if installed is None:
            return None
        if column == 'build':
            marker = _marker(installed.build_id, 20)
            return int(marker) if marker is not None else None
        if column == 'updated':
            return _timestamp(installed.last_updated)
        return _size(installed.size_on_disk)

    known, unknown = [], []
    for row in rows:
        item = value(row)
        (unknown if item is None else known).append((item, row))
    known.sort(key=lambda pair: pair[0], reverse=descending)
    return [row for _item, row in known + unknown]


def inventory_report(result=None, visible_row_ids=None, *, refresh_failed=False):
    """Describe a displayed scan snapshot using only canonical/sanitized fields.

    Local annotations, search text, roots, paths, filenames, issue details and
    unrecognized manifest text never enter this representation.
    """
    if result is not None and type(result) is not DiscoveryResult:
        raise ValueError('Choose a Game Hub discovery snapshot.')
    if type(refresh_failed) is not bool:
        raise ValueError('Refresh status must be a boolean.')
    if result is not None and (type(result.issues) is not tuple or len(result.issues) > 2000):
        raise ValueError('Game Hub snapshot exceeds its fixed issue bound.')
    installations = () if result is None else result.installed_games
    if type(installations) is not tuple or len(installations) > 500:
        raise ValueError('Game Hub snapshot exceeds its fixed installation bound.')
    grouped = {}
    for installed in installations:
        if type(installed) is not InstalledGame:
            raise ValueError('Game Hub snapshot contains an invalid installation.')
        mapping = _MAPPINGS.get(installed.app_id)
        if mapping is None or installed.game_id != mapping.game_id:
            raise ValueError('Game Hub snapshot contains an untracked installation.')
        grouped.setdefault(installed.app_id, []).append(installed)
    stop = None if result is None else result.stop_reason
    stop = stop if type(stop) is str and stop in _STOP_REASONS else ('unknown' if result is not None else None)
    state = 'not_scanned' if result is None else ('complete' if stop == 'complete' else 'partial')
    rows = {}
    for app_id, mapping in _MAPPINGS.items():
        game = get_game(mapping.game_id)
        present = grouped.get(app_id, ())
        for ordinal, installed in enumerate(present or (None,)):
            identity = f'{app_id}:{ordinal}' if installed is not None else f'{app_id}:missing'
            rows[identity] = {
                'game_id': game.id, 'title': game.title, 'edition': game.subtitle,
                'platform': game.platform, 'steam_app_id': app_id,
                'installation': ('detected' if installed is not None else
                                 'not_scanned' if state == 'not_scanned' else
                                 'not_detected' if state == 'complete' else 'not_detected_partial'),
                'build_id': _marker(installed.build_id, 20) if installed is not None else None,
                'last_updated_unix': _timestamp(installed.last_updated) if installed is not None else None,
                'size_on_disk': _size(installed.size_on_disk) if installed is not None else None,
            }
    if visible_row_ids is None:
        identities = sorted(rows, key=lambda key: (rows[key]['title'].casefold(), key))
    else:
        if type(visible_row_ids) not in (tuple, list) or len(visible_row_ids) > len(rows):
            raise ValueError('Choose current visible Game Hub rows for export.')
        identities = list(visible_row_ids)
        if any(type(key) is not str or key not in rows for key in identities):
            raise ValueError('Choose current visible Game Hub rows for export.')
        if len(set(identities)) != len(identities):
            raise ValueError('Game Hub export cannot contain duplicate rows.')
    selected = [rows[key] for key in identities]
    return {
        'schema': 'koei-game-hub-inventory', 'schema_version': 1,
        'scope': 'visible_rows' if visible_row_ids is not None else 'tracked_profiles',
        'scan': {'state': state, 'stop_reason': stop, 'refresh_failed': refresh_failed,
                 'previous_results': refresh_failed and result is not None,
                 'issue_count': len(result.issues) if result is not None else 0},
        'coverage': {'tracked_profile_count': len(_MAPPINGS),
                     'detected_installation_count': len(installations),
                     'visible_row_count': len(selected),
                     'visible_profile_count': len({item['game_id'] for item in selected})},
        'contains_paths': False, 'contains_local_notes': False,
        'games': selected,
    }


def inventory_bytes(result=None, visible_row_ids=None, *, refresh_failed=False):
    """Freeze and bound a display snapshot before a modal destination prompt."""
    report = inventory_report(result, visible_row_ids, refresh_failed=refresh_failed)
    raw = (json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False) + '\n').encode('ascii')
    if len(raw) > MAX_REPORT_BYTES:
        raise ValueError('Game Hub inventory report exceeds its fixed size bound.')
    return raw


def export_inventory(destination, result=None, visible_row_ids=None, *, refresh_failed=False):
    """Write one explicit new JSON report, never replacing an existing entry."""
    return write_report_bytes(inventory_bytes(result, visible_row_ids,
                                              refresh_failed=refresh_failed), destination)
