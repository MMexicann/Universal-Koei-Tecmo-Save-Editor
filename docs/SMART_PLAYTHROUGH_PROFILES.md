# Smart Playthrough Profiles

Smart Playthrough Profiles save a reusable reference to a verified Save Vault
snapshot, exact game-version text and optional manager exports. Open the feature
from **Save Library → Save Doctor / Detection / Vault → Smart Playthrough
Profiles…**.

## Create, preview and prepare

Choose a verified Vault snapshot, name the profile and enter the exact version
you intend to use. Playthrough Profiles requires a manually entered game
product version and does not consume Game Version Tracker observations.
Optional component imports must identify the same registered game/platform and
exact version as the selected save snapshot.

The Game Version Tracker reads mapped Steam app manifests and can show exact
Steam build IDs alongside reviewed compatibility records. A Steam build ID is
installation metadata; it does not establish the game's product version or save
format revision. The separate Game Patch Compatibility Analyzer compares two
install snapshots and can evaluate explicit requirements. Profile preview still
uses the exact user-entered version and labels it `user_asserted`; it does not
infer that value from a Steam build ID or synthesize analyzer evidence.

Preview reports whether the profile version exactly matches the entered
installed version and whether the referenced snapshot still passes Vault hash
and native qualification. Any mismatch or missing/corrupt snapshot blocks
preparation.

Preparing a compatible profile can optionally snapshot an independent copied
save before restoring the profile into a **new isolated directory**. That is a
safe way to prepare another playthrough copy. It does not activate a game
profile, launch a game or switch game-managed state. It never overwrites an
existing folder or live save. Live and cloud paths are rejected. A failed write
may leave an incomplete new isolated directory, following the Vault restore
contract; the error identifies that directory for review and does not claim
success. If the optional backup was completed first, the error also reports its
Vault snapshot ID.

Creating a new profile-store or environment directory uses a handle-bound
operation on Windows and Linux. Other POSIX platforms fail closed when a new
directory is required because this application does not have an equivalent
safe create-and-bind primitive there.

## Manager component contract

The component providers are fixed to these identities:

| Component | Provider |
| --- | --- |
| `mod_configuration` | `mod_manager` |
| `game_settings` | `configuration_manager` |
| `character_build` | `character_workshop` |

An exported UTF-8 JSON component has this shape:

```json
{
  "component": "game_settings",
  "provider": "configuration_manager",
  "schema_version": 1,
  "game_id": "registered-game-platform-id",
  "game_version": "exact-version-string",
  "payload": { "example": "manager-owned JSON data" }
}
```

The profile store validates bounded JSON, rejects duplicate keys and nonfinite
numbers, checks the provider/component pair, and requires exact game and version
matches. It binds a SHA-256 digest to each component in the profile manifest and
staged artifact. Components are opaque data and are not applied to the game.
Profiles accept bounded JSON imports; they do not automatically export from or
apply through the manager tools. The Configuration Manager is available as a
separate tool, but it does not yet export this component envelope. Its current
Arland DX PC catalog IDs do not match a registered save-game identity, and its
profiles do not establish an exact installed game version, so those settings
cannot yet be attached to a Save Vault playthrough. Do not substitute a
configuration ID for a save ID or a settings format revision for a game version.
A future adapter needs a shared registered game identity and exact version
evidence before it can export a path-free `game_settings` snapshot.

## Reports

The **Export visible report…** action writes a new JSON file and refuses to
replace an existing one. Preview reports use schema `koei-playthrough-preview`;
prepared environment reports use `koei-playthrough-environment-report`. Both
identify the installed version source as `user_asserted`, list compatibility
blockers and record `components_applied: false` and `live_save_written: false`.
Prepared reports additionally include the verified Vault snapshot ID, relative
restored-save location, optional active-copy backup ID and component digests.
Component JSON files are staged directly in the new environment folder as
`component-<type>.json` beside `playthrough-report.json`.
They omit absolute local paths and save bytes. These reports summarize this
application's checks; they do not establish that the game loads the save or that
manager data is compatible beyond matching the declared game/version strings.

## Integration coverage

`tests/test_playthrough_profiles.py` uses generated and existing procedural
fixtures only. It covers bounded profile persistence, exact version matching,
component digests, save and companion byte preservation, copied-save backup,
new-directory restoration, corrupt/tampered data, failed backup reporting and
rejection of existing, Vault and live/cloud destinations. It does not need
private player saves or establish actual game loading.

```text
python -m unittest tests.test_playthrough_profiles -v
```
