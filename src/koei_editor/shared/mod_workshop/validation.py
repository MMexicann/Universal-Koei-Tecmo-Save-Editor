"""Metadata and compatibility checks for user-authored mod packages."""

from dataclasses import dataclass
import re
from typing import Any

from .asset_explorer import AssetSafetyError, normalize_target_path, verify_replacement
from .models import AssetReplacement, Dependency, ModManifest, SCHEMA_VERSION
from .project_manager import load_project


MOD_ID = re.compile(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*\Z")
SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z")
VERSION_TERM = re.compile(r"(>=|<=|>|<|==|=)?\s*(\d+\.\d+\.\d+)\Z")
RIGHTS_STATUSES = frozenset({"creator-owned", "permissive-license", "public-domain"})


@dataclass(frozen=True)
class InstalledMod:
    mod_id: str
    version: str


@dataclass(frozen=True)
class CompatibilityContext:
    game_id: str
    game_version: str
    platform: str
    installed_mods: tuple[InstalledMod, ...] = ()


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "severity": self.severity, "message": self.message}


@dataclass(frozen=True)
class ValidationReport:
    findings: tuple[Finding, ...]

    @property
    def valid(self) -> bool:
        return not any(item.severity == "error" for item in self.findings)

    def to_dict(self) -> dict[str, Any]:
        errors = sum(item.severity == "error" for item in self.findings)
        warnings = sum(item.severity == "warning" for item in self.findings)
        return {
            "schema": "koei-mod-workshop.validation.v1",
            "valid": self.valid,
            "summary": {"errors": errors, "warnings": warnings},
            "findings": [item.to_dict() for item in self.findings],
        }


def valid_mod_id(value: str) -> bool:
    return bool(MOD_ID.fullmatch(value))


def version_satisfies(actual: str, requirement: str) -> bool:
    """Match a semantic version against ``*`` or comma-separated comparators."""
    actual_match = SEMVER.fullmatch(actual.strip())
    if actual_match is None:
        return False
    if requirement.strip() == "*":
        return True
    actual_parts = tuple(map(int, actual_match.groups()))
    terms = requirement.split(",")
    if not terms or any(not term.strip() for term in terms):
        return False
    for term in terms:
        match = VERSION_TERM.fullmatch(term.strip())
        if match is None:
            return False
        operator, version = match.groups()
        expected_match = SEMVER.fullmatch(version)
        if expected_match is None:
            return False
        expected_parts = tuple(map(int, expected_match.groups()))
        operator = operator or "=="
        if operator in ("=", "==") and actual_parts != expected_parts:
            return False
        if operator == ">" and not actual_parts > expected_parts:
            return False
        if operator == ">=" and not actual_parts >= expected_parts:
            return False
        if operator == "<" and not actual_parts < expected_parts:
            return False
        if operator == "<=" and not actual_parts <= expected_parts:
            return False
    return True


def version_or_exact(actual: str, requirement: str) -> bool:
    """Allow a comparator range or a literal game build label."""
    if requirement.strip() == "*":
        return True
    if any(operator in requirement for operator in (">", "<", "=")):
        return version_satisfies(actual, requirement)
    return actual.strip().casefold() == requirement.strip().casefold()


def validate_manifest(
    manifest: ModManifest,
    context: CompatibilityContext | None = None,
) -> ValidationReport:
    findings: list[Finding] = []

    def add(code: str, message: str, severity: str = "error") -> None:
        findings.append(Finding(code, severity, message))

    if manifest.schema_version != SCHEMA_VERSION:
        add("manifest.schema.unsupported", f"Manifest schema {manifest.schema_version} is not supported.")
    if not valid_mod_id(manifest.mod_id):
        add("manifest.id.invalid", "Mod ID must use lowercase letters, digits, dots, underscores or hyphens.")
    for key, value in (
        ("name", manifest.name),
        ("author", manifest.author),
        ("game_id", manifest.game_id),
        ("game_version", manifest.game_version),
        ("platform", manifest.platform),
        ("license", manifest.license),
    ):
        if not value.strip():
            add(f"manifest.{key}.required", f"{key.replace('_', ' ').capitalize()} is required.")
    if SEMVER.fullmatch(manifest.version) is None:
        add("manifest.version.invalid", "Mod version must use three numeric semantic-version parts, such as 1.0.0.")

    seen_dependencies: set[str] = set()
    for dependency in manifest.dependencies:
        _validate_dependency(dependency, manifest.mod_id, seen_dependencies, add)

    seen_targets: set[str] = set()
    for replacement in manifest.replacements:
        _validate_replacement(replacement, seen_targets, add)

    if context is not None:
        _validate_context(manifest, context, add)
    if not findings:
        add("manifest.valid", "Manifest fields and declared dependencies are valid.", "info")
    return ValidationReport(tuple(findings))


