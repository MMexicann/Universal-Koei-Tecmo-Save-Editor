"""Exact-build compatibility records and path-free local build history.

Steam's ``buildid`` is a store build marker. It is distinct from a game's save
format revision and from this editor's profile-level file qualification. This
module only joins compatibility evidence to an exact installed build; missing
evidence stays ``unknown``.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from urllib.parse import urlsplit

from koei_editor.game_registry import GAMES
from koei_editor.resources import data_file
from koei_editor.shared.preferences import preference_path
from koei_editor.shared import save_discovery


ARTIFACT_KINDS = ('save_editor', 'mod', 'config_tool', 'asset_format')
COMPATIBILITY_STATUSES = ('verified', 'unsupported', 'unknown')
MAX_CATALOG_BYTES = 256 * 1024
MAX_CATALOG_RECORDS = 512
MAX_HISTORY_BYTES = 256 * 1024
MAX_HISTORY_EVENTS = 2000
_APP_ID = re.compile(r'[1-9][0-9]{0,9}\Z')
_BUILD_ID = re.compile(r'[0-9]{1,20}\Z')
_LAST_UPDATED = re.compile(r'[0-9]{1,12}\Z')
_ARTIFACT_ID = re.compile(r'[a-z][a-z0-9_.:-]{0,95}\Z')
_REASON = re.compile(r'[a-z][a-z0-9_]{0,63}\Z')
_NEXT_STEP = re.compile(r'[a-z][a-z0-9_]{0,63}\Z')
_NEXT_STEP_IDS = frozenset(('evidence', 'troubleshooting'))
_REFERENCE = re.compile(r'(?:docs/[A-Za-z0-9_./-]{1,240}|https://[^\s]{1,300})\Z')
_GAMES = {game.id: game for game in GAMES}
_STEAM_PROFILES = {(item.game_id, item.app_id) for item in save_discovery.STEAM_MAPPINGS}


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _timestamp(value):
    if type(value) is not str or not 1 <= len(value) <= 32:
        return False
    try:
        parsed = _timestamp_order(value)
    except ValueError:
        return False
    return parsed is not None


def _timestamp_order(value):
    """Parse an accepted timezone-qualified ISO timestamp into UTC for ordering."""
    parsed = datetime.fromisoformat(value[:-1] + '+00:00' if value.endswith('Z') else value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('Timestamp must include a timezone.')
    return parsed.astimezone(timezone.utc)


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate version tracker metadata key.')
        value[key] = item
    return value


def _no_constant(value):
    raise ValueError('Nonfinite version tracker metadata is unsupported.')


def _decode(raw, label):
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                          parse_constant=_no_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f'{label} metadata is malformed.') from exc


def _valid_build_id(value, *, optional=False):
    return ((optional and value is None) or
            (type(value) is str and _BUILD_ID.fullmatch(value) is not None))


def _valid_game_profile(game_id, platform):
    game = _GAMES.get(game_id) if type(game_id) is str else None
    return game is not None and type(platform) is str and game.platform == platform


def _valid_steam_profile(game_id, platform, app_id):
    return (_valid_game_profile(game_id, platform)
            and type(app_id) is str and _APP_ID.fullmatch(app_id) is not None
            and (game_id, app_id) in _STEAM_PROFILES)


def _valid_reference(value):
    if type(value) is not str or _REFERENCE.fullmatch(value) is None:
        return False
    if value.startswith('https://'):
        parts = urlsplit(value)
        return (len(value) <= 300 and bool(parts.hostname) and parts.username is None
                and parts.password is None)
    parts = value.split('/')
    return (parts[0] == 'docs' and len(parts) >= 2
            and all(part not in ('', '.', '..') for part in parts))


def _valid_mapping_reference(value):
    """Accept only reviewed documentation references for Steam mapping evidence."""
    if type(value) is not str or not value.startswith('docs/'):
        return False
    if _REFERENCE.fullmatch(value) is None:
        return False
    parts = value.split('/')
    return len(parts) >= 2 and all(part not in ('', '.', '..') for part in parts)


def tracker_history_path(preferences_path=None):
    """Return the private app settings path used for local build observations."""
    base = Path(preferences_path) if preferences_path is not None else preference_path()
    return base.with_name('version_tracker.history.json')


@dataclass(frozen=True)
class BuildObservation:
    """One installed build observation, intentionally without its local path."""

    game_id: str
    platform: str
    app_id: str
    build_id: str | None
    last_updated: str | None
    observed_at: str
    source: str = 'steam_manifest'
    confidence: str = 'installation_metadata'
    evidence: tuple[str, ...] = ()

    def __post_init__(self):
        if not _valid_steam_profile(self.game_id, self.platform, self.app_id):
            raise ValueError('Build observation must use a reviewed game/platform/app mapping.')
        if not _valid_build_id(self.build_id, optional=True):
            raise ValueError('Build observation has an invalid Steam build ID.')
        if not ((self.last_updated is None) or
                (type(self.last_updated) is str and _LAST_UPDATED.fullmatch(self.last_updated) is not None)):
            raise ValueError('Build observation has an invalid Steam last-updated marker.')
        if not _timestamp(self.observed_at):
            raise ValueError('Build observation time must include a timezone.')
        if self.source != 'steam_manifest' or self.confidence != 'installation_metadata':
            raise ValueError('Unsupported build observation source or confidence.')
        if (type(self.evidence) is not tuple or len(self.evidence) > 20
                or any(not _valid_mapping_reference(ref) for ref in self.evidence)
                or len(set(self.evidence)) != len(self.evidence)):
            raise ValueError('Build observation has invalid evidence references.')


@dataclass(frozen=True)
class CompatibilityRecord:
    """Evidence-backed compatibility for one exact game/platform/app/build tuple."""

    game_id: str
    platform: str
    app_id: str
    build_id: str | None
    artifact_kind: str
    artifact_id: str
    artifact_name: str
    artifact_version: str | None
    status: str
    reason_code: str
    explanation: str
    evidence: tuple[str, ...]
    checked_at: str
    next_step_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class BuildHistoryEvent:
    """Path-free first-seen/build-change event stored on this computer."""

    event_kind: str
    game_id: str
    platform: str
    app_id: str
    previous_build_id: str | None
    build_id: str | None
    last_updated: str | None
    observed_at: str
    source: str = 'steam_manifest'
    confidence: str = 'installation_metadata'

    @property
    def warning(self):
        if self.event_kind != 'build_changed':
            return ''
        before = self.previous_build_id or 'unavailable'
        after = self.build_id or 'unavailable'
        return (f'Steam build ID changed from {before} to {after}. Review exact-build compatibility entries '
                'for this build; the recorded change alone does not establish incompatibility.')


def _validate_record(value):
    fields = {'game_id', 'platform', 'app_id', 'build_id', 'artifact_kind', 'artifact_id', 'artifact_name',
              'artifact_version', 'status', 'reason_code', 'explanation', 'evidence', 'checked_at',
              'next_step_ids'}
    if type(value) is not dict or set(value) != fields:
        raise ValueError('Compatibility metadata has unexpected fields.')
    if not _valid_steam_profile(value['game_id'], value['platform'], value['app_id']):
        raise ValueError('Compatibility metadata names an unreviewed game/platform/app profile.')
    if not _valid_build_id(value['build_id']):
        raise ValueError('Compatibility metadata requires one exact decimal build ID.')
    if type(value['artifact_kind']) is not str or value['artifact_kind'] not in ARTIFACT_KINDS:
        raise ValueError('Compatibility metadata names an unsupported artifact kind.')
    artifact_id = value['artifact_id']
    if type(artifact_id) is not str or _ARTIFACT_ID.fullmatch(artifact_id) is None:
        raise ValueError('Compatibility metadata has an invalid artifact ID.')
    if artifact_id in (f'unverified_{value["artifact_kind"]}', f'unlisted_{value["artifact_kind"]}'):
        raise ValueError('Compatibility metadata uses a reserved synthetic artifact ID.')
    name = value['artifact_name']
    if (type(name) is not str or not 1 <= len(name.strip()) <= 120
            or any(ord(character) < 32 for character in name)):
        raise ValueError('Compatibility metadata has an invalid artifact name.')
    version = value['artifact_version']
    if version is not None:
        if (type(version) is not str or len(version) > 128 or not version.strip()
                or any(ord(character) < 32 for character in version)):
            raise ValueError('Compatibility metadata has an invalid artifact version.')
        version = version.strip()
    if type(value['status']) is not str or value['status'] not in COMPATIBILITY_STATUSES:
        raise ValueError('Compatibility metadata has an invalid status.')
    reason = value['reason_code']
    if type(reason) is not str or _REASON.fullmatch(reason) is None:
        raise ValueError('Compatibility metadata has an invalid reason code.')
    explanation = value['explanation']
    if type(explanation) is not str or not 1 <= len(explanation.strip()) <= 1200 or '\0' in explanation:
        raise ValueError('Compatibility metadata requires a concise explanation.')
    evidence = value['evidence']
    if (type(evidence) not in (list, tuple) or len(evidence) > 20
            or any(not _valid_reference(ref) for ref in evidence)
            or len(set(evidence)) != len(evidence)):
        raise ValueError('Compatibility metadata has invalid evidence references.')
    checked_at = value['checked_at']
    if not _timestamp(checked_at):
        raise ValueError('Compatibility metadata requires a timezone-qualified check time.')
    next_steps = value['next_step_ids']
    if (type(next_steps) not in (list, tuple) or len(next_steps) > 20
            or any(type(item) is not str or _NEXT_STEP.fullmatch(item) is None
                   or item not in _NEXT_STEP_IDS for item in next_steps)
            or len(set(next_steps)) != len(next_steps)):
        raise ValueError('Compatibility metadata has an unresolved next-step ID.')
    if value['status'] in ('verified', 'unsupported') and (not evidence or not version):
        raise ValueError('Verified or unsupported records require an artifact version and evidence.')
    if value['status'] == 'unsupported' and not next_steps:
        raise ValueError('Unsupported records require at least one resolved next step.')
    return CompatibilityRecord(
        value['game_id'], value['platform'], value['app_id'], value['build_id'],
        value['artifact_kind'], artifact_id,
        name.strip(), version, value['status'], reason, explanation.strip(), tuple(evidence),
        checked_at, tuple(next_steps))


def _validated_records(records):
    if type(records) not in (tuple, list) or len(records) > MAX_CATALOG_RECORDS:
        raise ValueError('Compatibility catalog exceeds its fixed record limit.')
    validated = tuple(_validate_record(record.__dict__) if isinstance(record, CompatibilityRecord)
                      else _validate_record(record) for record in records)
    keys = [(item.game_id, item.platform, item.app_id, item.build_id, item.artifact_kind, item.artifact_id,
             _timestamp_order(item.checked_at)) for item in validated]
    if len(set(keys)) != len(keys):
        raise ValueError('Compatibility catalog contains duplicate exact-build check rows.')
    return validated


def load_catalog():
    """Load the reviewed exact-build catalog from packaged runtime metadata."""
    try:
        with data_file('version_compatibility.json').open('rb') as stream:
            raw = stream.read(MAX_CATALOG_BYTES + 1)
    except (OSError, ValueError) as exc:
        raise ValueError('Bundled compatibility catalog could not be read.') from exc
    if len(raw) > MAX_CATALOG_BYTES:
        raise ValueError('Bundled compatibility catalog exceeds its fixed byte limit.')
    value = _decode(raw, 'Compatibility catalog')
    if (type(value) is not dict or set(value) != {'schema_version', 'records'}
            or type(value['schema_version']) is not int or value['schema_version'] != 1):
        raise ValueError('Bundled compatibility catalog schema is unsupported.')
    records = value['records']
    if type(records) is not list:
        raise ValueError('Bundled compatibility records must be an array.')
    return _validated_records(records)


def build_observations(discovery_result, observed_at=None):
    """Convert safe installed-game results into observations without local paths."""
    if not hasattr(discovery_result, 'installed_games'):
        raise ValueError('Choose a save-discovery result with installed-game entries.')
    observed_at = _now() if observed_at is None else observed_at
    if not _timestamp(observed_at):
        raise ValueError('Observation time must include a timezone.')
    observations = []
    for item in discovery_result.installed_games:
        game = _GAMES.get(item.game_id)
        if game is None:
            raise ValueError('Installed-game metadata names an unregistered profile.')
        observations.append(BuildObservation(
            item.game_id, game.platform, item.app_id, item.build_id, item.last_updated,
            observed_at, item.source, item.confidence,
            (item.evidence,) if item.evidence else ()))
    keys = [(item.game_id, item.app_id) for item in observations]
    if len(keys) > 500 or len(set(keys)) != len(keys):
        raise ValueError('Installed-game observations are ambiguous or exceed their fixed limit.')
    return tuple(observations)


@dataclass(frozen=True)
class BuildScanResult:
    """Path-free scan output with enough diagnostics to explain an empty result."""

    observations: tuple[BuildObservation, ...]
    issues: tuple[str, ...]
    stop_reason: str
    visited_entries: int
    metadata_bytes: int
    mapped_game_ids: tuple[str, ...]


def scan_installed_builds(**kwargs):
    """Scan only mapped Steam manifests and return observations plus safe diagnostics."""
    result = save_discovery.discover_installed_builds(**kwargs)
    return BuildScanResult(build_observations(result), result.issues, result.stop_reason,
                           result.visited_entries, result.metadata_bytes, result.mapped_game_ids)


def _unknown_record(observation, artifact_kind, *, unlisted=False):
    names = {
        'save_editor': 'Save editor compatibility',
        'mod': 'Mod compatibility',
        'config_tool': 'Configuration tool compatibility',
        'asset_format': 'Asset format compatibility',
    }
    explanations = {
        'save_editor': ('No exact compatibility record ties this installed Steam build to the editor profile. '
                        'The profile’s documented save-format scope is separate from the game executable build.'),
        'mod': 'No version-specific mod compatibility record is available for this installed game build.',
        'config_tool': ('No version-specific configuration-tool compatibility record is available for '
                        'this installed game build.'),
        'asset_format': ('No version-specific asset-format compatibility record is available for '
                         'this installed game build.'),
    }
    category_names = {
        'save_editor': 'save editors',
        'mod': 'mods',
        'config_tool': 'configuration tools',
        'asset_format': 'asset formats',
    }
    if unlisted:
        category = category_names[artifact_kind]
        artifact_id = f'unlisted_{artifact_kind}'
        artifact_name = f'Other unlisted {category}'
        reason_code = 'incomplete_artifact_inventory'
        explanation = (f'Exact-build records cover some named {category}. The catalog is not a complete inventory, '
                       f'so other {category} remain unknown for this installed build.')
    else:
        artifact_id = f'unverified_{artifact_kind}'
        artifact_name = names[artifact_kind]
        reason_code = 'no_exact_build_record'
        explanation = explanations[artifact_kind]
    return CompatibilityRecord(
        observation.game_id, observation.platform, observation.app_id, observation.build_id, artifact_kind,
        artifact_id, artifact_name, None, 'unknown', reason_code, explanation, (), observation.observed_at,
        ('evidence', 'troubleshooting'))


def compatibility_for(observation, records=None):
    """Return latest exact matches and explicit unknown rows for missing coverage.

    Categories with named exact records also get an unknown row for other
    artifacts because the catalog does not claim to be a complete inventory.
    """
    if not isinstance(observation, BuildObservation):
        raise ValueError('Choose a validated installed build observation.')
    records = load_catalog() if records is None else _validated_records(records)
    matching = (item for item in records if item.game_id == observation.game_id
                and item.platform == observation.platform
                and item.app_id == observation.app_id
                and observation.build_id is not None and item.build_id == observation.build_id)
    latest_by_artifact = {}
    for item in matching:
        key = (item.artifact_kind, item.artifact_id)
        current = latest_by_artifact.get(key)
        if current is None or _timestamp_order(item.checked_at) > _timestamp_order(current.checked_at):
            latest_by_artifact[key] = item
    exact = tuple(latest_by_artifact.values())
    present = {item.artifact_kind for item in exact}
    fallback = tuple(_unknown_record(observation, kind, unlisted=kind in present)
                     for kind in ARTIFACT_KINDS)
    return tuple(sorted(exact + fallback, key=lambda item: (ARTIFACT_KINDS.index(item.artifact_kind),
                                                            item.artifact_name.casefold(), item.artifact_id)))


def compatibility_history(game_id, artifact_kind=None, artifact_id=None, records=None, app_id=None):
    """Return reviewed catalog history for a game/app/tool, oldest check first."""
    if type(game_id) is not str or game_id not in _GAMES:
        raise ValueError('Choose a registered game profile.')
    if app_id is not None and not _valid_steam_profile(game_id, _GAMES[game_id].platform, app_id):
        raise ValueError('Choose a reviewed Steam app mapping for this game profile.')
    if artifact_kind is not None and (type(artifact_kind) is not str or artifact_kind not in ARTIFACT_KINDS):
        raise ValueError('Choose a supported compatibility artifact kind.')
    if artifact_id is not None and (type(artifact_id) is not str or _ARTIFACT_ID.fullmatch(artifact_id) is None):
        raise ValueError('Choose a valid compatibility artifact ID.')
    records = load_catalog() if records is None else _validated_records(records)
    matches = [item for item in records if item.game_id == game_id
               and (app_id is None or item.app_id == app_id)
               and (artifact_kind is None or item.artifact_kind == artifact_kind)
               and (artifact_id is None or item.artifact_id == artifact_id)]
    return tuple(sorted(matches, key=lambda item: (_timestamp_order(item.checked_at), item.build_id,
                                                    item.artifact_kind, item.artifact_id)))


def _validate_history_event(value):
    fields = {'event_kind', 'game_id', 'platform', 'app_id', 'previous_build_id', 'build_id',
              'last_updated', 'observed_at', 'source', 'confidence'}
    if type(value) is not dict or set(value) != fields:
        raise ValueError('Build history event has unexpected fields.')
    if type(value['event_kind']) is not str or value['event_kind'] not in ('first_seen', 'build_changed'):
        raise ValueError('Build history event kind is unsupported.')
    if not _valid_steam_profile(value['game_id'], value['platform'], value['app_id']):
        raise ValueError('Build history event names an unreviewed game/platform/app mapping.')
    if not _valid_build_id(value['previous_build_id'], optional=True):
        raise ValueError('Build history event has an invalid previous build ID.')
    if not _valid_build_id(value['build_id'], optional=True):
        raise ValueError('Build history event has an invalid build ID.')
    if not ((value['last_updated'] is None) or
            (type(value['last_updated']) is str and _LAST_UPDATED.fullmatch(value['last_updated']) is not None)):
        raise ValueError('Build history event has an invalid update marker.')
    if not _timestamp(value['observed_at']):
        raise ValueError('Build history event time must include a timezone.')
    if value['event_kind'] == 'first_seen' and value['previous_build_id'] is not None:
        raise ValueError('First-seen history cannot contain a previous build.')
    if value['build_id'] is None:
        raise ValueError('Build history events require a valid Steam build ID.')
    if value['event_kind'] == 'build_changed' and (value['previous_build_id'] is None
                                                   or value['previous_build_id'] == value['build_id']):
        raise ValueError('Build-change history must identify a changed build marker.')
    if value['source'] != 'steam_manifest' or value['confidence'] != 'installation_metadata':
        raise ValueError('Build history has an unsupported observation source.')
    return BuildHistoryEvent(**value)


def load_history(path=None):
    """Load bounded path-free local history; missing files are an empty history.

    Invalid data raises ``ValueError`` so a later scan never overwrites an
    unreadable or unsupported local history file.
    """
    selected = Path(path) if path is not None else tracker_history_path()
    try:
        with selected.open('rb') as stream:
            raw = stream.read(MAX_HISTORY_BYTES + 1)
    except FileNotFoundError:
        return ()
    except OSError as exc:
        raise ValueError('Local build history could not be read.') from exc
    if len(raw) > MAX_HISTORY_BYTES:
        raise ValueError('Local build history exceeds its fixed byte limit.')
    value = _decode(raw, 'Local build history')
    if (type(value) is not dict or set(value) != {'schema_version', 'events'}
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or type(value['events']) is not list or len(value['events']) > MAX_HISTORY_EVENTS):
        raise ValueError('Local build history schema is unsupported.')
    events = tuple(_validate_history_event(item) for item in value['events'])
    seen_events = set()
    latest = {}
    for event in events:
        identity = (event.game_id, event.app_id)
        event_key = (identity, event.event_kind, event.previous_build_id, event.build_id, event.observed_at)
        if event_key in seen_events:
            raise ValueError('Local build history contains duplicate events.')
        seen_events.add(event_key)
        previous = latest.get(identity)
        if previous is None:
            if event.event_kind != 'first_seen':
                raise ValueError('Local build history begins without a first-seen event.')
        elif (event.event_kind != 'build_changed'
              or event.previous_build_id != previous.build_id):
            raise ValueError('Local build history contains a broken build transition.')
        latest[identity] = event
    return events


def _write_history(path, events):
    payload = {'schema_version': 1, 'events': [event.__dict__ for event in events]}
    raw = (json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
    if len(raw) > MAX_HISTORY_BYTES:
        raise ValueError('Local build history exceeds its fixed byte limit.')
    destination = Path(path)
    try:
        if destination.exists() or destination.is_symlink():
            info = destination.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
                raise ValueError('Local build history destination is not an ordinary file.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile('wb', dir=destination.parent,
                                             prefix='.version-tracker.', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    except OSError as exc:
        raise ValueError('Local build history could not be saved.') from exc


def record_scan(observations, path=None, observed_at=None):
    """Append first-seen/build-change events and return the newly recorded rows.

    Repeated scans of the same Steam build do not add history. A build change
    prompts review of exact-build entries without inferring current status.
    """
    if type(observations) not in (tuple, list) or len(observations) > 500:
        raise ValueError('Installed-build observations exceed their fixed limit.')
    checked = tuple(observations)
    if any(not isinstance(item, BuildObservation) for item in checked):
        raise ValueError('Build history accepts only validated observations.')
    identities = [(item.game_id, item.app_id) for item in checked]
    if len(set(identities)) != len(identities):
        raise ValueError('Build scan contains duplicate game/app identities.')
    if observed_at is not None and not _timestamp(observed_at):
        raise ValueError('Scan time must include a timezone.')
    target = Path(path) if path is not None else tracker_history_path()
    history = list(load_history(target))
    last_by_identity = {}
    for event in history:
        last_by_identity[(event.game_id, event.app_id)] = event
    added = []
    for observation in checked:
        # A missing marker is not evidence of an update. Keep the last known
        # marker unchanged and let the current observation explain the gap.
        if observation.build_id is None:
            continue
        previous = last_by_identity.get((observation.game_id, observation.app_id))
        if previous is None:
            kind = 'first_seen'
            previous_build = None
        elif previous.build_id != observation.build_id:
            kind = 'build_changed'
            previous_build = previous.build_id
        else:
            continue
        event = BuildHistoryEvent(
            kind, observation.game_id, observation.platform, observation.app_id, previous_build,
            observation.build_id, observation.last_updated,
            observed_at if observed_at is not None else observation.observed_at,
            observation.source, observation.confidence)
        added.append(event)
        last_by_identity[(observation.game_id, observation.app_id)] = event
    if added:
        if len(history) + len(added) > MAX_HISTORY_EVENTS:
            raise ValueError('Local build history reached its fixed event limit; no events were discarded.')
        history.extend(added)
        _write_history(target, history)
    return tuple(added)
