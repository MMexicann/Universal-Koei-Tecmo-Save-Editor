# Mod Manager validation report

Validation was run on 2026-10-22 from the repository root. The test fixtures
create synthetic ZIP packages and temporary Nioh 2-shaped directories; no game
files, loader DLLs, or player mods are included.

## Commands and results

| Command | Result |
| --- | --- |
| `PYTHONPATH=src python -m unittest tests.test_mod_manager -v` | 12 tests passed. Covers package path and payload rejection, dependency/conflict checks, profile asset collisions, install/disable/uninstall, preservation of original fixture files, changed-file refusal, rollback, interrupted transaction recovery, and mutations blocked while recovery fails. |
| `PYTHONPATH=src python -m unittest tests.test_mod_manager_nexus -v` | 11 tests passed. Mocked downloader checks cover the Nioh 2 request and safe-ID gate, bounded nonblocking queue, shutdown race, thread-start failure, logical filename handling, manager-owned temporary ZIP, filename-based fallback IDs, existing import validation, no auto-install, sanitized failures, and safe rate-limit results. |
| `PYTHONPATH=src python -m unittest tests.test_mod_manager_transaction_concurrency -v` | 1 regression test passed. It pauses an apply operation after the uncommitted journal is written, queues a Nexus import, verifies the live journal and staging directory remain untouched until apply completes, and checks both operations finish with consistent state and no journal. |
| `PYTHONPATH=src python -m unittest tests.test_application_shell` | 40 tests ran: 9 passed and 31 Tk tests skipped because this environment has no display (`$DISPLAY` is unset). |
| `PYTHONPATH=src python -m unittest tests.test_nexus_mods tests.test_nexus_contract_audit` | 20 browser and API contract tests passed, including the selected-file handoff route. |
| `PYTHONPATH=src python -m unittest tests.test_mod_manager tests.test_mod_manager_nexus tests.test_mod_manager_transaction_concurrency tests.test_application_shell tests.test_nexus_mods tests.test_nexus_contract_audit` | 84 tests ran: 53 passed and 31 GUI tests skipped because this environment has no display. |
| `PYTHONPATH=src python -m py_compile src/koei_editor/shared/mod_manager.py src/koei_editor/shared/mod_manager_gui.py src/koei_editor/application.py src/koei_editor/mods/nexus_api.py src/koei_editor/mods/nexus_browser.py tests/test_mod_manager_nexus.py tests/test_mod_manager_transaction_concurrency.py tests/test_application_shell.py tests/test_nexus_mods.py tests/test_nexus_contract_audit.py` | Syntax compilation passed. |
| `PYTHONPATH=src python -m tools.update_supported_games --check` | Passed: 98 supported game/platform adapters. |
| `git diff --check` | Passed with no whitespace errors. |
| `python -m tools.package_release --verify-only` | Passed: v3.1, 1,234 public source files verified. This validates manifest hashes only; it does not build or validate a Windows executable. |

## Audit limits

- The service tests demonstrate operations against generated fixtures. They do
  not identify or validate the version of a user's `d3d11.dll`.
- No game launch, mod load, save, or gameplay behavior was exercised.
- The Tk manager workspace tests were skipped in this headless environment.
- The adapter supports Nioh 2 Windows PC only. Other Koei Tecmo games remain
  unsupported pending independently verified installation and restoration
  methods.
- The Nexus browser handoff only imports an explicitly selected Nioh 2 ZIP into
  the library. Other listed Nexus games are browse-only; the manager never
  enables or installs a downloaded package automatically.
- Transaction/recovery serialization is within one `ModManager` instance. The
  tests do not cover two separate app processes modifying the same game folder.
- Earlier service and UI reviews resolved transaction mutation and failed-root
  selection recovery gaps. A later safety review found a race between a live
  install journal and background import recovery; the follow-up lock and
  deterministic concurrency test cover that case.

The exact support evidence and ownership rules are in
[MOD_MANAGER.md](MOD_MANAGER.md). The PR's CI should run the GUI cases on its
Windows display-capable test environment and verify the full source manifest.
