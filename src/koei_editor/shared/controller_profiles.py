"""App-owned game input profiles; this module never edits native game settings.

Profiles are notes/templates associated with an exact registered Windows PC
game. They are stored in the application's configuration directory and must
not be confused with game configuration files or Steam Input layouts.
"""
from dataclasses import dataclass, replace
from contextlib import contextmanager
import json
import os
import stat
from pathlib import Path
import re
import tempfile
import uuid

from koei_editor.game_registry import GAMES
from koei_editor.shared.preferences import preference_path
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.games.dw3.models import SaveError


SCHEMA = 1
MAX_STORE_BYTES = 512 * 1024
MAX_PROFILE_BYTES = 64 * 1024
MAX_PROFILES = 256
MAX_BINDINGS = 64
MAX_NAME = 64
MAX_ACTION = 80
MAX_INPUT = 48

LAYOUTS = {
    'generic': 'Generic',
    'xbox': 'Xbox labels',
    'playstation': 'PlayStation labels',
    'nintendo': 'Nintendo labels',
    'custom': 'Custom',
}

_GAME_IDS = frozenset(game.id for game in GAMES if game.platform == 'Windows PC')
_ID = re.compile(r'[a-f0-9]{32}\Z')
_SAFE_TEXT = re.compile(r'[^\x00-\x1f\x7f]*\Z')


class ProfileError(ValueError):
    """A profile or profile store is invalid or unsafe to use."""


@dataclass(frozen=True)
class Binding:
    """A user-defined action label and its keyboard/controller labels."""

    action: str
    keyboard: str = ''
    controller: str = ''


@dataclass(frozen=True)
class ControllerProfile:
    """A local profile template for one exact registered PC game."""

    profile_id: str
    game_id: str
    name: str
    layout: str
    bindings: tuple[Binding, ...] = ()
    preset_id: str = 'custom'


def default_store_path():
    """Return the application-owned settings path, outside game folders."""
    return preference_path().with_name('controller_profiles.json')


def _valid_text(value, label, maximum, *, allow_empty=False):
    if type(value) is not str:
        raise ProfileError(f'{label} must be text.')
    value = value.strip()
    if (not _SAFE_TEXT.fullmatch(value)
            or any(0xd800 <= ord(character) <= 0xdfff for character in value)
            or len(value) > maximum
            or (not allow_empty and not value)):
        raise ProfileError(f'{label} must be plain text up to {maximum} characters.')
    return value


def _valid_profile_id(value):
    if type(value) is not str or not _ID.fullmatch(value):
        raise ProfileError('Profile identity is invalid.')
    return value


def normalize_profile(profile):
    """Validate and normalize one profile without consulting a game file."""
    if not isinstance(profile, ControllerProfile):
        raise ProfileError('Choose a controller profile.')
    profile_id = _valid_profile_id(profile.profile_id)
    if type(profile.game_id) is not str or profile.game_id not in _GAME_IDS:
        raise ProfileError('Choose an exact registered Windows PC game.')
    name = _valid_text(profile.name, 'Profile name', MAX_NAME)
    if type(profile.layout) is not str or profile.layout not in LAYOUTS:
        raise ProfileError('Choose a supported controller label layout.')
    preset_id = _valid_text(profile.preset_id, 'Preset identity', 40)
    if preset_id != 'custom' and preset_id not in PRESETS:
        raise ProfileError('Preset identity is unsupported.')
    if type(profile.bindings) not in (tuple, list) or len(profile.bindings) > MAX_BINDINGS:
        raise ProfileError(f'A profile can contain at most {MAX_BINDINGS} actions.')
    bindings = []
    seen = set()
    for item in profile.bindings:
        if not isinstance(item, Binding):
            raise ProfileError('Profile actions must be bindings.')
        action = _valid_text(item.action, 'Action name', MAX_ACTION)
        keyboard = _valid_text(item.keyboard, 'Keyboard input', MAX_INPUT, allow_empty=True)
        controller = _valid_text(item.controller, 'Controller input', MAX_INPUT, allow_empty=True)
        if not keyboard and not controller:
            raise ProfileError('Each action needs a keyboard key or controller button.')
        key = action.casefold()
        if key in seen:
            raise ProfileError('Action names must be unique in a profile.')
        seen.add(key)
        bindings.append(Binding(action, keyboard, controller))
    return ControllerProfile(profile_id, profile.game_id, name, profile.layout,
                             tuple(bindings), preset_id)


