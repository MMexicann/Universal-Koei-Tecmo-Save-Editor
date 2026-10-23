# Game Troubleshooting Center

The Game Troubleshooting Center provides bounded, read-only checks for a
selected Windows PC game profile. It inspects only installation, configuration
and mod folders that the user selects. It never launches a game, installer,
mod, shell command or repair tool, and it never writes into selected game or
configuration folders.

Folder scans run on Windows and Linux through anchored, no-follow directory
access. Linux uses directory-relative file descriptors. Windows uses native
local-drive handles, retains the selected ancestor chain, enumerates native
128-bit file identities and opens configuration files relative to the held
parent. Linked/reparse items and changed identities are rejected. Network shares,
device paths or filesystems without the required native identity/enumeration
support remain **Unknown**. Windows behavior requires actual native CI checks;
Linux checks do not qualify Windows APIs. The selected game profile remains a
Windows PC profile; scanning it on Linux does not certify Wine/Proton behavior.

## Reading a report

Reports use schema `koei-game-troubleshooting` version `1` and include the
bundled ruleset version. Finding IDs and category order are stable. JSON output
contains no scan timestamp, absolute path, configuration value, file content or
file hash, so the same evidence and ruleset produce repeatable output. When a
folder exceeds a safety limit, partial listings are not used to claim that
files or markers are present or absent.

Statuses mean:

- **Passed:** the stated bounded check succeeded. This does not certify the
  entire game or system.
- **Warning:** an observation deserves review, but it does not by itself prove
  the cause of a problem.
- **Failed:** a reviewed requirement or selected input was rejected.
- **Unknown:** the selected evidence could not be assessed safely.
- **Not checked:** no applicable reviewed rule or explicit input was available.
- **Partial:** some checks completed while others were unknown or not checked.

An empty folder does not prove a missing prerequisite. A visible loader name
does not prove that a mod is installed or that two mods conflict. A Steam app ID
is candidate package metadata; it does not identify the contents of a selected
folder. Unknown and not-checked results are deliberate where game-specific
evidence is absent.

## Checks

**Installation.** The tool confirms that a selected folder can be read and
counts ordinary files within a fixed depth and entry limit. It does not read or
hash executables, verify Steam files, inspect installation binaries, or compare
every file with a publisher manifest. Linked and reparse-point items are
skipped.

**Configuration.** If a configuration folder is selected, the tool performs a
size-limited syntax parse of ordinary `.ini`, `.cfg`, `.json` and `.xml` files.
UTF-8 and UTF-8 with a byte-order mark are checked; other encodings are left
unverified. It does not retain values, display setting contents, or decide
whether a valid setting is correct for a particular game build. A syntax
warning should be checked against the game's own documentation before any
manual change.

**Mods.** The catalog can hold exact, per-game relative filename patterns for
documented mod conflicts, including their version scope and source. A matching
pattern is reported as a possible match because this scan does not inspect file
contents or confirm installed game/mod versions. The current catalog has no
reviewed conflict patterns; without one, the report says conflicts are not
checked.

**Prerequisites.** The catalog records source-backed requirements but does not
infer that a component is missing without a reliable probe. For DYNASTY
WARRIORS: ORIGINS, KOEI TECMO lists DirectX 12 or over; this scan reports the
requirement as informational and does not inspect system folders or establish
graphics feature support. Other profiles without reviewed requirements are
not checked.

**Compatibility.** The catalog currently records one version-specific official
Steam update note for DYNASTY WARRIORS: ORIGINS. KOEI TECMO says Steam v1.0.1.1
(2026-01-30) fixed battle frame-rate drops after selecting a companion added in
the *Visions of Four Heroes* DLC. The center does not read the installed game
version or reproduce the symptom; it presents the note as informational and
recommends checking Steam only when the described symptom applies.

Sources:

- [DYNASTY WARRIORS: ORIGINS Steam system requirements](https://www.koeitecmoamerica.com/dw_origins/us/products/steam_spec.html)
- [DYNASTY WARRIORS: ORIGINS official update history](https://www.koeitecmoamerica.com/dw_origins/us/update/)

## Safety and reproducibility

Selected game, configuration and mod folders are inspected read-only, with
configuration files opened only within the fixed file-size limit. Symlinks and
reparse points are not followed. Report export writes a new JSON report to a
location the user chooses; it does not change the selected game folders. If a
scan reaches a limit or cannot read a selected path, the result says so instead
of treating unseen files as missing.

The bundled catalog is schema-validated at load time. Each game-specific
prerequisite, mod conflict or compatibility rule carries a stable ID and
primary source URL.
Synthetic tests use temporary trees and assert that their contents remain
unchanged after scanning. Linux race tests replace queued directories and files;
native Windows cases require handle-bound enumeration/reads without a pathname
fallback, reject replaced identities and verify that held directory handles
prevent rename. Configuration values and native file identities remain internal
and never enter exported reports.
