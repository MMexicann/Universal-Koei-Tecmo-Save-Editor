# Workshop to Mod Manager

The Workshop can export a ZIP that the Mod Manager can import directly. Generic
Workshop ZIPs remain available for projects using other loaders or package rules.
Neither export nor library import installs a loader or changes game files.

## Supported project layouts

Use the exact manager game ID in the project and its compatibility context:

| Game ID | Replacement targets |
| --- | --- |
| `nioh2_pc` | Exactly one `.ini` and at least one `.fmt`, `.vb`, `.ib` or `.dds`, all under the INI's folder. |
| `nioh3_pc` | `.g1m`, `.g1t` or `.g1ts` named with eight hexadecimal digits, optionally prefixed by `0x`; flat or within one common wrapper folder. |

The project platform is `Windows PC`. These are Windows game/loader layouts;
running toolkit commands on Linux does not establish Proton or in-game
compatibility. `mods games` lists the current methods, evidence and limitations.
Loader installation and actual game-load validation remain separate.

Manager export preserves required dependencies with version `*`. Optional or
version-constrained dependencies are rejected because the manager cannot retain
their full semantics. Use a generic Workshop ZIP for those projects. Every
replacement must be an installable payload; documentation-only targets are
rejected rather than silently omitted.

## In the application

Open the Workshop's **Package** tab and choose **Export for Mod Manager…**.
The toolkit validates the saved project and entered compatibility context, then
shows the selected game, loader method and payload count for confirmation. Choose
a new ZIP filename in an existing folder. The exported ZIP can then be imported
into the matching manager library. Applying a game profile is a separate action.

The ZIP contains `koei-mod.json`, the selected replacements and a README retaining
the Workshop's metadata, compatibility context and self-declared rights. The
manager reviews it with the same rules used by its importer. A SHA-256 review
token binds confirmation to the exact deterministic ZIP; changed metadata or
payloads require a new review. Exports are limited to 64 MiB including metadata,
and existing files, links and destination races cannot replace other entries.

## Headless workflow

All `mods` results are JSON. These commands work without a GUI display:

```sh
universal-koei-toolkit mods games
universal-koei-toolkit mods validate --game nioh2_pc replacement.zip
universal-koei-toolkit mods import --game nioh2_pc replacement.zip --library ./mod-library --dry-run
universal-koei-toolkit mods import --game nioh2_pc replacement.zip --library ./mod-library
universal-koei-toolkit mods list --game nioh2_pc --library ./mod-library
```

Library paths are explicit. Use a dedicated application-data folder, separate
from game files. Listing an absent library and dry-run import do not create it.
Normal import adds a validated package to the library without enabling or
deploying it. Libraries are scoped by the selected game; do not infer mod support
from the separate save-editor catalog.

For a Workshop project, supply a small UTF-8 context file:

```json
{
  "game_id": "nioh2_pc",
  "game_version": "1.0.0",
  "platform": "Windows PC",
  "installed_mods": []
}
```

Installed dependencies use `{"mod_id": "example.mod", "version": "1.0.0"}`.
The context is entered by the author; the toolkit does not scan a game to verify
it. Review before exporting:

```sh
universal-koei-toolkit mods workshop-review ./project --context context.json
# Inspect package_review and compatibility, then use that result's review_token:
universal-koei-toolkit mods workshop-export ./project --context context.json --output ./new-manager.zip --review-token REVIEW_TOKEN
```

Success has exit code `0`, `success: true`, and a documented `status`
(`listed`, `validated`, `reviewed`, `imported` or `exported`). Runtime rejection
returns `1`, with an error on stderr and no success JSON. Invalid arguments or an
unknown explicit game selector return `2`. Review JSON exposes declared mod
metadata and payload names; inspect it before sharing. Procedural tests establish
package and storage behavior, not successful loading in either game.