def create_profile(game_id, name, *, layout='generic', bindings=(), preset_id='custom', profile_id=None):
    """Create a validated, unsaved profile for one registered PC game."""
    if type(bindings) not in (tuple, list):
        raise ProfileError('Profile actions must be a list or tuple.')
    value = ControllerProfile(uuid.uuid4().hex if profile_id is None else profile_id, game_id, name,
                              layout, bindings, preset_id)
    return normalize_profile(value)


PRESETS = {
    'blank': {
        'name': 'Blank profile', 'layout': 'generic', 'bindings': (),
    },
    'keyboard_wasd': {
        'name': 'Keyboard WASD starter', 'layout': 'generic',
        'bindings': (
            Binding('Move up', 'W'), Binding('Move down', 'S'),
            Binding('Move left', 'A'), Binding('Move right', 'D'),
            Binding('Confirm', 'Enter'), Binding('Cancel', 'Escape'),
            Binding('Pause or menu', 'Escape'),
        ),
    },
    'keyboard_arrows': {
        'name': 'Keyboard arrows starter', 'layout': 'generic',
        'bindings': (
            Binding('Move up', 'Up'), Binding('Move down', 'Down'),
            Binding('Move left', 'Left'), Binding('Move right', 'Right'),
            Binding('Confirm', 'Enter'), Binding('Cancel', 'Escape'),
            Binding('Pause or menu', 'Escape'),
        ),
    },
    'controller_xbox': {
        'name': 'Xbox label starter', 'layout': 'xbox',
        'bindings': (
            Binding('Face button 1', controller='A'), Binding('Face button 2', controller='B'),
            Binding('Face button 3', controller='X'), Binding('Face button 4', controller='Y'),
            Binding('Menu', controller='Start'), Binding('View', controller='Back'),
        ),
    },
    'controller_playstation': {
        'name': 'PlayStation label starter', 'layout': 'playstation',
        'bindings': (
            Binding('Face button 1', controller='Cross'), Binding('Face button 2', controller='Circle'),
            Binding('Face button 3', controller='Square'), Binding('Face button 4', controller='Triangle'),
            Binding('Menu', controller='Options'), Binding('View', controller='Share'),
        ),
    },
    'controller_nintendo': {
        'name': 'Nintendo label starter', 'layout': 'nintendo',
        'bindings': (
            Binding('Face button 1', controller='B'), Binding('Face button 2', controller='A'),
            Binding('Face button 3', controller='Y'), Binding('Face button 4', controller='X'),
            Binding('Menu', controller='Plus'), Binding('View', controller='Minus'),
        ),
    },
}


def create_from_preset(game_id, preset_id, name=None):
    """Create a starter template; its bindings are user-editable suggestions."""
    if type(preset_id) is not str or preset_id not in PRESETS:
        raise ProfileError('Choose a known profile starter.')
    preset = PRESETS[preset_id]
    return create_profile(game_id, preset['name'] if name is None else name, layout=preset['layout'],
                          bindings=preset['bindings'], preset_id=preset_id)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProfileError('Profile data contains a duplicate property.')
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ProfileError('Profile data contains a nonfinite JSON value.')


def _encode_profile(profile):
    profile = normalize_profile(profile)
    return {
        'profile_id': profile.profile_id,
        'game_id': profile.game_id,
        'name': profile.name,
        'layout': profile.layout,
        'preset_id': profile.preset_id,
        'bindings': [
            {'action': binding.action, 'keyboard': binding.keyboard,
             'controller': binding.controller}
            for binding in profile.bindings
        ],
    }


def _decode_profile(value):
    if (type(value) is not dict
            or set(value) != {'profile_id', 'game_id', 'name', 'layout', 'preset_id', 'bindings'}
            or type(value['bindings']) is not list):
        raise ProfileError('Profile data does not match the supported schema.')
    bindings = []
    for item in value['bindings']:
        if type(item) is not dict or set(item) != {'action', 'keyboard', 'controller'}:
            raise ProfileError('Profile action data does not match the supported schema.')
        bindings.append(Binding(item['action'], item['keyboard'], item['controller']))
    return normalize_profile(ControllerProfile(
        value['profile_id'], value['game_id'], value['name'], value['layout'],
        tuple(bindings), value['preset_id']))


