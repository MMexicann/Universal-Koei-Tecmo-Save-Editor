"""Verified, copy-preserving management for a small catalog of settings.

This module deliberately does not provide a generic INI editor. Every accepted
filename selects one exact adapter and only its documented keys can be written.
All other bytes remain opaque and unchanged.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import uuid

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.copy_storage import atomic_new


FORMAT_ID = 'atelier_arland_dx_settings_ini'
FORMAT_VERSION = 1
FORMAT_FILENAME = 'ArlandDX_Settings.ini'
MOD_FORMAT_ID = 'arland_dx_fix_mod_ini'
MOD_FORMAT_FILENAME = 'arland-fix.ini'
MAX_CONFIG_BYTES = 256 * 1024
MAX_PROFILE_BYTES = 32 * 1024
MAX_BACKUP_JSON_BYTES = 384 * 1024
MAX_PROFILE_COUNT = 256
MAX_BACKUP_COUNT = 1000
_ID = re.compile(r'[0-9a-f]{32}\Z')
_HASH = re.compile(r'[0-9a-f]{64}\Z')
_PROFILE_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}\Z')
_DIGITS = re.compile(br'[ \t]*([0-9]+)[ \t]*\Z')
_BOOL_VALUE = re.compile(br'[ \t]*(true|false|1|0|yes|no)[ \t]*\Z', re.IGNORECASE)
_SECTION = re.compile(br'[ \t]*\[([^\]\r\n]+)\][ \t]*\Z')


class ConfigurationError(ValueError):
    """Base class for rejected configuration operations."""


class UnsupportedConfigurationError(ConfigurationError):
    """The file cannot be identified as a supported configuration format."""


class IncompatibleConfigurationError(ConfigurationError):
    """The selected game, profile, or backup does not match the target."""


class ConfigurationChangedError(ConfigurationError):
    """The selected file changed after it was inspected."""


@dataclass(frozen=True)
class SupportedGame:
    id: str
    title: str
    platform: str = 'PC'
    format_id: str = FORMAT_ID
    format_version: int = FORMAT_VERSION
    filename: str = FORMAT_FILENAME
    format_ids: tuple[str, ...] = (FORMAT_ID, MOD_FORMAT_ID)


SUPPORTED_GAMES = (
    SupportedGame('arland_rorona_dx', 'Atelier Rorona: The Alchemist of Arland DX'),
    SupportedGame('arland_totori_dx', 'Atelier Totori: The Adventurer of Arland DX'),
    SupportedGame('arland_meruru_dx', 'Atelier Meruru: The Apprentice of Arland DX'),
)
_GAMES = {game.id: game for game in SUPPORTED_GAMES}
ConfigGame = SupportedGame


@dataclass(frozen=True)
class SupportedFormat:
    id: str
    label: str
    filename: str
    version: int
    evidence_url: str
    license_name: str


SUPPORTED_FORMATS = (
    SupportedFormat(FORMAT_ID, 'Atelier Arland DX game settings', FORMAT_FILENAME, FORMAT_VERSION,
                    'https://github.com/nicoverbruggen/atelier-arland-fixes/tree/96a4506892de3284a8adc78a4b6a96d67e8bbf59',
                    'MIT project source'),
    SupportedFormat(MOD_FORMAT_ID, 'Arland DX Fix mod settings', MOD_FORMAT_FILENAME, 1,
                    'https://github.com/nicoverbruggen/atelier-arland-fixes/tree/96a4506892de3284a8adc78a4b6a96d67e8bbf59',
                    'MIT project source'),
)
_FORMATS = {item.id: item for item in SUPPORTED_FORMATS}
_FORMAT_BY_FILENAME = {item.filename.casefold(): item for item in SUPPORTED_FORMATS}


@dataclass(frozen=True)
class FieldSpec:
    id: str
    label: str
    category: str
    section: str
    key: str
    choices: tuple[tuple[int, str], ...] = ()
    writable: bool = False
    format_id: str = FORMAT_ID
    value_kind: str = 'integer'


FIELD_SPECS = (
    FieldSpec('fullscreen', 'Full Screen', 'graphics', 'Window', 'FullScreen',
              ((0, 'Off'), (1, 'On')), True),
    FieldSpec('language', 'Language', 'other', 'Lang', 'Language',
              ((1, 'Japanese'), (2, 'English'), (3, 'Simplified Chinese'),
               (4, 'Traditional Chinese')), True),
    FieldSpec('outline', 'Outline', 'graphics', 'Graphics', 'Outline',
              ((0, 'Off'), (1, 'On')), True),
    # The source documents the two resolution keys, but not their accepted
    # value domain. Keep their exact observed text visible and read-only.
    FieldSpec('screen_width', 'Screen Width', 'graphics', 'Graphics', 'ScreenWidth'),
    FieldSpec('screen_height', 'Screen Height', 'graphics', 'Graphics', 'ScreenHeight'),
    FieldSpec('mod_shadow_multiplier', 'Shadow Multiplier', 'graphics', 'Rendering', 'ShadowMultiplier',
              ((1, '1'), (2, '2'), (4, '4'), (8, '8')), True, MOD_FORMAT_ID),
    FieldSpec('mod_smaa', 'SMAA', 'graphics', 'Rendering', 'SMAA',
              ((0, 'Off'), (1, 'On')), True, MOD_FORMAT_ID, 'boolean'),
    FieldSpec('mod_sharpen', 'Sharpen', 'graphics', 'Rendering', 'Sharpen',
              ((0, '0'), (30, '30'), (60, '60'), (100, '100')), True, MOD_FORMAT_ID),
    FieldSpec('mod_battle_cutin_shadows', 'Battle Cut-in Shadows', 'gameplay', 'Battle', 'BattleCutInShadows',
              ((0, 'Off'), (1, 'On')), True, MOD_FORMAT_ID, 'boolean'),
    FieldSpec('mod_battle_cutin_dimming', 'Battle Cut-in Dimming', 'gameplay', 'Battle', 'BattleCutInDimming',
              ((0, 'Off'), (1, 'On')), True, MOD_FORMAT_ID, 'boolean'),
    FieldSpec('mod_skip_logos', 'Skip Logos', 'other', 'Startup', 'SkipLogos',
              ((0, 'Off'), (1, 'On')), True, MOD_FORMAT_ID, 'boolean'),
    FieldSpec('mod_skip_intro_movie', 'Skip Intro Movie', 'other', 'Startup', 'SkipIntroMovie',
              ((0, 'Off'), (1, 'On')), True, MOD_FORMAT_ID, 'boolean'),
    FieldSpec('mod_skip_launcher', 'Skip Launcher', 'other', 'Launcher', 'SkipLauncher',
              ((0, 'Off'), (1, 'On')), True, MOD_FORMAT_ID, 'boolean'),
    FieldSpec('mod_verbose_logging', 'Verbose Logging', 'other', 'Diagnostics', 'VerboseLogging',
              ((0, 'Off'), (1, 'On')), True, MOD_FORMAT_ID, 'boolean'),
)
_FIELDS = {field.id: field for field in FIELD_SPECS}
_FIELDS_BY_FORMAT = {format_id: tuple(item for item in FIELD_SPECS if item.format_id == format_id)
                     for format_id in _FORMATS}
_TARGET_KEYS = {
    format_id: {(field.section.casefold(), field.key.casefold()): field
                for field in _FIELDS_BY_FORMAT[format_id]}
    for format_id in _FORMATS
}


@dataclass(frozen=True)
class ConfigField:
    id: str
    label: str
    category: str
    value: int | str
    display_value: str
    writable: bool
    choices: tuple[tuple[int, str], ...] = ()


@dataclass(frozen=True)
class _ValueLocation:
    field_id: str
    start: int
    end: int
    raw_value: bytes


@dataclass(frozen=True)
class ConfigDocument:
    game_id: str
    game_title: str
    format_id: str
    format_version: int
    path: Path
    sha256: str
    raw: bytes = field(repr=False)
    fields: tuple[ConfigField, ...] = ()
    _locations: tuple[_ValueLocation, ...] = field(default=(), repr=False, compare=False)
    _source_identity: tuple[int, int] | None = field(default=None, repr=False, compare=False)

    @property
    def filename(self):
        return self.path.name


@dataclass(frozen=True)
class CompatibilityResult:
    compatible: bool
    message: str
    game_match: bool
    format_match: bool


@dataclass(frozen=True)
class ConfigDifference:
    field_id: str
    label: str
    category: str
    left_value: int | str | None
    right_value: int | str | None


@dataclass(frozen=True)
class ConfigComparison:
    compatible: bool
    same_game: bool
    changed_fields: tuple[ConfigDifference, ...]
    opaque_difference: bool
    message: str


@dataclass(frozen=True)
class ConfigProfile:
    id: str
    name: str
    game_id: str
    format_id: str
    format_version: int
    created_utc: str
    values: tuple[tuple[str, int], ...]

    @property
    def settings(self):
        return dict(self.values)


@dataclass(frozen=True)
class ConfigBackup:
    id: str
    game_id: str
    filename: str
    format_id: str
    format_version: int
    created_utc: str
    sha256: str
    size_bytes: int


def configuration_data_dir():
    """Return the private application-data directory for path-free records."""
    if os.name == 'nt':
        base = Path(os.environ.get('APPDATA') or os.environ.get('LOCALAPPDATA') or
                    Path.home() / 'AppData' / 'Roaming')
    elif sys_platform() == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    return base / 'UniversalKoeiTecmoSaveEditor' / 'game-configurations'


def sys_platform():
    # Kept as a tiny function so tests can patch platform selection without
    # changing the os.name behavior of file handling.
    import sys
    return sys.platform


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Configuration metadata contains a duplicate property.')
        result[key] = value
    return result


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')


def _reject_constant(_value):
    raise ValueError('Non-finite numbers are not allowed.')


def _is_reparse(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def _check_components(path, *, allow_missing=False, with_leaf=False):
    """Reject links/reparse points in the supplied path before resolving it."""
    candidate = Path(path).absolute()
    current = Path(candidate.anchor)
    if not current.anchor:
        current = Path.cwd().anchor and Path(Path.cwd().anchor) or Path.cwd()
    parts = candidate.parts[1:] if candidate.anchor else candidate.parts
    missing_seen = False
    leaf = None
    for index, part in enumerate(parts):
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            if not allow_missing:
                raise ConfigurationError('The configuration path does not exist.')
            missing_seen = True
            continue
        if missing_seen:
            raise ConfigurationError('A storage path appeared below a missing directory.')
        if index == len(parts) - 1:
            leaf = info
        if _is_reparse(info):
            raise ConfigurationError('Configuration files and storage reject symbolic links and reparse paths.')
        if index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):
            raise ConfigurationError('A configuration path parent is not an ordinary directory.')
    try:
        resolved = safe_path(candidate)
        return (resolved, leaf) if with_leaf else resolved
    except (OSError, SaveError, RuntimeError, ValueError) as error:
        raise ConfigurationError(str(error)) from error


def _ensure_directory(path):
    candidate = Path(path).absolute()
    # Walk from the root to create one component at a time. Checking before
    # each mkdir avoids following a pre-existing link in a caller-selected root.
    current = Path(candidate.anchor) if candidate.anchor else Path.cwd()
    parts = candidate.parts[1:] if candidate.anchor else candidate.parts
    for part in parts:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            try:
                current.mkdir(mode=0o700)
            except FileExistsError:
                pass
            except OSError as error:
                raise ConfigurationError(f'Cannot create configuration storage: {error}') from error
            try:
                info = current.lstat()
            except OSError as error:
                raise ConfigurationError(f'Cannot inspect configuration storage: {error}') from error
        if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
            raise ConfigurationError('Configuration storage must use ordinary directories.')
    _check_components(candidate)
    return candidate.resolve()


def _check_file(path):
    resolved, qualified = _check_components(path, with_leaf=True)
    if (qualified is None or _is_reparse(qualified) or not stat.S_ISREG(qualified.st_mode)
            or qualified.st_nlink != 1):
        raise ConfigurationError('Configuration management requires an ordinary, unaliased file.')
    try:
        info = Path(path).lstat()
    except OSError as error:
        raise ConfigurationError(f'Cannot inspect configuration file: {error}') from error
    if (_is_reparse(info) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
        raise ConfigurationError('Configuration management requires an ordinary, unaliased file.')
    if (info.st_dev, info.st_ino) != (qualified.st_dev, qualified.st_ino):
        raise ConfigurationChangedError('The configuration path changed after qualification.')
    return resolved, info


def _read_bounded_file(path, limit, *, with_source=False):
    resolved, before = _check_file(path)
    if before.st_size < 0 or before.st_size > limit:
        raise UnsupportedConfigurationError('The selected file exceeds the configuration size limit.')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    try:
        descriptor = os.open(resolved, flags)
    except OSError as error:
        raise ConfigurationError(f'Cannot read the selected configuration: {error}') from error
    try:
        opened = os.fstat(descriptor)
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
            raise ConfigurationChangedError('The selected configuration changed before it could be read.')
        chunks, length = [], 0
        while length <= limit:
            chunk = os.read(descriptor, min(65536, limit + 1 - length))
            if not chunk:
                break
            chunks.append(chunk)
            length += len(chunk)
        raw = b''.join(chunks)
        if length > limit:
            raise UnsupportedConfigurationError('The selected file exceeds the configuration size limit.')
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        current = Path(path).lstat()
    except OSError as error:
        raise ConfigurationChangedError('The selected configuration disappeared while being read.') from error
    if (not stat.S_ISREG(after.st_mode) or after.st_nlink != 1 or _is_reparse(after)
            or not stat.S_ISREG(current.st_mode) or current.st_nlink != 1 or _is_reparse(current)
            or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) !=
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            or opened.st_ctime_ns != after.st_ctime_ns
            or (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) !=
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)):
        raise ConfigurationChangedError('The selected configuration changed while being read.')
    if with_source:
        return raw, resolved, (current.st_dev, current.st_ino)
    return raw


def _line_spans(raw):
    start = 0
    index = 0
    while index < len(raw):
        if raw[index] not in (10, 13):
            index += 1
            continue
        end = index + 1
        if raw[index] == 13 and end < len(raw) and raw[end] == 10:
            end += 1
        yield start, end
        start = end
        index = end
    if start < len(raw):
        yield start, len(raw)


def _field_value(field_spec, raw_value):
    if field_spec.value_kind == 'boolean':
        match = _BOOL_VALUE.fullmatch(raw_value)
        if match:
            token = match.group(1).lower()
            value = 1 if token in (b'true', b'1', b'yes') else 0
            label = 'On' if value else 'Off'
            return value, label, True
        display = raw_value.decode('ascii', 'backslashreplace').strip() or '(empty)'
        return display, f'Unrecognized value ({display}); preserved', False
    match = _DIGITS.fullmatch(raw_value)
    if match:
        token = match.group(1)
        # Avoid Python's integer conversion limit for hostile, oversized values.
        # They remain visible as opaque text and can never become writable.
        if len(token) > 128:
            display = token.decode('ascii', 'backslashreplace')
            return display, f'Unrecognized value ({display}); preserved', False
        value = int(token)
        allowed = {choice for choice, _label in field_spec.choices}
        writable = field_spec.writable and value in allowed
        display = next((label for choice, label in field_spec.choices if choice == value), str(value))
        if field_spec.writable and not writable:
            display = f'Unrecognized value ({value}); preserved'
        return value, display, writable
    display = raw_value.decode('ascii', 'backslashreplace').strip() or '(empty)'
    return display, f'Unrecognized value ({display}); preserved', False


def _encoded_value(spec, value, location):
    if spec.value_kind != 'boolean':
        return str(value).encode('ascii')
    match = re.fullmatch(br'([ \t]*)(true|false|1|0|yes|no)([ \t]*)', location.raw_value,
                         re.IGNORECASE)
    if match is None:
        raise ConfigurationError(f'{spec.label} does not use a recognized boolean encoding.')
    prior = match.group(2)
    lowered = prior.lower()
    if lowered in (b'1', b'0'):
        token = b'1' if value else b'0'
    elif lowered in (b'yes', b'no'):
        token = b'yes' if value else b'no'
    else:
        token = b'true' if value else b'false'
    if prior.isupper():
        token = token.upper()
    elif prior[:1].isupper() and prior[1:].islower():
        token = token[:1].upper() + token[1:]
    return token


def _format_for(game_id, path, format_id=None):
    game = _GAMES.get(game_id)
    if game is None:
        raise UnsupportedConfigurationError('Choose one of the exact supported Atelier Arland DX PC profiles.')
    format_spec = (_FORMAT_BY_FILENAME.get(Path(path).name.casefold()) if format_id is None
                   else _FORMATS.get(format_id))
    if (format_spec is None or format_spec.id not in game.format_ids
            or Path(path).name.casefold() != format_spec.filename.casefold()):
        supported = ', '.join(_FORMATS[item].filename for item in game.format_ids if item in _FORMATS)
        raise UnsupportedConfigurationError(f'This game profile only supports these exact files: {supported}.')
    return game, format_spec


def _parse_bytes(raw, game_id, path, format_id=None):
    game, format_spec = _format_for(game_id, path, format_id)
    if not isinstance(raw, bytes) or len(raw) > MAX_CONFIG_BYTES or b'\x00' in raw:
        raise UnsupportedConfigurationError('The selected file is not a bounded supported text configuration.')
    field_specs = _FIELDS_BY_FORMAT[format_spec.id]
    target_keys = _TARGET_KEYS[format_spec.id]
    fields_by_id = {}
    locations = {}
    section = ''
    field_counts = {}
    for line_start, line_end in _line_spans(raw):
        line = raw[line_start:line_end]
        content = line.rstrip(b'\r\n')
        trimmed = content.lstrip(b' \t')
        if not trimmed or trimmed.startswith((b';', b'#')):
            continue
        section_match = _SECTION.fullmatch(content)
        if section_match:
            try:
                section = section_match.group(1).decode('ascii').casefold()
            except UnicodeDecodeError:
                section = ''
            continue
        if trimmed.startswith(b'['):
            # An unsupported header must not inherit the preceding known
            # section and turn an opaque key into an editable setting.
            raise UnsupportedConfigurationError('A section header uses unsupported or ambiguous syntax.')
        if not section or b'=' not in content:
            continue
        equals = content.find(b'=')
        try:
            key = content[:equals].strip().decode('ascii').casefold()
        except UnicodeDecodeError:
            continue
        spec = target_keys.get((section, key))
        if spec is None:
            continue
        field_counts[spec.id] = field_counts.get(spec.id, 0) + 1
        if field_counts[spec.id] > 1:
            raise UnsupportedConfigurationError(f'{spec.section}/{spec.key} appears more than once; the format is ambiguous.')
        value_start = line_start + equals + 1
        value_bytes = content[equals + 1:]
        match = _DIGITS.fullmatch(value_bytes)
        if match:
            absolute_start = value_start + match.start(1)
            absolute_end = value_start + match.end(1)
        else:
            # Keeping the full value span makes opaque comparisons sensitive
            # to malformed values, without granting the field write support.
            whitespace = len(value_bytes) - len(value_bytes.lstrip(b' \t'))
            absolute_start = value_start + whitespace
            absolute_end = value_start + len(value_bytes.rstrip(b' \t'))
        value, display, writable = _field_value(spec, value_bytes)
        fields_by_id[spec.id] = ConfigField(spec.id, spec.label, spec.category,
                                            value, display, writable, spec.choices)
        locations[spec.id] = _ValueLocation(spec.id, absolute_start, absolute_end, value_bytes)
    if not fields_by_id:
        raise UnsupportedConfigurationError('No documented Atelier Arland DX settings were found in this file.')
    fields = tuple(fields_by_id[spec.id] for spec in field_specs if spec.id in fields_by_id)
    locs = tuple(locations[spec.id] for spec in field_specs if spec.id in locations)
    return ConfigDocument(game.id, game.title, format_spec.id, format_spec.version, Path(path),
                          _digest(raw), raw, fields, locs)


def inspect_config(path, game_id):
    """Read and validate one exact supported settings file without modifying it."""
    candidate = Path(path)
    _game, format_spec = _format_for(game_id, candidate)
    raw, resolved, identity = _read_bounded_file(candidate, MAX_CONFIG_BYTES, with_source=True)
    return replace(_parse_bytes(raw, game_id, resolved, format_spec.id), _source_identity=identity)


def supported_settings(document):
    """Return only documented settings present in this exact file."""
    _require_document(document)
    return document.fields


def _require_document(document):
    if (not isinstance(document, ConfigDocument) or document.game_id not in _GAMES
            or document.format_id not in _FORMATS
            or document.format_id not in _GAMES[document.game_id].format_ids
            or type(document.format_version) is not int
            or document.format_version != _FORMATS[document.format_id].version
            or not isinstance(document.path, Path) or not document.path.is_absolute()
            or type(document._source_identity) is not tuple or len(document._source_identity) != 2
            or any(type(value) is not int for value in document._source_identity)
            or document.filename.casefold() != _FORMATS[document.format_id].filename.casefold()
            or type(document.raw) is not bytes or document.sha256 != _digest(document.raw)):
        raise IncompatibleConfigurationError('This configuration document does not match a supported format.')
    parsed = _parse_bytes(document.raw, document.game_id, document.path, document.format_id)
    if (document.game_title != parsed.game_title or document.fields != parsed.fields
            or document._locations != parsed._locations):
        raise IncompatibleConfigurationError('This configuration document has inconsistent parsed settings.')


def compatibility_check(document, game_id=None, format_id=None, format_version=None):
    """Check an opened document against an exact optional game/format target."""
    try:
        _require_document(document)
    except ConfigurationError as error:
        return CompatibilityResult(False, str(error), False, False)
    game_match = game_id is None or (type(game_id) is str and document.game_id == game_id)
    version_match = format_version is None or (type(format_version) is int
                                               and document.format_version == format_version)
    format_match = ((format_id is None or (type(format_id) is str and document.format_id == format_id))
                    and version_match)
    if game_match and format_match:
        message = 'The file matches the selected game and verified settings format.'
    elif not game_match and not format_match:
        message = 'The file belongs to a different game and settings format.'
    elif not game_match:
        message = 'The file belongs to a different game profile.'
    else:
        message = 'The settings format or revision is incompatible.'
    return CompatibilityResult(game_match and format_match, message, game_match, format_match)


def _field_map(document):
    return {item.id: item for item in document.fields}


def serialize_config(document, changes):
    """Return a surgically updated copy; no missing or undocumented key is added."""
    _require_document(document)
    if type(changes) is not dict:
        raise ConfigurationError('Configuration changes must be a mapping of supported setting IDs to values.')
    fields = _field_map(document)
    locations = {item.field_id: item for item in document._locations}
    replacements = []
    for field_id, value in changes.items():
        spec = _FIELDS.get(field_id)
        current = fields.get(field_id)
        location = locations.get(field_id)
        if (spec is None or spec.format_id != document.format_id
                or current is None or location is None):
            raise IncompatibleConfigurationError(f'{field_id!r} is not a documented setting present in this file.')
        if not spec.writable or not current.writable:
            raise ConfigurationError(f'{spec.label} is read-only for this file or its current value.')
        if type(value) is not int or value not in {choice for choice, _label in spec.choices}:
            raise ConfigurationError(f'{spec.label} must use one of its documented values.')
        if value == current.value:
            continue
        replacements.append((location.start, location.end, _encoded_value(spec, value, location)))
    updated = document.raw
    for start, end, replacement in sorted(replacements, reverse=True):
        updated = updated[:start] + replacement + updated[end:]
    if len(updated) > MAX_CONFIG_BYTES:
        raise ConfigurationError('The edited settings file exceeds its size limit.')
    reopened = _parse_bytes(updated, document.game_id, document.path, document.format_id)
    actual = _field_map(reopened)
    for field_id, value in changes.items():
        if actual[field_id].value != value:
            raise ConfigurationError(f'{field_id} did not survive a read-back check.')
    return updated


def _confirm_unchanged(document):
    _require_document(document)
    current, resolved, identity = _read_bounded_file(document.path, MAX_CONFIG_BYTES, with_source=True)
    if (resolved != document.path or identity != document._source_identity
            or _digest(current) != document.sha256):
        raise ConfigurationChangedError('The configuration changed after it was opened. Reload it before writing.')
    return current


def _owned_staging(path, identity):
    info = path.lstat()
    return (stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and not _is_reparse(info)
            and (info.st_dev, info.st_ino) == identity)


def _atomic_replace(document, updated):
    path = document.path
    _confirm_unchanged(document)
    resolved, before = _check_file(path)
    if (before.st_dev, before.st_ino) != document._source_identity:
        raise ConfigurationChangedError('The configuration changed before the write. Reload it before continuing.')
    temporary, identity = None, None
    try:
        with tempfile.NamedTemporaryFile(mode='w+b', dir=resolved.parent,
                                         prefix='.koei-config.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            opened = os.fstat(stream.fileno())
            identity = (opened.st_dev, opened.st_ino)
            if stream.write(updated) != len(updated):
                raise ConfigurationError('The temporary settings write was incomplete.')
            stream.flush()
            os.fsync(stream.fileno())
            stream.seek(0)
            if stream.read(len(updated) + 1) != updated:
                raise ConfigurationError('The temporary settings failed exact-byte verification.')
            # Preserve permissions through the owned descriptor where supported;
            # never chmod a pathname that another process may have replaced.
            if hasattr(os, 'fchmod'):
                try:
                    os.fchmod(stream.fileno(), stat.S_IMODE(before.st_mode))
                except OSError:
                    pass
            if not _owned_staging(temporary, identity):
                raise ConfigurationChangedError('The temporary settings changed before publication.')
        # These checks also reject substitutions after the staging handle closes.
        if not _owned_staging(temporary, identity):
            raise ConfigurationChangedError('The temporary settings changed before publication.')
        # Do not reopen the staging pathname for verification: its bounded
        # content check belongs to the owned descriptor above.
        _confirm_unchanged(document)
        if not _owned_staging(temporary, identity):
            raise ConfigurationChangedError('The temporary settings changed before publication.')
        os.replace(temporary, resolved)
        temporary = None
        readback, actual_path, actual_identity = _read_bounded_file(path, MAX_CONFIG_BYTES, with_source=True)
        if readback != updated or actual_path != resolved or actual_identity != identity:
            raise ConfigurationError('The saved settings did not match their exact read-back bytes and identity.')
        return replace(_parse_bytes(readback, document.game_id, resolved, document.format_id),
                       _source_identity=actual_identity)
    except ConfigurationError:
        raise
    except OSError as error:
        raise ConfigurationError(f'Cannot safely write the configuration: {error}') from error
    finally:
        if temporary is not None and identity is not None:
            try:
                if _owned_staging(temporary, identity):
                    temporary.unlink()
            except OSError:
                pass


def save_config(document, changes, backup_dir=None):
    """Save reviewed values in-place after a verified automatic backup."""
    _require_document(document)
    _confirm_unchanged(document)
    updated = serialize_config(document, changes)
    if updated == document.raw:
        return inspect_config(document.path, document.game_id)
    create_backup(document, backup_dir)
    # Backup I/O takes time; bind the write to the same exact original snapshot.
    _confirm_unchanged(document)
    saved = _atomic_replace(document, updated)
    for field_id, value in changes.items():
        actual = _field_map(saved).get(field_id)
        if actual is None or actual.value != value:
            raise ConfigurationError(f'{field_id} failed post-write value verification.')
    return saved


def _opaque_projection(document):
    """Remove complete recognized setting lines before comparing opaque data.

    Known-key presence and value changes belong in ``changed_fields``. Blank
    known section headers left by a removed key are schema scaffolding too;
    unknown sections, comments, keys and all other bytes remain comparable.
    """
    locations = {item.field_id: item for item in document._locations}
    fields = _field_map(document)
    mapped_lines = set()
    for line_start, line_end in _line_spans(document.raw):
        for field_id, location in locations.items():
            if field_id in fields and line_start <= location.start <= line_end:
                mapped_lines.add((line_start, line_end))
                break

    known_sections = {item.section.casefold() for item in _FIELDS_BY_FORMAT[document.format_id]}
    lines, section_group, group_index = [], -1, {}
    current_section = None
    spans = tuple(_line_spans(document.raw))
    for line_start, line_end in spans:
        line = document.raw[line_start:line_end]
        content = line.rstrip(b'\r\n')
        section_match = _SECTION.fullmatch(content)
        is_header = section_match is not None
        if is_header:
            section_group += 1
            try:
                # Match the parser's normalization exactly: case folding only.
                # Whitespace inside brackets makes this an unknown section.
                current_section = section_match.group(1).decode('ascii').casefold()
            except UnicodeDecodeError:
                current_section = None
            group_index[section_group] = current_section
        mapped = (line_start, line_end) in mapped_lines
        if not is_header and not mapped and content.strip():
            if section_group >= 0:
                group_index[section_group] = current_section
            lines.append((line, False, section_group))
        elif not is_header and not mapped:
            lines.append((line, False, section_group))
        elif is_header:
            lines.append((line, True, section_group))
        # Mapped setting lines are omitted as a whole, including their line
        # terminator, so a missing known key is not reported as opaque data.

    section_has_opaque = {}
    for line, is_header, group in lines:
        if not is_header and line.rstrip(b'\r\n').strip():
            section_has_opaque[group] = True
    return b''.join(
        line for line, is_header, group in lines
        if not is_header or section_has_opaque.get(group, False)
        or group_index.get(group) not in known_sections
    )


def compare_configs(left, right):
    """Compare known settings and report whether remaining opaque bytes differ."""
    _require_document(left)
    _require_document(right)
    compatible = left.format_id == right.format_id and left.format_version == right.format_version
    same_game = left.game_id == right.game_id
    if not compatible:
        return ConfigComparison(False, same_game, (), left.raw != right.raw,
                                'These files use different verified configuration formats.')
    left_fields, right_fields = _field_map(left), _field_map(right)
    differences = []
    for spec in FIELD_SPECS:
        a, b = left_fields.get(spec.id), right_fields.get(spec.id)
        av = a.value if a else None
        bv = b.value if b else None
        if av != bv:
            differences.append(ConfigDifference(spec.id, spec.label, spec.category, av, bv))
    opaque = _opaque_projection(left) != _opaque_projection(right)
    scope = 'same game' if same_game else 'same verified format across different titles'
    return ConfigComparison(True, same_game, tuple(differences), opaque,
                            f'Compared documented settings for the {scope}.')


def _valid_profile_name(name):
    return type(name) is str and bool(_PROFILE_NAME.fullmatch(name)) and not name.endswith((' ', '.'))


def _profile_path(profile_id, profile_dir=None):
    if type(profile_id) is not str or not _ID.fullmatch(profile_id):
        raise ConfigurationError('The selected profile ID is invalid.')
    root = _ensure_directory(profile_dir or configuration_data_dir() / 'profiles')
    return root / f'{profile_id}.json'


def _write_new_record(path, raw, limit):
    if len(raw) > limit:
        raise ConfigurationError('The configuration record exceeds its size limit.')
    _ensure_directory(path.parent)
    try:
        _check_components(path, allow_missing=True)
        # Callers validate the complete profile/backup manifest before this
        # publication. The shared writer verifies those same serialized bytes
        # on its owned bounded handle before creating a new destination.
        result = atomic_new(raw, path, mode=0o600)
        if _read_bounded_file(result, limit) != raw:
            raise ConfigurationError('The configuration record failed exact-byte read-back.')
    except (OSError, SaveError, RuntimeError) as error:
        # A failed or replaced record is retained; it may belong to another
        # process. Never unlink the user-selected record pathname on failure.
        raise ConfigurationError(f'Cannot save a configuration record: {error}') from error


def _parse_profile(raw, expected_id=None):
    if len(raw) > MAX_PROFILE_BYTES:
        raise ConfigurationError('The profile exceeds its size limit.')
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (ValueError, TypeError, RecursionError, UnicodeDecodeError) as error:
        raise ConfigurationError('The profile is not valid JSON.') from error
    required = {'schema', 'id', 'name', 'game_id', 'format_id', 'format_version', 'created_utc', 'values'}
    if type(value) is not dict or set(value) != required:
        raise ConfigurationError('The profile schema or compatibility identity is unsupported.')
    game = _GAMES.get(value.get('game_id')) if type(value.get('game_id')) is str else None
    format_spec = _FORMATS.get(value.get('format_id')) if type(value.get('format_id')) is str else None
    if (type(value.get('schema')) is not int or value['schema'] != 1
            or type(value.get('id')) is not str or not _ID.fullmatch(value['id'])
            or expected_id is not None and value['id'] != expected_id
            or not _valid_profile_name(value.get('name')) or game is None or format_spec is None
            or format_spec.id not in game.format_ids or type(value.get('format_version')) is not int
            or value.get('format_version') != format_spec.version
            or type(value.get('created_utc')) is not str or len(value['created_utc']) > 40
            or type(value.get('values')) is not dict or not value['values']):
        raise ConfigurationError('The profile schema or compatibility identity is unsupported.')
    values = []
    for field_id, number in value['values'].items():
        spec = _FIELDS.get(field_id)
        if (spec is None or spec.format_id != value['format_id'] or not spec.writable or type(number) is not int
                or number not in {choice for choice, _label in spec.choices}):
            raise ConfigurationError('The profile contains an unsupported setting or value.')
        values.append((field_id, number))
    return ConfigProfile(value['id'], value['name'], value['game_id'], value['format_id'],
                         value['format_version'], value['created_utc'], tuple(sorted(values)))


def create_profile(document, name, profile_dir=None):
    """Save current documented writable settings without any source path."""
    _require_document(document)
    if not _valid_profile_name(name):
        raise ConfigurationError('Use a profile name of 1–64 letters, digits, spaces, dots, dashes or underscores.')
    _confirm_unchanged(document)
    values = {item.id: item.value for item in document.fields if item.writable}
    if not values:
        raise ConfigurationError('This configuration has no verified writable settings to profile.')
    profile_id = uuid.uuid4().hex
    created = _utc_now()
    record = {'schema': 1, 'id': profile_id, 'name': name, 'game_id': document.game_id,
              'format_id': document.format_id, 'format_version': document.format_version,
              'created_utc': created, 'values': values}
    raw = _json_bytes(record)
    profile = _parse_profile(raw, profile_id)
    root = _ensure_directory(profile_dir or configuration_data_dir() / 'profiles')
    if len(list(root.glob('*.json'))) >= MAX_PROFILE_COUNT:
        raise ConfigurationError('The profile limit has been reached.')
    _write_new_record(root / f'{profile_id}.json', raw, MAX_PROFILE_BYTES)
    return profile


def _profile_root(profile_dir=None):
    root = Path(profile_dir or configuration_data_dir() / 'profiles')
    try:
        return _check_components(root)
    except ConfigurationError as error:
        if not root.exists():
            return None
        raise error


def list_profiles(profile_dir=None):
    root = _profile_root(profile_dir)
    if root is None or not root.exists():
        return ()
    try:
        names = sorted(root.glob('*.json'))
    except OSError as error:
        raise ConfigurationError(f'Cannot list profiles: {error}') from error
    if len(names) > MAX_PROFILE_COUNT:
        raise ConfigurationError('The profile directory exceeds its entry limit.')
    profiles = []
    for path in names:
        try:
            if not _ID.fullmatch(path.stem):
                continue
            raw = _read_bounded_file(path, MAX_PROFILE_BYTES)
            profiles.append(_parse_profile(raw, path.stem))
        except (ConfigurationError, OSError):
            # Corrupt or foreign records remain untouched and are not loaded.
            continue
    return tuple(sorted(profiles, key=lambda item: (item.game_id, item.name.casefold(), item.id)))


def apply_profile(document, profile):
    """Return validated setting assignments; the caller must still review/save."""
    _require_document(document)
    if not isinstance(profile, ConfigProfile):
        raise ConfigurationError('Choose a profile loaded by this manager.')
    if (type(profile.id) is not str or not _ID.fullmatch(profile.id)
            or not _valid_profile_name(profile.name)
            or type(profile.created_utc) is not str or len(profile.created_utc) > 40
            or type(profile.values) is not tuple or not profile.values):
        raise ConfigurationError('The selected profile metadata is invalid.')
    seen = set()
    for pair in profile.values:
        if type(pair) is not tuple or len(pair) != 2:
            raise ConfigurationError('The selected profile settings are invalid.')
        field_id, number = pair
        spec = _FIELDS.get(field_id) if type(field_id) is str else None
        if (type(field_id) is not str or field_id in seen or spec is None
                or spec.format_id != profile.format_id
                or not spec.writable or type(number) is not int
                or number not in {choice for choice, _label in spec.choices}):
            raise ConfigurationError('The selected profile contains an unsupported setting or value.')
        seen.add(field_id)
    result = compatibility_check(document, profile.game_id, profile.format_id, profile.format_version)
    if not result.compatible:
        raise IncompatibleConfigurationError(result.message)
    fields = _field_map(document)
    assignments = profile.settings
    for field_id in assignments:
        field = fields.get(field_id)
        if field is None or not field.writable:
            raise IncompatibleConfigurationError(f'The current file does not contain writable {field_id}.')
    return assignments


def delete_profile(profile_id, profile_dir=None):
    path = _profile_path(profile_id, profile_dir)
    try:
        raw = _read_bounded_file(path, MAX_PROFILE_BYTES)
        _parse_profile(raw, profile_id)
        path.unlink()
    except FileNotFoundError as error:
        raise ConfigurationError('The selected profile no longer exists.') from error
    except OSError as error:
        raise ConfigurationError(f'Cannot remove the profile: {error}') from error
    return True


def _backup_root(backup_dir=None, *, create=False):
    root = Path(backup_dir or configuration_data_dir() / 'backups')
    if create:
        return _ensure_directory(root)
    try:
        return _check_components(root)
    except ConfigurationError:
        if not root.exists():
            return None
        raise


def _parse_backup(raw, expected_id=None):
    if len(raw) > MAX_BACKUP_JSON_BYTES:
        raise ConfigurationError('The backup exceeds its size limit.')
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (ValueError, TypeError, RecursionError, UnicodeDecodeError) as error:
        raise ConfigurationError('The backup record is not valid JSON.') from error
    required = {'schema', 'id', 'game_id', 'filename', 'format_id', 'format_version',
                'created_utc', 'sha256', 'size_bytes', 'data_base64'}
    if type(value) is not dict or set(value) != required:
        raise ConfigurationError('The backup schema or compatibility identity is unsupported.')
    game = _GAMES.get(value.get('game_id')) if type(value.get('game_id')) is str else None
    format_spec = _FORMATS.get(value.get('format_id')) if type(value.get('format_id')) is str else None
    if (type(value.get('schema')) is not int or value['schema'] != 1
            or type(value.get('id')) is not str or not _ID.fullmatch(value['id'])
            or expected_id is not None and value['id'] != expected_id
            or game is None or format_spec is None or format_spec.id not in game.format_ids
            or value.get('filename') != format_spec.filename
            or type(value.get('format_version')) is not int
            or value.get('format_version') != format_spec.version
            or type(value.get('created_utc')) is not str or len(value['created_utc']) > 40
            or type(value.get('sha256')) is not str or not _HASH.fullmatch(value['sha256'])
            or type(value.get('size_bytes')) is not int or not 0 <= value['size_bytes'] <= MAX_CONFIG_BYTES
            or type(value.get('data_base64')) is not str):
        raise ConfigurationError('The backup schema or compatibility identity is unsupported.')
    try:
        data = base64.b64decode(value['data_base64'], validate=True)
    except (ValueError, TypeError) as error:
        raise ConfigurationError('The backup data is not valid base64.') from error
    if len(data) != value['size_bytes'] or _digest(data) != value['sha256']:
        raise ConfigurationError('The backup bytes do not match their recorded digest.')
    _parse_bytes(data, value['game_id'], value['filename'], value['format_id'])
    backup = ConfigBackup(value['id'], value['game_id'], value['filename'], value['format_id'],
                          value['format_version'], value['created_utc'], value['sha256'], value['size_bytes'])
    return backup, data


def create_backup(document, backup_dir=None):
    """Back up the exact opened configuration bytes to private app storage."""
    _require_document(document)
    current = _confirm_unchanged(document)
    root = _backup_root(backup_dir, create=True)
    if len(list(root.glob('*.json'))) >= MAX_BACKUP_COUNT:
        raise ConfigurationError('The configuration backup limit has been reached.')
    backup_id = uuid.uuid4().hex
    created = _utc_now()
    record = {'schema': 1, 'id': backup_id, 'game_id': document.game_id,
              'filename': _FORMATS[document.format_id].filename, 'format_id': document.format_id,
              'format_version': document.format_version, 'created_utc': created,
              'sha256': _digest(current), 'size_bytes': len(current),
              'data_base64': base64.b64encode(current).decode('ascii')}
    raw = _json_bytes(record)
    backup, _data = _parse_backup(raw, backup_id)
    _write_new_record(root / f'{backup_id}.json', raw, MAX_BACKUP_JSON_BYTES)
    return backup


def list_backups(backup_dir=None, game_id=None):
    root = _backup_root(backup_dir)
    if root is None or not root.exists():
        return ()
    if game_id is not None and game_id not in _GAMES:
        raise IncompatibleConfigurationError('Choose one of the exact supported game profiles.')
    try:
        names = sorted(root.glob('*.json'))
    except OSError as error:
        raise ConfigurationError(f'Cannot list configuration backups: {error}') from error
    if len(names) > MAX_BACKUP_COUNT:
        raise ConfigurationError('The backup directory exceeds its entry limit.')
    backups = []
    for path in names:
        try:
            if not _ID.fullmatch(path.stem):
                continue
            backup, _data = _parse_backup(_read_bounded_file(path, MAX_BACKUP_JSON_BYTES), path.stem)
            if game_id is None or backup.game_id == game_id:
                backups.append(backup)
        except (ConfigurationError, OSError):
            continue
    return tuple(sorted(backups, key=lambda item: (item.created_utc, item.id), reverse=True))


def restore_backup(document, backup_id, backup_dir=None):
    """Restore one same-game verified backup through atomic exact-byte read-back."""
    _require_document(document)
    root = _backup_root(backup_dir)
    if root is None:
        raise ConfigurationError('No configuration backup directory exists.')
    if type(backup_id) is not str or not _ID.fullmatch(backup_id):
        raise ConfigurationError('The selected backup ID is invalid.')
    path = root / f'{backup_id}.json'
    try:
        backup, raw = _parse_backup(_read_bounded_file(path, MAX_BACKUP_JSON_BYTES), backup_id)
    except FileNotFoundError as error:
        raise ConfigurationError('The selected backup no longer exists.') from error
    if backup.game_id != document.game_id or backup.format_id != document.format_id:
        raise IncompatibleConfigurationError('This backup belongs to a different game or format.')
    if _digest(raw) == document.sha256:
        _confirm_unchanged(document)
        return inspect_config(document.path, document.game_id)
    _confirm_unchanged(document)
    create_backup(document, backup_dir)
    _confirm_unchanged(document)
    restored = _atomic_replace(document, raw)
    if restored.raw != raw or restored.sha256 != backup.sha256:
        raise ConfigurationError('The restored configuration failed exact-byte verification.')
    return restored


def _masked_field_value(location):
    return b'<mapped>'


