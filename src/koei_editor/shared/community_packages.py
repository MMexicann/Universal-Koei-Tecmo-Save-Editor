"""Strict, data-only Koei Tecmo community sharing packages.

This module validates portable descriptions. It never loads code, applies a
configuration, opens a mod URL, reads a game save, or contacts a remote service.
Package documents contain declarative metadata only; host features must perform
their own allowlist checks before offering any import or apply action.
"""
from collections.abc import Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat
import unicodedata
from urllib.parse import urlsplit
from types import MappingProxyType

from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.save_safety import safe_path


SCHEMA = 'koei-tecmo-community-package'
SCHEMA_VERSION = 1
MAX_BYTES = 1024 * 1024
MAX_ITEMS = 256
SUFFIX = '.koei-community.json'

MAX_ID_LENGTH = 128
MAX_KEY_LENGTH = 128
MAX_TITLE_LENGTH = 160
MAX_AUTHOR_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 1000
MAX_DETAIL_LENGTH = 2048
MAX_VALUE_TEXT_LENGTH = 1024
MAX_VERSION_LENGTH = 80
MAX_URL_LENGTH = 2048
MAX_DOCUMENT_NODES = 70_000
MAX_INTEGER = (1 << 64) - 1
MIN_INTEGER = -(1 << 63)

KINDS = frozenset((
    'character_build', 'mod_list', 'configuration_preset',
    'playthrough_manifest', 'compatibility_report',
))
_STATUSES = frozenset(('planned', 'active', 'complete', 'skipped'))
_COMPATIBILITY_STATUSES = frozenset(('compatible', 'incompatible', 'unknown'))
_ID = re.compile(r'[a-z0-9]+(?:[._-][a-z0-9]+)*\Z')
_GAME_ID = re.compile(r'[a-z][a-z0-9_]{0,63}\Z')
_HASH = re.compile(r'[0-9a-f]{64}\Z')
_TOP_LEVEL_KEYS = frozenset((
    'schema', 'version', 'kind', 'id', 'title', 'author', 'game_id',
    'platform', 'game_version', 'description', 'payload',
))


class CommunityPackageError(ValueError):
    """A package is malformed, unsupported, unsafe to read, or not writable."""


@dataclass(frozen=True)
class CommunityPackage:
    """A validated community package with a recursively immutable payload."""

    kind: str
    id: str
    title: str
    author: str
    game_id: str
    platform: str
    game_version: str | None
    description: str
    payload: Mapping[str, object]


def _fail(message):
    raise CommunityPackageError(message)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail('Community package JSON contains a duplicate property name.')
        result[key] = value
    return result


def _invalid_number(_value):
    _fail('Community package numbers must be whole integers or declared scalar values.')


def _keys(value, expected, label):
    if type(value) is not dict or set(value) != set(expected):
        _fail(f'Community package {label} has missing or unknown properties.')


def _text(value, label, maximum, *, multiline=False):
    if type(value) is not str or not value.strip() or len(value) > maximum:
        _fail(f'Community package {label} must be nonempty text within its length limit.')
    for character in value:
        category = unicodedata.category(character)
        if category.startswith('C') or (not multiline and category in ('Zl', 'Zp')):
            _fail(f'Community package {label} contains unsupported control or invisible characters.')
    return value


def _identity(value, label='ID', maximum=MAX_ID_LENGTH):
    if (type(value) is not str or len(value) > maximum
            or not _ID.fullmatch(value)):
        _fail(f'Community package {label} must use lowercase ASCII letters, digits, dots, dashes or underscores.')
    return value


def _integer(value, label, minimum=0, maximum=MAX_INTEGER):
    if type(value) is not int or not minimum <= value <= maximum:
        _fail(f'Community package {label} must be a whole number within its supported range.')
    return value


def _scalar(value, label):
    if type(value) is bool:
        return value
    if type(value) is int:
        return _integer(value, label, MIN_INTEGER, MAX_INTEGER)
    if type(value) is str:
        return _text(value, label, MAX_VALUE_TEXT_LENGTH)
    _fail(f'Community package {label} must be a string, whole number or boolean.')