def _parse_json(raw, maximum, label):
    if type(raw) is not bytes or len(raw) > maximum:
        raise ProfileError(f'{label} is larger than the supported limit.')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                           parse_constant=_invalid_constant)
    except ProfileError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise ProfileError(f'{label} is not valid UTF-8 JSON.') from error
    return value


def _decode_store(raw):
    value = _parse_json(raw, MAX_STORE_BYTES, 'Profile store')
    if (type(value) is not dict or set(value) != {'schema', 'profiles'}
            or type(value['schema']) is not int or value['schema'] != SCHEMA
            or type(value['profiles']) is not list or len(value['profiles']) > MAX_PROFILES):
        raise ProfileError('Profile store uses an unsupported schema.')
    profiles = tuple(_decode_profile(item) for item in value['profiles'])
    identities = [(profile.game_id, profile.profile_id) for profile in profiles]
    if len(identities) != len(set(identities)):
        raise ProfileError('Profile store contains duplicate identities.')
    return profiles


def _serialize_store(profiles):
    normalized = tuple(normalize_profile(item) for item in profiles)
    if len(normalized) > MAX_PROFILES:
        raise ProfileError(f'A store can contain at most {MAX_PROFILES} profiles.')
    identities = [(profile.game_id, profile.profile_id) for profile in normalized]
    if len(identities) != len(set(identities)):
        raise ProfileError('Profile store contains duplicate identities.')
    data = (json.dumps({'schema': SCHEMA,
                        'profiles': [_encode_profile(item) for item in normalized]},
                       ensure_ascii=True, sort_keys=True) + '\n').encode('utf-8')
    if len(data) > MAX_STORE_BYTES:
        raise ProfileError('Profile store is larger than the supported limit.')
    return data


def _owned_identity(path):
    try:
        info = path.lstat()
        if (stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and not getattr(info, 'st_file_attributes', 0) & 0x400):
            return info.st_dev, info.st_ino
    except OSError:
        pass
    return None


def _owned_snapshot(path):
    try:
        info = path.lstat()
        if (stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and not getattr(info, 'st_file_attributes', 0) & 0x400):
            return (info.st_dev, info.st_ino, info.st_size,
                    info.st_mtime_ns, info.st_ctime_ns)
    except OSError:
        pass
    return None


def _retain_creator(stream):
    """Pin the created file so a removed inode cannot be reused during cleanup.

    Windows retains its close-before-publication semantics: a duplicated writer
    prevents rename, while even a share-DELETE metadata handle can leave an
    unlinked name delete-pending and prevent an unrelated replacement. That
    branch uses the complete post-write path snapshot as its cleanup guard.
    """
    return os.dup(stream.fileno()) if os.name != 'nt' else None


def _unlink_owned(path, identity, descriptor, snapshot=None):
    # A failed operation must preserve a replacement another application has
    # left at our former staging/recovery name. POSIX keeps its creator descriptor
    # open; a remembered inode after close is not proof of ownership on filesystems
    # that immediately recycle removed inodes. Windows requires a complete snapshot
    # because retaining an open handle changes deletion/publication semantics.
    try:
        if descriptor is None:
            if snapshot is None:
                return
            held_identity = identity
        else:
            held = os.fstat(descriptor)
            held_identity = held.st_dev, held.st_ino
        if (held_identity == identity
                and _owned_identity(path) == identity
                and (snapshot is None or _owned_snapshot(path) == snapshot)):
            path.unlink(missing_ok=True)
    except OSError:
        pass


@dataclass
class _OwnedTemporary:
    path: Path
    descriptor: int | None
    identity: tuple[int, int]
    snapshot: tuple | None = None
    retain: bool = False


