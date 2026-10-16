"""Optional theme and field pins, separate from game save storage."""
import json
import os
from pathlib import Path
import re
import sys
import tempfile


THEMES = frozenset({'Light', 'Dark'})
MAX_BYTES = 256 * 1024
MAX_PIN_GAMES = 256
MAX_PINNED_FIELDS = 256
_GAME_ID = re.compile(r'[a-z][a-z0-9_]{0,63}\Z')
_FIELD_ID = re.compile(r'[A-Za-z0-9_.:-]{1,160}\Z')


def preference_path():
    if os.name == 'nt':
        base = Path(os.environ.get('APPDATA') or os.environ.get('LOCALAPPDATA') or
                    Path.home() / 'AppData' / 'Roaming')
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    return base / 'UniversalKoeiTecmoSaveEditor' / 'preferences.json'


def normalize_pins(field_ids):
    """Return bounded stable field identities, never paths, labels or values."""
    if type(field_ids) not in (tuple, list, set, frozenset):
        raise ValueError('Pinned fields must be a collection of stable field IDs.')
    if len(field_ids) > MAX_PINNED_FIELDS:
        raise ValueError(f'Pin at most {MAX_PINNED_FIELDS} fields per game.')
    if any(type(key) is not str or not _FIELD_ID.fullmatch(key) for key in field_ids):
        raise ValueError('Pinned fields must use valid stable field IDs.')
    return tuple(sorted(set(field_ids)))


def _valid_game_id(game_id):
    return type(game_id) is str and _GAME_ID.fullmatch(game_id) is not None


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Preferences contain a duplicate property name.')
        value[key] = item
    return value


def _invalid_constant(_value):
    raise ValueError('Preferences cannot contain nonfinite JSON values.')


def _load(path=None):
    try:
        with Path(path if path is not None else preference_path()).open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return None
        value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        if (type(value) is not dict or type(value.get('schema')) is not int
                or type(value.get('theme')) is not str or value['theme'] not in THEMES):
            return None
        if value['schema'] == 1 and set(value) == {'schema', 'theme'}:
            return {'theme': value['theme'], 'pins': {}}
        if (value['schema'] != 2 or set(value) != {'schema', 'theme', 'pins'}
                or type(value['pins']) is not dict or len(value['pins']) > MAX_PIN_GAMES):
            return None
        pins = {}
        for game_id, ids in value['pins'].items():
            if not _valid_game_id(game_id) or type(ids) is not list:
                return None
            normalized = normalize_pins(ids)
            if len(normalized) != len(ids):
                return None
            pins[game_id] = normalized
        return {'theme': value['theme'], 'pins': pins}
    except (OSError, ValueError, TypeError, RecursionError):
        return None


def load_theme(path=None):
    """Missing, inaccessible or unsupported settings fall back to Light."""
    value = _load(path)
    return value['theme'] if value is not None else 'Light'


def load_pins(game_id, path=None):
    """Read pins for one exact game/platform; unavailable dynamic IDs are kept."""
    if not _valid_game_id(game_id):
        return ()
    value = _load(path)
    return value['pins'].get(game_id, ()) if value is not None else ()


def _save(value, path):
    temporary = None
    try:
        # Retain the tiny legacy schema until a user actually pins a field.
        content = ({'schema': 2, 'theme': value['theme'], 'pins': value['pins']}
                   if value['pins'] else {'schema': 1, 'theme': value['theme']})
        data = (json.dumps(content, ensure_ascii=True, sort_keys=True) + '\n').encode('utf-8')
        if len(data) > MAX_BYTES:
            return False
        destination = Path(path if path is not None else preference_path())
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='wb', dir=destination.parent,
                                         prefix='.preferences.', suffix='.tmp', delete=False) as stream:
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


def save_theme(name, path=None):
    """Atomically remember a theme while retaining pins for every game."""
    if type(name) is not str or name not in THEMES:
        return False
    value = _load(path) or {'theme': 'Light', 'pins': {}}
    value['theme'] = name
    return _save(value, path)


def save_pins(game_id, field_ids, path=None):
    """Atomically remember exact-game pins without storing saves or values."""
    if not _valid_game_id(game_id):
        return False
    try:
        ids = normalize_pins(field_ids)
    except (ValueError, TypeError):
        return False
    value = _load(path) or {'theme': 'Light', 'pins': {}}
    if ids:
        value['pins'][game_id] = ids
    else:
        value['pins'].pop(game_id, None)
    if len(value['pins']) > MAX_PIN_GAMES:
        return False
    return _save(value, path)
