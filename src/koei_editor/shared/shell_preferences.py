"""Bounded shell preferences containing stable command IDs, never save paths."""
from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import re
import tempfile

from koei_editor.shared.preferences import preference_path

MAX_BYTES = 32768
MAX_FAVORITES = 128
MAX_RECENT = 20
_ID = re.compile(r'(?:(?:game|tool|command):[a-z][a-z0-9_-]{0,63}|plugin:[a-z][a-z0-9_.:-]{0,160})\Z')


@dataclass(frozen=True)
class ShellPreferences:
    language: str = 'en'
    text_size: int = 100
    favorites: tuple = ()
    recent: tuple = ()


def shell_path(legacy_path=None):
    base = Path(legacy_path) if legacy_path is not None else preference_path()
    return base.with_name(base.stem + '.shell.json')


def _ids(items, limit):
    if (type(items) not in (list, tuple) or len(items) > limit
            or any(type(item) is not str or not _ID.fullmatch(item) for item in items)
            or len(set(items)) != len(items)):
        raise ValueError('Shell history accepts only bounded stable command IDs.')
    return tuple(items)


def _validate(value):
    if (not isinstance(value, ShellPreferences) or value.language not in ('en', 'de')
            or type(value.text_size) is not int or value.text_size not in (100, 120, 140)):
        raise ValueError('Unsupported shell preferences.')
    return replace(value, favorites=_ids(value.favorites, MAX_FAVORITES), recent=_ids(value.recent, MAX_RECENT))


def load(path=None):
    try:
        with Path(path if path is not None else shell_path()).open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return ShellPreferences()
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('Duplicate shell preference.')
                result[key] = value
            return result
        data = json.loads(raw, object_pairs_hook=unique)
        if (type(data) is not dict or set(data) != {'schema', 'language', 'text_size', 'favorites', 'recent'}
                or type(data['schema']) is not int or data['schema'] != 1):
            return ShellPreferences()
        return _validate(ShellPreferences(**{key: data[key] for key in data if key != 'schema'}))
    except (OSError, ValueError, TypeError, RecursionError):
        return ShellPreferences()


def save(value, path=None):
    temporary = None
    try:
        value = _validate(value)
        data = (json.dumps({'schema': 1, **value.__dict__}, sort_keys=True, ensure_ascii=True) + '\n').encode()
        destination = Path(path if path is not None else shell_path())
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile('wb', dir=destination.parent, prefix='.shell.', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        return True
    except (OSError, ValueError, TypeError):
        return False
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def remember(value, command_id):
    """Record workspace identities only, without paths or gameplay data."""
    if type(command_id) is not str or not _ID.fullmatch(command_id) or not command_id.startswith(('game:', 'tool:')):
        return value
    return replace(value, recent=(command_id,) + tuple(key for key in value.recent if key != command_id)[:MAX_RECENT - 1])


def toggle_favorite(value, command_id):
    if type(command_id) is not str or not _ID.fullmatch(command_id):
        return value
    if command_id in value.favorites:
        return replace(value, favorites=tuple(key for key in value.favorites if key != command_id))
    if len(value.favorites) >= MAX_FAVORITES:
        return value
    return replace(value, favorites=value.favorites + (command_id,))
