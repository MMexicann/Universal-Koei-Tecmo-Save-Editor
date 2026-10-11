"""Read-only, bounded owner context from an original copied Steam sidecar.

Games consume the private account value explicitly. Nothing here changes game
ownership, writes metadata, or relaxes the general ban on opening cloud files.
Only the native single-account Valve VDF shape is admitted.
"""
from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import re
import stat

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.save_safety import safe_path

MAX_OWNER_SIZE = 4096
OWNER_BASENAME = 'steam_autocloud.vdf'
STEAM_INDIVIDUAL_BASE = 76561197960265728
_VDF = re.compile(
    rb'[ \t\r\n]*"steam_autocloud\.vdf"[ \t\r\n]*\{[ \t\r\n]*'
    rb'"accountid"[ \t\r\n]*"([1-9][0-9]{0,9})"[ \t\r\n]*\}[ \t\r\n]*')


def _account(raw):
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_OWNER_SIZE:
        raise SaveError('Steam owner metadata has an invalid bounded size.')
    match = _VDF.fullmatch(raw)
    if match is None:
        raise SaveError('Requires the original single-account Steam owner metadata.')
    value = int(match.group(1))
    if not 1 <= value <= 0xFFFFFFFF:
        raise SaveError('Steam owner metadata requires an individual account number.')
    return value


@dataclass(frozen=True, repr=False)
class OwnerContext:
    """Opaque original sidecar; sensitive bytes and paths never enter repr."""
    source: Path = field(repr=False)
    raw: bytes = field(repr=False)

    def __repr__(self):
        return '<SteamOwnerContext>'

    @property
    def sha256(self):
        _account(self.raw)
        return hashlib.sha256(self.raw).hexdigest()

    @property
    def account_id(self):
        """Private low DWORD for owner-dependent codecs; never display it."""
        return _account(self.raw)

    @property
    def steam_id64(self):
        """Public-universe individual instance-one encoding, privately consumed."""
        return STEAM_INDIVIDUAL_BASE + self.account_id

    @property
    def basename(self):
        return self.source.name


def _copied_path(path):
    try:
        lexical = Path(path).absolute()
        # Reject metadata reached through aliases even if its current bytes match.
        if any(part.is_symlink() for part in (lexical, *lexical.parents)):
            raise SaveError('Use ordinary separate copies for Steam owner context.')
        resolved = safe_path(lexical)
        if resolved.exists():
            info = resolved.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise SaveError('Use ordinary separate copies for Steam owner context.')
        return resolved
    except (OSError, TypeError, ValueError):
        raise SaveError('Steam owner context requires an accessible separate save copy.') from None


def _sidecar(save_path):
    save_path = _copied_path(save_path)
    try:
        candidates = []
        for entry in save_path.parent.iterdir():
            if entry.name.casefold() == OWNER_BASENAME:
                candidates.append(entry)
                if len(candidates) > 1:
                    raise SaveError('Steam owner metadata is ambiguous beside this copy.')
        if len(candidates) != 1:
            raise SaveError('Keep the original steam_autocloud.vdf beside the copied save.')
        companion = candidates[0]
        if companion.is_symlink():
            raise SaveError('Steam owner metadata must be an ordinary separate copy.')
        # This narrow read exception checks the directory through a non-metadata
        # save path. safe_path itself still prohibits general VDF access/writes.
        return companion
    except OSError:
        raise SaveError('Steam owner metadata is unavailable beside this copy.') from None


def _read(companion):
    descriptor = None
    try:
        descriptor = os.open(companion, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                             | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_BINARY', 0))
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise SaveError('Steam owner metadata must be an ordinary separate copy.')
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            raw = stream.read(MAX_OWNER_SIZE + 1)
            after = os.fstat(stream.fileno())
        current = companion.lstat()
        if (stat.S_ISLNK(current.st_mode) or current.st_nlink != 1
                or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                != (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)):
            raise SaveError('Steam owner metadata changed while being read; reopen the copy.')
        _account(raw)
        return raw
    except OSError:
        raise SaveError('Steam owner metadata is unavailable or is not a separate file.') from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def read_owner(save_path):
    """Read the original standard-named VDF next to an explicitly copied save."""
    companion = _sidecar(save_path)
    raw = _read(companion)
    if _sidecar(save_path) != companion:
        raise SaveError('Steam owner metadata changed while being read; reopen the copy.')
    return OwnerContext(companion, raw)


def validate_owner(context):
    """Require immutable original metadata immediately before a protected action."""
    if (type(context) is not OwnerContext or not isinstance(context.source, Path)
            or context.source.name.casefold() != OWNER_BASENAME):
        raise SaveError('The opened Steam owner context is invalid; reopen the copy.')
    _account(context.raw)
    current = read_owner(context.source.with_name('.koei-owner-context-copy'))
    if current.source != context.source or current.raw != context.raw:
        raise SaveError('The original Steam owner metadata changed; reopen the copy.')
    return context


def require_matching_owner(context, destination_save):
    """Require the same original private sidecar in a destination/backup bundle.

    The game adapter owns atomic save/backup operations and their hash bindings.
    It must repeat this check after backup immediately before writing game bytes.
    This helper neither generates nor copies owner metadata.
    """
    validate_owner(context)
    other = read_owner(destination_save)
    if other.raw != context.raw or other.basename != context.basename:
        raise SaveError('Keep the same original Steam owner metadata with the destination copy.')
    return other
