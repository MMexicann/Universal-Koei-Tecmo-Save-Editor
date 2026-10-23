"""Compare immutable game-install snapshots against explicit requirements.

This module deliberately does not discover installations, inspect archive bytes,
or manage mods. The Tracker owns installation discovery and bounded Steam build
metadata; it does not currently hand off the product version or this schema's
file/archive/format inventory arrays. Snapshot fields are explicit inputs.
Compatibility requirements are a separate optional input contract; the current
Mod Manager does not generate them automatically. Reports describe evidence without claiming
that a hash change proves incompatibility.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new


SNAPSHOT_SCHEMA_ID = "org.koei-tecmo.game-install-snapshot"
REQUIREMENTS_SCHEMA_ID = "org.koei-tecmo.compatibility-requirements"
REPORT_SCHEMA_ID = "org.koei-tecmo.game-compatibility-report"
SCHEMA_VERSION = 1
_HEX_256 = re.compile(r"^[0-9a-fA-F]{64}$")
_HEX_32 = re.compile(r"^[0-9a-fA-F]{1,8}$")
_MAX_JSON_BYTES = 64 * 1024 * 1024
_MAX_JSON_NESTING = 256
_KINDS = ("mods", "tools", "saves")
_ARCHIVE_STATUSES = ("parsed", "unsupported", "malformed")
_UNKNOWN_EVIDENCE_VALUES = {"unknown", "unavailable", "unverified", "n/a", "none", "null", "?"}


class CompatibilityInputError(ValueError):
    """Raised when a snapshot or requirements document violates its schema."""


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CompatibilityInputError(f"Duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _check_json_nesting(raw: str, source: Path) -> None:
    """Reject excessive container depth consistently across JSON decoders."""
    closing: list[str] = []
    in_string = False
    escaped = False
    for character in raw:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
        elif character in "[{":
            closing.append("]" if character == "[" else "}")
            if len(closing) > _MAX_JSON_NESTING:
                raise CompatibilityInputError(
                    f"JSON input {source.name!r} exceeds the {_MAX_JSON_NESTING}-level nesting limit."
                )
        elif character in "]}" and closing and closing[-1] == character:
            closing.pop()


def load_json(path: str | Path) -> Any:
    """Load one UTF-8 JSON document, rejecting duplicate keys and huge inputs."""
    source = Path(path)
    descriptor: int | None = None
    try:
        if not stat.S_ISREG(source.stat().st_mode):
            raise CompatibilityInputError(
                f"JSON input {source.name!r} must be a regular file."
            )
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(source, flags)
        stream = os.fdopen(descriptor, "rb")
        descriptor = None  # The stream now owns the descriptor.
        with stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise CompatibilityInputError(
                    f"JSON input {source.name!r} must be a regular file."
                )
            raw_bytes = stream.read(_MAX_JSON_BYTES + 1)
    except CompatibilityInputError:
        raise
    except OSError as exc:
        raise CompatibilityInputError(f"Cannot read JSON input {source.name!r}: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if len(raw_bytes) > _MAX_JSON_BYTES:
        raise CompatibilityInputError(
            f"JSON input {source.name!r} exceeds the {_MAX_JSON_BYTES}-byte limit."
        )
    try:
        raw = raw_bytes.decode("utf-8-sig")
    except UnicodeError as exc:
        raise CompatibilityInputError(f"Cannot read UTF-8 JSON input {source.name!r}: {exc}") from exc
    _check_json_nesting(raw, source)
    try:
        return json.loads(raw, object_pairs_hook=_object_without_duplicate_keys)
    except CompatibilityInputError:
        # Preserve the more specific duplicate-key failure raised by the hook.
        raise
    except json.JSONDecodeError as exc:
        raise CompatibilityInputError(
            f"Invalid JSON in {source.name!r} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except (ValueError, RecursionError) as exc:
        raise CompatibilityInputError(f"Invalid JSON in {source.name!r}: {exc}") from exc


def _require_mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CompatibilityInputError(f"{where} must be a JSON object.")
    return value


def _require_string(value: Any, where: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise CompatibilityInputError(f"{where} must be a non-empty string.")
    if any(unicodedata.category(character) in ("Cc", "Cs", "Zl", "Zp") for character in value):
        raise CompatibilityInputError(f"{where} must not contain control, surrogate, or line-separator characters.")
    return value


def _is_unknown_evidence(value: str | None) -> bool:
    return value is not None and value.strip().casefold() in _UNKNOWN_EVIDENCE_VALUES


def _require_non_path_text(value: Any, where: str) -> str:
    text = _require_string(value, where)
    # These fields are labels, never absolute install paths. Namespaced IDs may
    # contain separators, so reject only absolute POSIX/Windows path prefixes.
    if text.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", text):
        raise CompatibilityInputError(f"{where} must not be an absolute path.")
    return text


def _require_int(value: Any, where: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise CompatibilityInputError(f"{where} must be an integer greater than or equal to {minimum}.")
    return value


def _safe_relative_path(value: Any, where: str) -> str:
    path = _require_string(value, where)
    if "\\" in path or path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise CompatibilityInputError(f"{where} must be a relative POSIX path.")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise CompatibilityInputError(f"{where} must not contain empty, '.' or '..' path components.")
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or parsed.as_posix() != path:
        raise CompatibilityInputError(f"{where} must be a normalized relative POSIX path.")
    return path


def _optional_sha256(value: Any, where: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _HEX_256.fullmatch(value):
        raise CompatibilityInputError(f"{where} must be a 64-character SHA-256 hex string or null.")
    return value.lower()


def _optional_crc32(value: Any, where: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        if not 0 <= value <= 0xFFFFFFFF:
            raise CompatibilityInputError(f"{where} must be a 32-bit CRC value.")
        return f"{value:08x}"
    if isinstance(value, str) and _HEX_32.fullmatch(value):
        return value.lower().zfill(8)
    raise CompatibilityInputError(f"{where} must be a 32-bit CRC integer, up to 8 hex digits, or null.")


def _validate_snapshot(value: Any, label: str) -> dict[str, Any]:
    raw = _require_mapping(value, label)
    if raw.get("schema_id") != SNAPSHOT_SCHEMA_ID:
        raise CompatibilityInputError(f"{label}.schema_id must be {SNAPSHOT_SCHEMA_ID!r}.")
    if raw.get("schema_version") != SCHEMA_VERSION or isinstance(raw.get("schema_version"), bool):
        raise CompatibilityInputError(f"{label}.schema_version must be {SCHEMA_VERSION}.")

    game_id = _require_non_path_text(raw.get("game_id"), f"{label}.game_id")
    platform_id = _require_non_path_text(raw.get("platform_id"), f"{label}.platform_id")

    version_raw = _require_mapping(raw.get("version"), f"{label}.version")
    version = {
        "value": _require_non_path_text(version_raw.get("value"), f"{label}.version.value"),
        "source": _require_non_path_text(version_raw.get("source"), f"{label}.version.source"),
    }
    if "build_id" in version_raw and version_raw["build_id"] is not None:
        version["build_id"] = _require_non_path_text(version_raw["build_id"], f"{label}.version.build_id")

    captured_at = None
    if "captured_at" in raw and raw["captured_at"] is not None:
        captured_at_text = _require_string(raw["captured_at"], f"{label}.captured_at")
        try:
            captured_at_value = datetime.fromisoformat(captured_at_text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CompatibilityInputError(
                f"{label}.captured_at must be a timezone-aware ISO-8601 date-time."
            ) from exc
        if captured_at_value.tzinfo is None or captured_at_value.utcoffset() is None:
            raise CompatibilityInputError(
                f"{label}.captured_at must include a timezone offset."
            )
        captured_at = captured_at_value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    files_raw = raw.get("files")
    if not isinstance(files_raw, list):
        raise CompatibilityInputError(f"{label}.files must be an array.")
    files: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(files_raw):
        where = f"{label}.files[{index}]"
        item = _require_mapping(item, where)
        relative_path = _safe_relative_path(item.get("relative_path"), f"{where}.relative_path")
        if relative_path in files:
            raise CompatibilityInputError(f"{label}.files contains duplicate path {relative_path!r}.")
        files[relative_path] = {
            "relative_path": relative_path,
            "size_bytes": _require_int(item.get("size_bytes"), f"{where}.size_bytes"),
            "sha256": _optional_sha256(
                item.get("sha256") if "sha256" in item else "__missing__",
                f"{where}.sha256",
            ),
        }

    archives_raw = raw.get("archives")
    if not isinstance(archives_raw, list):
        raise CompatibilityInputError(f"{label}.archives must be an array.")
    archives: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(archives_raw):
        where = f"{label}.archives[{index}]"
        item = _require_mapping(item, where)
        relative_path = _safe_relative_path(item.get("relative_path"), f"{where}.relative_path")
        if relative_path in archives:
            raise CompatibilityInputError(f"{label}.archives contains duplicate path {relative_path!r}.")
        format_id_raw = item.get("format_id")
        format_id = None if format_id_raw is None else _require_non_path_text(format_id_raw, f"{where}.format_id")
        status = item.get("status")
        if status not in _ARCHIVE_STATUSES:
            raise CompatibilityInputError(
                f"{where}.status must be one of {', '.join(_ARCHIVE_STATUSES)}."
            )
        entries_raw = item.get("entries")
        if not isinstance(entries_raw, list):
            raise CompatibilityInputError(f"{where}.entries must be an array.")
        entries: dict[str, dict[str, Any]] = {}
        for entry_index, entry in enumerate(entries_raw):
            entry_where = f"{where}.entries[{entry_index}]"
            entry = _require_mapping(entry, entry_where)
            entry_path = _safe_relative_path(entry.get("path"), f"{entry_where}.path")
            if entry_path in entries:
                raise CompatibilityInputError(f"{where}.entries contains duplicate path {entry_path!r}.")
            normalized_entry = {
                "path": entry_path,
                "size_bytes": _require_int(entry.get("size_bytes"), f"{entry_where}.size_bytes"),
                "compressed_size_bytes": (
                    None if entry.get("compressed_size_bytes") is None else
                    _require_int(entry["compressed_size_bytes"], f"{entry_where}.compressed_size_bytes")
                ),
                "crc32": _optional_crc32(entry.get("crc32"), f"{entry_where}.crc32"),
                "sha256": _optional_sha256(entry.get("sha256"), f"{entry_where}.sha256"),
            }
            entries[entry_path] = normalized_entry
        archives[relative_path] = {
            "relative_path": relative_path,
            "format_id": format_id,
            "status": status,
            "entries": entries,
        }

    formats_raw = raw.get("formats")
    if not isinstance(formats_raw, list):
        raise CompatibilityInputError(f"{label}.formats must be an array.")
    formats: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(formats_raw):
        where = f"{label}.formats[{index}]"
        item = _require_mapping(item, where)
        format_id = _require_non_path_text(item.get("id"), f"{where}.id")
        if format_id in formats:
            raise CompatibilityInputError(f"{label}.formats contains duplicate id {format_id!r}.")
        revision_raw = item.get("revision")
        revision = None if revision_raw is None else _require_non_path_text(revision_raw, f"{where}.revision")
        evidence_raw = item.get("evidence_paths")
        if not isinstance(evidence_raw, list):
            raise CompatibilityInputError(f"{where}.evidence_paths must be an array.")
        evidence_paths = [_safe_relative_path(path, f"{where}.evidence_paths[]") for path in evidence_raw]
        if len(set(evidence_paths)) != len(evidence_paths):
            raise CompatibilityInputError(f"{where}.evidence_paths contains duplicate paths.")
        evidence_paths.sort()
        confidence_raw = item.get("confidence")
        if confidence_raw is not None and not isinstance(confidence_raw, (str, int, float)):
            raise CompatibilityInputError(f"{where}.confidence must be a string, number, or null.")
        if isinstance(confidence_raw, bool):
            raise CompatibilityInputError(f"{where}.confidence must not be a boolean.")
        if isinstance(confidence_raw, (int, float)) and not 0.0 <= confidence_raw <= 1.0:
            raise CompatibilityInputError(f"{where}.confidence as a number must be between 0 and 1.")
        if isinstance(confidence_raw, str):
            confidence_raw = _require_non_path_text(confidence_raw, f"{where}.confidence")
        formats[format_id] = {
            "id": format_id,
            "revision": revision,
            "evidence_paths": evidence_paths,
            "confidence": confidence_raw,
        }

    normalized = {
        "game_id": game_id,
        "platform_id": platform_id,
        "version": version,
        "files": files,
        "archives": archives,
        "formats": formats,
    }
    if captured_at is not None:
        normalized["captured_at"] = captured_at
    return normalized


def _validate_requirements(value: Any) -> list[dict[str, Any]]:
    raw = _require_mapping(value, "requirements")
    if raw.get("schema_id") != REQUIREMENTS_SCHEMA_ID:
        raise CompatibilityInputError(f"requirements.schema_id must be {REQUIREMENTS_SCHEMA_ID!r}.")
    if raw.get("schema_version") != SCHEMA_VERSION or isinstance(raw.get("schema_version"), bool):
        raise CompatibilityInputError(f"requirements.schema_version must be {SCHEMA_VERSION}.")
    rows = raw.get("requirements")
    if not isinstance(rows, list):
        raise CompatibilityInputError("requirements.requirements must be an array.")
    seen_ids: set[str] = set()
    result: list[dict[str, Any]] = []
    for index, item in enumerate(rows):
        where = f"requirements.requirements[{index}]"
        item = _require_mapping(item, where)
        requirement_id = _require_non_path_text(item.get("id"), f"{where}.id")
        if requirement_id in seen_ids:
            raise CompatibilityInputError(f"requirements contains duplicate id {requirement_id!r}.")
        seen_ids.add(requirement_id)
        kind = item.get("kind")
        if kind not in _KINDS:
            raise CompatibilityInputError(f"{where}.kind must be one of {', '.join(_KINDS)}.")
        requirement = {
            "id": requirement_id,
            "name": _require_non_path_text(item.get("name"), f"{where}.name"),
            "kind": kind,
            "game_id": _require_non_path_text(item.get("game_id"), f"{where}.game_id"),
            "platform_id": _require_non_path_text(item.get("platform_id"), f"{where}.platform_id"),
        }

        for field in ("supported_versions", "supported_build_ids"):
            allowlist_raw = item.get(field)
            if allowlist_raw is None:
                requirement[field] = None
                continue
            if not isinstance(allowlist_raw, list):
                raise CompatibilityInputError(f"{where}.{field} must be an array when provided.")
            if not allowlist_raw:
                raise CompatibilityInputError(f"{where}.{field} must not be an empty allowlist.")
            allowlist = [_require_non_path_text(value, f"{where}.{field}[]") for value in allowlist_raw]
            if len(set(allowlist)) != len(allowlist):
                raise CompatibilityInputError(f"{where}.{field} contains duplicate values.")
            requirement[field] = sorted(allowlist)

        required_files_raw = item.get("required_files", [])
        if not isinstance(required_files_raw, list):
            raise CompatibilityInputError(f"{where}.required_files must be an array.")
        required_files: dict[str, dict[str, Any]] = {}
        for req_index, file_item in enumerate(required_files_raw):
            req_where = f"{where}.required_files[{req_index}]"
            file_item = _require_mapping(file_item, req_where)
            path = _safe_relative_path(file_item.get("relative_path"), f"{req_where}.relative_path")
            if path in required_files:
                raise CompatibilityInputError(f"{where}.required_files contains duplicate path {path!r}.")
            digest = _optional_sha256(file_item.get("sha256"), f"{req_where}.sha256")
            if digest is None:
                raise CompatibilityInputError(f"{req_where}.sha256 must not be null.")
            required_files[path] = {"relative_path": path, "sha256": digest}
        requirement["required_files"] = required_files

        required_formats_raw = item.get("required_formats", [])
        if not isinstance(required_formats_raw, list):
            raise CompatibilityInputError(f"{where}.required_formats must be an array.")
        required_formats: dict[str, dict[str, Any]] = {}
        for req_index, format_item in enumerate(required_formats_raw):
            req_where = f"{where}.required_formats[{req_index}]"
            format_item = _require_mapping(format_item, req_where)
            format_id = _require_non_path_text(format_item.get("id"), f"{req_where}.id")
            if format_id in required_formats:
                raise CompatibilityInputError(f"{where}.required_formats contains duplicate id {format_id!r}.")
            revision_raw = format_item.get("revision")
            revision = None if revision_raw is None else _require_non_path_text(revision_raw, f"{req_where}.revision")
            required_formats[format_id] = {"id": format_id, "revision": revision}
        requirement["required_formats"] = required_formats

        archive_entries_raw = item.get("required_archive_entries", [])
        if not isinstance(archive_entries_raw, list):
            raise CompatibilityInputError(f"{where}.required_archive_entries must be an array.")
        required_archive_entries: dict[tuple[str, str], dict[str, Any]] = {}
        for req_index, entry_item in enumerate(archive_entries_raw):
            req_where = f"{where}.required_archive_entries[{req_index}]"
            entry_item = _require_mapping(entry_item, req_where)
            archive_path = _safe_relative_path(entry_item.get("relative_path"), f"{req_where}.relative_path")
            entry_path = _safe_relative_path(entry_item.get("path"), f"{req_where}.path")
            key = (archive_path, entry_path)
            if key in required_archive_entries:
                raise CompatibilityInputError(f"{where}.required_archive_entries contains duplicate {key!r}.")
            format_id_raw = entry_item.get("format_id")
            format_id = None if format_id_raw is None else _require_non_path_text(format_id_raw, f"{req_where}.format_id")
            digest = _optional_sha256(entry_item.get("sha256"), f"{req_where}.sha256")
            required_archive_entries[key] = {
                "relative_path": archive_path,
                "path": entry_path,
                "format_id": format_id,
                "sha256": digest,
            }
        requirement["required_archive_entries"] = required_archive_entries
        result.append(requirement)
    return result


def _file_comparison(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    old_files = before["files"]
    new_files = after["files"]
    added = [dict(new_files[path]) for path in sorted(new_files.keys() - old_files.keys())]
    removed = [dict(old_files[path]) for path in sorted(old_files.keys() - new_files.keys())]
    modified: list[dict[str, Any]] = []
    unverified: list[dict[str, str]] = [
        {"relative_path": item["relative_path"], "reason": f"sha256_missing_for_{action}_file"}
        for action, items in (("added", added), ("removed", removed))
        for item in items
        if item["sha256"] is None
    ]
    unchanged_count = 0
    for path in sorted(old_files.keys() & new_files.keys()):
        old = old_files[path]
        new = new_files[path]
        fields: list[str] = []
        if old["size_bytes"] != new["size_bytes"]:
            fields.append("size_bytes")
        old_hash, new_hash = old["sha256"], new["sha256"]
        if old_hash is not None and new_hash is not None:
            if old_hash != new_hash:
                fields.append("sha256")
            elif old["size_bytes"] != new["size_bytes"]:
                # Identical content digests cannot describe two different byte
                # lengths. Keep the size delta visible but flag the evidence as
                # inconsistent rather than treating the digest as conclusive.
                unverified.append({"relative_path": path, "reason": "sha256_size_conflict"})
        elif old_hash != new_hash:
            unverified.append({"relative_path": path, "reason": "sha256_missing_on_one_side"})
        elif old_hash is None:
            unverified.append({"relative_path": path, "reason": "sha256_missing_on_both_sides"})
        if fields:
            modified.append({
                "relative_path": path,
                "before": {"size_bytes": old["size_bytes"], "sha256": old_hash},
                "after": {"size_bytes": new["size_bytes"], "sha256": new_hash},
                "changed_fields": fields,
                "verification": (
                    "inconsistent_metadata"
                    if old_hash is not None and old_hash == new_hash and old["size_bytes"] != new["size_bytes"]
                    else "sha256" if old_hash is not None and new_hash is not None
                    else "size_or_partial_hash"
                ),
            })
        elif old_hash is not None:
            unchanged_count += 1
        elif old["size_bytes"] == new["size_bytes"]:
            # Equal sizes with no digest are not proof that bytes are unchanged.
            continue
        else:
            # A size delta already appears in modified; retain the unknown digest note.
            continue
    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "unverified": unverified,
        "unchanged_count": unchanged_count,
    }


def _entry_comparison(old_entries: Mapping[str, Any], new_entries: Mapping[str, Any]) -> dict[str, Any]:
    added = [dict(new_entries[path]) for path in sorted(new_entries.keys() - old_entries.keys())]
    removed = [dict(old_entries[path]) for path in sorted(old_entries.keys() - new_entries.keys())]
    modified: list[dict[str, Any]] = []
    unverified_by_path: dict[str, str] = {}
    unchanged_count = 0
    for entry in added + removed:
        if entry["crc32"] is None and entry["sha256"] is None:
            unverified_by_path[entry["path"]] = "checksum_missing"
    for path in sorted(old_entries.keys() & new_entries.keys()):
        old, new = old_entries[path], new_entries[path]
        fields = ["size_bytes"] if old["size_bytes"] != new["size_bytes"] else []
        for field in ("compressed_size_bytes", "crc32", "sha256"):
            if old[field] is not None and new[field] is not None and old[field] != new[field]:
                fields.append(field)

        shared_checksum = (
            (old["sha256"] is not None and new["sha256"] is not None)
            or (old["crc32"] is not None and new["crc32"] is not None)
        )
        if (
            old["sha256"] is not None
            and old["sha256"] == new["sha256"]
            and old["size_bytes"] != new["size_bytes"]
        ):
            unverified_by_path[path] = "sha256_size_conflict"
        if (
            old["sha256"] is not None
            and old["sha256"] == new["sha256"]
            and old["crc32"] is not None
            and new["crc32"] is not None
            and old["crc32"] != new["crc32"]
        ):
            unverified_by_path[path] = "sha256_crc_conflict"
        if not shared_checksum:
            if (old["crc32"] is None and old["sha256"] is None) or (
                new["crc32"] is None and new["sha256"] is None
            ):
                unverified_by_path[path] = "checksum_missing"
            else:
                unverified_by_path[path] = "no_shared_checksum"
        if (old["compressed_size_bytes"] is None) != (new["compressed_size_bytes"] is None):
            unverified_by_path.setdefault(path, "compressed_size_missing_on_one_side")
        if fields:
            modified.append({
                "path": path,
                "before": {
                    field: old[field]
                    for field in ("size_bytes", "compressed_size_bytes", "crc32", "sha256")
                },
                "after": {
                    field: new[field]
                    for field in ("size_bytes", "compressed_size_bytes", "crc32", "sha256")
                },
                "changed_fields": fields,
            })
        elif shared_checksum:
            unchanged_count += 1
    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "unverified": [
            {"path": path, "reason": unverified_by_path[path]}
            for path in sorted(unverified_by_path)
        ],
        "unchanged_count": unchanged_count,
    }


def _empty_entry_comparison() -> dict[str, Any]:
    return {"added": [], "removed": [], "modified": [], "unverified": [], "unchanged_count": 0}


def _archive_member_inventory(archive: Mapping[str, Any], action: str) -> dict[str, Any]:
    if archive["status"] != "parsed":
        return _empty_entry_comparison()
    entries = [dict(archive["entries"][path]) for path in sorted(archive["entries"])]
    unverified = [
        {"path": entry["path"], "reason": "checksum_missing"}
        for entry in entries
        if entry["crc32"] is None and entry["sha256"] is None
    ]
    result = _empty_entry_comparison()
    result[action] = entries
    result["unverified"] = unverified
    return result


def _archive_analysis_status(archive: Mapping[str, Any]) -> str:
    if archive["status"] != "parsed" or archive["format_id"] is None:
        return "unknown"
    if any(
        entry["crc32"] is None and entry["sha256"] is None
        for entry in archive["entries"].values()
    ):
        return "unknown"
    return "complete"


def _archive_incomplete_reason(entry_rows: list[Mapping[str, Any]]) -> str:
    if any(row["reason"] in ("checksum_missing", "no_shared_checksum") for row in entry_rows):
        return "member_checksum_missing"
    if any(row["reason"] == "sha256_crc_conflict" for row in entry_rows):
        return "member_checksum_conflict"
    if any(row["reason"] == "sha256_size_conflict" for row in entry_rows):
        return "member_size_hash_conflict"
    return "member_metadata_incomplete"


def _archive_comparison(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    old_archives = before["archives"]
    new_archives = after["archives"]
    added: list[dict[str, Any]] = []
    for path in sorted(new_archives.keys() - old_archives.keys()):
        archive = new_archives[path]
        added.append({
            "relative_path": path,
            "format_id": archive["format_id"],
            "status": archive["status"],
            "analysis_status": _archive_analysis_status(archive),
            "entries": _archive_member_inventory(archive, "added"),
        })
    removed: list[dict[str, Any]] = []
    for path in sorted(old_archives.keys() - new_archives.keys()):
        archive = old_archives[path]
        removed.append({
            "relative_path": path,
            "format_id": archive["format_id"],
            "status": archive["status"],
            "analysis_status": _archive_analysis_status(archive),
            "entries": _archive_member_inventory(archive, "removed"),
        })
    changed: list[dict[str, Any]] = []
    unknown: list[dict[str, str]] = []
    for row in added + removed:
        if row["analysis_status"] == "unknown":
            if row["status"] == "malformed":
                reason = "archive_structure_unavailable"
            elif row["status"] == "unsupported":
                reason = "archive_format_unsupported"
            elif row["format_id"] is None:
                reason = "archive_format_id_missing"
            else:
                reason = None  # Parsed member metadata below identifies the incomplete evidence.
            if reason is not None:
                unknown.append({"relative_path": row["relative_path"], "reason": reason})
        if row["entries"]["unverified"]:
            unknown.append({
                "relative_path": row["relative_path"],
                "reason": _archive_incomplete_reason(row["entries"]["unverified"]),
            })
    unchanged_count = 0
    for path in sorted(old_archives.keys() & new_archives.keys()):
        old, new = old_archives[path], new_archives[path]
        format_changed = old["format_id"] != new["format_id"]
        status_changed = old["status"] != new["status"]
        if old["status"] != "parsed" or new["status"] != "parsed":
            reason = "archive_format_unsupported" if "unsupported" in (old["status"], new["status"]) else "archive_structure_unavailable"
            unknown.append({"relative_path": path, "reason": reason})
            if format_changed or status_changed:
                entries = _empty_entry_comparison()
                entries["observed_before"] = [
                    dict(old["entries"][member_path])
                    for member_path in sorted(old["entries"])
                ] if old["status"] == "parsed" else []
                entries["observed_after"] = [
                    dict(new["entries"][member_path])
                    for member_path in sorted(new["entries"])
                ] if new["status"] == "parsed" else []
                changed.append({
                    "relative_path": path,
                    "before": {"format_id": old["format_id"], "status": old["status"]},
                    "after": {"format_id": new["format_id"], "status": new["status"]},
                    "format_changed": format_changed,
                    "status_changed": status_changed,
                    "analysis_status": "unknown",
                    "entries": entries,
                })
            continue
        entries = _entry_comparison(old["entries"], new["entries"])
        is_changed = format_changed or any(entries[key] for key in ("added", "removed", "modified"))
        analysis_status = "complete"
        if old["format_id"] is None or new["format_id"] is None or entries["unverified"]:
            analysis_status = "unknown"
        if is_changed:
            changed.append({
                "relative_path": path,
                "before": {"format_id": old["format_id"], "status": old["status"]},
                "after": {"format_id": new["format_id"], "status": new["status"]},
                "format_changed": format_changed,
                "status_changed": status_changed,
                "analysis_status": analysis_status,
                "entries": entries,
            })
            if old["format_id"] is None or new["format_id"] is None:
                unknown.append({"relative_path": path, "reason": "archive_format_id_missing"})
            if entries["unverified"]:
                unknown.append({
                    "relative_path": path,
                    "reason": _archive_incomplete_reason(entries["unverified"]),
                })
        else:
            if analysis_status == "complete":
                unchanged_count += 1
            if old["format_id"] is None or new["format_id"] is None:
                unknown.append({"relative_path": path, "reason": "archive_format_id_missing"})
            if entries["unverified"]:
                unknown.append({
                    "relative_path": path,
                    "reason": _archive_incomplete_reason(entries["unverified"]),
                })
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unknown": unknown,
        "unchanged_count": unchanged_count,
    }


def _format_comparison(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    old_formats, new_formats = before["formats"], after["formats"]
    added = [dict(new_formats[format_id]) for format_id in sorted(new_formats.keys() - old_formats.keys())]
    removed = [dict(old_formats[format_id]) for format_id in sorted(old_formats.keys() - new_formats.keys())]
    changed: list[dict[str, Any]] = []
    unchanged_count = 0
    fields = ("revision", "evidence_paths", "confidence")
    for format_id in sorted(old_formats.keys() & new_formats.keys()):
        old, new = old_formats[format_id], new_formats[format_id]
        changed_fields = [field for field in fields if old[field] != new[field]]
        if changed_fields:
            changed.append({
                "id": format_id,
                "before": dict(old),
                "after": dict(new),
                "changed_fields": changed_fields,
            })
        else:
            unchanged_count += 1
    return {"added": added, "removed": removed, "changed": changed, "unchanged_count": unchanged_count}


def _evaluate_requirement(requirement: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    reasons: list[dict[str, str]] = []
    unknown = False
    declared_count = (
        len(requirement["required_files"])
        + len(requirement["required_formats"])
        + len(requirement["required_archive_entries"])
        + int(requirement["supported_versions"] is not None)
        + int(requirement["supported_build_ids"] is not None)
    )
    if declared_count == 0:
        return {"status": "unspecified", "reasons": []}

    version = snapshot["version"]
    supported_versions = requirement["supported_versions"]
    if supported_versions is not None:
        if _is_unknown_evidence(version["value"]):
            unknown = True
            reasons.append({"type": "supported_version_unknown", "candidate_value": version["value"]})
        elif version["value"] not in supported_versions:
            reasons.append({
                "type": "supported_version_not_listed",
                "candidate_value": version["value"],
                "supported_values": ",".join(supported_versions),
            })

    supported_build_ids = requirement["supported_build_ids"]
    if supported_build_ids is not None:
        build_id = version.get("build_id")
        if build_id is None or _is_unknown_evidence(build_id):
            unknown = True
            reasons.append({"type": "supported_build_id_unknown"})
        elif build_id not in supported_build_ids:
            reasons.append({
                "type": "supported_build_id_not_listed",
                "candidate_value": build_id,
                "supported_values": ",".join(supported_build_ids),
            })

    for path, expected in sorted(requirement["required_files"].items()):
        observed = snapshot["files"].get(path)
        if observed is None:
            reasons.append({"type": "required_file_missing", "path": path})
        elif observed["sha256"] is None:
            unknown = True
            reasons.append({"type": "required_file_hash_unknown", "path": path})
        elif observed["sha256"] != expected["sha256"]:
            reasons.append({"type": "required_file_hash_mismatch", "path": path})

    for format_id, expected in sorted(requirement["required_formats"].items()):
        observed = snapshot["formats"].get(format_id)
        if observed is None:
            reasons.append({"type": "required_format_missing", "format_id": format_id})
        elif expected["revision"] is not None:
            if observed["revision"] is None:
                unknown = True
                reasons.append({"type": "required_format_revision_unknown", "format_id": format_id})
            elif observed["revision"] != expected["revision"]:
                reasons.append({"type": "required_format_revision_mismatch", "format_id": format_id})

    for (archive_path, entry_path), expected in sorted(requirement["required_archive_entries"].items()):
        archive = snapshot["archives"].get(archive_path)
        if archive is None:
            reasons.append({
                "type": "required_archive_missing",
                "relative_path": archive_path,
                "entry_path": entry_path,
            })
            continue
        if archive["status"] != "parsed":
            unknown = True
            reasons.append({
                "type": "required_archive_structure_unknown",
                "relative_path": archive_path,
                "entry_path": entry_path,
                "archive_status": archive["status"],
            })
            continue
        if expected["format_id"] is not None:
            if archive["format_id"] is None:
                unknown = True
                reasons.append({
                    "type": "required_archive_format_unknown",
                    "relative_path": archive_path,
                    "entry_path": entry_path,
                })
            elif archive["format_id"] != expected["format_id"]:
                reasons.append({
                    "type": "required_archive_format_mismatch",
                    "relative_path": archive_path,
                    "entry_path": entry_path,
                })
                continue
        entry = archive["entries"].get(entry_path)
        if entry is None:
            reasons.append({
                "type": "required_archive_entry_missing",
                "relative_path": archive_path,
                "entry_path": entry_path,
            })
        elif expected["sha256"] is not None:
            if entry["sha256"] is None:
                unknown = True
                reasons.append({
                    "type": "required_archive_entry_hash_unknown",
                    "relative_path": archive_path,
                    "entry_path": entry_path,
                })
            elif entry["sha256"] != expected["sha256"]:
                reasons.append({
                    "type": "required_archive_entry_hash_mismatch",
                    "relative_path": archive_path,
                    "entry_path": entry_path,
                })

    has_mismatch = any(
        "mismatch" in reason["type"]
        or "missing" in reason["type"]
        or reason["type"].endswith("_not_listed")
        for reason in reasons
    )
    if has_mismatch:
        status = "not_satisfied"
    elif unknown:
        status = "unknown"
    else:
        status = "satisfied"
    return {"status": status, "reasons": reasons}


def _impact_report(
    requirements: list[dict[str, Any]], before: Mapping[str, Any], after: Mapping[str, Any], changed: bool
) -> dict[str, Any]:
    matched = [
        requirement for requirement in requirements
        if requirement["game_id"] == after["game_id"] and requirement["platform_id"] == after["platform_id"]
    ]
    consumers: list[dict[str, Any]] = []
    for requirement in sorted(matched, key=lambda item: (item["kind"], item["id"])):
        old = _evaluate_requirement(requirement, before)
        new = _evaluate_requirement(requirement, after)
        if new["status"] == "satisfied":
            status = "improved" if old["status"] == "not_satisfied" else "requirements_satisfied"
        elif new["status"] == "not_satisfied":
            if old["status"] == "satisfied":
                status = "may_affect"
            elif old["status"] == "not_satisfied":
                status = "already_not_satisfied"
            else:
                status = "unknown"
        else:
            status = "unknown"
        consumers.append({
            "id": requirement["id"],
            "name": requirement["name"],
            "kind": requirement["kind"],
            "status": status,
            "baseline": old,
            "candidate": new,
        })

    by_kind: dict[str, dict[str, Any]] = {}
    for kind in _KINDS:
        rows = [consumer for consumer in consumers if consumer["kind"] == kind]
        counts = {status: sum(row["status"] == status for row in rows) for status in (
            "may_affect", "requirements_satisfied", "unknown", "already_not_satisfied", "improved"
        )}
        if counts["may_affect"]:
            kind_status = "may_affect"
        elif counts["unknown"]:
            kind_status = "unknown"
        elif counts["already_not_satisfied"]:
            kind_status = "already_not_satisfied"
        elif counts["requirements_satisfied"]:
            kind_status = "requirements_satisfied"
        elif counts["improved"]:
            kind_status = "improved"
        else:
            kind_status = "unknown" if changed else "unchanged"
        by_kind[kind] = {"status": kind_status, "requirement_count": len(rows), "counts": counts}

    if any(item["status"] == "may_affect" for item in consumers):
        status = "may_affect"
    elif not matched:
        status = "unknown" if changed else "unchanged"
    elif any(item["status"] == "unknown" for item in consumers):
        status = "unknown"
    elif any(item["status"] == "already_not_satisfied" for item in consumers):
        status = "requirements_not_satisfied_before_and_after"
    elif any(item["status"] == "improved" for item in consumers):
        status = "requirements_improved"
    else:
        status = "requirements_satisfied"

    return {
        "status": status,
        "requirements_evaluated": len(consumers),
        "by_kind": by_kind,
        "consumers": consumers,
        "interpretation": (
            "Requirement results describe declared fingerprints and format revisions. "
            "They do not prove that a game, mod, tool, or save will load successfully."
        ),
    }


def analyze_snapshots(
    before_snapshot: Mapping[str, Any],
    after_snapshot: Mapping[str, Any],
    requirements: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare two explicit game-install snapshots and optional requirements.

    Paths in the snapshots must be normalized relative POSIX paths. The report
    contains only relative paths and never includes an installation root.
    """
    before = _validate_snapshot(before_snapshot, "before")
    after = _validate_snapshot(after_snapshot, "after")
    if before["game_id"] != after["game_id"]:
        raise CompatibilityInputError("Snapshots must describe the same game_id.")
    if before["platform_id"] != after["platform_id"]:
        raise CompatibilityInputError("Snapshots must describe the same platform_id.")

    requirement_rows = [] if requirements is None else _validate_requirements(requirements)
    files = _file_comparison(before, after)
    archives = _archive_comparison(before, after)
    formats = _format_comparison(before, after)
    before_version = before["version"]
    after_version = after["version"]
    evidence_reasons: list[dict[str, str]] = []
    if _is_unknown_evidence(before_version["value"]):
        evidence_reasons.append({"type": "version_value_unknown", "side": "baseline"})
    if _is_unknown_evidence(after_version["value"]):
        evidence_reasons.append({"type": "version_value_unknown", "side": "candidate"})

    before_build_id = before_version.get("build_id")
    after_build_id = after_version.get("build_id")
    before_build_unknown = _is_unknown_evidence(before_build_id)
    after_build_unknown = _is_unknown_evidence(after_build_id)
    if before_build_unknown:
        evidence_reasons.append({"type": "build_id_unknown", "side": "baseline"})
    if after_build_unknown:
        evidence_reasons.append({"type": "build_id_unknown", "side": "candidate"})
    if (before_build_id is None) != (after_build_id is None):
        evidence_reasons.append({"type": "build_id_asymmetric"})

    version_values_known = not (
        _is_unknown_evidence(before_version["value"])
        or _is_unknown_evidence(after_version["value"])
    )
    build_values_known = (
        before_build_id is not None
        and after_build_id is not None
        and not before_build_unknown
        and not after_build_unknown
    )
    confirmed_version_delta = (
        version_values_known and before_version["value"] != after_version["value"]
    )
    confirmed_build_delta = build_values_known and before_build_id != after_build_id
    version_changed: bool | None
    if confirmed_version_delta or confirmed_build_delta:
        version_changed = True
    elif evidence_reasons:
        version_changed = None
    else:
        version_changed = False
    version = {
        "changed": version_changed,
        "status": "unknown" if version_changed is None else "changed" if version_changed else "unchanged",
        "before": dict(before["version"]),
        "after": dict(after["version"]),
        "source_changed": before["version"]["source"] != after["version"]["source"],
        "evidence_reasons": evidence_reasons,
    }
    has_changes = bool(
        version_changed is True
        or files["added"] or files["removed"] or files["modified"]
        or archives["added"] or archives["removed"] or archives["changed"]
        or formats["added"] or formats["removed"] or formats["changed"]
    )
    comparison_uncertain = bool(files["unverified"] or archives["unknown"] or evidence_reasons)
    impacts = _impact_report(requirement_rows, before, after, has_changes or comparison_uncertain)
    return {
        "schema_id": REPORT_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "game_id": before["game_id"],
        "platform_id": before["platform_id"],
        "version_change": version,
        "file_changes": files,
        "archive_changes": archives,
        "format_changes": formats,
        "impacts": impacts,
        "overall_status": impacts["status"],
        "evidence_status": "unknown" if comparison_uncertain else "complete",
        "provenance": {
            "baseline_captured_at": before.get("captured_at"),
            "candidate_captured_at": after.get("captured_at"),
        },
        "has_changes": has_changes,
    }


