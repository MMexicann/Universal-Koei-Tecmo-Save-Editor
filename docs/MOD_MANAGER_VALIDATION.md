# Mod Manager validation report

Validation was run on 2026-10-22 from the repository root. The test fixtures
create synthetic ZIP packages and temporary Nioh 2-shaped directories; no game
files, loader DLLs, or player mods are included.

## Commands and results

| Command | Result |
| --- | --- |
| `PYTHONPATH=src python -m unittest tests.test_mod_manager -v` | 12 tests passed. Covers package path and payload rejection, dependency/conflict checks, profile asset collisions, install/disable/uninstall, preservation of original fixture files, changed-file refusal, rollback, interrupted transaction recovery, and mutations blocked while recovery fails. |
| `PYTHONPATH=src python -m unittest tests.test_mod_manager_nexus -v` | 11 tests passed. Mocked downloader checks cover the Nioh 2 request and safe-ID gate, bounded nonblocking queue, shutdown race, thread-start failure, logical filename handling, manager-owned temporary ZIP, filename-based fallback IDs, existing import validation, no auto-install, sanitized failures, and safe rate-limit results. |
| `PYTHONPATH=src python -m unittest tests.test_application_shell -v` | 38 tests ran: 8 passed and 30 Tk tests skipped because this environment has no display (`$DISPLAY` is unset). A headless mocked assertion covers the manager handoff seam; visible workspace behavior needs a GUI-capable run. |
| `PYTHONPATH=src python -m py_compile src/koei_editor/shared/mod_manager.py src/koei_editor/shared/mod_manager_gui.py src/koei_editor/application.py tests/test_mod_manager_nexus.py tests/test_application_shell.py` | Syntax compilation passed. |
| `git diff --check` | Passed with no whitespace errors. |
| `python -m tools.package_release --verify-only` | Passed: v3.1, 1,227 public source files verified. This validates manifest hashes only; it does not build or validate a Windows executable. |

## Audit limits

- The service tests demonstrate operations against generated fixtures. They do
  not identify or validate the version of a user's `d3d11.dll`.
- No game launch, mod load, save, or gameplay behavior was exercised.
- The Tk manager workspace tests were skipped in this headless environment.
- The adapter supports Nioh 2 Windows PC only. Other Koei Tecmo games remain
  unsupported pending independently verified installation and restoration
  methods.
- Independent service and UI reviews found and resolved transaction-mutation
  and failed-root-selection recovery gaps; their final reviews found no blockers.

The exact support evidence and ownership rules are in
[MOD_MANAGER.md](MOD_MANAGER.md). The PR's CI should run the GUI cases on its
Windows display-capable test environment and verify the full source manifest.
