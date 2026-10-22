"""Portable data models for mod projects and their replacement files.

The workshop stores references to user-provided replacements. It never extracts
or copies the game's original files into a project or package.
"""

from dataclasses import dataclass
from typing import Any


SCHEMA_VERSION = 1


class ManifestError(ValueError):
    """Raised when a project manifest cannot be read safely."""


@dataclass(frozen=True)
class Dependency:
    mod_id: str
    version: str = "*"
    optional: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"mod_id": self.mod_id, "version": self.version, "optional": self.optional}

    @classmethod
    def from_dict(cls, value: Any) -> "Dependency":
        if not isinstance(value, dict):
            raise ManifestError("Each dependency must be an object.")
        return cls(
            mod_id=_string(value, "mod_id"),
            version=_string(value, "version", default="*"),
            optional=_boolean(value, "optional", default=False),
        )


@dataclass(frozen=True)
class AssetReplacement:
    source_path: str
    target_path: str
    sha256: str
    license: str
    attribution: str = ""
    rights_status: str = "creator-owned"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "target_path": self.target_path,
            "sha256": self.sha256,
            "license": self.license,
            "attribution": self.attribution,
            "rights_status": self.rights_status,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "AssetReplacement":
        if not isinstance(value, dict):
            raise ManifestError("Each asset replacement must be an object.")
        return cls(
            source_path=_string(value, "source_path"),
            target_path=_string(value, "target_path"),
            sha256=_string(value, "sha256"),
            license=_string(value, "license"),
            attribution=_string(value, "attribution", default=""),
            rights_status=_string(value, "rights_status", default="creator-owned"),
        )


@dataclass(frozen=True)
class ModManifest:
    mod_id: str
    name: str
    version: str
    author: str
    description: str
    game_id: str
    game_version: str
    platform: str
    license: str
    dependencies: tuple[Dependency, ...] = ()
    replacements: tuple[AssetReplacement, ...] = ()
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "mod_id": self.mod_id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "game_id": self.game_id,
            "game_version": self.game_version,
            "platform": self.platform,
            "license": self.license,
            "dependencies": [item.to_dict() for item in self.dependencies],
            "replacements": [item.to_dict() for item in self.replacements],
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ModManifest":
        if not isinstance(value, dict):
            raise ManifestError("A project manifest must be a JSON object.")
        schema_version = value.get("schema_version", SCHEMA_VERSION)
        if type(schema_version) is not int:
            raise ManifestError("schema_version must be an integer.")
        dependencies = value.get("dependencies", [])
        replacements = value.get("replacements", [])
        if not isinstance(dependencies, list) or not isinstance(replacements, list):
            raise ManifestError("dependencies and replacements must be arrays.")
        return cls(
            mod_id=_string(value, "mod_id"),
            name=_string(value, "name"),
            version=_string(value, "version"),
            author=_string(value, "author"),
            description=_string(value, "description", default=""),
            game_id=_string(value, "game_id"),
            game_version=_string(value, "game_version"),
            platform=_string(value, "platform"),
            license=_string(value, "license"),
            dependencies=tuple(Dependency.from_dict(item) for item in dependencies),
            replacements=tuple(AssetReplacement.from_dict(item) for item in replacements),
            schema_version=schema_version,
        )


def _string(value: dict[str, Any], key: str, default: str | None = None) -> str:
    result = value.get(key, default)
    if not isinstance(result, str):
        raise ManifestError(f"{key} must be a string.")
    return result


def _boolean(value: dict[str, Any], key: str, default: bool = False) -> bool:
    result = value.get(key, default)
    if type(result) is not bool:
        raise ManifestError(f"{key} must be a boolean.")
    return result
