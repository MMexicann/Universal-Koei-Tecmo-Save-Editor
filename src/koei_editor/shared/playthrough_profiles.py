"""Bounded local playthrough profiles built around verified Save Vault snapshots.

Profiles retain only a reference to an existing vault snapshot plus inert JSON
exports from the other managers. Preparing a profile makes a new isolated
directory; it never applies a mod, changes settings, edits a build, or writes to
a live game save.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import uuid

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, new_child_bound
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.save_vault import _ordinary, _profile_path, _read


PROFILE_SCHEMA_VERSION = 1
MAX_PROFILES = 500
MAX_PROFILE_BYTES = 1024 * 1024
MAX_COMPONENT_BYTES = 256 * 1024
MAX_STORE_BYTES = 128 * 1024 * 1024
MAX_REPORT_BYTES = 256 * 1024
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 10_000
_PROFILE_ID = re.compile('[0-9a-f]{32}')
_COMPONENTS = {
    'mod_configuration': 'mod_manager',
    'game_settings': 'configuration_manager',
    'character_build': 'character_workshop',
}
_COMPONENT_FIELDS = {'component', 'provider', 'schema_version', 'game_id',
                     'game_version', 'payload'}
_PROFILE_FIELDS = {'schema_version', 'id', 'name', 'created_utc', 'game_id',
                   'game_version', 'save_snapshot_id', 'components'}


@dataclass(frozen=True)
class ProfileComponentSnapshot:
    """A manager export retained as data and never interpreted as a command."""

    component: str
    provider: str
    schema_version: int
    game_id: str
    game_version: str
    payload: object


@dataclass(frozen=True)
class PlaythroughProfile:
    id: str
    name: str
    created_utc: str
    game_id: str
    game_version: str
    save_snapshot_id: str
    components: tuple[ProfileComponentSnapshot, ...]


@dataclass(frozen=True)
class PlaythroughPreview:
    profile: PlaythroughProfile
    compatible: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    report: dict


@dataclass(frozen=True)
class PreparedEnvironment:
    destination: Path
    save_path: Path
    backup_snapshot_id: str | None
    report_path: Path
    report: dict


class PlaythroughPreparationError(SaveError):
    """Preparation failed after creating a new environment directory."""

    def __init__(self, message, *, backup_snapshot_id, destination):
        super().__init__(message)
        self.backup_snapshot_id = backup_snapshot_id
        self.destination = Path(destination)


def _canonical_json(value):
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True,
                          separators=(',', ':'), allow_nan=False).encode('ascii')
    except (TypeError, ValueError, RecursionError) as error:
        raise SaveError('Profile data must be bounded JSON without nonfinite numbers.') from error


def _pretty_json(value, maximum):
    try:
        raw = (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2,
                           allow_nan=False) + '\n').encode('ascii')
    except (TypeError, ValueError, RecursionError) as error:
        raise SaveError('Profile data must be bounded JSON without nonfinite numbers.') from error
    if not 0 < len(raw) <= maximum:
        raise SaveError('Profile JSON exceeds its fixed size bound.')
    return raw


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON object field.')
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError('Nonfinite JSON number.')


def _loads(raw, maximum, label):
    if type(raw) is not bytes or not 0 < len(raw) <= maximum:
        raise SaveError(f'{label} is empty or exceeds its fixed size bound.')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                          parse_constant=_invalid_constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise SaveError(f'{label} is not valid UTF-8 JSON or contains duplicate fields.') from error


def _check_json_tree(value):
    """Enforce a useful structural bound in addition to the encoded byte bound."""
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if count > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            raise SaveError('Component JSON exceeds its fixed structure bound.')
        if type(item) is dict:
            for key, child in item.items():
                if type(key) is not str:
                    raise SaveError('Component JSON object fields must be strings.')
                pending.append((child, depth + 1))
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
        elif item is None or type(item) in (str, int, float, bool):
            if type(item) is float and not math.isfinite(item):
                raise SaveError('Component JSON cannot contain nonfinite numbers.')
        else:
            raise SaveError('Component payloads may contain only JSON values.')


def _text(value, field, maximum, *, allow_empty=False):
    if (type(value) is not str or len(value) > maximum
            or (not allow_empty and not value)
            or any(ord(character) < 32 or ord(character) == 127 for character in value)):
        raise SaveError(f'Profile {field} must be ordinary printable text no longer than {maximum} characters.')
    return value


def _game_identity(game_id):
    _text(game_id, 'game/platform identity', 100)
    try:
        return get_game(game_id)
    except (KeyError, ValueError, TypeError) as error:
        raise SaveError('Choose a registered game/platform profile.') from error


def _game_version(value):
    return _text(value, 'game version', 120)


def _component_payload(value):
    _check_json_tree(value)
    raw = _canonical_json(value)
    if not 0 < len(raw) <= MAX_COMPONENT_BYTES:
        raise SaveError('A manager component payload exceeds its 256 KiB bound.')
    return _loads(raw, MAX_COMPONENT_BYTES, 'Manager component payload')


def _component_fields(component):
    if type(component) is not ProfileComponentSnapshot:
        raise SaveError('Choose a supported manager component snapshot.')
    if type(component.component) is not str or type(component.provider) is not str:
        raise SaveError('Manager component and provider identities must be strings.')
    expected_provider = _COMPONENTS.get(component.component)
    if expected_provider is None or component.provider != expected_provider:
        raise SaveError('The manager component/provider pair is not supported.')
    if type(component.schema_version) is not int or not 1 <= component.schema_version <= 1_000_000:
        raise SaveError('Manager component schema version must be a positive integer.')
    _game_identity(component.game_id)
    _game_version(component.game_version)
    payload = _component_payload(component.payload)
    return {
        'component': component.component,
        'provider': component.provider,
        'schema_version': component.schema_version,
        'game_id': component.game_id,
        'game_version': component.game_version,
        'payload': payload,
    }


def _component_digest(fields):
    return hashlib.sha256(_canonical_json(fields)).hexdigest()


def _component_from_fields(value, *, require_digest=False):
    if type(value) is not dict or not _COMPONENT_FIELDS <= set(value):
        raise SaveError('Manager component snapshot has an invalid structure.')
    extras = set(value) - _COMPONENT_FIELDS
    if extras - {'sha256'} or require_digest and extras != {'sha256'}:
        raise SaveError('Manager component snapshot contains unsupported fields.')
    try:
        item = ProfileComponentSnapshot(
            component=value['component'], provider=value['provider'],
            schema_version=value['schema_version'], game_id=value['game_id'],
            game_version=value['game_version'], payload=value['payload'])
        fields = _component_fields(item)
    except (KeyError, TypeError) as error:
        raise SaveError('Manager component snapshot has an invalid structure.') from error
    if 'sha256' in value and (type(value['sha256']) is not str
                              or value['sha256'] != _component_digest(fields)):
        raise SaveError('Manager component snapshot hash does not match its JSON payload.')
    return item


def load_component_snapshot(path):
    """Load one bounded manager-export JSON file, rejecting duplicate fields."""
    try:
        raw, _ = _read(path, MAX_COMPONENT_BYTES)
        value = _loads(raw, MAX_COMPONENT_BYTES, 'Manager component snapshot')
        return _component_from_fields(value)
    except (OSError, ValueError, TypeError) as error:
        if isinstance(error, SaveError):
            raise
        raise SaveError('Manager component snapshot could not be read safely.') from error


def dump_component_snapshot(component):
    """Return the validated manager-export schema as pretty JSON text."""
    fields = _component_fields(component)
    return _pretty_json(fields, MAX_COMPONENT_BYTES).decode('ascii')


def _profile_to_payload(profile):
    return {
        'schema_version': PROFILE_SCHEMA_VERSION,
        'id': profile.id,
        'name': profile.name,
        'created_utc': profile.created_utc,
        'game_id': profile.game_id,
        'game_version': profile.game_version,
        'save_snapshot_id': profile.save_snapshot_id,
        'components': [dict(_component_fields(component),
                            sha256=_component_digest(_component_fields(component)))
                       for component in profile.components],
    }


def _profile_bytes(profile):
    payload = _profile_to_payload(profile)
    envelope = {'payload': payload, 'sha256': hashlib.sha256(_canonical_json(payload)).hexdigest()}
    return _pretty_json(envelope, MAX_PROFILE_BYTES)


def _profile_from_bytes(raw, expected_id):
    envelope = _loads(raw, MAX_PROFILE_BYTES, 'Playthrough profile manifest')
    if (type(envelope) is not dict or set(envelope) != {'payload', 'sha256'}
            or type(envelope['sha256']) is not str
            or envelope['sha256'] != hashlib.sha256(_canonical_json(envelope['payload'])).hexdigest()):
        raise SaveError('Playthrough profile manifest checksum is invalid.')
    payload = envelope['payload']
    if type(payload) is not dict or set(payload) != _PROFILE_FIELDS:
        raise SaveError('Playthrough profile manifest has an invalid schema.')
    if payload['schema_version'] != PROFILE_SCHEMA_VERSION or type(payload['schema_version']) is not int:
        raise SaveError('Playthrough profile schema version is unsupported.')
    profile_id = payload['id']
    if (type(profile_id) is not str or _PROFILE_ID.fullmatch(profile_id) is None
            or profile_id != expected_id):
        raise SaveError('Playthrough profile identifier does not match its manifest path.')
    _text(payload['name'], 'name', 120)
    _text(payload['created_utc'], 'creation timestamp', 40)
    _game_identity(payload['game_id'])
    _game_version(payload['game_version'])
    snapshot_id = payload['save_snapshot_id']
    if type(snapshot_id) is not str or _PROFILE_ID.fullmatch(snapshot_id) is None:
        raise SaveError('Playthrough profile refers to an invalid Save Vault snapshot identifier.')
    records = payload['components']
    if type(records) is not list or len(records) > len(_COMPONENTS):
        raise SaveError('Playthrough profile has too many manager components.')
    components, seen = [], set()
    for record in records:
        component = _component_from_fields(record, require_digest=True)
        fields = _component_fields(component)
        if fields['game_id'] != payload['game_id'] or fields['game_version'] != payload['game_version']:
            raise SaveError('Manager component belongs to a different game or game version.')
        if component.component in seen:
            raise SaveError('Playthrough profile contains duplicate manager components.')
        seen.add(component.component)
        components.append(component)
    return PlaythroughProfile(profile_id, payload['name'], payload['created_utc'],
                              payload['game_id'], payload['game_version'], snapshot_id,
                              tuple(components))


def _directory(path, *, create=False):
    """Resolve an ordinary directory using the vault's link and alias guards."""
    path, info = _ordinary(path, directory=True, missing=True)
    if info is None and create:
        parent, parent_info = _ordinary(path.parent, directory=True)
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
        path, info = _ordinary(path, directory=True)
        current_parent, current_parent_info = _ordinary(path.parent, directory=True)
        if (current_parent, current_parent_info.st_dev, current_parent_info.st_ino) != (
                parent, parent_info.st_dev, parent_info.st_ino):
            raise SaveError('The profile-store parent directory changed identity.')
    return path, info


