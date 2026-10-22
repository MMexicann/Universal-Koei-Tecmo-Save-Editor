"""Safe registration and integrity checks for user-supplied replacements.

This module never opens a game archive or discovers files inside a game
installation. Callers select replacement files inside a mod project directory.
"""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path, PureWindowsPath
from typing import BinaryIO

from .models import AssetReplacement


RIGHTS_STATUSES = frozenset({"creator-owned", "permissive-license", "public-domain"})
HASH_CHUNK_SIZE = 1024 * 1024


class AssetSafetyError(ValueError):
    """Raised when a replacement source or target path is unsafe."""


def normalize_target_path(target_path: str) -> str:
    """Validate a replacement destination and return a zip-safe POSIX path."""
    if not isinstance(target_path, str):
        raise AssetSafetyError("The replacement target must be a text path.")
    if not target_path or target_path != target_path.strip():
        raise AssetSafetyError("The replacement target cannot be empty or padded with spaces.")
    if any(ord(character) < 32 or ord(character) == 127 for character in target_path):
        raise AssetSafetyError("The replacement target cannot contain control characters.")
    windows_path = PureWindowsPath(target_path)
    if target_path.startswith(("/", "\\")) or windows_path.is_absolute() or windows_path.drive:
        raise AssetSafetyError("The replacement target must be relative to the game content root.")
    normalized = target_path.replace("\\", "/")
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise AssetSafetyError("The replacement target cannot contain empty, current, or parent path segments.")
    if any(any(character in part for character in ':<>"|?*') for part in parts):
        raise AssetSafetyError("The replacement target contains a reserved path character.")
    return "/".join(parts)


def register_replacement(
    project_root: str | os.PathLike[str],
    source_file: str | os.PathLike[str],
    target_path: str,
    *,
    license: str,
    rights_status: str,
    attribution: str = "",
) -> AssetReplacement:
    """Create a manifest record for one replacement file inside a project.

    The asset's rights declaration is supplied by the user. Registration checks
    that it is an allowed value and records it; it cannot verify ownership.
    """
    source, relative_source = _resolve_project_file(project_root, source_file)
    target = normalize_target_path(target_path)
    if not isinstance(rights_status, str) or rights_status not in RIGHTS_STATUSES:
        choices = ", ".join(sorted(RIGHTS_STATUSES))
        raise AssetSafetyError(f"Rights status must be explicitly declared as one of: {choices}.")
    if not isinstance(license, str) or not license.strip():
        raise AssetSafetyError("A license or rights label is required for each replacement.")
    if not isinstance(attribution, str):
        raise AssetSafetyError("Attribution must be text.")
    if rights_status == "permissive-license" and not attribution.strip():
        raise AssetSafetyError("Permissively licensed replacements require attribution details.")
    digest = _hash_open_project_file(source)
    return AssetReplacement(
        source_path=relative_source.as_posix(),
        target_path=target,
        sha256=digest,
        license=license.strip(),
        attribution=attribution.strip(),
        rights_status=rights_status,
    )


def verify_replacement(
    project_root: str | os.PathLike[str], replacement: AssetReplacement
) -> str:
    """Re-hash a replacement and reject missing, changed, or unsafe sources."""
    if not isinstance(replacement, AssetReplacement):
        raise AssetSafetyError("A typed AssetReplacement record is required.")
    _validate_rights(replacement.rights_status, replacement.license, replacement.attribution)
    normalize_target_path(replacement.target_path)
    source, _relative_source = _resolve_project_file(project_root, replacement.source_path)
    digest = _hash_open_project_file(source)
    if digest.casefold() != replacement.sha256.casefold():
        raise AssetSafetyError(
            f"Replacement source changed after registration: {replacement.source_path}"
        )
    return digest


