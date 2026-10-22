"""Build and verify reproducible mod archives from declared replacements."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
from typing import Any
import zipfile

from .asset_explorer import AssetSafetyError, copy_verified_replacement, normalize_target_path
from .models import ManifestError, ModManifest
from .project_manager import MANIFEST_FILENAME, load_project
from .validation import CompatibilityContext, ValidationReport, validate_manifest, validate_project


REPORT_FILENAME = "verification.json"
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_ASSET_BYTES = 256 * 1024 * 1024
MAX_PACKAGE_BYTES = 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200


class PackageError(ValueError):
    """Raised when a package cannot be built or verified safely."""


def build_package(
    project_dir: str | os.PathLike[str],
    output_file: str | os.PathLike[str],
    context: CompatibilityContext | None = None,
) -> dict[str, Any]:
    """Build a verified ZIP containing metadata and selected replacement files.

    Only the user-provided files referenced by the manifest are read. Original
    game files and other project files are never copied into the archive.
    Existing destinations are left untouched.
    """
    # load_project checks every path component before loading, so preserve the
    # caller's lexical path here instead of resolving away a selected symlink.
    root = Path(os.path.abspath(Path(project_dir).expanduser()))
    manifest = load_project(root)
    if context is None:
        raise PackageError("Choose a game, version, platform and installed mod list before packaging.")
    validation = validate_project(root, context)
    if not validation.valid:
        raise PackageError(_validation_message(validation))
    if not manifest.replacements:
        raise PackageError("Add at least one replacement file before creating a package.")

    seen: set[str] = set()
    replacements: list[tuple[str, Any]] = []
    packaged_replacements: list[dict[str, Any]] = []
    for replacement in manifest.replacements:
        try:
            target = normalize_target_path(replacement.target_path)
        except AssetSafetyError as error:
            raise PackageError(str(error)) from error
        package_path = f"replacements/{target}"
        if package_path.casefold() in seen:
            raise PackageError(f"Duplicate package target: {target}")
        seen.add(package_path.casefold())
        replacements.append((package_path, replacement))
        packaged_replacements.append({**replacement.to_dict(), "source_path": package_path})

    compatibility = validate_manifest(manifest, context)
    package_manifest = manifest.to_dict()
    package_manifest["replacements"] = packaged_replacements
    manifest_bytes = _json_bytes(package_manifest)
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise PackageError("Package manifest is larger than the 2 MiB safety limit.")
    replacements.sort(key=lambda item: item[0].casefold())

    destination = Path(output_file).expanduser()
    if not destination.is_absolute():
        destination = Path.cwd() / destination
    destination = Path(os.path.abspath(destination))
    _reject_symlink_components(destination.parent)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Package destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent, delete=False
        ) as temporary:
            temporary_name = temporary.name
        with zipfile.ZipFile(temporary_name, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            assets: list[dict[str, Any]] = []
            total_bytes = 0
            for name, replacement in replacements:
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                # Keep replacements uncompressed. Many texture/audio formats
                # are already compressed, and highly compressible inputs can
                # otherwise exceed the verifier's decompression-ratio bound.
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                with archive.open(info, "w", force_zip64=True) as destination_stream:
                    try:
                        digest, size = copy_verified_replacement(
                            root, replacement, destination_stream, max_bytes=MAX_ASSET_BYTES
                        )
                    except AssetSafetyError as error:
                        raise PackageError(str(error)) from error
                total_bytes += size
                if total_bytes + len(manifest_bytes) > MAX_PACKAGE_BYTES:
                    raise PackageError(f"Package exceeds the {MAX_PACKAGE_BYTES} byte size limit.")
                assets.append({"path": name, "sha256": digest, "size_bytes": size})
            report = _build_report(manifest, assets, context, compatibility)
            report_bytes = _json_bytes(report)
            total_bytes += len(manifest_bytes) + len(report_bytes)
            if total_bytes > MAX_PACKAGE_BYTES:
                raise PackageError(f"Package exceeds the {MAX_PACKAGE_BYTES} byte size limit.")
            if len(report_bytes) > MAX_MANIFEST_BYTES:
                raise PackageError("Package verification report is larger than the 2 MiB safety limit.")
            for name, payload in sorted(
                ((MANIFEST_FILENAME, manifest_bytes), (REPORT_FILENAME, report_bytes)),
                key=lambda item: item[0].casefold(),
            ):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, payload)
        verify_package(temporary_name)
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"Package destination already exists: {destination}")
        # Hard-link publication is atomic and fails if another process creates
        # the destination after our initial existence check.
        os.link(temporary_name, destination)
        Path(temporary_name).unlink()
        temporary_name = None
    except Exception:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
        raise

    report["package"] = {
        "file_name": destination.name,
        "sha256": _sha256_file(destination),
        "size_bytes": destination.stat().st_size,
    }
    return report


def verify_package(package_file: str | os.PathLike[str]) -> dict[str, Any]:
    """Verify package paths, manifest metadata and every replacement digest."""
    package = Path(package_file).expanduser()
    if package.is_symlink() or not package.is_file():
        raise PackageError("The package must be a regular, non-symbolic-link file.")
    if package.stat().st_size > MAX_PACKAGE_BYTES:
        raise PackageError(f"Package exceeds the {MAX_PACKAGE_BYTES} byte size limit.")
    try:
        with zipfile.ZipFile(package, "r") as archive:
            members = _validated_members(archive)
            if MANIFEST_FILENAME not in members or REPORT_FILENAME not in members:
                raise PackageError("Package is missing mod.json or verification.json.")
            manifest_info = members[MANIFEST_FILENAME]
            if manifest_info.file_size > MAX_MANIFEST_BYTES:
                raise PackageError("Package manifest is larger than the 2 MiB safety limit.")
            if members[REPORT_FILENAME].file_size > MAX_MANIFEST_BYTES:
                raise PackageError("Package verification report is larger than the 2 MiB safety limit.")
            try:
                manifest_value = json.loads(archive.read(MANIFEST_FILENAME).decode("utf-8"))
                manifest = ModManifest.from_dict(manifest_value)
                stored_report = json.loads(archive.read(REPORT_FILENAME).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, ManifestError) as error:
                raise PackageError(f"Package metadata is invalid: {error}") from error
            metadata_report = validate_manifest(manifest)
            if not metadata_report.valid:
                raise PackageError("Package manifest failed metadata validation: " + _validation_message(metadata_report))
            if not isinstance(stored_report, dict) or stored_report.get("schema") != "koei-mod-workshop.package-verification.v1":
                raise PackageError("Package verification report is missing or has an unsupported schema.")
            if stored_report.get("valid") is not True:
                raise PackageError("Package verification report does not attest to a passing build.")
            context = _context_from_report(stored_report)
            compatibility = validate_manifest(manifest, context)
            if not compatibility.valid:
                raise PackageError("Package compatibility report does not pass for its declared context.")

            expected_names: set[str] = {MANIFEST_FILENAME, REPORT_FILENAME}
            verified_assets = 0
            verified_entries: list[dict[str, Any]] = []
            for replacement in manifest.replacements:
                target = normalize_target_path(replacement.target_path)
                name = f"replacements/{target}"
                if name.casefold() in {item.casefold() for item in expected_names}:
                    raise PackageError(f"Duplicate replacement target: {target}")
                info = members.get(name)
                if info is None:
                    raise PackageError(f"Package is missing replacement file: {target}")
                if replacement.source_path != name:
                    raise PackageError(f"Packaged source reference is not archive-relative: {target}")
                if info.file_size > MAX_ASSET_BYTES:
                    raise PackageError(f"Replacement is larger than the {MAX_ASSET_BYTES} byte safety limit: {target}")
                digest = hashlib.sha256()
                size = 0
                with archive.open(name, "r") as source:
                    while chunk := source.read(1024 * 1024):
                        size += len(chunk)
                        if size > MAX_ASSET_BYTES:
                            raise PackageError(f"Replacement is larger than the {MAX_ASSET_BYTES} byte safety limit: {target}")
                        digest.update(chunk)
                actual = digest.hexdigest()
                if actual.casefold() != replacement.sha256.casefold():
                    raise PackageError(f"Replacement digest does not match the manifest: {target}")
                expected_names.add(name)
                verified_assets += 1
                verified_entries.append({"path": name, "sha256": actual, "size_bytes": size})
            if set(members) != expected_names:
                extra = sorted(set(members) - expected_names)
                raise PackageError("Package contains undeclared files: " + ", ".join(extra))
            if stored_report.get("mod_id") != manifest.mod_id or stored_report.get("mod_version") != manifest.version:
                raise PackageError("Package verification report does not match the manifest.")
            if stored_report != _build_report(manifest, verified_entries, context, compatibility):
                raise PackageError("Package verification report does not match the verified package contents.")
    except (AssetSafetyError, OSError, zipfile.BadZipFile, RuntimeError, EOFError) as error:
        raise PackageError(f"Package could not be read safely: {error}") from error

    return {
        "schema": "koei-mod-workshop.package-verification.v1",
        "valid": True,
        "mod_id": manifest.mod_id,
        "mod_version": manifest.version,
        "compatibility": stored_report["compatibility"],
        "assets": verified_entries,
        "summary": {"replacement_files": verified_assets, "errors": 0},
        "checks": [
            {"id": "archive.paths", "status": "passed"},
            {"id": "manifest.metadata", "status": "passed"},
            {"id": "replacement.sha256", "status": "passed", "count": verified_assets},
            {"id": "game-assets", "status": "not-included-by-tool",
             "detail": "The workshop packages only selected replacement files; it never extracts original game assets."},
            {"id": "asset-rights", "status": "self-declared",
             "detail": "Rights and license declarations come from the project author and are not independently verified."},
        ],
    }


def _validated_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    members: dict[str, zipfile.ZipInfo] = {}
    seen: set[str] = set()
    total = 0
    for info in archive.infolist():
        name = info.filename
        if not name or name.endswith("/") or "\\" in name:
            raise PackageError(f"Unsafe package path: {name!r}")
        path = PurePosixPath(name)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in name.split("/")):
            raise PackageError(f"Unsafe package path: {name!r}")
        if any(ord(character) < 32 or ord(character) == 127 for character in name):
            raise PackageError("Package file names cannot contain control characters.")
        if name.casefold() in seen:
            raise PackageError(f"Duplicate package path: {name}")
        seen.add(name.casefold())
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            raise PackageError(f"Package entry is not a regular file: {name}")
        if info.file_size < 0 or info.file_size > MAX_ASSET_BYTES:
            raise PackageError(f"Package entry exceeds the per-file size limit: {name}")
        if info.file_size and info.compress_size == 0:
            raise PackageError(f"Package entry has an invalid compressed size: {name}")
        if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            raise PackageError(f"Package entry has an unsafe compression ratio: {name}")
        total += info.file_size
        if total > MAX_PACKAGE_BYTES:
            raise PackageError(f"Package exceeds the {MAX_PACKAGE_BYTES} byte size limit.")
        members[name] = info
    return members


def _build_report(
    manifest: ModManifest,
    assets: list[dict[str, Any]],
    context: CompatibilityContext,
    compatibility: ValidationReport,
) -> dict[str, Any]:
    assets = sorted(assets, key=lambda item: item["path"].casefold())
    return {
        "schema": "koei-mod-workshop.package-verification.v1",
        "valid": True,
        "mod_id": manifest.mod_id,
        "mod_version": manifest.version,
        "compatibility": {
            "status": "passed-with-warnings" if any(item.severity == "warning" for item in compatibility.findings) else "passed",
            "context": _context_to_dict(context),
            "validation": compatibility.to_dict(),
        },
        "checks": [
            {"id": "manifest.metadata", "status": "passed"},
            {"id": "asset.sources", "status": "passed", "count": len(assets)},
            {"id": "asset.rights", "status": "self-declared",
             "detail": "License and ownership declarations are supplied by the project author and are not independently verified."},
            {"id": "game-assets", "status": "not-included-by-tool",
             "detail": "Only selected replacement files are packaged; original game files are not extracted or copied."},
        ],
        "assets": assets,
    }


def _context_to_dict(context: CompatibilityContext) -> dict[str, Any]:
    return {
        "game_id": context.game_id,
        "game_version": context.game_version,
        "platform": context.platform,
        "installed_mods": [
            {"mod_id": item.mod_id, "version": item.version}
            for item in context.installed_mods
        ],
    }


def _context_from_report(report: dict[str, Any]) -> CompatibilityContext:
    compatibility = report.get("compatibility")
    if not isinstance(compatibility, dict):
        raise PackageError("Package compatibility context is missing.")
    value = compatibility.get("context")
    if not isinstance(value, dict):
        raise PackageError("Package compatibility context is invalid.")
    installed = value.get("installed_mods")
    if not isinstance(installed, list):
        raise PackageError("Installed mod declarations in the compatibility context are invalid.")
    try:
        from .validation import InstalledMod
        installed_mods = tuple(InstalledMod(item["mod_id"], item["version"]) for item in installed)
        context = CompatibilityContext(
            game_id=value["game_id"],
            game_version=value["game_version"],
            platform=value["platform"],
            installed_mods=installed_mods,
        )
    except (KeyError, TypeError) as error:
        raise PackageError("Package compatibility context has invalid fields.") from error
    if any(not isinstance(item, str) for item in (context.game_id, context.game_version, context.platform)):
        raise PackageError("Package compatibility context fields must be text.")
    if any(not isinstance(item.mod_id, str) or not isinstance(item.version, str) for item in installed_mods):
        raise PackageError("Installed mod IDs and versions must be text.")
    return context


def _validation_message(report) -> str:
    return "; ".join(item.message for item in report.findings if item.severity == "error") or "Project validation failed."


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_symlink_components(path: Path) -> None:
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise PackageError(f"Package output path contains a symbolic link: {candidate}")
