# Koei Tecmo Game Configuration Manager

The **Game Configuration Manager** opens from **Editing and Research**. It
inspects, compares, profiles, backs up, restores and edits a narrow list of
verified settings in two Atelier Arland DX PC text files. It does not use the
save editor's game registry: configuration formats have their own exact catalog
and compatibility identifiers.

## Supported formats

| Game profile | Exact filename | Verified writable settings |
| --- | --- | --- |
| Atelier Rorona: The Alchemist of Arland DX (PC) | `ArlandDX_Settings.ini` | `Window/FullScreen` (0/1), `Lang/Language` (1–4), `Graphics/Outline` (0/1) |
| Atelier Totori: The Adventurer of Arland DX (PC) | `ArlandDX_Settings.ini` | Same documented settings |
| Atelier Meruru: The Apprentice of Arland DX (PC) | `ArlandDX_Settings.ini` | Same documented settings |
| Any of the three profiles, when the Arland DX Fix mod is installed | `arland-fix.ini` | `Rendering/ShadowMultiplier` (1/2/4/8), `SMAA` (true/false, 1/0 or yes/no), `Sharpen` (0/30/60/100 launcher presets), `Battle/BattleCutInShadows` and `BattleCutInDimming` (true/false, 1/0 or yes/no), `Startup/SkipLogos` and `SkipIntroMovie` (true/false, 1/0 or yes/no), `Launcher/SkipLauncher` (true/false, 1/0 or yes/no), `Diagnostics/VerboseLogging` (true/false, 1/0 or yes/no) |

For the game settings file, the manager displays `Graphics/ScreenWidth` and
`Graphics/ScreenHeight` as read-only when present. Their values depend on the
monitor and the source does not establish a complete accepted domain. The mod's
`Sharpen` setting can contain custom values at runtime; only the four values
offered by the mod launcher are writable here. The mod reads boolean spellings
from their first character, as documented in its source, and its launcher writes
canonical lowercase `true` and `false`. Other observed values are shown and
preserved without coercion.

The manager accepts a file only when its exact filename matches an adapter,
the user chooses one of the exact game profiles, and at least one documented
section/key is present. A supported file may omit other optional settings; the
manager writes a setting only when that exact key already exists and its current
value is in the setting's verified writable domain. It does not add missing
keys, normalize the whole file, edit unknown keys, or infer a format from
extension alone. It preserves comments, line endings, ordering and all unmapped
bytes. Duplicate occurrences of a mapped key are rejected as ambiguous.
Unsupported files are left untouched.

Stage a documented setting, then choose **Review Changes** to compare its
opened and pending values. **Undo** reverses the latest staging action,
including a staged profile. These actions leave the file unchanged; only
**Save staged settings** writes the reviewed values. **Create backup** is
available after opening a supported file and captures its exact source bytes.

Profiles are private, path-free records bound to the selected game, exact format
ID and format revision. Applying one requires every saved setting to be present
and writable in the opened file; incompatible or partial targets are rejected
as a whole. The user reviews validated pending values before saving.
Comparisons report mapped differences and separately report
whether the remaining opaque bytes differ. Backups retain the exact original
bytes and are bound to the same identity. Save and restore create an automatic
backup, check for source changes, write atomically, and verify the bytes read
back. Compatibility checks compare explicit game and format identities; they do
not confirm an installation or prove in-game behavior.

The manager stores its path-free records under the user's application-data
directory in `UniversalKoeiTecmoSaveEditor/game-configurations/` (profiles and
backups use separate subdirectories). The source configuration is edited only
after an explicit selection in the workspace.

## Evidence and licenses