def validate_project(
    project_dir: str,
    context: CompatibilityContext | None = None,
) -> ValidationReport:
    """Validate project metadata, compatibility and recorded asset digests."""
    try:
        manifest = load_project(project_dir)
    except (OSError, ValueError) as error:
        return ValidationReport((Finding("project.load.failed", "error", str(error)),))
    report = validate_manifest(manifest, context)
    findings = list(report.findings)
    for replacement in manifest.replacements:
        try:
            verify_replacement(project_dir, replacement)
        except AssetSafetyError as error:
            findings.append(Finding("asset.source.invalid", "error", str(error)))
    if not any(item.severity == "error" for item in findings):
        findings.append(Finding(
            "asset.sources.verified",
            "info",
            f"Verified {len(manifest.replacements)} user-provided replacement source(s) against their recorded SHA-256 digests.",
        ))
    return ValidationReport(tuple(findings))


def _validate_dependency(dependency: Dependency, own_id: str, seen: set[str], add) -> None:
    dep_id = dependency.mod_id.strip()
    normalized = dep_id.casefold()
    if not valid_mod_id(normalized):
        add("dependency.id.invalid", f"Dependency ID '{dep_id}' is not valid.")
    if normalized == own_id.casefold():
        add("dependency.self", f"Mod '{own_id}' cannot depend on itself.")
    if normalized in seen:
        add("dependency.duplicate", f"Dependency '{dep_id}' is declared more than once.")
    seen.add(normalized)
    if dependency.version.strip() != "*" and not version_satisfies("0.0.0", dependency.version):
        # A valid range must parse even when its lower bound is above zero.
        if not _valid_version_range(dependency.version):
            add("dependency.version.invalid", f"Dependency '{dep_id}' has an invalid version range.")


def _valid_version_range(requirement: str) -> bool:
    if requirement.strip() == "*":
        return True
    terms = requirement.split(",")
    return bool(terms) and all(VERSION_TERM.fullmatch(term.strip()) for term in terms)


def _validate_replacement(replacement: AssetReplacement, seen_targets: set[str], add) -> None:
    try:
        target = normalize_target_path(replacement.target_path)
    except AssetSafetyError:
        target = replacement.target_path
        add("asset.target.unsafe", f"Replacement target '{replacement.target_path}' is not a safe relative path.")
    normalized = target.casefold()
    if normalized in seen_targets:
        add("asset.target.duplicate", f"Replacement target '{replacement.target_path}' is declared more than once.")
    seen_targets.add(normalized)
    if not re.fullmatch(r"[0-9a-fA-F]{64}", replacement.sha256):
        add("asset.hash.invalid", f"Replacement for '{replacement.target_path}' has no valid SHA-256 digest.")
    if replacement.rights_status not in RIGHTS_STATUSES:
        add("asset.rights.unverified", f"Replacement for '{replacement.target_path}' needs a permitted rights declaration.")
    if not replacement.license.strip():
        add("asset.license.required", f"Replacement for '{replacement.target_path}' needs a license declaration.")
    if replacement.rights_status == "permissive-license" and not replacement.attribution.strip():
        add("asset.attribution.required", f"Permissively licensed replacement '{replacement.target_path}' needs attribution.")


def _validate_context(manifest: ModManifest, context: CompatibilityContext, add) -> None:
    if context.game_id.strip().casefold() != manifest.game_id.strip().casefold():
        add("compatibility.game.mismatch", "Selected game does not match the project's target game.")
    if context.platform.strip().casefold() != manifest.platform.strip().casefold():
        add("compatibility.platform.mismatch", "Selected platform does not match the project's target platform.")
    if not version_or_exact(context.game_version, manifest.game_version):
        add("compatibility.game_version.mismatch", "Selected game version is outside the project's declared compatibility range.")

    installed: dict[str, InstalledMod] = {}
    for item in context.installed_mods:
        normalized = item.mod_id.strip().casefold()
        if not valid_mod_id(normalized):
            add("compatibility.installed_id.invalid", f"Installed mod ID '{item.mod_id}' is invalid.")
        if SEMVER.fullmatch(item.version.strip()) is None:
            add("compatibility.installed_version.invalid", f"Installed mod '{item.mod_id}' has an invalid semantic version.")
        if normalized in installed:
            add("compatibility.installed_duplicate", f"Installed mod '{item.mod_id}' is listed more than once.")
        installed[normalized] = item
    for dependency in manifest.dependencies:
        found = installed.get(dependency.mod_id.strip().casefold())
        if found is None:
            if dependency.optional:
                add("compatibility.dependency_optional_missing",
                    f"Optional dependency '{dependency.mod_id}' is not listed as installed.", "warning")
            else:
                add("compatibility.dependency_missing", f"Required dependency '{dependency.mod_id}' is not listed as installed.")
        elif not version_satisfies(found.version, dependency.version):
            add("compatibility.dependency_version", f"Installed '{dependency.mod_id}' version {found.version} does not satisfy {dependency.version}.")
