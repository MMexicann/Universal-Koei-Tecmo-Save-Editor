"""Exclusive JSON report export through an identity-bound existing directory."""
from functools import partial
import json
import math
import os
from pathlib import Path
import stat

from koei_editor.shared.copy_storage import publish_new_child_bound as _publish_new_child_bound
from koei_editor.shared.save_safety import safe_path

# Report failures discard only an owned pending child after confirmed native
# rejection. Existing manifest callers retain their recoverable pending default.
publish_new_child_bound = partial(_publish_new_child_bound, cleanup_pending_on_failure=True)

MAX_REPORT_BYTES = 1024 * 1024


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Report JSON contains duplicate fields.')
        value[key] = item
    return value


def _constant(_value):
    raise ValueError('Report JSON must contain finite numbers.')


def write_report_bytes(data, destination):
    """Write bounded caller-reviewed JSON to a new child of an ordinary folder.

    This helper does not collect or redact report content. Callers own their
    schemas. It refuses aliases and never creates directories, replaces an
    existing child, retries an uncertain publication or deletes foreign entries.
    The shared publisher retains verified native handles and uses mode 0600 on
    Linux; destination-specific and supported-platform checks remain mandatory.
    """
    if type(data) is not bytes or not 0 < len(data) <= MAX_REPORT_BYTES:
        raise ValueError('Report data must be bounded JSON bytes.')
    try:
        value = json.loads(data.decode('utf-8'), object_pairs_hook=_unique, parse_constant=_constant)
    except (ValueError, RecursionError) as error:
        raise ValueError('Report data must be valid bounded JSON.') from None
    if type(value) not in (dict, list):
        raise ValueError('A report must be a JSON object or array.')
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > 64:
            raise ValueError('Report JSON exceeds its nesting bound.')
        if type(item) is float and not math.isfinite(item):
            raise ValueError('Report JSON must contain finite numbers.')
        if type(item) is dict:
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
    requested = Path(os.path.abspath(destination))
    if safe_path(destination) != requested:
        raise ValueError('Choose a new report file without path aliases.')
    try:
        requested.lstat()
    except FileNotFoundError:
        pass
    else:
        raise FileExistsError('Choose a new report filename; existing entries are never replaced.')
    parent_info = None
    for directory in requested.parents:
        info = directory.lstat()
        if (not stat.S_ISDIR(info.st_mode) or getattr(info, 'st_file_attributes', 0)
                & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
            raise ValueError('Choose an existing ordinary report folder without aliases.')
        if directory == requested.parent:
            parent_info = info
    if parent_info is None:
        raise ValueError('Choose a report file inside an existing folder.')
    return publish_new_child_bound(data, requested.parent, requested.name,
                                   (parent_info.st_dev, parent_info.st_ino))
