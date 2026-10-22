# Game Hub Validation Report

```json
{
  "schema_version": 1,
  "feature": "koei_tecmo_game_hub",
  "base_commit": "065096967a4b3dd4513aaffe40c8fc495f8e75c4",
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
      "command": "PYTHONPATH=src python -m unittest tests.test_game_hub_discovery tests.test_game_hub_gui tests.test_save_discovery tests.test_application_shell tests.test_version_tracker tests.test_help_center -v",
      "status": "passed",
      "tests": 115,
      "passed": 80,
      "skipped": 35,
      "failures": 0,
      "skip_reason": "Tk display unavailable in this environment"
    },
    "full_suite": {
      "command": "PYTHONPATH=src python -m tools.run_tests --workers 4 --report /tmp/koei-game-hub-rebased-report.json",
      "status": "environment_limited",
      "tested_base_commit": "3de7583dec2107dbf8589bc9dc9e4fcda9bf6b91",
      "tested_feature_head": "e5d653f",
      "tests": 3513,
      "skipped": 960,
      "failures": 0,
      "errors": 2,
      "error_modules": {
        "test_rotk3_dos.py": "An existing Tk test creates a root without checking for display availability; this headless environment raised TclError because DISPLAY is unset.",
        "test_universal_packaging.py": "test_distinct_registered_scalar_backend_is_collected uses a SimpleNamespace fixture without the achievement_source attribute now read by build_args after merged PR #111."
      },
      "source_changed": false,
      "remaining_checks": "Windows PR workflows are required for display-backed GUI coverage. The scanner dependency PR #119 and this Hub PR must pass their required checks before merge."
    },
    "package_verification": {
      "command": "python -m tools.package_release --verify-only",
      "status": "passed",
      "public_source_entries": 1226
    },
    "supported_game_inventory": {
      "command": "PYTHONPATH=src python -m tools.update_supported_games --check",
      "status": "passed",
      "profiles": 98
    },
    "windows_build_configuration": {
      "command": "PYTHONPATH=src python -m tools.build_windows --print-config",
      "status": "passed"
    }
  },
  "compatibility": {
    "scanner_api_owner": "PR #119: discover_installed_builds",
    "legacy_installed_game_positional_fields_preserved": true,
    "release_created": false,
    "version_bumped": false
  }
}
```