@contextmanager
def _owned_temporary(directory, data, *, prefix, suffix):
    """Create, verify and retain one private staging/recovery file's ownership."""
    owned = None
    try:
        with tempfile.NamedTemporaryFile(mode='w+b', dir=directory,
                                         prefix=prefix, suffix=suffix,
                                         delete=False) as stream:
            info = os.fstat(stream.fileno())
            descriptor = _retain_creator(stream)
            owned = _OwnedTemporary(Path(stream.name), descriptor, (info.st_dev, info.st_ino))
            stream.write(data)
            stream.flush()
            owned.snapshot = _owned_snapshot(owned.path)
            os.fsync(stream.fileno())
            stream.seek(0)
            if stream.read(len(data) + 1) != data:
                raise OSError('Profile staging bytes changed before publication.')
        if _owned_identity(owned.path) != owned.identity:
            raise OSError('Profile staging file changed before publication.')
        # Windows may finalize the writer's timestamps when it closes. Capture
        # freshness from the same path-stat API used by cleanup, while the
        # POSIX creator descriptor continues to pin its file identity. On
        # Windows this full snapshot also detects replacement/in-place changes.
        owned.snapshot = _owned_snapshot(owned.path)
        yield owned
    finally:
        if owned is not None:
            try:
                if not owned.retain:
                    _unlink_owned(owned.path, owned.identity, owned.descriptor, owned.snapshot)
            finally:
                if owned.descriptor is not None:
                    os.close(owned.descriptor)


def _atomic_write(destination, data, *, backup=None):
    """Atomically replace one app-owned profile file and optionally snapshot it."""
    destination = Path(destination)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ProfileError('Profile data could not be saved safely.') from error
    if backup is not None and destination.exists():
        try:
            with destination.open('rb') as stream:
                previous = stream.read(MAX_STORE_BYTES + 1)
        except OSError as error:
            raise ProfileError('The existing profile store could not be backed up safely.') from error
        if len(previous) > MAX_STORE_BYTES:
            raise ProfileError('The existing profile store is larger than the supported limit.')
        _decode_store(previous)
        _atomic_write(backup, previous)
    try:
        with _owned_temporary(destination.parent, data,
                              prefix=f'.{destination.name}.', suffix='.tmp') as owned:
            os.replace(owned.path, destination)
    except OSError as error:
        raise ProfileError('Profile data could not be saved safely.') from error


def _write_new_file(destination, data, *, error_message):
    """Publish a complete private file without replacing a concurrent destination.

    The shared writer stages bytes under a unique temporary name and creates
    the destination exclusively only after verification. Failure must never
    unlink the user-selected name: another process may have created it.
    """
    destination = Path(destination)
    try:
        atomic_new(data, destination, mode=0o600)
    except (OSError, SaveError) as error:
        raise ProfileError(error_message) from error
    return destination


