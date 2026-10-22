# Character & Weapon Workshop Test Evidence

The record below is machine-readable. The full local runner report is in the ignored `work/character_weapon_workshop_test_evidence.json` artifact for this workspace.

```json
{
  "schema": "koei-editor-test-evidence/v1",
  "feature": "Character & Weapon Workshop",
  "evidence_type": "local-validation",
  "checks": [
    {
      "name": "workshop-focused-unittest-suite",
      "command": "PYTHONPATH=src python -m unittest tests.test_character_weapon_workshop_model tests.test_character_weapon_workshop_dw3 tests.test_character_weapon_workshop_projections tests.test_character_weapon_workshop_staging tests.test_samurai4dx_workshop tests.test_character_weapon_workshop_gui tests.test_universal_packaging tests.test_package_release",
      "status": "passed",
      "tested_base_commit": "6fa3cf0",
      "tests": 96,
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
      "tested_base_commit": "6fa3cf0",
      "verified_public_source_entries": 1242
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