def _list(value, label, *, allow_empty=False):
    if type(value) is not list or len(value) > MAX_ITEMS or (not allow_empty and not value):
        minimum = 'zero or' if allow_empty else 'one to'
        _fail(f'Community package {label} must contain {minimum} {MAX_ITEMS} items.')
    return value


def _optional_text(value, label, maximum):
    if value is None:
        return None
    return _text(value, label, maximum)


def _url(value):
    if value is None:
        return None
    value = _text(value, 'mod source URL', MAX_URL_LENGTH)
    if not value.startswith('https://'):
        _fail('Mod source URLs must use lowercase HTTPS and cannot contain credentials or whitespace.')
    try:
        parsed = urlsplit(value)
        # Touch .port as it validates malformed numeric ports.
        _port = parsed.port
        hostname = parsed.hostname
    except ValueError as error:
        raise CommunityPackageError('Mod source URLs must be ordinary HTTPS URLs.') from error
    if (parsed.scheme != 'https' or not hostname or parsed.username is not None
            or parsed.password is not None or any(character.isspace() for character in value)):
        _fail('Mod source URLs must use HTTPS and cannot contain credentials or whitespace.')
    return value


def _validate_character_build(payload):
    _keys(payload, ('character_id', 'level', 'stats', 'skills', 'equipment'), 'character build payload')
    _identity(payload['character_id'], 'character ID')
    if payload['level'] is not None:
        _integer(payload['level'], 'character level', 1, 9999)

    stats = _list(payload['stats'], 'character stats', allow_empty=True)
    seen_stats = set()
    for item in stats:
        _keys(item, ('key', 'value'), 'character stat')
        key = _identity(item['key'], 'stat key', MAX_KEY_LENGTH)
        if key in seen_stats:
            _fail('Character stat keys must be unique.')
        seen_stats.add(key)
        _scalar(item['value'], 'stat value')

    skills = _list(payload['skills'], 'character skills', allow_empty=True)
    seen_skills = set()
    for item in skills:
        _keys(item, ('id', 'rank'), 'character skill')
        identity = _identity(item['id'], 'skill ID')
        if identity in seen_skills:
            _fail('Character skill IDs must be unique.')
        seen_skills.add(identity)
        _integer(item['rank'], 'skill rank', 0, 9999)

    equipment = _list(payload['equipment'], 'character equipment', allow_empty=True)
    seen_slots = set()
    for item in equipment:
        _keys(item, ('slot', 'id'), 'character equipment item')
        slot = _identity(item['slot'], 'equipment slot', MAX_KEY_LENGTH)
        _identity(item['id'], 'equipment ID')
        if slot in seen_slots:
            _fail('Character equipment slots must be unique.')
        seen_slots.add(slot)

    if payload['level'] is None and not stats and not skills and not equipment:
        _fail('A character build must contain a level, stat, skill or equipment value.')


def _validate_mod_list(payload):
    _keys(payload, ('mods', 'load_order'), 'mod list payload')
    mods = _list(payload['mods'], 'mod list')
    identities = set()
    enabled = set()
    for item in mods:
        _keys(item, ('id', 'title', 'version', 'source_url', 'sha256', 'enabled'), 'mod entry')
        identity = _identity(item['id'], 'mod ID')
        if identity in identities:
            _fail('Mod IDs must be unique.')
        identities.add(identity)
        _text(item['title'], 'mod title', MAX_TITLE_LENGTH)
        _optional_text(item['version'], 'mod version', MAX_VERSION_LENGTH)
        _url(item['source_url'])
        digest = item['sha256']
        if digest is not None and (type(digest) is not str or not _HASH.fullmatch(digest)):
            _fail('A mod hash must be a lowercase SHA-256 digest or null.')
        if type(item['enabled']) is not bool:
            _fail('Each mod must have an explicit enabled boolean.')
        if item['enabled']:
            enabled.add(identity)

    order = _list(payload['load_order'], 'mod load order', allow_empty=True)
    seen = set()
    for identity in order:
        _identity(identity, 'load-order mod ID')
        if identity in seen:
            _fail('Mod load order must not repeat an ID.')
        if identity not in enabled:
            _fail('Mod load order may include enabled mods only.')
        seen.add(identity)
    if seen != enabled:
        _fail('Mod load order must list every enabled mod exactly once.')


