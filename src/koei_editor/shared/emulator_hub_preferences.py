"""Bounded local emulator launch-profile storage; contains no save data."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile

from koei_editor.shared.preferences import preference_path
from koei_editor.shared import emulator_hub


MAX_BYTES = 256 * 1024
MAX_PROFILES = 128


@dataclass(frozen=True)
class HubPreferences:
    profiles: tuple = ()


def preferences_path(legacy_path=None):
    base = Path(legacy_path) if legacy_path is not None else preference_path()
    return base.with_name(base.stem + '.emulators.json')


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Emulator preferences contain a duplicate property.')
        value[key] = item
    return value


def _validate(settings):
    if type(settings) is not HubPreferences or type(settings.profiles) is not tuple \
            or len(settings.profiles) > MAX_PROFILES:
        raise ValueError('Unsupported emulator preferences.')
    profiles = tuple(emulator_hub.validate_launch_profile(item) for item in settings.profiles)
    if len({item.id for item in profiles}) != len(profiles):
        raise ValueError('Emulator launch profiles must have unique IDs.')
    return HubPreferences(profiles)


def load(path=None):
    try:
        with Path(path if path is not None else preferences_path()).open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return HubPreferences()
        data = json.loads(raw, object_pairs_hook=_unique_object)
        if (type(data) is not dict or set(data) != {'schema', 'profiles'}
                or type(data['schema']) is not int or data['schema'] != 1
                or type(data['profiles']) is not list or len(data['profiles']) > MAX_PROFILES):
            return HubPreferences()
        profiles = []
        expected_keys = {'id', 'provider_id', 'executable', 'game_id', 'content_path'}
        for item in data['profiles']:
            if type(item) is not dict or set(item) != expected_keys:
                return HubPreferences()
            profiles.append(emulator_hub.LaunchProfile(**item))
        return _validate(HubPreferences(tuple(profiles)))
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        return HubPreferences()


def save(settings, path=None):
    temporary = None
    try:
        settings = _validate(settings)
        data = {'schema': 1, 'profiles': [profile.__dict__ for profile in settings.profiles]}
        encoded = (json.dumps(data, ensure_ascii=True, sort_keys=True) + '\n').encode('utf-8')
        if len(encoded) > MAX_BYTES:
            return False
        destination = Path(path if path is not None else preferences_path())
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile('wb', dir=destination.parent,
                                         prefix='.emulators.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        return True
    except (OSError, ValueError, TypeError, KeyError):
        return False
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def add_profile(settings, profile):
    settings = _validate(settings)
    profile = emulator_hub.validate_launch_profile(profile)
    updated = tuple(item for item in settings.profiles if item.id != profile.id) + (profile,)
    if len(updated) > MAX_PROFILES:
        raise ValueError(f'Save at most {MAX_PROFILES} emulator launch profiles.')
    return HubPreferences(updated)


def remove_profile(settings, profile_id):
    settings = _validate(settings)
    if type(profile_id) is not str:
        return settings
    return HubPreferences(tuple(item for item in settings.profiles if item.id != profile_id))
