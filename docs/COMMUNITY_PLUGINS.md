# Community contributions and plugin API 1

Community plugins add plain-text help, preparation workflows and commands that
open that content. They cannot edit saves, register a game, run Python, access
application sessions, open a network connection or invoke operating-system
commands. Their text is community guidance, not verified compatibility evidence.
The existing explicit [game registry](../src/koei_editor/game_registry.py) and
[scalar adapter contract](../src/koei_editor/shared/adapter_contract.py) remain
authoritative for game support and editing.

## Inspect, review and enable

Open the application's Community plugins panel and choose a directory containing
`*.plugin.json` files. Discovery is explicit, shallow and read only. It never
imports modules, scans Python entry points or installs packages. Valid and
rejected candidates appear in the list; search covers titles and declarations.

Select a candidate to inspect its ID, author, API, exact capabilities, SHA-256
and every declaration. Review its text, select the review checkbox, then choose
**Enable reviewed snapshot**. This approves only that immutable manifest snapshot
for the current session. Disabled plugins contribute nothing to runtime search
or command resolution. **Disable selected plugin** revokes all contributions
immediately. Restarting or successfully inspecting a directory again resets
every approval. Editing a file never changes an approved snapshot: inspect and
approve the new digest separately. Author names are self-declared, not verified
identities or digital signatures.

The panel supports English and German. Every declaration has an explicit locale;
hosts may filter runtime search by locale. Community text stays visible in its
original language. No automatic translation or remote service is used.

## Create and check a declaration

Copy [the bilingual example](../tools/community_plugin_template/example.plugin.json)
to your own directory. Keep a stable namespaced plugin ID such as
`community.your-guide`. Give each contribution its own stable local ID, including
separate IDs for translations. The runtime ID becomes
`community.your-guide:prepare-en`.

From an installed checkout, validate a directory without enabling anything:

```text
python -m tools.check_community_plugins tools/community_plugin_template
```

Exit 0 means all discovered declarations pass schema and registration checks;
an empty directory, invalid declarations or conflicts return 1. This does not
certify the accuracy of contributed advice or game compatibility. Output contains
manifest basenames and public metadata, never selected directory paths, player
saves, account data or personal diagnostics.

Each manifest has exactly these required properties; unknown properties fail
closed:

| Property | Contract |
| --- | --- |
| `schema` | Integer `1`; booleans are rejected |
| `api` | Exact string `"1"`; no ranges, coercion or fallback |
| `id` | Stable lowercase ID with a community namespace containing a dot |
| `title`, `author` | Nonempty plain text, at most 160 characters each |
| `version` | Numeric `major.minor.patch`; plugin version is separate from app v3.0 |
| `description` | Nonempty plain text, at most 1,000 characters |
| `capabilities` | Unique subset of `help`, `workflows`, `commands`; must exactly match contributed kinds |
| `contributions` | 1–64 declarations |

All declarations require exactly `kind`, `id`, `title`, `locale`, `game_ids` and
the properties specific to their kind:

| Kind | Extra properties | Behavior |
| --- | --- | --- |
| `help` | `body`: nonempty text, at most 8,192 characters | Read-only guidance |
| `workflows` | `platforms`: 1–12 unique labels, at most 80 characters each; `steps`: 1–24 nonempty text steps, at most 2,048 characters each | Read-only ordered instructions |
| `commands` | `target`: local ID of this plugin's help or workflow | Returns content for the host to display |

IDs contain lowercase ASCII letters/digits separated by dots, hyphens or
underscores and are at most 80 characters. Local IDs must be unique across all
kinds and locales. Titles are at most 160 characters; locales are `en` or `de`.
`game_ids` is a unique list of up to 32 exact host-registered game/platform IDs;
an empty list means global guidance. Game IDs do not create adapters or establish
support. A command's locale and game scope must match its target. Commands cannot
target another command, another plugin, a host operation, a file or a URL.

The parser accepts UTF-8 JSON only, rejects duplicate keys, nonfinite numbers,
deeply nested invalid input, control characters and invisible format controls.
Manifests are bounded to 128 KiB, directory inspection to 512 entries and 64
matching manifests. Discovery does not recurse. Symlinks and nonregular files are
rejected, bounded reads check the opened file identity, and errors avoid exposing
selected private directory paths. Duplicate plugin/contribution identities
quarantine every conflicting candidate; host-reserved IDs also fail closed.

## Host integration

The core [community_plugins.py](../src/koei_editor/shared/community_plugins.py)
does not import the application or game backends:

```python
from koei_editor.shared.community_plugins import PluginCatalog, discover_plugins

# host_game_ids and host_reserved_ids come from the host's explicit registries.
candidates = discover_plugins(user_selected_directory, known_game_ids=host_game_ids)
catalog = PluginCatalog(candidates, reserved_ids=host_reserved_ids)

# Only after an explicit review action for this displayed snapshot:
candidate = candidates[0]
catalog.approve(candidate.manifest.id, sha256=candidate.sha256,
                capabilities=candidate.manifest.capabilities)

articles = catalog.search('companion', kind='help', locale='en')
commands = catalog.contributions('commands')
content = catalog.resolve_command(commands[0].id)
catalog.disable(candidate.manifest.id)
```

Check `catalog.entries` for candidate/error/enabled states before offering approval.
`contributions()` and `search()` expose only enabled contributions;
`resolve_command()` returns an immutable `Contribution`, never a callback.
Render all text as plain text, retain a community provenance label, and do not
interpret links, markup, code or paths as executable actions. The API's dataclass
constructors are for trusted host code; external input must pass through
`validate_manifest()` or `discover_plugins()`, rather than constructing candidates
from decoded dictionaries.

[PluginPanel](../src/koei_editor/shared/plugin_gui.py) supplies a complete retained
Tk view with `.frame`, `.catalog`, `.apply_theme(palette)`,
`.set_language('en'/'de')` and optional `on_change(catalog)` callback. Hosts can
refresh help/palette results on change. `contribution_text()` formats inert content
for a read-only preview. Approval is deliberately in memory, separate from game
save storage and global preference files.

## Contributing new game support or executable functionality

Use the existing [scalar adapter starter](../tools/adapter_template/INSTRUCTIONS.md)
and [contributor guide](../CONTRIBUTING.md). Python in a process has that process's
permissions; **this API is not a sandbox and never loads community Python**.
Executable functionality requires source review, normal focused PRs and required
checks before it becomes part of the application. There is no hot-loading bypass.

A game submission must qualify its exact game/platform/revision, immutable
no-edit roundtrip, field evidence/bounds, corruption and foreign-format rejection,
native integrity, staged edits, read-back, Undo, backups and safe new-copy writes.
Register only reviewed implementations, update canonical inventories, and keep
procedural checks, genuine-file qualification and actual game loading/re-saving
distinct. Reuse the existing adapter contract and storage helpers; do not create
a parallel registry, editor or save writer through plugins. Newly claimed support
also needs the reviewed metadata, build/source-manifest entries and documentation
specified by the contributor guide.

Future executable extensions would require a separately reviewed process-isolation
and capability protocol. API 1 grants no such execution or storage capabilities.
Application v3.0 includes this data-only API; plugin versions remain independent.