The exact filenames, file keys, setting values and mod launcher behavior are
documented by the third-party **Atelier Arland Fixes** source at commit
[`96a4506892de3284a8adc78a4b6a96d67e8bbf59`](https://github.com/nicoverbruggen/atelier-arland-fixes/tree/96a4506892de3284a8adc78a4b6a96d67e8bbf59).
Its [`config.cpp`](https://github.com/nicoverbruggen/atelier-arland-fixes/blob/96a4506892de3284a8adc78a4b6a96d67e8bbf59/src/core/config.cpp)
and [`launcher_gui.cpp`](https://github.com/nicoverbruggen/atelier-arland-fixes/blob/96a4506892de3284a8adc78a4b6a96d67e8bbf59/src/launcher/launcher_gui.cpp)
show the named settings and the launcher choices. The repository's
[MIT license](https://github.com/nicoverbruggen/atelier-arland-fixes/blob/96a4506892de3284a8adc78a4b6a96d67e8bbf59/LICENSE)
covers that project's source. This manager is an independent implementation;
it does not bundle or redistribute the mod, game files, or vendor utilities.
The language code labels and the mod's `Sharpen` launcher choices therefore have
third-party source evidence, not publisher documentation.

Koei Tecmo's Steam manuals document user-facing options, but do not define these
file schemas or other games' on-disk settings mappings. For example, the
[Rorona DX](https://store.steampowered.com/manual/936160),
[Totori DX](https://store.steampowered.com/manual/936180) and
[Meruru DX](https://store.steampowered.com/manual/936190) manuals describe
in-game language and audio options. They do not establish a general-purpose INI
format. KOEI TECMO's [System Viewer](https://www.gamecity.ne.jp/products/ktsv/en/)
is an official hardware reporting tool, not a configuration manager.

The third-party source calls the stock executables `ArlandDXEnv.exe` and
`ArlandDXLauncher.exe`, but no official vendor documentation for those names or
the files was found. They are not required or invoked by this feature. The
official [Dynasty Warriors 8 Xtreme Legends Complete Edition Steam announcement](https://store.steampowered.com/oldnews/?appgroupname=Dynasty+Warriors+8+Xtreme+Legends+Complete+Edition&appids=278080&feed=steam_community_announcements&l=english)
mentions a launch configuration tool; it does not disclose a file schema, so
that game's configuration remains unsupported here.

## Unsupported configuration files

Controls are not currently supported. The official
[*Bladestorm: Nightmare* manual](https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/350310/manuals/steam%28digital%29_BSN-EN.pdf),
pages 12–13, and the [*Dynasty Warriors 7 Xtreme Legends Definitive Edition*
manual](https://store.steampowered.com/manual/968790), page 10, describe editable
controls but do not map them to a serialized file format. Names such as
`inputmap.dat` and `inputmap1.dat` alone are not sufficient evidence for a
parser or writer. The same rule applies to graphics and gameplay settings in
other Koei Tecmo games: an in-game option is not evidence of an editable on-disk
schema.

No settings are invented to fill this gap. Additional support requires a
reproducible format description or licensed source that establishes the exact
filename, key locations, accepted values and compatibility scope, plus
fixtures and regression tests. Do not point this manager at save files or
unlisted configuration files.

## Stable integration boundary

The application exposes this feature as the retained tool route
`tool:game_configuration` and the method `Application.show_game_configuration()`.
The service API is `koei_editor.shared.configuration_manager`; its catalog is
`SUPPORTED_GAMES` and `SUPPORTED_FORMATS`, separate from save-game registration.
Callers should use `inspect_config`, `supported_settings`,
`compatibility_check`, `compare_configs`, `create_profile`, `apply_profile`,
`create_backup`, `restore_backup` and `save_config` instead of interpreting INI
bytes themselves. Profiles and backups carry explicit format IDs and versions.
Do not assume that every supported game's settings file represents the same
schema: compare compatibility identities before exchanging profile values.

This manager does not read Steam app IDs or installed build IDs. Its
compatibility result means that an explicitly selected file and profile match a
cataloged game and settings format; it is not a Game Version Tracker result.
That tracker requires separate exact-build evidence before reporting a tool or
format as verified for an installed build.

Game Hub and Playthrough Profiles do not apply these configuration profiles.
The Playthrough
Profiles component contract uses game-registry `game_id` and exact `game_version`
fields, while this configuration catalog has independent IDs and
`format_id`/`format_version` fields. The current Arland DX PC profiles have no
matching save-registry identity, so their settings cannot be attached to a
Playthrough Profile. Do not substitute a configuration ID for a save ID or a
format revision for a game version. A future adapter may export a path-free
`game_settings` component only when it can establish the same registered game
identity and exact game version; until then, manager snapshots remain separate
inert data. The route and service API provide a stable handoff point without
making either feature a dependency.

## Integration checks

Review the pinned evidence and catalog above
against the shipped sources, then verify these points before extending or
consuming the manager:

- keep the configuration catalog separate from save-format adapters and game
  registration;
- route discovery through `tool:game_configuration` and consume the public
  service API rather than parsing INI text in each workspace;
- preserve explicit game and format selection, exact filenames and current
  read-only boundaries;
- require source-backed field domains, reproducible fixtures and regression
  tests before marking any new field writable;
- review profile/backup compatibility by `game_id`, `format_id` and
  `format_version`, and keep stored profile records path-free;
- do not claim publisher verification or real-game load validation from the
  third-party source and synthetic tests alone.

The fixtures in `tests/test_configuration_manager.py` are synthetic public
text files made from the documented shape; they are not captured player or
game-installation data. Passing tests establish the manager's parsing,
preservation and operation contracts, not real-game acceptance.