def _directory_identity(path):
    _, info = _ordinary(path, directory=True)
    return info.st_dev, info.st_ino


@contextmanager
def _store_lock(directory):
    lock = directory / '.lock'
    _, info = _ordinary(lock, directory=True, missing=True)
    if info is not None:
        raise SaveError('Playthrough profile store is busy or has an interrupted operation lock.')
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError:
        raise SaveError('Playthrough profile store is busy or has an interrupted operation lock.') from None
    _, info = _ordinary(lock, directory=True)
    identity = (info.st_dev, info.st_ino)
    try:
        yield
    finally:
        try:
            _, current = _ordinary(lock, directory=True)
            if (current.st_dev, current.st_ino) == identity:
                lock.rmdir()
        except (OSError, SaveError):
            pass


class PlaythroughProfileStore:
    """Private, bounded profile manifests stored beside a selected Save Vault."""

    def __init__(self, vault):
        if not callable(getattr(vault, 'list_snapshots', None)) or not callable(getattr(vault, 'verify', None)):
            raise SaveError('Choose an opened Save Vault for playthrough profiles.')
        self.vault = vault

    @property
    def directory(self):
        return Path(self.vault.root) / 'playthrough_profiles'

    def _directory(self, *, create=False):
        return _directory(self.directory, create=create)

    def _snapshot(self, game_id, snapshot_id):
        candidates = self.vault.list_snapshots(game_id=game_id)
        match = next((item for item in candidates if item.id == snapshot_id), None)
        if match is None or match.game_id != game_id:
            raise SaveError('The selected Save Vault snapshot does not belong to this game/platform profile.')
        verification = self.vault.verify(snapshot_id)
        if len(verification) != 1 or not verification[0].valid:
            raise SaveError('The selected Save Vault snapshot failed hash or native qualification.')
        return match

    def _read_profile(self, profile_id, directory=None):
        if type(profile_id) is not str or _PROFILE_ID.fullmatch(profile_id) is None:
            raise SaveError('Choose a valid playthrough profile identifier.')
        directory = directory or self._directory()[0]
        raw, _ = _read(directory / (profile_id + '.json'), MAX_PROFILE_BYTES)
        return _profile_from_bytes(raw, profile_id)

    def _scan(self, directory):
        profiles, total = [], 0
        with os.scandir(directory) as entries:
            for count, entry in enumerate(entries):
                if count >= MAX_PROFILES + 1:
                    raise SaveError('Playthrough profile store exceeds its fixed entry bound.')
                if entry.name == '.lock':
                    continue
                match = re.fullmatch('([0-9a-f]{32})[.]json', entry.name)
                if match is None:
                    raise SaveError('Playthrough profile store contains an unexpected entry.')
                profile_id = match.group(1)
                raw, _ = _read(Path(entry.path), MAX_PROFILE_BYTES)
                total += len(raw)
                if total > MAX_STORE_BYTES:
                    raise SaveError('Playthrough profile store exceeds its fixed metadata bound.')
                profiles.append(_profile_from_bytes(raw, profile_id))
        if len(profiles) > MAX_PROFILES:
            raise SaveError('Playthrough profile store exceeds its fixed profile bound.')
        return tuple(sorted(profiles, key=lambda item: (item.name.casefold(), item.id)))

    def create_profile(self, name, game_id, game_version, save_snapshot_id, components=()):
        name = _text(name, 'name', 120)
        game = _game_identity(game_id)
        game_version = _game_version(game_version)
        if type(save_snapshot_id) is not str or _PROFILE_ID.fullmatch(save_snapshot_id) is None:
            raise SaveError('Choose a valid Save Vault snapshot identifier.')
        if components is None:
            components = ()
        try:
            components = tuple(components)
        except TypeError as error:
            raise SaveError('Manager components must be a sequence of JSON snapshots.') from error
        if len(components) > len(_COMPONENTS):
            raise SaveError('A playthrough profile supports at most three manager components.')
        validated, seen = [], set()
        for component in components:
            fields = _component_fields(component)
            if fields['game_id'] != game.id or fields['game_version'] != game_version:
                raise SaveError('Each manager component must match the profile game and exact game version.')
            if fields['component'] in seen:
                raise SaveError('Choose at most one export for each manager component.')
            seen.add(fields['component'])
            validated.append(ProfileComponentSnapshot(**fields))
        self._snapshot(game.id, save_snapshot_id)
        profile = PlaythroughProfile(uuid.uuid4().hex, name,
                                     datetime.now(timezone.utc).isoformat(), game.id,
                                     game_version, save_snapshot_id, tuple(validated))
        raw = _profile_bytes(profile)
        directory, _ = self._directory(create=True)
        with _store_lock(directory):
            existing = self._scan(directory)
            if len(existing) >= MAX_PROFILES:
                raise SaveError('Playthrough profile store reached its profile limit.')
            if sum(len(_profile_bytes(item)) for item in existing) + len(raw) > MAX_STORE_BYTES:
                raise SaveError('Playthrough profile store reached its metadata byte limit.')
            self._snapshot(game.id, save_snapshot_id)
            target = directory / (profile.id + '.json')
            _ordinary(target, missing=True)
            result = atomic_new(raw, safe_path(target))
            if _read(result, MAX_PROFILE_BYTES)[0] != raw:
                raise SaveError('New playthrough profile failed its local read-back check.')
        return profile

    def list_profiles(self, game_id=None):
        if game_id is not None:
            _game_identity(game_id)
        directory, info = self._directory()
        if info is None:
            return ()
        with _store_lock(directory):
            profiles = self._scan(directory)
        return tuple(profile for profile in profiles if game_id is None or profile.game_id == game_id)

    def load(self, profile_id):
        profile = self._load_metadata(profile_id)
        self._snapshot(profile.game_id, profile.save_snapshot_id)
        return profile

    def _load_metadata(self, profile_id):
        directory, info = self._directory()
        if info is None:
            raise SaveError('The requested playthrough profile does not exist.')
        with _store_lock(directory):
            return self._read_profile(profile_id, directory)

    def preview(self, profile_id, installed_game_version):
        installed_game_version = _game_version(installed_game_version)
        profile = self._load_metadata(profile_id)
        blockers = []
        save_snapshot_verified = False
        if installed_game_version != profile.game_version:
            blockers.append('installed_game_version_mismatch')
        try:
            self._snapshot(profile.game_id, profile.save_snapshot_id)
        except (OSError, ValueError, TypeError, SaveError):
            blockers.append('save_snapshot_invalid_or_unavailable')
        else:
            save_snapshot_verified = True
        blockers = tuple(blockers)
        warnings = ('Manager component exports are inert JSON; they are not applied during profile preparation.',)
        report = {
            'schema': 'koei-playthrough-preview',
            'schema_version': 1,
            'report_scope': 'compatibility_preview',
            'profile_id': profile.id,
            'profile_name': profile.name,
            'game_id': profile.game_id,
            'profile_game_version': profile.game_version,
            'installed_game_version': installed_game_version,
            'installed_game_version_source': 'user_asserted',
            'compatible': not blockers,
            'blockers': list(blockers),
            'warnings': list(warnings),
            'save_snapshot_id': profile.save_snapshot_id,
            'save_snapshot_verified': save_snapshot_verified,
            'components_applied': False,
            'live_save_written': False,
            'components': [
                {'component': item.component, 'provider': item.provider,
                 'schema_version': item.schema_version}
                for item in profile.components
            ],
        }
        return PlaythroughPreview(profile, not blockers, blockers, warnings, report)

    def prepare_environment(self, profile_id, destination, installed_game_version,
                            active_save_copy=None):
        preview = self.preview(profile_id, installed_game_version)
        if not preview.compatible:
            raise SaveError('Playthrough profile cannot be prepared until its game version and Save Vault snapshot validate.')
        profile = preview.profile
        snapshot = self._snapshot(profile.game_id, profile.save_snapshot_id)

        destination, info = _ordinary(destination, directory=True, missing=True)
        if info is not None:
            raise FileExistsError('Environment preparation requires a new destination directory.')
        if self.vault._contains(destination):
            raise SaveError('Choose a fresh environment folder outside the Save Vault.')
        parent, parent_info = _ordinary(destination.parent, directory=True)
        safe_path(destination)
        save_destination = destination / 'save-copy'
        # This nested directory cannot pass _ordinary until its new parent
        # exists. Apply the lexical/live/cloud guard before creating anything;
        # SaveVault.restore will recheck ordinary path identity after creation.
        safe_path(save_destination)
        _profile_path(profile.game_id, save_destination / snapshot.filename)

        backup_snapshot_id = None
        if active_save_copy is not None:
            slug = re.sub(r'[^A-Za-z0-9_.-]', '-', profile.game_id)[:32] or 'game'
            game_tag = hashlib.sha256(profile.game_id.encode('utf-8')).hexdigest()[:8]
            branch = f'active-backup-{slug}-{game_tag}'
            backup = self.vault.snapshot(
                profile.game_id, active_save_copy, branch=branch,
                label=f'Playthrough profile backup {profile.name[:120]}')
            backup_snapshot_id = backup.id

        try:
            try:
                destination.mkdir(mode=0o700)
            except FileExistsError:
                raise SaveError('The environment destination appeared before preparation.') from None
            _, created_info = _ordinary(destination, directory=True)
            created_identity = (created_info.st_dev, created_info.st_ino)
            _, current_parent_info = _ordinary(parent, directory=True)
            if ((current_parent_info.st_dev, current_parent_info.st_ino)
                    != (parent_info.st_dev, parent_info.st_ino)):
                raise SaveError('The environment parent changed identity during preparation.')

            save_path = self.vault.restore(profile.save_snapshot_id, save_destination)
            if _directory_identity(destination) != created_identity:
                raise SaveError('The new environment directory changed identity during preparation.')

            component_rows = []
            if profile.components:
                component_directory = destination / 'components'
                component_directory.mkdir(mode=0o700)
                component_directory, component_info = _ordinary(
                    component_directory, directory=True)
                component_identity = (component_info.st_dev, component_info.st_ino)
                for component in profile.components:
                    fields = _component_fields(component)
                    digest = _component_digest(fields)
                    document = dict(fields, sha256=digest)
                    raw = _pretty_json(document, MAX_COMPONENT_BYTES)
                    component_path = component_directory / (component.component + '.json')
                    new_child_bound(raw, component_directory, component_path.name,
                                    component_identity)
                    if _read(component_path, MAX_COMPONENT_BYTES)[0] != raw:
                        raise SaveError('Staged manager component failed its local read-back check.')
                    component_rows.append({
                        'component': component.component,
                        'provider': component.provider,
                        'schema_version': component.schema_version,
                        'path': 'components/' + component.component + '.json',
                        'sha256': digest,
                        'applied': False,
                    })

            relative_save = Path('save-copy') / snapshot.filename
            report = {
                'schema': 'koei-playthrough-environment-report',
                'schema_version': 1,
                'created_utc': datetime.now(timezone.utc).isoformat(),
                'profile_id': profile.id,
                'profile_name': profile.name,
                'game_id': profile.game_id,
                'profile_game_version': profile.game_version,
                'installed_game_version': installed_game_version,
                'installed_game_version_source': 'user_asserted',
                'compatible': True,
                'save_snapshot_id': profile.save_snapshot_id,
                'save_snapshot_verified': True,
                'restored_save_path': relative_save.as_posix(),
                'active_save_backup_snapshot_id': backup_snapshot_id,
                'components': component_rows,
                'components_applied': False,
                'components_staged_as_inert_json': True,
                'live_save_written': False,
            }
            report_raw = _pretty_json(report, MAX_REPORT_BYTES)
            report_path = destination / 'playthrough-report.json'
            new_child_bound(report_raw, destination, report_path.name, created_identity)
            if _read(report_path, MAX_REPORT_BYTES)[0] != report_raw:
                raise SaveError('Environment report failed its local read-back check.')
            if _directory_identity(destination) != created_identity:
                raise SaveError('The new environment directory changed identity before completion.')
            return PreparedEnvironment(destination, save_path, backup_snapshot_id,
                                      report_path, report)
        except Exception as error:
            backup_notice = (f' The separate-copy backup is Save Vault snapshot '
                             f'{backup_snapshot_id}.' if backup_snapshot_id is not None else '')
            raise PlaythroughPreparationError(
                f'Environment preparation failed. No live save was written. '
                f'Review the new environment at {destination} for partial files before reuse.'
                f'{backup_notice} Preparation error: {error}',
                backup_snapshot_id=backup_snapshot_id, destination=destination,
            ) from error
