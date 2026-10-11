"""Native revision-A4 Karma Embers, with immutable original Steam context.

The game has owner-dependent CBC framing and no body checksum. Constants and
the one writable field were independently recovered from the native serializer;
see docs/ABYSS_PC_FORMAT.md. All remaining decrypted bytes are opaque and retained.
"""
from dataclasses import dataclass, field as data_field
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw3.save_codec import CNG_AES
from koei_editor.shared.copy_storage import atomic_new, snapshot_backup, restore_snapshot
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.steam_owner import (OwnerContext, read_owner, validate_owner,
                                            require_matching_owner)

GAME_ID = 'abyss_pc'
EXTENSION = '.bin'
SAVE_SIZE = 0x30000
REVISION = 0xA4
INTEGRITY_KIND = 'none'
OUTER_MAGIC = b'470558d4d8015d9f'
INNER_MAGIC = b'a1423bc7d48e148b'
IV = bytes.fromhex('e1c1c49f9a3019341ea820f99fd09a83')
OWNER_MASK = 0xFABE9C015F6E379A
# Native vtable+0x58 size callbacks for revision A4, in registry order. These
# are serialized lengths, not the current/backup arrays' in-memory strides.
SECTIONS = (
    ('Persistent profile', 1, 0x21C6B),
    ('Slot information', 1, 0x333),
    ('Hero records', 298, 0x39),
    ('Current run', 1, 0xC40),
    ('Roster selection records', 20, 5),
    ('Additional records', 64, 5),
)
SERIALIZED_EXTENT = 4 + sum(count * stride for _, count, stride in SECTIONS)
assert SERIALIZED_EXTENT == 0x26FE0 < SAVE_SIZE - 32


@dataclass(frozen=True)
class Field:
    id: str = 'karma_embers'
    label: str = 'Karma Embers'
    offset: int = 6
    maximum: int = 9_999_999
    minimum: int = 0
    size: int = 4
    group: str = 'Resources'
    slot: int = 0
    kind: str = 'int'
    maxable: bool = True

    def value(self, payload):
        return struct.unpack_from('<I', payload, self.offset)[0]

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError('Karma Embers requires a whole number from 0 to 9,999,999.')


KARMA = Field()


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Warriors: Abyss'
    size: int = SAVE_SIZE
    fields: tuple = (KARMA,)
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = ('PC revision-A4 gameplay slots: Karma Embers. Keep the original '
                 'steam_autocloud.vdf beside the copied slot and the edited destination.')


FORMAT = Format()


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path = data_field(repr=False)
    raw: bytes = data_field(repr=False)
    payload: bytes = data_field(repr=False)
    owner: OwnerContext = data_field(repr=False)

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select the Warriors: Abyss PC gameplay profile.')
    return FORMAT


def _key(owner):
    if type(owner) is not OwnerContext:
        raise SaveError('Requires the original copied Steam owner context.')
    return str(owner.steam_id64 ^ OWNER_MASK).encode('ascii').ljust(32, b'\0')


def _decoded(raw, owner):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:16] != OUTER_MAGIC:
        raise SaveError('Requires a complete encrypted Abyss gameplay slot copy; SYSTEMDATA is separate.')
    with CNG_AES('CBC') as provider:
        plain = provider.transform(raw[16:], _key(owner), direction='decrypt', iv=IV)
    if not hmac.compare_digest(plain[:16], INNER_MAGIC):
        raise SaveError('The copied slot does not match its original Steam owner metadata.')
    payload = plain[16:]
    if struct.unpack_from('<I', payload)[0] != REVISION:
        raise SaveError('Unsupported Warriors: Abyss PC gameplay revision.')
    position = 4
    for _name, count, stride in SECTIONS:
        position += count * stride
        if position > len(payload):
            raise SaveError('Abyss serialized objects exceed the complete copied capacity.')
    return payload


def _decode_with_owner(raw, owner, source=Path('GAMEDATA00.BIN')):
    return Document(FORMAT, Path(source), raw, _decoded(raw, owner), owner)


