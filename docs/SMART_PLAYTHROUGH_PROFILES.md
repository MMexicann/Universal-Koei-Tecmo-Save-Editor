# Smart Playthrough Profiles

Smart Playthrough Profiles save a reusable reference to a verified Save Vault
snapshot, exact game-version text and optional manager exports. Open the feature
from **Save Library → Save Doctor / Detection / Vault → Smart Playthrough
Profiles…**.

## Create, preview and prepare

Choose a verified Vault snapshot, name the profile and enter the exact version
you intend to use. The version is entered by the user; this application does not
detect installed game builds. Optional component imports must identify the same
registered game/platform and exact version as the selected save snapshot.

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
staged artifact. Components are opaque data: this checkout does not include the
Game Hub, Mod Manager, Configuration Manager or Character Workshop execution
interfaces, so it cannot export from or apply to those managers. A future adapter
can exchange the typed `ProfileComponentSnapshot` without treating a profile as
an executable command.

## Reports

The **Export visible report…** action writes a new JSON file and refuses to
replace an existing one. Preview reports use schema `koei-playthrough-preview`;
prepared environment reports use `koei-playthrough-environment-report`. Both
identify the installed version source as `user_asserted`, list compatibility
blockers and record `components_applied: false` and `live_save_written: false`.
Prepared reports additionally include the verified Vault snapshot ID, relative
restored-save location, optional active-copy backup ID and component digests.
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
