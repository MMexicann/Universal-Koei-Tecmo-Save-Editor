# Koei Tecmo Community Toolkit format 1

The Community Toolkit provides portable, data-only documents for character
builds, mod lists, configuration presets, playthrough manifests and compatibility
reports. Each file uses the `koei-tecmo-community-package` JSON envelope at
schema version `1`. The five standalone Draft 2020-12 JSON Schemas are
[listed below](#schemas).

These portable packages are separate from the existing
[Community plugin API](COMMUNITY_PLUGINS.md). Package data does not add
capabilities to plugins or change their execution limits.

These files are community-authored metadata. A valid package has passed structural
validation only: character values are not checked against a game's rules, a mod
is not certified safe or compatible, configuration keys are not automatically
recognized, playthrough steps are not verified and compatibility reports are
not application attestations. Display the author and community provenance. A
report's `compatible` status is its author's claim, not a Koei Tecmo or application
endorsement.

## Package envelope

Every package has exactly these properties. Unknown keys fail validation.

| Property | Contract |
| --- | --- |
| `schema` | Exact string `koei-tecmo-community-package` |
| `version` | Integer `1`; booleans are not accepted as integers |
| `kind` | `character_build`, `mod_list`, `configuration_preset`, `playthrough_manifest` or `compatibility_report` |
| `id` | Stable lowercase ASCII package identity, up to 128 characters; use a namespace such as `community.example-build` |
| `title` | Nonempty plain text, up to 160 characters |
| `author` | Nonempty plain text, up to 120 characters; author names are self-declared |
| `game_id` | Lowercase game-profile ID, up to 64 characters |
| `platform` | Lowercase platform ID, up to 64 characters; use `any` when the package is not platform-specific |
| `game_version` | A nonempty version label up to 80 characters, or `null` when unspecified |
| `description` | Nonempty plain text, up to 1,000 characters |
| `payload` | The exact object for the selected `kind`, described below |

Package, character, mod, skill, equipment, objective, component and setting IDs
use lowercase ASCII letters and digits, with dots, hyphens or underscores
between segments; they are limited to 128 characters. Setting keys and stat keys
have the same limit. Game-profile IDs start with a lowercase letter and use only
lowercase letters, digits or underscores. Platform IDs use the general ID form
with a 64-character limit. Text is inert and should be rendered as escaped plain
text. Scalar text values are nonempty and at most 1,024 characters; version
labels are nonempty and at most 80 characters; compatibility details are
nonempty and at most 2,048 characters; mod source URLs are at most 2,048
characters. Integer scalar values range from −9,223,372,036,854,775,808 through
18,446,744,073,709,551,615.

Files are UTF-8 JSON, limited to 1 MiB. Arrays contain at most 256 entries.
JSON Schema provides structural checks; runtime validation additionally rejects
duplicate property names, control and invisible format characters, nonfinite
numbers, fractional or exponent-form JSON numbers, and excessive nesting. Number
tokens must use integer notation. It parses HTTPS URLs and rejects malformed
authorities or ports, credentials and whitespace. Runtime validation also
enforces uniqueness rules and cross-record relationships. This includes
checking the mod load order against enabled mods and rejecting playthrough
dependency cycles, which JSON Schema does not express.

Never include copyrighted game assets, private saves, account identifiers,
personal file paths or restricted code. No package kind accepts embedded files.

## Package kinds

### `character_build`

The payload contains `character_id`, `level`, `stats`, `skills` and `equipment`.
`character_id`, stat `key`s, skill `id`s, equipment `slot`s and equipment `id`s
are stable identifiers. `level` is an integer from 1 through 9,999 or `null`.
Stats are `{ "key", "value" }` records; values are strings, integers or
booleans. Skills are `{ "id", "rank" }` records with integer ranks from 0
through 9,999. Equipment entries are `{ "slot", "id" }` records. These
identifiers are descriptive references, not instructions to modify a save.
Provide a level or at least one stat, skill or equipment entry. Each list may be
empty when another value makes the build nonempty. Stat keys, skill IDs and
equipment slots must be unique. Scalar strings are nonempty and at most 1,024
characters.

### `mod_list`

The payload contains at least one mod and a `load_order` list. Each mod has `id`,
`title`, `version`, `source_url`, `sha256` and `enabled`. `version`, `source_url`
and `sha256` may be `null`. A source link, when present, uses lowercase
`https://`; a digest, when present, is 64 lowercase hexadecimal characters.
`load_order` contains every enabled mod ID exactly once and refers to entries in
the same list. It is empty only when no mod is enabled. Mod IDs must be unique.
Version labels are nonempty and at most 80 characters; titles are nonempty and
at most 160. URLs cannot contain whitespace or credentials.

A mod list contains references and optional digests only. It never embeds a mod,
game executable, archive, asset, script, loader or restricted code. The reader
does not fetch a link or verify the linked download. Users should inspect a
mod's provenance and files with their normal security tools before installing it.
Before sharing a package, review source URLs for access tokens, private hostnames
and other sensitive query values.

### `configuration_preset`

The payload contains at least one `{ "key", "value" }` setting, and keys must
be unique. Values are nonempty strings up to 1,024 characters, integers or
booleans; floating-point and null values are rejected. Package validation checks
only the data shape. A consuming feature must match keys against its own explicit
allowlist, show the full proposed change and require an intentional user action
before applying recognized values. Unknown settings are ignored or rejected by
that integration; a package cannot supply paths, commands or arbitrary files.

### `playthrough_manifest`

The payload contains at least one `{ "id", "title", "status", "order",
"depends_on" }` record. Status is `planned`, `active`, `complete` or `skipped`;
`order` is a unique integer from 0 through 100,000. Objective IDs are unique.
Every dependency names another objective in this manifest, cannot refer to
itself and the dependency graph must be acyclic. Manifests describe checklists
and relationships; they contain no save bytes, account identity or private save
path. Objective titles are nonempty and at most 160 characters.

### `compatibility_report`

The payload contains at least one `{ "component", "version", "status",
"details" }` record. `version` may be `null`; status is
`compatible`, `incompatible` or `unknown`. Component/version pairs are unique.
Details are nonempty plain text up to 2,048 characters, not executable
instructions. This is a portable report of a contributor's observation; it does
not grant the package authority to alter the application's supported-game
registry or mark a game's editor verified.

## Validate and share

Run the local checker on a selected folder:

```text
python -m tools.check_community_packages PATH_TO_SELECTED_FOLDER
```

Discovery is shallow and bounded: it examines at most 512 directory entries
and 256 matching files, with each package limited to 1 MiB. The checker prints a
path-free JSON `koei-tecmo-community-validation-report` version 1 document; it
does not include local filenames or paths. Exit code 0 means at least
one package was found and every package passed structure validation. An empty
folder, discovery error or any invalid package returns a nonzero exit code.
`validation_scope` is `package_structure_only`; a valid report is not a game
compatibility certification. Results use stable file indexes in deterministic
filename order. Package and game IDs remain contributor-authored metadata;
review a report before sharing it.

The repository includes small fictional metadata examples, all for
`sample_game` and the `any` platform:

- [Character build](../tools/community_package_templates/character_build.koei-community.json)
- [Mod list](../tools/community_package_templates/mod_list.koei-community.json)
- [Configuration preset](../tools/community_package_templates/configuration_preset.koei-community.json)
- [Playthrough manifest](../tools/community_package_templates/playthrough_manifest.koei-community.json)
- [Compatibility report](../tools/community_package_templates/compatibility_report.koei-community.json)

The public module is `koei_editor.shared.community_packages`:

```python
from koei_editor.shared.community_packages import dumps, export, load, loads

package = loads(raw_json_bytes)        # bounded UTF-8 parse and full validation
portable_bytes = dumps(package)         # validate again before serialization
reopened = load(selected_package_path)  # bounded ordinary-file read
new_path = export(package, destination) # create a new file; never overwrite
```

`export(package, path)` validates and writes a new package file without replacing
an existing destination. The `*.koei-community.json` suffix identifies these
documents. `loads()` and file import return a validated `CommunityPackage` data
object; constructors are for trusted host code. External data must go through
the public readers. No API in this format executes, imports, installs or invokes
package content.

Keep community packages in a folder or share them through a service you choose.
The application does not host, upload, synchronize or distribute packages.
There is no remote hosting service in this feature.

## Schemas

- [Character build v1](schemas/koei-community-character_build-v1.schema.json)
- [Mod list v1](schemas/koei-community-mod_list-v1.schema.json)
- [Configuration preset v1](schemas/koei-community-configuration_preset-v1.schema.json)
- [Playthrough manifest v1](schemas/koei-community-playthrough_manifest-v1.schema.json)
- [Compatibility report v1](schemas/koei-community-compatibility_report-v1.schema.json)

## Integration contract

Package parsing is independent of the editor and game adapters. A host feature
can use the validated `CommunityPackage` as a read-only proposal, then perform
its own exact-profile lookup, target allowlist checks, preview and authorization.
Use the stable package `kind`, `game_id`, `platform`, `game_version` and payload
keys as the integration boundary. Preserve the package ID and author in any
review UI, and do not treat an unrecognized game, field, mod or setting as
supported merely because the document parses.

Portable builds do not replace source-bound edit presets or the separately
qualified reusable-resource preset API. Applying values to a save still requires
the existing editor's native validation, dependency checks, change review,
Undo, backups and Save As workflow.
