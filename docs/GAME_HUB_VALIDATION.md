# Game Hub Validation Report

```json
{
  "schema_version": 1,
  "feature": "koei_tecmo_game_hub",
  "scope": {
    "steam_mappings": "Existing reviewed Windows PC profile mappings",
    "discovery": "Steam library and app manifest metadata only",
    "launch": "Known Steam app IDs through the registered steam://run handler",
    "installation_management": [
      "View install and Steam library paths locally",
      "Open the install folder",
      "Save bounded local notes beside preferences"
    ],
    "build_metadata_note": "Steam build IDs are not asserted to be in-game patch versions"
  },
  "checks": {
    "focused_tests": {
      "command": "python -m unittest tests.test_game_hub_discovery tests.test_game_hub_gui tests.test_save_discovery tests.test_application_shell -v",
      "status": "passed",
      "tests": 86,
      "skipped": 30,
      "skip_reason": "Tk display unavailable in this environment"
    },
    "full_suite": {
      "command": "python -m tools.run_tests --workers 4",
      "status": "pending"
    },
    "package_verification": {
      "command": "python -m tools.package_release --verify-only",
      "status": "pending"
    },
    "windows_ci": {
      "status": "pending"
    }
  },
  "compatibility": {
    "legacy_installed_game_positional_fields_preserved": true,
    "release_created": false,
    "version_bumped": false
  }
}
```