def _validate_configuration_preset(payload):
    _keys(payload, ('settings',), 'configuration preset payload')
    settings = _list(payload['settings'], 'configuration settings')
    seen = set()
    for item in settings:
        _keys(item, ('key', 'value'), 'configuration setting')
        key = _identity(item['key'], 'configuration key', MAX_KEY_LENGTH)
        if key in seen:
            _fail('Configuration setting keys must be unique.')
        seen.add(key)
        _scalar(item['value'], 'configuration value')


def _validate_playthrough_manifest(payload):
    _keys(payload, ('objectives',), 'playthrough manifest payload')
    objectives = _list(payload['objectives'], 'playthrough objectives')
    by_id = {}
    orders = set()
    dependencies = {}
    for item in objectives:
        _keys(item, ('id', 'title', 'status', 'order', 'depends_on'), 'playthrough objective')
        identity = _identity(item['id'], 'objective ID')
        if identity in by_id:
            _fail('Playthrough objective IDs must be unique.')
        _text(item['title'], 'objective title', MAX_TITLE_LENGTH)
        if type(item['status']) is not str or item['status'] not in _STATUSES:
            _fail('Playthrough objective status is unsupported.')
        order = _integer(item['order'], 'objective order', 0, 100_000)
        if order in orders:
            _fail('Playthrough objective order values must be unique.')
        orders.add(order)
        prerequisite_ids = _list(item['depends_on'], 'objective dependencies', allow_empty=True)
        clean_dependencies = []
        dependency_set = set()
        for dependency in prerequisite_ids:
            dependency = _identity(dependency, 'objective dependency ID')
            if dependency == identity or dependency in dependency_set:
                _fail('An objective cannot depend on itself or repeat a dependency.')
            dependency_set.add(dependency)
            clean_dependencies.append(dependency)
        by_id[identity] = item
        dependencies[identity] = tuple(clean_dependencies)

    if any(dependency not in by_id for values in dependencies.values() for dependency in values):
        _fail('Playthrough objective dependencies must refer to objectives in this manifest.')

    # A bounded iterative DFS rejects dependency cycles without recursion.
    completed = set()
    for start in by_id:
        if start in completed:
            continue
        active = set()
        stack = [(start, False)]
        while stack:
            identity, exiting = stack.pop()
            if exiting:
                active.remove(identity)
                completed.add(identity)
                continue
            if identity in completed:
                continue
            if identity in active:
                _fail('Playthrough objective dependencies must not contain a cycle.')
            active.add(identity)
            stack.append((identity, True))
            for dependency in dependencies[identity]:
                if dependency not in completed:
                    if dependency in active:
                        _fail('Playthrough objective dependencies must not contain a cycle.')
                    stack.append((dependency, False))


def _validate_compatibility_report(payload):
    _keys(payload, ('entries',), 'compatibility report payload')
    entries = _list(payload['entries'], 'compatibility report entries')
    seen = set()
    for item in entries:
        _keys(item, ('component', 'version', 'status', 'details'), 'compatibility report entry')
        component = _identity(item['component'], 'compatibility component ID')
        version = _optional_text(item['version'], 'component version', MAX_VERSION_LENGTH)
        if type(item['status']) is not str or item['status'] not in _COMPATIBILITY_STATUSES:
            _fail('Compatibility status must be compatible, incompatible or unknown.')
        _text(item['details'], 'compatibility details', MAX_DETAIL_LENGTH)
        identity = component, version
        if identity in seen:
            _fail('Compatibility report component/version pairs must be unique.')
        seen.add(identity)


