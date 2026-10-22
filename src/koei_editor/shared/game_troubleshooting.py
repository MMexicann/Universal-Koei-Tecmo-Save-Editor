"""Bounded, read-only diagnostics for selected Koei Tecmo PC installations.

The center reads only folders a user selects. It does not run game code, write
into an installation, repair configuration, install prerequisites, or infer a
fault when the reviewed metadata cannot support one.
"""

from dataclasses import dataclass
import configparser
import json
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from koei_editor.game_registry import GAMES
from koei_editor.resources import data_file
from koei_editor.shared.save_discovery import STEAM_MAPPINGS


SCHEMA = "koei-game-troubleshooting"
SCHEMA_VERSION = 1
CATEGORY_ORDER = ("installation", "configuration", "mods", "prerequisites", "compatibility")
STATUSES = ("passed", "warning", "failed", "unknown", "not_checked")
SEVERITIES = ("info", "warning", "error")
_BUILTIN_FINDING_IDS = frozenset({
    "installation.selected_root", "installation.scan_limit", "installation.links_skipped",
    "installation.steam_candidate", "configuration.selected_root", "configuration.syntax",
    "configuration.scan_limits", "mods.scan", "mods.conflicts",
    "mods.scan_limits", "prerequisites.reviewed_rules", "compatibility.reviewed_notes",
})
MAX_CATALOG_BYTES = 128 * 1024
MAX_ROOTS = 3
MAX_ENTRIES = 2000
MAX_DEPTH = 4
MAX_CONFIG_FILES = 128
MAX_CONFIG_BYTES = 256 * 1024
_SUPPORTED_CONFIGS = {".ini", ".cfg", ".json", ".xml"}


class TroubleshootingError(ValueError):
    """Invalid diagnostic request or unsupported bundled troubleshooting data."""


@dataclass(frozen=True)
class TroubleshootingFinding:
    id: str
    category: str
    status: str
    severity: str
    title: str
    summary: str
    evidence: tuple[str, ...]
    recommendation: str
    source: str | None = None


