# Character & Weapon Workshop Test Evidence

The record below is machine-readable. The full local runner report is in the ignored `work/character_weapon_workshop_test_evidence.json` artifact for this workspace.

```json
{
  "schema": "koei-editor-test-evidence/v1",
  "feature": "Character & Weapon Workshop",
  "evidence_type": "local-validation-and-windows-pr-ci",
  "checks": [
    {
      "name": "workshop-focused-unittest-suite",
      "command": "PYTHONPATH=src python -m unittest tests.test_character_weapon_workshop_model tests.test_character_weapon_workshop_dw3 tests.test_character_weapon_workshop_projections tests.test_character_weapon_workshop_staging tests.test_samurai4dx_workshop tests.test_character_weapon_workshop_gui tests.test_universal_packaging tests.test_package_release",
      "status": "passed",
      "tested_base_commit": "e09ec11",
      "tested_head_commit": "0934ecb",
      "tests": 98,
      "skipped": 7,
      "skip_reason": "Tk GUI tests require a display; this workspace has no DISPLAY or Xvfb."
    },
    {
      "name": "supported-game-inventory",
      "command": "python -m tools.update_supported_games --check",
      "status": "passed",
      "adapters": 98
    },
    {
      "name": "source-package-manifest",
      "command": "python -m tools.package_release --verify-only",
      "status": "passed",
      "tested_base_commit": "e09ec11",
      "tested_head_commit": "0934ecb",
      "verified_public_source_entries": 1283
    },
    {
      "name": "windows-pr-workflow-before-latest-mainline-rebase",
      "command": "GitHub Actions Windows build and release workflow run 39842751104",
      "status": "failed-with-unrelated-mainline-tests",
      "tested_base_commit": "05c8bfe",
      "tested_head_commit": "f59ea7c",
      "tests": 3587,
      "skipped": 507,
      "failures": 9,
      "errors": 2,
      "passed_shards": [1],
      "workshop_test_modules_passed": {
        "tests/test_character_weapon_workshop_dw3.py": 6,
        "tests/test_character_weapon_workshop_gui.py": 7,
        "tests/test_character_weapon_workshop_model.py": 6,
        "tests/test_character_weapon_workshop_projections.py": 7,
        "tests/test_character_weapon_workshop_staging.py": 6,
        "tests/test_samurai4dx_workshop.py": 4,
        "tests/test_universal_packaging.py": 38,
        "tests/test_package_release.py": 22
      },
      "integration_test_failure_fixed_after_run": "tests/test_universal_app.py expected set omitted the existing Completion Companion tab; corrected in the latest head.",
      "other_failing_modules_unchanged_by_feature": [
        "tests/test_application_shell.py",
        "tests/test_emulator_hub.py",
        "tests/test_research_import.py",
        "tests/test_completion_companion_view.py",
        "tests/test_editing_tools_application.py",
        "tests/test_mod_manager_nexus.py"
      ],
      "release_jobs": "skipped; no release was produced"
    },
    {
      "name": "full-repository-unittest-suite",
      "command": "python -m tools.run_tests --workers 4 --report work/character_weapon_workshop_test_evidence.json",
      "status": "environment-limited",
      "tested_base_commit": "cede8a9 (before rebase; feature changes included)",
      "tests": 3388,
      "skipped": 954,
      "failures": 0,
      "errors": 1,
      "error_module": "tests/test_rotk3_dos.py",
      "error_test": "Rotk3DosGuiTests.test_generated_editor_apply_undo_review_inspector_theme_safe_save",
      "error": "tk.TclError: no display name and no $DISPLAY environment variable",
      "feature_test_modules_passed": [
        "tests/test_character_weapon_workshop_dw3.py",
        "tests/test_character_weapon_workshop_gui.py",
        "tests/test_character_weapon_workshop_model.py",
        "tests/test_character_weapon_workshop_projections.py",
        "tests/test_character_weapon_workshop_staging.py",
        "tests/test_samurai4dx_workshop.py"
      ]
    }
  ],
  "behavior_boundaries": [
    "Build plans are inert planning data and do not write save files.",
    "The workshop stages supported values only through existing validated editor workflows.",
    "Unmapped gameplay formulas are not inferred or calculated."
  ],
  "release_or_version_change": false
}
```
