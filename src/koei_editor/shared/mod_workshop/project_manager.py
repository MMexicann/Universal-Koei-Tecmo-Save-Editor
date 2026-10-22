"""Safe local project initialization and manifest dependency editing."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .models import Dependency, ManifestError, ModManifest
from .templates import get_template


MANIFEST_FILENAME = "mod.json"
PROJECT_README_FILENAME = "README.md"
_MOD_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_CONSTRAINT_RE = re.compile(r"^(?:==|=|>=|<=|>|<)?\s*\d+\.\d+\.\d+$")


def initialize_project(
    project_dir: str | os.PathLike[str],
    manifest: ModManifest,
    template_id: str = "blank",
) -> Path:
    """Create a new project folder without replacing any existing folder.

    The project contains only metadata, a README and an empty ``assets``
    directory. It never reads a game installation or copies original assets.
    Requiring a new directory also prevents a user from accidentally selecting
    an existing, possibly game-owned directory as the project root.
    """
    template = get_template(template_id)
    root = _absolute_path(project_dir)
    _reject_symlink_components(root)
    if root.exists():
        raise FileExistsError(f"Project directory already exists: {root}")
    root.parent.mkdir(parents=True, exist_ok=True)
    try:
        root.mkdir()
    except FileExistsError as exc:
        raise FileExistsError(f"Project directory already exists: {root}") from exc

    created: list[Path] = []
    try:
        assets_dir = root / "assets"
        assets_dir.mkdir()
        created.append(assets_dir)
        for subfolder in template.asset_subfolders:
            asset_subfolder = assets_dir / subfolder
            asset_subfolder.mkdir()
            created.append(asset_subfolder)
        manifest_path = root / MANIFEST_FILENAME
        _write_new_text_file(manifest_path, json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n")
        created.append(manifest_path)
        readme_path = root / PROJECT_README_FILENAME
        _write_new_text_file(readme_path, _project_readme(manifest, template.name, template.asset_guidance))
        created.append(readme_path)
    except Exception:
        for path in reversed(created):
            if path.is_dir() and not path.is_symlink():
                path.rmdir()
            elif path.exists() or path.is_symlink():
                path.unlink()
        root.rmdir()
        raise
    return root


def load_project(project_dir: str | os.PathLike[str]) -> ModManifest:
    """Load the JSON manifest from a project folder."""
    root = _absolute_path(project_dir)
    _reject_symlink_components(root)
    if not root.is_dir():
        raise FileNotFoundError(f"Project directory does not exist: {root}")
    manifest_path = root / MANIFEST_FILENAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ManifestError("Project manifest is missing or is a symbolic link.")
    if manifest_path.stat().st_size > 2 * 1024 * 1024:
        raise ManifestError("Project manifest is larger than the 2 MiB safety limit.")
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Could not read project manifest: {exc}") from exc
    return ModManifest.from_dict(value)


def save_manifest(project_dir: str | os.PathLike[str], manifest: ModManifest) -> Path:
    """Replace only the project's manifest file, never project assets."""
    root = _absolute_path(project_dir)
    _reject_symlink_components(root)
    if not root.is_dir():
        raise FileNotFoundError(f"Project directory does not exist: {root}")
    manifest_path = root / MANIFEST_FILENAME
    if manifest_path.is_symlink():
        raise ManifestError("Project manifest must not be a symbolic link.")
    payload = json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n"
    temporary = root / f".{MANIFEST_FILENAME}.{os.getpid()}.tmp"
    if temporary.exists() or temporary.is_symlink():
        raise FileExistsError(f"Temporary manifest path already exists: {temporary}")
    try:
        _write_new_text_file(temporary, payload)
        os.replace(temporary, manifest_path)
    finally:
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()
    return manifest_path


def add_dependency(manifest: ModManifest, dependency: Dependency) -> ModManifest:
    """Return a new manifest with one validated dependency appended."""
    _validate_dependency(dependency, manifest)
    existing = {item.mod_id.casefold() for item in manifest.dependencies}
    if dependency.mod_id.casefold() in existing:
        raise ValueError(f"Dependency is already declared: {dependency.mod_id}")
    return ModManifest(
        **{
            **manifest.__dict__,
            "dependencies": manifest.dependencies + (dependency,),
        }
    )


def remove_dependency(manifest: ModManifest, mod_id: str) -> ModManifest:
    """Return a new manifest without the selected dependency."""
    normalized = mod_id.strip().casefold()
    if not normalized:
        raise ValueError("Dependency ID is required.")
    dependencies = tuple(item for item in manifest.dependencies if item.mod_id.casefold() != normalized)
    return ModManifest(**{**manifest.__dict__, "dependencies": dependencies})


def validate_dependency(dependency: Dependency, manifest: ModManifest | None = None) -> None:
    """Validate a dependency ID and its supported version constraint syntax."""
    _validate_dependency(dependency, manifest)


def _validate_dependency(dependency: Dependency, manifest: ModManifest | None) -> None:
    mod_id = dependency.mod_id.strip()
    if not _MOD_ID_RE.fullmatch(mod_id):
        raise ValueError("Dependency ID must start with a lowercase letter and contain only lowercase letters, digits, dots, underscores or hyphens.")
    if manifest is not None and mod_id.casefold() == manifest.mod_id.strip().casefold():
        raise ValueError("A mod cannot depend on itself.")
    constraint = dependency.version.strip()
    if constraint != "*" and not _valid_version_constraint(constraint):
        raise ValueError("Dependency version must be '*', a semantic version, or comma-separated comparison constraints such as '>=1.2.0,<2.0.0'.")


def _valid_version_constraint(value: str) -> bool:
    pieces = [piece.strip() for piece in value.split(",")]
    if not pieces or any(not piece or not _CONSTRAINT_RE.fullmatch(piece) for piece in pieces):
        return False
    # Reject contradictory duplicate comparison operators such as >=1.0.0,>=2.0.0.
    operators = [re.match(r"^(==|=|>=|<=|>|<)?", piece).group(1) or "=" for piece in pieces]
    return len(operators) == len(set(operators))


def _absolute_path(path: str | os.PathLike[str]) -> Path:
    try:
        value = Path(path).expanduser()
    except TypeError as exc:
        raise ValueError("Project path must be a filesystem path.") from exc
    if not value.is_absolute():
        value = Path.cwd() / value
    return Path(os.path.abspath(value))


def _reject_symlink_components(path: Path) -> None:
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise ValueError(f"Project path contains a symbolic link: {candidate}")


def _write_new_text_file(path: Path, content: str) -> None:
    # Exclusive creation prevents following an existing file or symlink.
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def _project_readme(manifest: ModManifest, template_name: str, asset_guidance: str) -> str:
    return (
        f"# {manifest.name}\n\n"
        f"Template: {template_name}\n\n"
        "This project includes only replacement files added by its creator. "
        "Do not add original game files or extracted game archives.\n\n"
        f"{asset_guidance}\n\n"
        "See `mod.json` for game target, compatibility, license and dependency metadata.\n"
    )