@dataclass(frozen=True)
class TroubleshootingReport:
    game_id: str
    title: str
    platform: str
    ruleset_version: str
    findings: tuple[TroubleshootingFinding, ...]

    @property
    def overall_status(self):
        statuses = {finding.status for finding in self.findings}
        if "failed" in statuses:
            return "failed"
        if "warning" in statuses:
            return "warning"
        if statuses and statuses <= {"unknown", "not_checked"}:
            return "unknown"
        if "unknown" in statuses or "not_checked" in statuses:
            return "partial"
        return "passed"

    def to_dict(self):
        """Return a portable report without local paths, config values or hashes."""
        return {
            "schema": SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "ruleset_version": self.ruleset_version,
            "read_only": True,
            "game_id": self.game_id,
            "title": self.title,
            "platform": self.platform,
            "overall_status": self.overall_status,
            "findings": [
                {
                    "id": finding.id,
                    "category": finding.category,
                    "status": finding.status,
                    "severity": finding.severity,
                    "title": finding.title,
                    "summary": finding.summary,
                    "evidence": list(finding.evidence),
                    "recommendation": finding.recommendation,
                    "source": finding.source,
                }
                for finding in self.findings
            ],
        }

    def to_json(self):
        """Serialize deterministically for repeatable local review and Sol audits."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2,
                          sort_keys=True, allow_nan=False) + "\n"

    def to_text(self):
        rows = [
            "Koei Tecmo Game Troubleshooting Center",
            f"Game: {self.title} [{self.game_id}]",
            f"Platform: {self.platform}",
            f"Overall: {self.overall_status}",
            f"Ruleset: {self.ruleset_version} · schema {SCHEMA_VERSION}",
            "Read-only scan: selected files were not modified; no game executable was run.",
            "",
        ]
        for category in CATEGORY_ORDER:
            matches = [finding for finding in self.findings if finding.category == category]
            if not matches:
                continue
            rows.append(category.title())
            for finding in matches:
                rows.append(f"[{finding.status}] {finding.title} ({finding.id})")
                rows.append(f"  {finding.summary}")
                rows.extend("  Evidence: " + evidence for evidence in finding.evidence)
                rows.append("  Recommended next step: " + finding.recommendation)
                if finding.source:
                    rows.append("  Source: " + finding.source)
            rows.append("")
        return "\n".join(rows).rstrip() + "\n"


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate troubleshooting catalog key.")
        result[key] = value
    return result


def _safe_text(value, maximum=1200):
    return (type(value) is str and 0 < len(value) <= maximum
            and "\x00" not in value and not any(0xD800 <= ord(char) <= 0xDFFF for char in value))


def _source(value):
    if (not _safe_text(value, 1000) or not value.startswith("https://")
            or any(char.isspace() or ord(char) < 0x21 for char in value)):
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == "https" and bool(parsed.hostname)
                and parsed.username is None and parsed.password is None)
    except ValueError:
        return False


def _load_catalog():
    try:
        with data_file("game_troubleshooting.json").open("rb") as stream:
            raw = stream.read(MAX_CATALOG_BYTES + 1)
        if not 0 < len(raw) <= MAX_CATALOG_BYTES:
            raise ValueError("catalog size")
        catalog = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
        if (type(catalog) is not dict or set(catalog) != {"schema_version", "ruleset_version", "profiles"}
                or type(catalog["schema_version"]) is not int or catalog["schema_version"] != 1
                or not _safe_text(catalog["ruleset_version"], 40)
                or not re.fullmatch(r"[0-9]{4}\.[0-9]{2}(?:\.[0-9]{2})?", catalog["ruleset_version"])
                or type(catalog["profiles"]) is not list or len(catalog["profiles"]) > 64):
            raise ValueError("catalog header")
        registered = {game.id for game in GAMES if game.platform == "Windows PC"}
        seen_games = set()
        seen_rule_ids = set()
        for profile in catalog["profiles"]:
            if (type(profile) is not dict
                    or set(profile) != {"game_id", "prerequisites", "mod_conflicts", "compatibility"}
                    or type(profile["game_id"]) is not str or profile["game_id"] not in registered
                    or profile["game_id"] in seen_games
                    or type(profile["prerequisites"]) is not list
                    or len(profile["prerequisites"]) > 64
                    or type(profile["mod_conflicts"]) is not list
                    or len(profile["mod_conflicts"]) > 64
                    or type(profile["compatibility"]) is not list
                    or len(profile["compatibility"]) > 64):
                raise ValueError("profile")
            seen_games.add(profile["game_id"])
            for rule in profile["prerequisites"]:
                if (type(rule) is not dict
                        or set(rule) != {"id", "title", "summary", "evidence", "source", "recommendation"}
                        or not _safe_text(rule["id"], 100)
                        or not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", rule["id"])
                        or not _safe_text(rule["title"], 180)
                        or not _safe_text(rule["summary"])
                        or not _safe_text(rule["evidence"])
                        or not _source(rule["source"])
                        or not _safe_text(rule["recommendation"])):
                    raise ValueError("prerequisite")
                if rule["id"] in _BUILTIN_FINDING_IDS or rule["id"] in seen_rule_ids:
                    raise ValueError("duplicate profile rule")
                seen_rule_ids.add(rule["id"])
            for rule in profile["mod_conflicts"]:
                if (type(rule) is not dict
                        or set(rule) != {"id", "title", "summary", "evidence", "match_files",
                                         "affected_versions", "recommendation", "source"}
                        or not _safe_text(rule["id"], 100)
                        or not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", rule["id"])
                        or not _safe_text(rule["title"], 180)
                        or not _safe_text(rule["summary"])
                        or not _safe_text(rule["evidence"])
                        or type(rule["match_files"]) is not list
                        or not 2 <= len(rule["match_files"]) <= 16
                        or any(type(path) is not str or not _portable_relative(path)
                               for path in rule["match_files"])
                        or len({path.casefold() for path in rule["match_files"]}) != len(rule["match_files"])
                        or not _safe_text(rule["affected_versions"], 180)
                        or not _safe_text(rule["recommendation"])
                        or not _source(rule["source"])):
                    raise ValueError("mod conflict")
                if rule["id"] in _BUILTIN_FINDING_IDS or rule["id"] in seen_rule_ids:
                    raise ValueError("duplicate profile rule")
                seen_rule_ids.add(rule["id"])
            for rule in profile["compatibility"]:
                if (type(rule) is not dict
                        or set(rule) != {"id", "title", "summary", "evidence", "recommendation", "source"}
                        or not _safe_text(rule["id"], 100)
                        or not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", rule["id"])
                        or not _safe_text(rule["title"], 180)
                        or not _safe_text(rule["summary"])
                        or not _safe_text(rule["evidence"])
                        or not _safe_text(rule["recommendation"])
                        or not _source(rule["source"])):
                    raise ValueError("compatibility")
                if rule["id"] in _BUILTIN_FINDING_IDS or rule["id"] in seen_rule_ids:
                    raise ValueError("duplicate profile rule")
                seen_rule_ids.add(rule["id"])
        return catalog
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        raise TroubleshootingError("Bundled troubleshooting rules are invalid or unavailable.") from None


def _portable_relative(value):
    return (_safe_text(value, 256) and "\\" not in value and ":" not in value
            and all(part not in ("", ".", "..") for part in value.split("/")))


_CATALOG = _load_catalog()
RULESET_VERSION = _CATALOG["ruleset_version"]
_PROFILES = {profile["game_id"]: profile for profile in _CATALOG["profiles"]}


def _linked(info):
    return (stat.S_ISLNK(info.st_mode)
            or bool(getattr(info, "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)))


def _ordinary_root(value):
    """Return an accessible ordinary directory, rejecting links in its path."""
    try:
        if isinstance(value, bool) or not isinstance(value, (str, os.PathLike)):
            return None, "missing"
        path_text = os.fspath(value)
        if type(path_text) is not str or not path_text.strip() or len(path_text) > 4096:
            return None, "missing"
        selected = Path(path_text).expanduser()
        if not selected.is_absolute():
            selected = Path.cwd() / selected
        if ".." in selected.parts:
            return None, "unsafe"
        # Reject a symlink/reparse point in any selected path component.
        cursor = Path(selected.anchor)
        for part in selected.parts[1:]:
            cursor = cursor / part
            info = cursor.lstat()
            if _linked(info):
                return None, "unsafe"
        info = selected.lstat()
        if not stat.S_ISDIR(info.st_mode):
            return None, "not_directory"
        # Open the directory to distinguish readable from merely present.
        with os.scandir(selected) as iterator:
            next(iterator, None)
        return selected, "ready"
    except FileNotFoundError:
        return None, "missing"
    except (PermissionError, OSError, RuntimeError, ValueError):
        return None, "unreadable"


def _walk(root):
    """Enumerate names only; never follow links and stop at fixed limits."""
    files = []
    directories = [(root, 0)]
    visited = 0
    skipped_links = 0
    truncated = False
    while directories:
        directory, depth = directories.pop(0)
        if depth > MAX_DEPTH:
            truncated = True
            continue
        try:
            with os.scandir(directory) as iterator:
                entries = []
                for entry in iterator:
                    if visited + len(entries) >= MAX_ENTRIES:
                        truncated = True
                        directories.clear()
                        break
                    entries.append(entry)
                entries.sort(key=lambda item: (item.name.casefold(), item.name))
        except OSError:
            truncated = True
            continue
        for entry in entries:
            if visited >= MAX_ENTRIES:
                truncated = True
                directories.clear()
                break
            visited += 1
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError:
                truncated = True
                continue
            if _linked(info):
                skipped_links += 1
                continue
            if stat.S_ISDIR(info.st_mode):
                directories.append((Path(entry.path), depth + 1))
            elif stat.S_ISREG(info.st_mode):
                files.append((Path(entry.path), entry.name, info.st_size))
    files.sort(key=lambda item: (item[1].casefold(), item[1]))
    return files, visited, skipped_links, truncated


def _finding(identifier, category, status, severity, title, summary, evidence=(), recommendation="", source=None):
    return TroubleshootingFinding(identifier, category, status, severity, title, summary,
                                  tuple(evidence), recommendation, source)


def _scan_installation(game, path, findings):
    root, state = _ordinary_root(path) if path is not None else (None, "missing")
    if root is None:
        description = {
            "missing": "Choose the game's installation folder to inspect it.",
            "unsafe": "The selected folder or one of its parent folders is a symbolic link or reparse point.",
            "not_directory": "The selected installation path is not a directory.",
            "unreadable": "The selected installation folder could not be read.",
        }.get(state, "The installation folder was not checked.")
        findings.append(_finding("installation.selected_root", "installation", "unknown", "info",
            "Installation folder not checked", description,
            recommendation="Select the ordinary game folder through the folder picker and run the scan again."))
        files = []
        visited = skipped_links = 0
        truncated = False
    else:
        files, visited, skipped_links, truncated = _walk(root)
        if truncated:
            # A bounded prefix can differ across filesystems. Avoid conclusions
            # from it so repeated reports remain stable for oversized trees.
            findings.append(_finding("installation.scan_limit", "installation", "unknown", "info",
                "Installation scan reached a safety limit", "The scan reached its fixed depth or entry limit, so the selected installation could not be assessed completely.",
                (), "Choose a narrower game folder and scan again."))
        elif not files:
            findings.append(_finding("installation.selected_root", "installation", "warning", "warning",
                "No ordinary files found", "The selected installation folder is accessible but contains no ordinary files in the bounded scan.",
                ("0 ordinary files found",),
                "Confirm this is the installed game's folder. Use the official client only if you choose to check or restore its files."))
        else:
            executables = sum(name.casefold().endswith(".exe") for _path, name, _size in files)
            findings.append(_finding("installation.selected_root", "installation", "passed", "info",
                "Installation folder is readable", "The selected folder is an accessible directory; this scan does not validate game binaries or completeness.",
                (f"{len(files)} ordinary files found in a bounded scan", f"{executables} executable filename(s) found"),
                "If files appear missing, use the game's official launcher or publisher support instructions."))
        if skipped_links and not truncated:
            findings.append(_finding("installation.links_skipped", "installation", "not_checked", "info",
                "Linked items were skipped", "Symbolic links and reparse points were not followed.",
                (f"{skipped_links} linked item(s) skipped",),
                "Review linked locations yourself if the game intentionally stores files outside this folder."))

    mappings = [mapping for mapping in STEAM_MAPPINGS if mapping.game_id == game.id]
    if mappings:
        mapping = mappings[0]
        findings.append(_finding("installation.steam_candidate", "installation", "not_checked", "info",
            "Steam package mapping is available", "The reviewed Steam app ID is candidate metadata; it does not prove that this folder is the matching game or that its files are complete.",
            (f"Steam app ID {mapping.app_id}", f"Catalog evidence: {mapping.evidence}"),
            "Compare the selected folder with the game entry in your Steam library if needed."))
    else:
        findings.append(_finding("installation.steam_candidate", "installation", "not_checked", "info",
            "No reviewed Steam mapping is available", "This profile has no bundled Steam installation mapping, so automatic package identification was not attempted.",
            (), "Use the exact game/platform entry and select its installed folder manually."))


def _decode_config(path):
    """Return syntax result without retaining or exposing any configuration values."""
    try:
        before = path.lstat()
        if _linked(before) or not stat.S_ISREG(before.st_mode):
            return "unsafe"
        if before.st_size > MAX_CONFIG_BYTES:
            return "oversized"
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if _linked(opened) or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                    opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns):
                return "changed"
            raw = stream.read(MAX_CONFIG_BYTES + 1)
            after = os.fstat(stream.fileno())
        if len(raw) > MAX_CONFIG_BYTES or after.st_size > MAX_CONFIG_BYTES:
            return "oversized"
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            return "changed"
        text = raw.decode("utf-8-sig", errors="strict")
        suffix = path.suffix.casefold()
        if suffix == ".json":
            json.loads(text, parse_constant=_reject_json_constant)
        elif suffix in (".ini", ".cfg"):
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            parser.read_string(text)
        elif suffix == ".xml":
            ET.fromstring(text)
        return "valid"
    except (PermissionError, FileNotFoundError):
        return "unavailable"
    except UnicodeError:
        # Legacy game configs may use a local code page or UTF-16. Without a
        # trustworthy encoding signal, abstain instead of calling them invalid.
        return "unverified"
    except (ValueError, configparser.Error, ET.ParseError, RecursionError):
        return "invalid"
    except OSError:
        return "unavailable"


def _scan_configuration(path, findings):
    if path is None:
        findings.append(_finding("configuration.selected_root", "configuration", "not_checked", "info",
            "Configuration folder not selected", "Configuration files may be stored outside the installation folder, so they were not searched automatically.",
            (), "Select the game's configuration folder if you want the center to check basic text syntax."))
        return
    root, state = _ordinary_root(path)
    if root is None:
        findings.append(_finding("configuration.selected_root", "configuration", "unknown", "info",
            "Configuration folder could not be checked", "The selected configuration folder is missing, unsafe, unreadable, or not a directory.",
            (), "Confirm the folder in the game's documentation or settings and select it explicitly."))
        return
    files, visited, skipped_links, truncated = _walk(root)
    if truncated:
        findings.append(_finding("configuration.scan_limits", "configuration", "unknown", "info",
            "Configuration files were not fully checked", "The folder scan reached its fixed depth or entry limit, so partial contents were not used to assess configuration syntax.",
            (), "Choose a narrower configuration folder and scan again."))
        return
    candidates = [(file_path, name, size) for file_path, name, size in files
                  if Path(name).suffix.casefold() in _SUPPORTED_CONFIGS]
    if not candidates:
        findings.append(_finding("configuration.syntax", "configuration", "unknown", "info",
            "No supported text configuration files found", "No INI, CFG, JSON, or XML files were found in the bounded scan of the selected folder.",
            (f"{visited} filesystem entries inspected",),
            "This does not mean the game has no configuration. Check the game's documented settings location."))
        if skipped_links:
            findings.append(_finding("configuration.scan_limits", "configuration", "unknown", "info",
                "Linked configuration locations were skipped", "Symbolic links and reparse points were not followed, so they may contain configuration files that were not checked.",
                (), "Select the documented configuration folder directly if the game stores files in a linked location."))
        return
    checked = invalid = unverified = 0
    by_extension = {}
    for file_path, name, size in candidates[:MAX_CONFIG_FILES]:
        extension = Path(name).suffix.casefold()
        by_extension[extension] = by_extension.get(extension, 0) + 1
        result = _decode_config(file_path)
        if result == "valid":
            checked += 1
        elif result == "invalid":
            invalid += 1
        else:
            unverified += 1
    evidence = tuple(f"{by_extension[extension]} {extension[1:].upper()} file(s) observed"
                     for extension in sorted(by_extension))
    if invalid:
        findings.append(_finding("configuration.syntax", "configuration", "warning", "warning",
            "A selected text configuration file may have a syntax problem", f"Basic syntax parsing failed for {invalid} selected configuration file(s); this does not validate game-specific settings.",
            evidence + (f"{checked} file(s) passed basic syntax parsing",),
            "If the game reports a configuration error, review the affected file with the game's documented tools and keep a backup before making any manual change."))
    elif checked:
        findings.append(_finding("configuration.syntax", "configuration", "passed", "info",
            "Basic configuration syntax check passed", f"{checked} selected text configuration file(s) passed a basic syntax parse; setting values and game-specific meaning were not assessed.",
            evidence, "If a problem remains, compare the settings with the game's official documentation."))
    if unverified or skipped_links or len(candidates) > MAX_CONFIG_FILES:
        reasons = []
        if unverified:
            reasons.append(f"{unverified} file(s) were too large, unreadable, unsafe, changed during reading, or used an unsupported text encoding")
        if skipped_links:
            reasons.append(f"{skipped_links} linked item(s) were skipped")
        if len(candidates) > MAX_CONFIG_FILES:
            reasons.append(f"only the first {MAX_CONFIG_FILES} supported files were checked")
        findings.append(_finding("configuration.scan_limits", "configuration", "unknown", "info",
            "Some configuration files were not checked", "; ".join(reasons) + ".",
            evidence, "Choose a narrower configuration folder and scan again if needed."))


def _reject_json_constant(value):
    raise ValueError("Non-standard JSON constant.")


def _add_mod_conflict_unchecked(game, findings, reason):
    rules = _PROFILES.get(game.id, {}).get("mod_conflicts", ())
    if rules:
        summary = ("No exact reviewed filename pattern was established because " + reason
                   + ". Game/mod versions and file contents were not checked.")
    else:
        summary = "No reviewed per-title mod conflict patterns are available. " + reason
    findings.append(_finding("mods.conflicts", "mods", "not_checked", "info",
        "Mod conflicts not established", summary, (),
        "Check compatibility notes from the mod publisher or manager if a problem began after a mod change."))


def _scan_mods(game, installation_path, mods_path, findings):
    rules = _PROFILES.get(game.id, {}).get("mod_conflicts", ())
    selected = mods_path if mods_path is not None else installation_path
    root, state = _ordinary_root(selected) if selected is not None else (None, "missing")
    if root is None:
        findings.append(_finding("mods.scan", "mods", "unknown", "info",
            "Mod folder not checked", "Select a mod folder, or an installation folder, to compare ordinary filenames with any reviewed per-game conflict patterns.",
            (), "Select the folder used by your documented mod manager if you want a read-only pattern check."))
        _add_mod_conflict_unchecked(game, findings, "the selected mod folder was not available")
        return
    files, visited, skipped_links, truncated = _walk(root)
    if truncated:
        findings.append(_finding("mods.scan", "mods", "unknown", "info",
            "Mod folder was not fully checked", "The folder scan reached its fixed depth or entry limit, so partial contents were not used to match conflict patterns.",
            (), "Choose a narrower mod folder and scan again."))
        _add_mod_conflict_unchecked(game, findings, "the folder scan reached a safety limit")
        return
    findings.append(_finding("mods.scan", "mods", "passed", "info",
        "Selected mod folder scanned", "Ordinary filenames were compared only with reviewed per-game conflict patterns. File contents and game/mod versions were not opened or checked.",
        (f"{len(files)} ordinary file(s) inspected in a bounded scan",),
        "If a problem began after a mod change, check compatibility notes from the mod publisher or manager."))
    relative_files = {file_path.relative_to(root).as_posix().casefold()
                      for file_path, _name, _size in files}
    matched_rules = []
    for rule in rules:
        if {path.casefold() for path in rule["match_files"]} <= relative_files:
            findings.append(_finding(
                rule["id"], "mods", "warning", "warning", rule["title"],
                rule["summary"] + " The selected folder matched its exact filename pattern; file contents and installed versions were not checked.",
                (rule["evidence"],
                 f"Affected version scope: {rule['affected_versions']}",
                 f"{len(rule['match_files'])} catalogued filename(s) matched"),
                rule["recommendation"], source=rule["source"]))
            matched_rules.append(rule)
    if not matched_rules:
        if skipped_links:
            reason = "some linked locations were skipped"
        else:
            reason = "no exact reviewed filename pattern matched the bounded listing"
        _add_mod_conflict_unchecked(game, findings, reason)
    if skipped_links:
        findings.append(_finding("mods.scan_limits", "mods", "unknown", "info",
            "Linked mod locations were skipped", "Symbolic links and reparse points were not followed, so they may contain files that were not checked.",
            (f"{skipped_links} linked item(s) skipped",),
            "Select the documented mod folder directly if it stores files in a linked location."))


def _scan_prerequisites(game, findings):
    profile = _PROFILES.get(game.id, {})
    rules = profile.get("prerequisites", ())
    if not rules:
        findings.append(_finding("prerequisites.reviewed_rules", "prerequisites", "not_checked", "info",
            "Prerequisites not assessed", "No reviewed per-game prerequisite checklist is available for this profile.",
            (), "Check the game's official system requirements and install prerequisites only through the publisher or operating-system vendor."))
        return
    for rule in rules:
        finding = _finding(rule["id"], "prerequisites", "not_checked",
            "info", rule["title"], rule["summary"],
            (rule["evidence"],),
            rule["recommendation"], source=rule["source"])
        findings.append(finding)


def _scan_compatibility(game, findings):
    profile = _PROFILES.get(game.id, {})
    rules = profile.get("compatibility", ())
    if not rules:
        findings.append(_finding("compatibility.reviewed_notes", "compatibility", "not_checked", "info",
            "No reviewed compatibility notes available", "No title-specific compatibility issue is currently recorded in the bundled troubleshooting catalog.",
            (), "Check the game's official update history and support page if you are troubleshooting a specific symptom."))
        return
    for rule in rules:
        finding = _finding(rule["id"], "compatibility", "not_checked", "info",
            rule["title"], rule["summary"], (rule["evidence"],), rule["recommendation"],
            source=rule["source"])
        findings.append(finding)


def diagnose_game(game_id, installation_path=None, config_path=None, mods_path=None):
    """Diagnose one explicit registered Windows PC profile using bounded reads.

    ``installation_path``, ``config_path`` and ``mods_path`` are local selection
    inputs. They are never serialized. When ``mods_path`` is omitted, exact
    reviewed conflict patterns are checked in the selected installation folder.
    No game executable is opened or run and no selected file is changed.
    """
    game = next((candidate for candidate in GAMES if candidate.id == game_id), None)
    if game is None or game.platform != "Windows PC":
        raise TroubleshootingError("Choose a registered Windows PC game/platform profile.")
    if sum(value is not None for value in (installation_path, config_path, mods_path)) > MAX_ROOTS:
        raise TroubleshootingError("Choose no more than three diagnostic folders.")
    findings = []
    _scan_installation(game, installation_path, findings)
    _scan_configuration(config_path, findings)
    _scan_mods(game, installation_path, mods_path, findings)
    _scan_prerequisites(game, findings)
    _scan_compatibility(game, findings)
    category_rank = {category: index for index, category in enumerate(CATEGORY_ORDER)}
    findings.sort(key=lambda item: (category_rank[item.category], item.id))
    return TroubleshootingReport(game.id, game.title, game.platform, RULESET_VERSION, tuple(findings))
