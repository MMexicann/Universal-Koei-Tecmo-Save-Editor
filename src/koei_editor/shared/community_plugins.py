"""Opt-in, data-only community contributions. This is not a Python sandbox.

Discovery only reads bounded JSON snapshots. Approval binds the exact snapshot
and its capabilities for this catalog's lifetime; no plugin code is imported.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import unicodedata


API_VERSION = '1'
MAX_MANIFEST_BYTES = 128 * 1024
MAX_PLUGINS = 64
MAX_DIRECTORY_ENTRIES = 512
CAPABILITIES = frozenset({'help', 'workflows', 'commands'})
_ID = re.compile(r'[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*\Z')
_GAME_ID = re.compile(r'[a-z][a-z0-9_]{0,63}\Z')
_VERSION = re.compile(r'[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}\Z')


class PluginError(ValueError):
    """A manifest or approval failed a bounded, declarative policy check."""


@dataclass(frozen=True)
class Contribution:
    id: str
    kind: str
    title: str
    locale: str
    game_ids: tuple[str, ...] = ()
    body: str = ''
    platforms: tuple[str, ...] = ()
    steps: tuple[str, ...] = ()
    target: str = ''


@dataclass(frozen=True)
class PluginManifest:
    id: str
    title: str
    version: str
    author: str
    description: str
    api: str
    capabilities: tuple[str, ...]
    contributions: tuple[Contribution, ...]


@dataclass(frozen=True)
class PluginCandidate:
    filename: str
    sha256: str
    manifest: PluginManifest | None
    error: str = ''


@dataclass(frozen=True)
class PluginEntry:
    candidate: PluginCandidate
    enabled: bool
    error: str = ''


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PluginError('Duplicate JSON properties are not allowed.')
        result[key] = value
    return result


def _constant(_value):
    raise PluginError('Nonfinite JSON numbers are not allowed.')


def _keys(value, required):
    if type(value) is not dict or set(value) != set(required.split()):
        raise PluginError('Missing or unsupported manifest properties.')


def _text(value, limit=160, *, multiline=False):
    if type(value) is not str or not value.strip() or len(value) > limit:
        raise PluginError('Text must be nonempty and within its length limit.')
    # Avoid invisible directional overrides, embedded NULs and control injection.
    if any(unicodedata.category(char).startswith('C') and not (multiline and char in '\n\t')
           for char in value):
        raise PluginError('Text contains unsupported control characters.')
    return value


def _identity(value):
    if type(value) is not str or len(value) > 80 or not _ID.fullmatch(value):
        raise PluginError('IDs must use stable lowercase dotted, dashed or underscored names.')
    return value


def _list(value, maximum):
    if type(value) is not list or len(value) > maximum:
        raise PluginError('Expected a bounded list.')
    return value


def validate_manifest(raw, *, known_game_ids=()):
    """Validate UTF-8 JSON bytes; references may name only host-registered games.

    Unknown keys (including entry points, code, URLs and file paths) fail closed.
    Inline text is inert and must be rendered as plain text by the host.
    """
    if type(raw) is not bytes or len(raw) > MAX_MANIFEST_BYTES:
        raise PluginError('Manifest exceeds the byte limit or is not bytes.')
    try:
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_object, parse_constant=_constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise PluginError('Manifest must be bounded, unique-key UTF-8 JSON.') from error
    _keys(data, 'schema api id title version author description capabilities contributions')
    if type(data['schema']) is not int or data['schema'] != 1 or data['api'] != API_VERSION:
        raise PluginError('Manifest schema/API is incompatible with this host.')
    plugin_id = _identity(data['id'])
    if '.' not in plugin_id:
        raise PluginError('Plugin IDs require a community namespace, such as community.example.')
    if type(data['version']) is not str or not _VERSION.fullmatch(data['version']):
        raise PluginError('Plugin version must have numeric major.minor.patch components.')
    capabilities = tuple(_list(data['capabilities'], len(CAPABILITIES)))
    if (any(type(item) is not str or item not in CAPABILITIES for item in capabilities)
            or len(set(capabilities)) != len(capabilities)):
        raise PluginError('Unknown or duplicate plugin capabilities.')
    contributions = []
    identities = set()
    games = frozenset(known_game_ids)
    for item in _list(data['contributions'], 64):
        if type(item) is not dict or type(item.get('kind')) is not str:
            raise PluginError('Contributions require an explicit kind.')
        kind = item['kind']
        common = 'kind id title locale game_ids '
        if kind == 'help':
            _keys(item, common + 'body')
        elif kind == 'workflows':
            _keys(item, common + 'platforms steps')
        elif kind == 'commands':
            _keys(item, common + 'target')
        else:
            raise PluginError('Unsupported contribution kind.')
        local_id = _identity(item['id'])
        identity = plugin_id + ':' + local_id
        if identity in identities:
            raise PluginError('Contribution IDs must be unique across every kind and locale.')
        identities.add(identity)
        if item['locale'] not in ('en', 'de'):
            raise PluginError('Contributions currently support English or German.')
        game_ids = tuple(_list(item['game_ids'], 32))
        if (any(type(game) is not str or not _GAME_ID.fullmatch(game) or game not in games
                for game in game_ids) or len(set(game_ids)) != len(game_ids)):
            raise PluginError('Game references must be unique host-registered game IDs.')
        body, platforms, steps, target = '', (), (), ''
        if kind == 'help':
            body = _text(item['body'], 8192, multiline=True)
        elif kind == 'workflows':
            platforms = tuple(_text(platform, 80) for platform in _list(item['platforms'], 12))
            steps = tuple(_text(step, 2048, multiline=True) for step in _list(item['steps'], 24))
            if not platforms or not steps or len(set(platforms)) != len(platforms):
                raise PluginError('Workflows need unique platforms and at least one step.')
        else:
            target = plugin_id + ':' + _identity(item['target'])
        contributions.append(Contribution(identity, kind, _text(item['title']), item['locale'],
                                          game_ids, body, platforms, steps, target))
    if not contributions or set(capabilities) != {item.kind for item in contributions}:
        raise PluginError('Capabilities must exactly describe nonempty contributions.')
    targets = {item.id: item for item in contributions}
    for item in contributions:
        if item.kind == 'commands':
            target = targets.get(item.target)
            if target is None or target.kind not in ('help', 'workflows'):
                raise PluginError('Commands can only open their own declared help or workflow.')
            if target.locale != item.locale or target.game_ids != item.game_ids:
                raise PluginError('Command locale/game scope must match its target.')
    return PluginManifest(plugin_id, _text(data['title']), data['version'],
                          _text(data['author']), _text(data['description'], 1000, multiline=True),
                          API_VERSION, tuple(sorted(capabilities)), tuple(contributions))


def discover_plugins(directory, *, known_game_ids=()):
    """Read one user-selected directory, without recursion or executing anything.

    Symlinks and nonregular files are rejected. Invalid manifests remain visible
    as candidates with safe generic errors. Oversized directories fail as a unit.
    """
    paths = []
    known_game_ids = tuple(known_game_ids)
    try:
        with os.scandir(directory) as entries:
            for count, entry in enumerate(entries, 1):
                if count > MAX_DIRECTORY_ENTRIES:
                    raise PluginError('Selected directory contains too many entries.')
                if entry.name.endswith('.plugin.json'):
                    paths.append(Path(entry.path))
                    if len(paths) > MAX_PLUGINS:
                        raise PluginError('Selected directory contains too many plugin manifests.')
    except OSError as error:
        raise PluginError('The selected plugin directory is unavailable.') from error
    candidates = []
    for path in sorted(paths, key=lambda item: item.name):
        digest = ''
        try:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or len(path.name) > 180:
                raise PluginError('Plugin manifests must be regular files with bounded names.')
            descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                                 | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_BINARY', 0))
            with os.fdopen(descriptor, 'rb') as stream:
                opened = os.fstat(stream.fileno())
                if not stat.S_ISREG(opened.st_mode) or (info.st_dev, info.st_ino) != (opened.st_dev, opened.st_ino):
                    raise PluginError('Plugin manifest changed during discovery.')
                raw = stream.read(MAX_MANIFEST_BYTES + 1)
            digest = hashlib.sha256(raw).hexdigest()
            manifest = validate_manifest(raw, known_game_ids=known_game_ids)
            candidates.append(PluginCandidate(path.name, digest, manifest))
        except (OSError, PluginError) as error:
            message = str(error) if isinstance(error, PluginError) else 'Plugin manifest is unavailable.'
            candidates.append(PluginCandidate(path.name[:180], digest, None, message))
    return tuple(candidates)


class PluginCatalog:
    """Session-only approval and conflict guards for immutable discovery results."""

    def __init__(self, candidates=(), *, reserved_ids=()):
        self._candidates = tuple(candidates)
        if len(self._candidates) > MAX_PLUGINS or any(type(item) is not PluginCandidate for item in self._candidates):
            raise PluginError('Catalog requires bounded discovery candidates.')
        self._enabled = set()
        self._errors = {}
        seen = {}
        reserved = set(reserved_ids)
        for index, candidate in enumerate(self._candidates):
            if candidate.manifest is None:
                self._errors[index] = candidate.error or 'Manifest is invalid.'
                continue
            identities = (candidate.manifest.id,) + tuple(item.id for item in candidate.manifest.contributions)
            for identity in identities:
                if identity in reserved:
                    self._errors[index] = 'Registration conflicts with a host identity.'
                if identity in seen:
                    self._errors[index] = 'Duplicate plugin or contribution identity.'
                    self._errors[seen[identity]] = 'Duplicate plugin or contribution identity.'
                seen[identity] = index

    @property
    def entries(self):
        return tuple(PluginEntry(item, index in self._enabled, self._errors.get(index, ''))
                     for index, item in enumerate(self._candidates))

    def approve(self, plugin_id, *, sha256, capabilities):
        """Enable a previewed exact snapshot and its explicitly approved capabilities."""
        matches = [(index, item) for index, item in enumerate(self._candidates)
                   if item.manifest is not None and item.manifest.id == plugin_id]
        if len(matches) != 1 or matches[0][0] in self._errors:
            raise PluginError('Plugin is missing, invalid or has an identity conflict.')
        index, candidate = matches[0]
        if sha256 != candidate.sha256 or not re.fullmatch('[0-9a-f]{64}', sha256):
            raise PluginError('Approval requires the exact previewed manifest SHA-256.')
        if (type(capabilities) not in (tuple, list, set, frozenset)
                or any(type(item) is not str for item in capabilities)
                or len(capabilities) != len(candidate.manifest.capabilities)
                or set(capabilities) != set(candidate.manifest.capabilities)):
            raise PluginError('Approval requires every exact declared capability.')
        self._enabled.add(index)

    def disable(self, plugin_id):
        for index, candidate in enumerate(self._candidates):
            if candidate.manifest is not None and candidate.manifest.id == plugin_id:
                self._enabled.discard(index)

    def contributions(self, kind=None):
        return tuple(item for index, candidate in enumerate(self._candidates) if index in self._enabled
                     for item in candidate.manifest.contributions if kind is None or item.kind == kind)

    def search(self, query='', *, kind=None, locale=None):
        if type(query) is not str or len(query) > 256:
            raise PluginError('Search requires a bounded text query.')
        terms = query.casefold().split()
        result = []
        for item in self.contributions(kind):
            if locale is not None and item.locale != locale:
                continue
            searchable = ' '.join((item.title, item.body, *item.steps, *item.platforms, *item.game_ids)).casefold()
            if all(term in searchable for term in terms):
                result.append(item)
        return tuple(result)

    def resolve_command(self, command_id):
        """Return inert help/workflow content; the host chooses how to display it."""
        items = {item.id: item for item in self.contributions()}
        command = items.get(command_id)
        if command is None or command.kind != 'commands':
            raise PluginError('Command is unavailable or disabled.')
        return items[command.target]