def _validate_document(data):
    _keys(data, _TOP_LEVEL_KEYS, 'document')
    if type(data['schema']) is not str or data['schema'] != SCHEMA:
        _fail('This document is not a supported Koei Tecmo community package.')
    if type(data['version']) is not int or data['version'] != SCHEMA_VERSION:
        _fail('This Koei Tecmo community package version is not supported.')
    kind = data['kind']
    if type(kind) is not str or kind not in KINDS:
        _fail('Community package kind is unsupported.')
    _identity(data['id'], 'package ID')
    _text(data['title'], 'title', MAX_TITLE_LENGTH)
    _text(data['author'], 'author', MAX_AUTHOR_LENGTH)
    if type(data['game_id']) is not str or not _GAME_ID.fullmatch(data['game_id']):
        _fail('Community package game ID must use a bounded lowercase profile identifier.')
    _identity(data['platform'], 'platform ID', 64)
    _optional_text(data['game_version'], 'game version', MAX_VERSION_LENGTH)
    _text(data['description'], 'description', MAX_DESCRIPTION_LENGTH)
    if type(data['payload']) is not dict:
        _fail('Community package payload must be an object.')
    validators = {
        'character_build': _validate_character_build,
        'mod_list': _validate_mod_list,
        'configuration_preset': _validate_configuration_preset,
        'playthrough_manifest': _validate_playthrough_manifest,
        'compatibility_report': _validate_compatibility_report,
    }
    validators[kind](data['payload'])
    return data


def _check_node_budget(value):
    """Bound containers and total decoded values before validation/freezing."""
    pending = [value]
    count = 0
    while pending:
        item = pending.pop()
        count += 1
        if count > MAX_DOCUMENT_NODES:
            _fail('Community package exceeds the supported total item limit.')
        if type(item) is dict:
            if len(item) > MAX_ITEMS:
                _fail('Community package object exceeds the supported item limit.')
            pending.extend(item.values())
        elif type(item) is list:
            if len(item) > MAX_ITEMS:
                _fail('Community package list exceeds the supported item limit.')
            pending.extend(item)


def _freeze(value):
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value, *, depth=0, active=None, budget=None):
    if depth > 16:
        _fail('Community package object exceeds the supported nesting depth.')
    if active is None:
        active = set()
    if budget is None:
        budget = [0]
    budget[0] += 1
    if budget[0] > MAX_DOCUMENT_NODES:
        _fail('Community package object exceeds the supported item limit.')
    if type(value) in (dict, MappingProxyType):
        if len(value) > MAX_ITEMS:
            _fail('Community package object exceeds the supported item limit.')
        identity = id(value)
        if identity in active:
            _fail('Community package object cannot contain a cycle.')
        active.add(identity)
        try:
            return {key: _thaw(item, depth=depth + 1, active=active, budget=budget)
                    for key, item in value.items()}
        finally:
            active.remove(identity)
    if type(value) in (list, tuple):
        if len(value) > MAX_ITEMS:
            _fail('Community package object exceeds the supported item limit.')
        identity = id(value)
        if identity in active:
            _fail('Community package object cannot contain a cycle.')
        active.add(identity)
        try:
            return [_thaw(item, depth=depth + 1, active=active, budget=budget) for item in value]
        finally:
            active.remove(identity)
    return value


def _document(package):
    if type(package) is not CommunityPackage:
        _fail('Choose a validated CommunityPackage value to export.')
    return {
        'schema': SCHEMA,
        'version': SCHEMA_VERSION,
        'kind': package.kind,
        'id': package.id,
        'title': package.title,
        'author': package.author,
        'game_id': package.game_id,
        'platform': package.platform,
        'game_version': package.game_version,
        'description': package.description,
        'payload': _thaw(package.payload),
    }