class ProfileStore:
    """Bounded local profile storage under the application's config folder."""

    def __init__(self, path=None):
        self.path = Path(path) if path is not None else default_store_path()
        self.backup_path = self.path.with_name(self.path.name + '.bak')

    def list_profiles(self, game_id=None):
        profiles = self._load()
        if game_id is None:
            return profiles
        if type(game_id) is not str or game_id not in _GAME_IDS:
            raise ProfileError('Choose an exact registered Windows PC game.')
        return tuple(profile for profile in profiles if profile.game_id == game_id)

    def save_profile(self, profile):
        profile = normalize_profile(profile)
        profiles = list(self._load())
        for index, current in enumerate(profiles):
            if current.game_id == profile.game_id and current.profile_id == profile.profile_id:
                profiles[index] = profile
                break
        else:
            profiles.append(profile)
        self._save(profiles)
        return profile

    def delete_profile(self, game_id, profile_id):
        if type(game_id) is not str or game_id not in _GAME_IDS:
            raise ProfileError('Choose an exact registered Windows PC game.')
        _valid_profile_id(profile_id)
        profiles = list(self._load())
        updated = [item for item in profiles
                   if not (item.game_id == game_id and item.profile_id == profile_id)]
        if len(updated) == len(profiles):
            return False
        self._save(updated)
        return True

    def create_backup(self):
        """Save a validated snapshot of the current profile store to `.bak`."""
        if not self.path.exists():
            return False
        raw = self._read_store_bytes(self.path)
        _decode_store(raw)
        _atomic_write(self.backup_path, raw)
        return True

    def restore_backup(self):
        """Restore the validated `.bak`, keeping the current store as the new `.bak`."""
        raw = self._read_store_bytes(self.backup_path)
        _decode_store(raw)
        if self.path.exists():
            current = self._read_store_bytes(self.path)
            try:
                _decode_store(current)
            except ProfileError:
                # Preserve invalid bytes under an app-owned quarantine name so
                # a valid backup can still recover the store without discarding
                # the data that failed validation.
                quarantine = self.path.with_name(self.path.name + '.invalid')
                if quarantine.exists():
                    quarantine = quarantine.with_name(
                        quarantine.name + '.' + uuid.uuid4().hex)
                _write_new_file(quarantine, current,
                                error_message='Invalid profile data could not be preserved safely.')
            else:
                # Keep a recovery copy while committing the main store first.
                # This leaves the source backup intact if replacing the store
                # fails, and lets us roll back if promoting the old store to
                # `.bak` fails after the restore itself was written.
                try:
                    with _owned_temporary(self.path.parent, current,
                                          prefix=self.path.name + '.recovery.', suffix='') as recovery:
                        # A commit can be interrupted after its rename but
                        # before control returns here. Retain the original
                        # bytes until the operation's outcome is established.
                        recovery.retain = True
                        try:
                            _atomic_write(self.path, raw)
                        except ProfileError:
                            try:
                                unchanged = self._read_store_bytes(self.path) == current
                            except ProfileError:
                                unchanged = False
                            recovery.retain = not unchanged
                            raise
                        try:
                            _atomic_write(self.backup_path, current)
                        except ProfileError as error:
                            try:
                                _atomic_write(self.path, current)
                                if self._read_store_bytes(self.path) != current:
                                    raise ProfileError('The previous profile store could not be verified after rollback.')
                            except ProfileError as rollback_error:
                                raise ProfileError(
                                    f'Backup promotion failed; the previous profile store is preserved at {recovery.path}.') \
                                    from rollback_error
                            recovery.retain = False
                            raise ProfileError(
                                'Backup promotion failed; the current store and backup were restored to their prior state.') \
                                from error
                        recovery.retain = False
                except OSError as error:
                    raise ProfileError('The current profile store could not be preserved safely.') from error
                return _decode_store(raw)
        _atomic_write(self.path, raw)
        return _decode_store(raw)

    def import_profile(self, source):
        """Read one portable profile file; does not save or edit anything."""
        try:
            with Path(source).open('rb') as stream:
                raw = stream.read(MAX_PROFILE_BYTES + 1)
        except OSError as error:
            raise ProfileError('Profile file could not be read.') from error
        value = _parse_json(raw, MAX_PROFILE_BYTES, 'Profile file')
        if (type(value) is not dict or set(value) != {'schema', 'kind', 'profile'}
                or type(value['schema']) is not int or value['schema'] != SCHEMA
                or value['kind'] != 'controller-profile'):
            raise ProfileError('File is not a supported controller profile.')
        return _decode_profile(value['profile'])

    def export_profile(self, profile, destination):
        """Write one portable app profile to a new file without overwriting."""
        profile = normalize_profile(profile)
        destination = Path(destination)
        data = (json.dumps({'schema': SCHEMA, 'kind': 'controller-profile',
                            'profile': _encode_profile(profile)},
                           ensure_ascii=True, sort_keys=True) + '\n').encode('utf-8')
        if len(data) > MAX_PROFILE_BYTES:
            raise ProfileError('Profile export is larger than the supported limit.')
        return _write_new_file(
            destination, data,
            error_message='Profile export could not be written; choose a new file name.')

    def _load(self):
        if not self.path.exists():
            return ()
        return _decode_store(self._read_store_bytes(self.path))

    def _save(self, profiles):
        raw = _serialize_store(profiles)
        if self.path.exists():
            current = self._read_store_bytes(self.path)
            _decode_store(current)
        _atomic_write(self.path, raw, backup=self.backup_path)

    @staticmethod
    def _read_store_bytes(path):
        try:
            with Path(path).open('rb') as stream:
                raw = stream.read(MAX_STORE_BYTES + 1)
        except OSError as error:
            raise ProfileError('Profile data could not be read.') from error
        if len(raw) > MAX_STORE_BYTES:
            raise ProfileError('Profile data is larger than the supported limit.')
        return raw
