# Controller and input profiles

The Controller & Input Profiles workspace keeps profiles for exact registered
Windows PC game IDs in this application’s user configuration folder. A profile
records a name, a controller label layout, user-defined action names and their
keyboard and controller bindings. Built-in presets are editable starting
points. Selecting a profile only opens it in this manager; it does not apply
settings to a game.

The manager never writes into a game installation, save directory, Steam
directory or controller-tool configuration. It does not change Steam Input or
launch controller software. Profile storage is separate from game files and
uses bounded JSON, atomic replacement and a recoverable local backup. Export
and import move profile data only. Restoring a backup replaces the manager’s
profile collection after a confirmation and retains the current collection as
a recovery copy.

## Verified format scope

The repository currently has no qualified Koei Tecmo keybinding configuration
writer or documented external controller-tool profile format to edit:

- [Dynasty Warriors 3 save-format notes](SAVE_FORMAT.md) identify a shipped
  `DefaultGame.ini` setting for the save encryption key. It is not an input
  mapping file.
- [Warriors Orochi 3 Ultimate transfer notes](WO3U_PS4_RESOURCE_TRANSFER.md)
  identify an embedded PC platform-configuration span that contains controller
  data. Current transfers preserve its complete bytes; they do not edit the
  bindings.
- [Dynasty Warriors 6 conversion notes](DW6_CONVERSION.md) distinguish
  platform-specific controller mappings.
- [Original Warriors Orochi PC notes](WO1_PC_FORMAT.md) mention separate
  controller mappings in a shared archive, but that archive is not shipped.

These findings do not establish a writable configuration format or a version
and game-specific input mapping. No game configuration file is modified, and
no external tool integration is enabled. Future adapters need a documented
format, exact game/platform/revision scope, safe backup and restoration
behavior, and independent read-back checks before they can write a game or
external-tool configuration. Steam Input remains under the user’s control.

## Integration surface

The reusable profile store associates each profile with a registered game ID
and exposes validated profile data without opening game paths. The workspace
can be embedded by global navigation tools such as a Game Hub; a separate,
verified Game Configuration Manager can later provide its own explicitly
qualified configuration adapter. Profile metadata is not evidence of native
game support.

## Validation boundary

Automated tests use temporary app-owned JSON files to exercise schema checks,
presets, atomic saves, backup and recovery, import/export and malformed-file
rejection. They do not establish support for any native game configuration,
Steam Input action set or external controller tool. No actual game config or
Steam setting is read or changed.