def read_verified_replacement(
    project_root: str | os.PathLike[str],
    replacement: AssetReplacement,
    *,
    max_bytes: int | None = None,
) -> bytes:
    """Read and verify a replacement through one descriptor before returning it.

    The digest is calculated from the bytes read from the same open file
    descriptor. Packaging callers therefore do not need a separate hash-then-
    reopen sequence that could package content changed between those steps.
    """
    if not isinstance(replacement, AssetReplacement):
        raise AssetSafetyError("A typed AssetReplacement record is required.")
    if max_bytes is not None and (type(max_bytes) is not int or max_bytes < 0):
        raise ValueError("max_bytes must be a nonnegative integer.")
    _validate_rights(replacement.rights_status, replacement.license, replacement.attribution)
    normalize_target_path(replacement.target_path)
    source, _relative_source = _resolve_project_file(project_root, replacement.source_path)
    data, digest = _read_and_hash_open_project_file(source, max_bytes=max_bytes)
    if digest.casefold() != replacement.sha256.casefold():
        raise AssetSafetyError(
            f"Replacement source changed after registration: {replacement.source_path}"
        )
    return data


def copy_verified_replacement(
    project_root: str | os.PathLike[str],
    replacement: AssetReplacement,
    destination: BinaryIO,
    *,
    max_bytes: int | None = None,
) -> tuple[str, int]:
    """Copy and hash one replacement through the same opened source descriptor."""
    if not isinstance(replacement, AssetReplacement):
        raise AssetSafetyError("A typed AssetReplacement record is required.")
    if max_bytes is not None and (type(max_bytes) is not int or max_bytes < 0):
        raise ValueError("max_bytes must be a nonnegative integer.")
    _validate_rights(replacement.rights_status, replacement.license, replacement.attribution)
    normalize_target_path(replacement.target_path)
    source, _relative_source = _resolve_project_file(project_root, replacement.source_path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(source, flags)
    except OSError as error:
        raise AssetSafetyError("Replacement source could not be opened safely.") from error
    digest = hashlib.sha256()
    total = 0
    try:
        with os.fdopen(descriptor, "rb") as file:
            if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                raise AssetSafetyError("Replacement sources must be regular files.")
            while chunk := file.read(HASH_CHUNK_SIZE):
                total += len(chunk)
                if max_bytes is not None and total > max_bytes:
                    raise AssetSafetyError(f"Replacement is larger than the {max_bytes} byte safety limit.")
                destination.write(chunk)
                digest.update(chunk)
    except OSError as error:
        raise AssetSafetyError("Replacement source could not be copied safely.") from error
    actual_digest = digest.hexdigest()
    if actual_digest.casefold() != replacement.sha256.casefold():
        raise AssetSafetyError(f"Replacement source changed after registration: {replacement.source_path}")
    return actual_digest, total


def hash_project_file(
    project_root: str | os.PathLike[str], source_file: str | os.PathLike[str]
) -> tuple[str, str]:
    """Return the normalized project-relative source path and its SHA-256."""
    source, relative_source = _resolve_project_file(project_root, source_file)
    return relative_source.as_posix(), _hash_open_project_file(source)


def _validate_rights(rights_status: str, license: str, attribution: str) -> None:
    if rights_status not in RIGHTS_STATUSES:
        raise AssetSafetyError("The replacement has an unsupported or missing rights status.")
    if not isinstance(license, str) or not license.strip():
        raise AssetSafetyError("A license or rights label is required for each replacement.")
    if not isinstance(attribution, str):
        raise AssetSafetyError("Attribution must be text.")
    if rights_status == "permissive-license" and not attribution.strip():
        raise AssetSafetyError("Permissively licensed replacements require attribution details.")


def _resolve_project_file(
    project_root: str | os.PathLike[str], source_file: str | os.PathLike[str]
) -> tuple[Path, Path]:
    try:
        root_input = Path(project_root).expanduser()
        root_info = root_input.lstat()
        if _is_link_or_reparse_point(root_info):
            raise AssetSafetyError("The selected project root cannot be a symbolic link or junction.")
        root = root_input.resolve(strict=True)
    except AssetSafetyError:
        raise
    except (OSError, RuntimeError) as error:
        raise AssetSafetyError("The selected project directory does not exist.") from error
    if not root.is_dir():
        raise AssetSafetyError("The selected project root must be a directory.")

    raw_source = Path(source_file).expanduser()
    if not raw_source.parts:
        raise AssetSafetyError("Choose a replacement file inside the project.")
    if ".." in raw_source.parts:
        raise AssetSafetyError("Replacement source paths cannot contain parent traversal.")
    candidate = raw_source if raw_source.is_absolute() else root / raw_source
    try:
        lexical = Path(os.path.abspath(candidate))
        relative = _relative_path_by_identity(root, lexical)
    except (OSError, ValueError) as error:
        raise AssetSafetyError("Replacement files must be inside the selected project directory.") from error
    if not relative.parts:
        raise AssetSafetyError("A replacement source must be a file inside the project directory.")

    current = root
    for part in relative.parts:
        current = current / part
        try:
            source_info = current.lstat()
        except OSError as error:
            raise AssetSafetyError(f"Replacement source is missing: {relative.as_posix()}") from error
        if _is_link_or_reparse_point(source_info):
            raise AssetSafetyError("Replacement paths cannot pass through symbolic links or junctions.")

    try:
        resolved = candidate.resolve(strict=True)
        resolved_relative = _relative_path_by_identity(root, resolved)
    except (OSError, RuntimeError, ValueError) as error:
        raise AssetSafetyError("Replacement files must resolve inside the selected project directory.") from error
    if not stat.S_ISREG(resolved.stat().st_mode):
        raise AssetSafetyError("Replacement sources must be regular files.")
    return resolved, resolved_relative


def _relative_path_by_identity(root: Path, candidate: Path) -> Path:
    """Return a path below root, tolerating filesystem aliases such as Windows 8.3 names.

    pathlib's lexical relative check can reject two paths that refer to the
    same directory when one uses a Windows short name. Walk the candidate's
    parents by filesystem identity instead, then keep the existing lstat walk
    below root responsible for rejecting symlink traversal.
    """
    parts: list[str] = []
    current = candidate
    while True:
        try:
            same_as_root = os.path.samefile(current, root)
        except FileNotFoundError:
            same_as_root = False
        except OSError as error:
            raise ValueError("Could not safely establish project path containment.") from error
        if same_as_root:
            try:
                current_info = current.lstat()
            except OSError as error:
                raise ValueError("Could not safely inspect the selected project path.") from error
            if _is_link_or_reparse_point(current_info):
                raise ValueError("A symbolic link cannot stand in for the project root.")
            return Path(*reversed(parts))

        parent = current.parent
        if parent == current:
            break
        parts.append(current.name)
        current = parent

    raise ValueError("Path is not below the selected project directory.")


def _is_link_or_reparse_point(info: os.stat_result) -> bool:
    if stat.S_ISLNK(info.st_mode):
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(info, "st_file_attributes", 0) & reparse_flag)