def _md_code(value: Any) -> str:
    text = "".join(
        " " if unicodedata.category(character) in ("Cc", "Cs", "Zl", "Zp") else character
        for character in str(value)
    )
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    escaped = escaped.replace("|", "\\|").replace("`", "&#96;")
    return f"`{escaped}`"


def _version_label(value: Mapping[str, Any]) -> str:
    text = str(value.get("value", "unknown"))
    if value.get("build_id"):
        text += f" (build {value['build_id']})"
    return text


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render a deterministic, human-readable Markdown compatibility report."""
    if report.get("schema_id") != REPORT_SCHEMA_ID or report.get("schema_version") != SCHEMA_VERSION:
        raise CompatibilityInputError("report is not a supported game-compatibility report.")
    version_change = report["version_change"]
    version_changed_label = (
        "unknown" if version_change["changed"] is None
        else "yes" if version_change["changed"]
        else "no"
    )
    version_evidence_lines = [
        f"- Version evidence uncertain: {reason['type']} ({reason.get('side', 'both')})."
        for reason in version_change["evidence_reasons"]
    ]
    provenance = report["provenance"]
    provenance_lines = []
    if provenance["baseline_captured_at"] is not None:
        provenance_lines.append(
            f"- Baseline snapshot captured: {_md_code(provenance['baseline_captured_at'])}"
        )
    if provenance["candidate_captured_at"] is not None:
        provenance_lines.append(
            f"- Candidate snapshot captured: {_md_code(provenance['candidate_captured_at'])}"
        )
    lines = [
        "# Koei Tecmo Game Patch Compatibility Report",
        "",
        f"- Game: {_md_code(report['game_id'])}",
        f"- Platform: {_md_code(report['platform_id'])}",
        f"- Baseline version: {_md_code(_version_label(version_change['before']))}",
        f"- Candidate version: {_md_code(_version_label(version_change['after']))}",
        f"- Version/build changed: {version_changed_label}",
        *version_evidence_lines,
        *provenance_lines,
        f"- Overall declared-requirement assessment: **{report['overall_status']}**",
        f"- Overall evidence status: **{report['evidence_status']}**",
        "",
        "A changed file hash or archive entry is evidence of a patch change; by itself it does not prove incompatibility.",
        "",
        "## File changes",
        "",
    ]
    files = report["file_changes"]
    lines.append(
        f"Added: {len(files['added'])}; removed: {len(files['removed'])}; "
        f"modified: {len(files['modified'])}; unchanged with hashes: {files['unchanged_count']}; "
        f"unverified: {len(files['unverified'])}."
    )
    for label in ("added", "removed"):
        for item in files[label]:
            lines.append(f"- {label.title()}: {_md_code(item['relative_path'])} ({item['size_bytes']} bytes)")
    for item in files["modified"]:
        lines.append(
            f"- Modified: {_md_code(item['relative_path'])}; fields: "
            f"{', '.join(item['changed_fields'])}; verification: {item['verification']}."
        )
    for item in files["unverified"]:
        lines.append(f"- Hash unknown: {_md_code(item['relative_path'])} ({item['reason']}).")
    if not any(files[key] for key in ("added", "removed", "modified", "unverified")):
        lines.append("- No file changes recorded.")

    lines.extend(["", "## Archive structure changes", ""])
    archives = report["archive_changes"]
    lines.append(
        f"Added: {len(archives['added'])}; removed: {len(archives['removed'])}; "
        f"changed: {len(archives['changed'])}; unchanged parsed: {archives['unchanged_count']}; "
        f"unknown: {len(archives['unknown'])}."
    )
    for label in ("added", "removed"):
        for item in archives[label]:
            lines.append(
                f"- Archive {label}: {_md_code(item['relative_path'])}; "
                f"format: {_md_code(item['format_id'] or 'unknown')}; analysis: {item['analysis_status']}."
            )
            for entry in item["entries"][label]:
                compressed = entry["compressed_size_bytes"]
                lines.append(
                    f"  - Member {label}: {_md_code(entry['path'])}; size {entry['size_bytes']} bytes; "
                    f"compressed size {compressed if compressed is not None else 'unknown'} bytes."
                )
            for entry in item["entries"]["unverified"]:
                lines.append(f"  - Member evidence unknown: {_md_code(entry['path'])} ({entry['reason']}).")
    for item in archives["changed"]:
        lines.append(
            f"- Archive changed: {_md_code(item['relative_path'])}; "
            f"format: {_md_code(item['before']['format_id'] or 'unknown')} → "
            f"{_md_code(item['after']['format_id'] or 'unknown')}; analysis: {item['analysis_status']}."
        )
        for label in ("added", "removed", "modified"):
            for entry in item["entries"][label]:
                if label == "modified":
                    before_entry, after_entry = entry["before"], entry["after"]
                    before_compressed = before_entry["compressed_size_bytes"]
                    after_compressed = after_entry["compressed_size_bytes"]
                    lines.append(
                        f"  - Entry modified: {_md_code(entry['path'])}; fields: "
                        f"{', '.join(entry['changed_fields'])}; compressed size "
                        f"{before_compressed if before_compressed is not None else 'unknown'} → "
                        f"{after_compressed if after_compressed is not None else 'unknown'} bytes."
                    )
                else:
                    compressed = entry["compressed_size_bytes"]
                    lines.append(
                        f"  - Entry {label}: {_md_code(entry['path'])}; size {entry['size_bytes']} bytes; "
                        f"compressed size {compressed if compressed is not None else 'unknown'} bytes."
                    )
        for side, label in (("observed_before", "baseline"), ("observed_after", "candidate")):
            for entry in item["entries"].get(side, []):
                lines.append(
                    f"  - Known {label} member: {_md_code(entry['path'])}; "
                    f"size {entry['size_bytes']} bytes."
                )
        for entry in item["entries"]["unverified"]:
            lines.append(f"  - Member evidence unknown: {_md_code(entry['path'])} ({entry['reason']}).")
    for item in archives["unknown"]:
        lines.append(f"- Structure unknown: {_md_code(item['relative_path'])} ({item['reason']}).")
    if not any(archives[key] for key in ("added", "removed", "changed", "unknown")):
        lines.append("- No archive changes recorded.")

    lines.extend(["", "## Supported format metadata", ""])
    formats = report["format_changes"]
    lines.append(
        f"Added: {len(formats['added'])}; removed: {len(formats['removed'])}; "
        f"changed: {len(formats['changed'])}; unchanged: {formats['unchanged_count']}."
    )
    for label in ("added", "removed"):
        for item in formats[label]:
            lines.append(
                f"- Format {label}: {_md_code(item['id'])}, revision "
                f"{_md_code(item['revision'] or 'unknown')} (evidence: "
                f"{', '.join(_md_code(path) for path in item['evidence_paths']) or 'none'})."
            )
    for item in formats["changed"]:
        lines.append(
            f"- Format changed: {_md_code(item['id'])}; fields: {', '.join(item['changed_fields'])}; "
            f"revision {_md_code(item['before']['revision'] or 'unknown')} → "
            f"{_md_code(item['after']['revision'] or 'unknown')}."
        )
    if not any(formats[key] for key in ("added", "removed", "changed")):
        lines.append("- No supported-format metadata changes recorded.")

    lines.extend(["", "## Mod, tool, and save requirements", ""])
    impacts = report["impacts"]
    lines.append(f"Requirements evaluated: {impacts['requirements_evaluated']}; assessment: **{impacts['status']}**.")
    for kind in _KINDS:
        row = impacts["by_kind"][kind]
        lines.append(
            f"- {kind.title()}: **{row['status']}**; {row['requirement_count']} requirement(s)."
        )
    for consumer in impacts["consumers"]:
        lines.append(f"- {_md_code(consumer['name'])} ({consumer['kind']}): **{consumer['status']}**.")
        for phase in ("baseline", "candidate"):
            for reason in consumer[phase]["reasons"]:
                location = reason.get("path") or reason.get("relative_path")
                if reason.get("entry_path"):
                    location = f"{location}!/{reason['entry_path']}" if location else reason["entry_path"]
                details = [
                    f"{key}={_md_code(value)}"
                    for key, value in sorted(reason.items())
                    if key not in ("type", "path", "relative_path", "entry_path")
                ]
                if location:
                    details.insert(0, f"path={_md_code(location)}")
                detail = f" ({'; '.join(details)})" if details else ""
                lines.append(f"  - {phase.title()}: {reason['type']}{detail}.")
    if not impacts["consumers"]:
        lines.append("- No matching explicit requirements were supplied; impact assessment is unknown when changes exist.")
    lines.extend(["", impacts["interpretation"], ""])
    return "\n".join(lines)


def _write_report(path: Path, content: str) -> None:
    try:
        atomic_new(content.encode("utf-8"), path)
    except (OSError, SaveError, UnicodeError) as exc:
        raise CompatibilityInputError(f"Cannot write report {path.name!r}: {exc}") from exc


def _paths_alias(left: Path, right: Path) -> bool:
    try:
        if left.resolve() == right.resolve():
            return True
    except (OSError, RuntimeError) as exc:
        raise CompatibilityInputError("Cannot safely resolve an input or report path.") from exc
    try:
        return left.samefile(right)
    except (FileNotFoundError, NotADirectoryError):
        return False
    except OSError as exc:
        raise CompatibilityInputError("Cannot safely check input and report path aliases.") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare two immutable Koei Tecmo game-install snapshots and explicit compatibility requirements."
    )
    parser.add_argument("before", help="Baseline game-install snapshot JSON")
    parser.add_argument("after", help="Candidate game-install snapshot JSON")
    parser.add_argument("--requirements", help="Optional compatibility-requirements JSON")
    parser.add_argument("--json-out", help="Write the machine-readable report to this path")
    parser.add_argument("--markdown-out", help="Write the readable report to this path")
    args = parser.parse_args(argv)

    try:
        input_paths = [Path(args.before), Path(args.after)]
        requirements_path = Path(args.requirements) if args.requirements else None
        if requirements_path:
            input_paths.append(requirements_path)
        output_paths = [Path(path) for path in (args.json_out, args.markdown_out) if path]
        if any(_paths_alias(output, source) for output in output_paths for source in input_paths):
            raise CompatibilityInputError("Report output paths must not overwrite an input snapshot or requirements file.")
        if any(
            _paths_alias(output_paths[left], output_paths[right])
            for left in range(len(output_paths))
            for right in range(left + 1, len(output_paths))
        ):
            raise CompatibilityInputError("JSON and Markdown outputs must use different paths.")

        before = load_json(args.before)
        after = load_json(args.after)
        requirement_data = load_json(requirements_path) if requirements_path else None
        report = analyze_snapshots(before, after, requirement_data)
        markdown = render_markdown(report)
        if args.json_out:
            _write_report(Path(args.json_out), json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n")
        if args.markdown_out:
            _write_report(Path(args.markdown_out), markdown)
        if not output_paths:
            sys.stdout.write(markdown)
        return 0
    except CompatibilityInputError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