def decode(raw, game_id=GAME_ID, source=Path('GAMEDATA00.BIN')):
    """Shared scalar decode contract; the source carries its original sidecar."""
    get_format(game_id)
    source = _copy_path(source)
    owner = read_owner(source)
    result = _decode_with_owner(raw, owner, source)
    validate_owner(owner)
    return result


def _copy_path(path):
    try:
        original = Path(path).absolute()
        if any(candidate.is_symlink() for candidate in (original, *original.parents)):
            raise SaveError('Use ordinary separate Abyss save copies, without path aliases.')
        result = safe_path(original)
        for candidate in (original, result):
            normalized = str(candidate).replace('\\', '/').casefold()
            if re.search(r'/koeitecmo/warriorsabyss(?:/|$)', normalized):
                raise SaveError('Use a separate copy outside the live Warriors: Abyss save folder.')
        if result.suffix.casefold() != EXTENSION:
            raise SaveError('Choose a separate Abyss gameplay .bin copy.')
        if result.exists() and (not result.is_file() or result.stat().st_nlink != 1):
            raise SaveError('Use an ordinary separate Abyss gameplay file.')
        return result
    except (OSError, TypeError, ValueError):
        raise SaveError('Requires an accessible separate Abyss gameplay copy.') from None


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _copy_path(path)
    owner = read_owner(path)
    try:
        with path.open('rb') as stream:
            raw = stream.read(SAVE_SIZE + 1)
    except OSError:
        raise SaveError('The copied Abyss gameplay slot is unavailable.') from None
    document = _decode_with_owner(raw, owner, path)
    validate_owner(owner)
    return document


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or _decoded(document.raw, document.owner) != document.payload):
        raise SaveError('Requires an immutable qualified Abyss gameplay snapshot.')


def fields_for(document):
    validate_document(document)
    return FORMAT.fields


def field_map(document):
    return MappingProxyType({item.id: item for item in fields_for(document)})


def changed_payload(document, changes):
    validate_document(document)
    if type(changes) is not dict:
        raise SaveError('Abyss changes must be a field/value mapping.')
    result = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key != KARMA.id:
            raise SaveError('Only Karma Embers is writable in this Abyss revision.')
        if value != KARMA.value(document.payload):
            KARMA.validate(value)
        elif type(value) is not int:
            KARMA.validate(value)
        struct.pack_into('<I', result, KARMA.offset, value)
    return bytes(result)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    with CNG_AES('CBC') as provider:
        result = OUTER_MAGIC + provider.transform(INNER_MAGIC + payload, _key(document.owner),
                                                  direction='encrypt', iv=IV)
    if _decoded(result, document.owner) != payload:
        raise SaveError('Edited Abyss copy failed its native owner/revision framing check.')
    return result


def stage(document, changes, key, value):
    changed_payload(document, changes)
    if type(key) is not str or key != KARMA.id:
        raise SaveError('Only Karma Embers is writable in this Abyss revision.')
    original = KARMA.value(document.payload)
    if type(value) is not int or value != original:
        KARMA.validate(value)
    result = dict(changes)
    if value == original:
        result.pop(key, None)
    else:
        result[key] = value
    return result


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    try:
        keys = tuple(keys)
    except TypeError:
        raise SaveError('Choose verified Abyss field IDs for Max.') from None
    if any(type(key) is not str or key != KARMA.id for key in keys):
        raise SaveError('Only Karma Embers supports Max in this Abyss revision.')
    current = changes.get(KARMA.id, KARMA.value(document.payload))
    return {key: max(current, KARMA.value(document.payload), KARMA.maximum) for key in keys}


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    result = dict(changes)
    if group not in (None, 'Resources', 'All fields'):
        return result
    return stage(document, result, KARMA.id, limit_values(document, changes, [KARMA.id])[KARMA.id])


def review(document, changes):
    changed_payload(document, changes)
    return [(KARMA, KARMA.value(document.payload), changes[KARMA.id])] if KARMA.id in changes else []


