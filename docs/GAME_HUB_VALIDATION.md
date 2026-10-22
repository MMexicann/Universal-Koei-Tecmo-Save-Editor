# Game Hub Validation Report

```json
{
  "schema_version": 1,
  "feature": "koei_tecmo_game_hub",
  "base_commit": "60e70fe8c30ea76429a920a88a2b02ade9850244",
  "scope": {
    "steam_mappings": "Existing reviewed Windows PC profile mappings",
    "discovery": "Steam library and app manifest metadata only",
    "shared_discovery_api": "discover_installed_builds",
    "installation_paths": "Local UI only; excluded from reports and compatibility history",
    "launch": "Known Steam app IDs through the registered steam://run handler",
    "build_metadata_note": "Steam build IDs are not asserted to be in-game patch versions"
  },
  "checks": {
    "focused_tests": {
      "command": "PYTHONPATH=src python -m unittest tests.test_game_hub_discovery tests.test_game_hub_gui tests.test_save_discovery tests.test_application_shell tests.test_version_tracker tests.test_help_center tests.test_game_troubleshooting_gui",
      "status": "passed_with_gui_skips",
      "tests": 134,
      "passed": 86,
      "skipped": 48,
      "failures": 0,
      "skip_reason": "Tk display unavailable in this environment"
    },
    "package_verification": {
      "command": "python -m tools.package_release --verify-only",
      "status": "passed",
      "public_source_entries": 1277
    },
    "supported_game_inventory": {
      "command": "PYTHONPATH=src python -m tools.update_supported_games --check",
      "status": "passed",
      "profiles": 98
    },
    "windows_build_configuration": {
      "command": "PYTHONPATH=src python -m tools.build_windows --print-config",
      "status": "passed"
    },
    "source_validation": {
      "checks": [
        "git diff --check origin/codex/version-compatibility-tracker...HEAD",
        "python -m py_compile src/koei_editor/application.py src/koei_editor/shared/localization.py src/koei_editor/shared/game_hub.py src/koei_editor/shared/game_hub_gui.py tests/test_game_hub_gui.py"
      ],
      "status": "passed"
    },
    "windows_regression_fixes": {
      "control_f_focus": "The Game Hub search requests forced focus after the shortcut; the test enters through Application.show_game_hub with an existing query.",
      "ttk_state_values": "Windows tests normalize button state values to strings before comparison.",
      "scanner_fixture": "The install fixture keeps last_updated as a bounded decimal string.",
      "windows_execution": "pending_fresh_workflow_run"
    },
    "full_suite": {
      "status": "not_run_on_rebased_branch",
      "reason": "Focused integration validation was requested for this rebase; display-backed GUI coverage remains for CI."
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
