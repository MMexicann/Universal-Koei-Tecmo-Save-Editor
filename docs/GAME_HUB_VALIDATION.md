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
      "status": "environment_limited",
      "tests": 3369,
      "skipped": 950,
      "failures": 0,
      "errors": 1,
      "error_module": "test_rotk3_dos.py",
      "error_summary": "An existing Tk test creates a root without checking for display availability; this headless environment raised TclError because DISPLAY is unset.",
      "source_changed": false,
      "remaining_checks": "Windows CI is required to exercise GUI tests with a display."
    },
    "package_verification": {
      "command": "python -m tools.package_release --verify-only",
      "status": "passed",
      "public_source_entries": 1187
    }
  },
  "compatibility": {
    "legacy_installed_game_positional_fields_preserved": true,
    "release_created": false,
    "version_bumped": false
  }
}
```