def _source(document):
    validate_document(document)
    source = _copy_path(document.source)
    validate_owner(document.owner)
    require_matching_owner(document.owner, source)
    try:
        with source.open('rb') as stream:
            if stream.read(SAVE_SIZE + 1) != document.raw:
                raise SaveError('The original Abyss copy changed; reopen it before saving.')
    except OSError:
        raise SaveError('The original Abyss copy is unavailable; reopen it before saving.') from None
    return source


def backup(document):
    source = _source(document)
    snapshot = snapshot_backup(document.raw, source, GAME_ID, source.parent / 'UniversalEditorBackups')
    metadata = {'game_id': GAME_ID, 'kind': 'abyss-steam-owner-context',
                'owner_sha256': document.owner.sha256, 'owner_basename': document.owner.basename,
                'native_sha256': document.sha256}
    try:
        atomic_new(json.dumps(metadata).encode('utf-8'), snapshot.with_name(snapshot.name + '.context.json'))
        _source(document)
    except Exception:
        snapshot.unlink(missing_ok=True)
        snapshot.with_suffix('.json').unlink(missing_ok=True)
        snapshot.with_name(snapshot.name + '.context.json').unlink(missing_ok=True)
        raise
    return snapshot


def save_as(document, changes, destination):
    source = _source(document)
    destination = _copy_path(destination)
    require_matching_owner(document.owner, destination)
    if destination == source or destination.exists():
        raise FileExistsError('Choose a new file; original and existing copies are never replaced.')
    result = serialize(document, changes)
    backup(document)
    _source(document)
    require_matching_owner(document.owner, destination)
    atomic_new(result, destination)
    return read_save(destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    destination, backup_path = _copy_path(destination), _copy_path(backup_path)
    owner = read_owner(destination)
    try:
        with safe_path(backup_path.with_name(backup_path.name + '.context.json')).open('rb') as stream:
            raw_metadata = stream.read(1025)
        if len(raw_metadata) > 1024:
            raise SaveError('Abyss backup context metadata is too large.')
        metadata = json.loads(raw_metadata)
    except (OSError, ValueError, UnicodeError):
        raise SaveError('Abyss backup context metadata is missing or damaged.') from None
    if (type(metadata) is not dict or metadata.get('game_id') != GAME_ID
            or metadata.get('kind') != 'abyss-steam-owner-context'
            or metadata.get('owner_sha256') != owner.sha256
            or metadata.get('owner_basename') != owner.basename):
        raise SaveError('Restore requires the same original Steam owner metadata as the backup.')
    def qualify(raw):
        if metadata.get('native_sha256') != hashlib.sha256(raw).hexdigest():
            raise SaveError('Abyss backup bytes do not match their original context binding.')
        _decoded(raw, owner)
        validate_owner(owner)
        require_matching_owner(owner, destination)
    return restore_snapshot(backup_path, destination, GAME_ID, EXTENSION, SAVE_SIZE, validate_raw=qualify)


def prepare_copy_context(document, directory):
    """Preserve an original companion solely in a new private local test bundle."""
    _source(document)
    directory = _copy_path(Path(directory) / 'input-copy.bin').parent
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / document.owner.basename
    if target.exists():
        require_matching_owner(document.owner, directory / 'input-copy.bin')
        return
    # General atomic_new deliberately forbids VDF writes. This title-scoped
    # exception only preserves the already qualified original opaque sidecar
    # into a new local directory; it cannot change accounts or replace metadata.
    with target.open('xb') as stream:
        stream.write(document.owner.raw)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        require_matching_owner(document.owner, directory / 'input-copy.bin')
        _source(document)
    except Exception:
        target.unlink(missing_ok=True)
        raise


def record_label(slot, group='Resources'):
    return 'Permanent resources'


def recruitment_records(document):
    """Native ownership-query bytes, preserved; catalog names are not guessed."""
    validate_document(document)
    return tuple((record, document.payload[14 + record], 'Inspection only')
                 for record in range(0x33D))
