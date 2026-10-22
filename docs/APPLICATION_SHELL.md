# Application shell

The v3.0 shell owns navigation, retained workspaces, appearance and command
discovery. Game dashboards and their save/edit contracts remain in the game
editors. Returning to a workspace reuses the same editor instance and pending
changes. Navigation never opens a file automatically.

**Tools → Editing & Research → Game Asset Explorer** opens an optional,
read-only asset workspace. It asks the user to choose a local file and stores
only its stable workspace command ID in shell recents. It does not save paths or
asset contents. See [its format and validation limits](ASSET_EXPLORER.md).

Controller & Input Profiles is a retained global workspace available from
**Editing and Research** and Ctrl+K. It stores user-defined mappings in
application-owned profile storage; it does not apply them to game files or
Steam Input.

## Keyboard and discovery

- **Ctrl+K** opens the command palette from the library, tools or game editor.
  Search matches game/platform identities, tools and available editor commands.
- **Up/Down** changes the highlighted command; **Enter** executes it.
- **Esc** closes the palette and restores focus. The palette respects an
  existing modal review/safety dialog.
- **Ctrl+D**, or the visible favorite button, toggles a command favorite.
  Search `favorites` or `recent` to filter those groups. German equivalents
  also work when German is selected.
- **Koei Tecmo Mod Manager** is available in the Editing and Research menu and
  the Ctrl+K command palette. The manager is a retained workspace; its Nioh 2
  installation and profile controls are independent of save-editor sessions.
- **Ctrl+F** keeps the existing workspace-specific search behavior. **F1** opens
  the Help Center. Its menu includes compatibility, preparation guides, feedback,
  real-game validation and plugin documentation.

Editor windows shorter than 900 pixels use a compact single-row header with
Home, Help, Ctrl+K, the existing session selector and a Navigation button.
That button expands the full navigation and appearance settings in one click;
collapsing them preserves vertical space for fields and dashboards. Language
and text size also remain available through Ctrl+K commands in this mode.
Taller editor windows, the library, global tools and Help show full navigation.
The full header wraps navigation into two rows when space is limited. Library cards
reduce their column count as the window narrows. Language and
text size controls remain visible. English and German cover shell labels and
commands; game names, original technical evidence and game editor contents are
not automatically translated. Text sizes of 100%, 120% and 140% apply to shared
standard controls. Tk's platform DPI scaling remains enabled and is not replaced
with a hardcoded scaling factor.

## Game Hub

Game Hub is available from the main navigation and Ctrl+K. It reuses the bounded
Steam discovery scanner and its reviewed mappings for supported Windows PC
profiles. The first visit scans Steam's known install roots and any additional
libraries listed by `libraryfolders.vdf`; **Refresh installations** repeats the
scan, and **Browse** can select a Steam root directly. Detection reads install
manifests only. It does not inspect save folders or game files.

Installed rows show the Steam build ID, manifest update time, install size,
Steam library and installation folder. Steam's build ID is not necessarily the
game's displayed patch version. Launch explicitly asks the operating system to
open the known game's `steam://run/` link. **Open install folder** uses the local
file manager. Notes are optional local text saved beside the app's preferences;
they do not change Steam metadata or game files. A not-detected row describes
the current scan, and a partial scan is labelled as such.

The hub lists only game profiles with reviewed Steam install mappings. It does
not claim that profiles without a mapping are uninstalled. The separate Save
Library continues to handle copied save discovery and validation.

## Preferences and privacy

`shared/shell_preferences.py` stores a separate `preferences.shell.json` beside
the existing theme/pin preferences. The bounded, versioned schema contains only
language, text size, favorite command IDs and the latest 20 workspace IDs. It
contains no filenames, save paths, field values, account data or save contents.
No network request or telemetry is involved. Removing this file resets shell
preferences without changing existing theme/pin preferences or saves.

Unknown, malformed, duplicate or oversized preferences fall back to defaults.
Writes use an atomic replacement. Read-only sessions using
`Application(..., persist_preferences=False)` keep changes in memory.
Game Hub notes use a separate bounded local settings file and contain no install
paths. Steam install paths stay in the local view and are omitted from portable
discovery reports.

## Extending global commands

`shared/command_palette.py` provides immutable `CommandEntry` values and the pure
`search_commands` function. The application builds entries lazily when the
palette opens. `Application.execute_command` resolves only IDs present in the
current catalog through explicit callables. Enabled community plugin commands
are added after the plugin manager has approved them. Their `plugin:` identities
resolve to inert help content in the plugin panel. Preference files and community
metadata cannot supply Python callbacks, imports or shell commands.

To add a shell command, define its label in both catalogs in
`shared/localization.py`, add its entry in `Application.command_entries`, and
resolve its stable ID explicitly in `execute_command`. Use `game:`, `tool:` or
`command:` IDs followed by a lowercase identifier. Plugin IDs can also contain
namespacing punctuation, bounded to 161 characters. Never include save paths or
dynamic gameplay values in an identity.

Library searches reuse the immutable `LibraryCatalog` index. Changes in one Tk
event-loop burst coalesce into one render; explicit platform selection and Enter
flush pending search work. Every registered game button remains available
through the existing public mappings for integrations and keyboard navigation.

## Validation

Run `python -m unittest tests.test_application_shell tests.test_library_search
tests.test_universal_app tests.test_dashboard_application_theme -v` with a GUI
display. GUI modules must run serially on a shared display to avoid stealing
keyboard focus from each other. See [PERFORMANCE.md](PERFORMANCE.md) for the
repeatable library/startup benchmark. These checks do not establish real-game
load/re-save compatibility; native Windows release checks remain separate.