def loads(raw):
    """Parse bounded UTF-8 package bytes with strict, versioned validation."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        _fail(f'Choose a nonempty community package no larger than {MAX_BYTES // 1024} KiB.')
    try:
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                          parse_constant=_invalid_number, parse_float=_invalid_number)
    except CommunityPackageError:
        raise
    except (ValueError, UnicodeError, RecursionError) as error:
        raise CommunityPackageError('The community package is not valid UTF-8 JSON.') from error
    _check_node_budget(data)
    _validate_document(data)
    return CommunityPackage(
        kind=data['kind'], id=data['id'], title=data['title'], author=data['author'],
        game_id=data['game_id'], platform=data['platform'], game_version=data['game_version'],
        description=data['description'], payload=_freeze(data['payload']),
    )


def dumps(package):
    """Validate and serialize a package as stable UTF-8 JSON bytes."""
    data = _document(package)
    _validate_document(data)
    try:
        raw = (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    except (TypeError, ValueError, UnicodeError) as error:
        raise CommunityPackageError('The community package cannot be serialized as UTF-8 JSON.') from error
    if not 0 < len(raw) <= MAX_BYTES:
        _fail(f'The community package exceeds the {MAX_BYTES // 1024} KiB size limit.')
    return raw


def _ordinary(info):
    return (stat.S_ISREG(info.st_mode) and info.st_nlink == 1
            and not getattr(info, 'st_file_attributes', 0)
            & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))


def _token(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_nlink, getattr(info, 'st_file_attributes', 0))


def _read_bytes(path):
    """Read an ordinary bounded file and detect path/file replacement races."""
    try:
        selected = Path(path)
        before = selected.lstat()
        if not _ordinary(before) or not 0 < before.st_size <= MAX_BYTES:
            _fail('Choose a bounded ordinary community package file.')
        # Reject protected/live paths and canonicalize only after lstat rejected
        # symlinks, so safe_path cannot silently follow a selected symlink.
        canonical = safe_path(selected)
        flags = (os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
                 | getattr(os, 'O_NONBLOCK', 0))
        descriptor = os.open(selected, flags)
        try:
            opened = os.fstat(descriptor)
            if not _ordinary(opened) or _token(opened)[:-1] != _token(before)[:-1]:
                _fail('The community package changed before it could be read.')
            chunks = []
            remaining = MAX_BYTES + 1
            while remaining:
                block = os.read(descriptor, min(65536, remaining))
                if not block:
                    break
                chunks.append(block)
                remaining -= len(block)
            after_open = os.fstat(descriptor)
            after_path = selected.lstat()
            if (_token(after_open) != _token(opened) or _token(after_path) != _token(before)
                    or canonical != safe_path(selected)):
                _fail('The community package changed while it was being read.')
            raw = b''.join(chunks)
            if len(raw) != opened.st_size or len(raw) > MAX_BYTES:
                _fail('The community package changed size while it was being read.')
            return raw
        finally:
            os.close(descriptor)
    except CommunityPackageError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise CommunityPackageError('The selected community package file is unavailable or unsafe.') from error


def load(path):
    """Read one selected regular package file without following symlinks."""
    try:
        name = Path(path).name
    except (TypeError, ValueError) as error:
        raise CommunityPackageError('Choose a community package file.') from error
    if not name.casefold().endswith(SUFFIX):
        _fail(f'Choose a {SUFFIX} community package file.')
    return loads(_read_bytes(path))


def destination_path(path):
    """Append the dedicated package suffix and reject unsafe save paths."""
    try:
        destination = Path(path)
    except (TypeError, ValueError) as error:
        raise CommunityPackageError('Choose a new community package destination.') from error
    name = destination.name
    if not name.casefold().endswith(SUFFIX):
        if name.casefold().endswith('.json'):
            name = name[:-5]
        destination = destination.with_name(name + SUFFIX)
    try:
        return safe_path(destination)
    except (OSError, ValueError) as error:
        raise CommunityPackageError('Choose a safe new community package destination.') from error


def export(package, path):
    """Write and verify one new package file; existing destinations are retained."""
    raw = dumps(package)
    destination = destination_path(path)
    try:
        created = atomic_new(raw, destination)
        if _read_bytes(created) != raw:
            _fail('Export verification failed. The completed file was retained; do not use it.')
        return created
    except CommunityPackageError:
        raise
    except FileExistsError:
        raise
    except (OSError, ValueError) as error:
        raise CommunityPackageError('Could not create the community package at the selected destination.') from error