def _hash_open_project_file(source: Path) -> str:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(source, flags)
    except OSError as error:
        raise AssetSafetyError("Replacement source could not be opened safely.") from error
    digest = hashlib.sha256()
    try:
        with os.fdopen(descriptor, "rb") as file:
            if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                raise AssetSafetyError("Replacement sources must be regular files.")
            while chunk := file.read(HASH_CHUNK_SIZE):
                digest.update(chunk)
    except OSError as error:
        raise AssetSafetyError("Replacement source could not be read safely.") from error
    return digest.hexdigest()


def _read_and_hash_open_project_file(source: Path, *, max_bytes: int | None = None) -> tuple[bytes, str]:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(source, flags)
    except OSError as error:
        raise AssetSafetyError("Replacement source could not be opened safely.") from error
    digest = hashlib.sha256()
    content = bytearray()
    try:
        with os.fdopen(descriptor, "rb") as file:
            if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                raise AssetSafetyError("Replacement sources must be regular files.")
            while chunk := file.read(HASH_CHUNK_SIZE):
                if max_bytes is not None and len(content) + len(chunk) > max_bytes:
                    raise AssetSafetyError(f"Replacement is larger than the {max_bytes} byte safety limit.")
                content.extend(chunk)
                digest.update(chunk)
    except OSError as error:
        raise AssetSafetyError("Replacement source could not be read safely.") from error
    return bytes(content), digest.hexdigest()
