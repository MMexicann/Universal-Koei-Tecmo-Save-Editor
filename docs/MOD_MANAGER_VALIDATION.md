# Mod Manager validation report

The original PR validation below was run on 2026-10-22 from the repository root. The test fixtures
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

## Integration review of state ownership and download staging

The composed implementation uses the shared mutation guard for live
transaction/recovery exclusion as well as state ownership; a second transaction
lock is unnecessary. The concurrency regression observes that guard and its
paused `_atomic_json` wrapper preserves the revision digest returned by the
underlying write.

On 2026-10-22, the composed `test_mod_manager`, `test_mod_manager_nexus` and
`test_mod_manager_transaction_concurrency` suites passed **39 tests, no skips**
(24 state/service, 14 download queue, 1 live-journal interleaving). Added checks
include stale instances, process-crash recovery, persistent lock ownership,
foreign lock preservation, background extraction responsiveness, newly appearing
journals and retained incomplete/replaced downloads. A separate two-process
probe refused an active writer, released ownership when the child exited,
refused the stale instance afterward and preserved the child's profile and all
original fixture files. With the separately reviewed Windows device-name and GUI
selection-fixture corrections, the service/queue/live-journal/shell/Nexus suites
also passed **100 tests under Xvfb, no skips**. These are synthetic local checks,
not game loading.

The source-manifest result above belongs to the original PR. Integration must
regenerate and verify hashes after all reviewed patches are applied. Windows
frozen packaging, native file-lock behavior and Defender qualification remain
release checks.

## Audit limits

- The service tests demonstrate operations against generated fixtures. They do
  not identify or validate the version of a user's `d3d11.dll`.
- No game launch, mod load, save, or gameplay behavior was exercised.
- The Tk manager workspace tests were skipped in this headless environment.
- That original review covered Nioh 2 Windows PC only. The separate
  multi-game follow-up below documents the new Nioh 3 method and its limits.
- The Nexus browser handoff only imports an explicitly selected Nioh 2 ZIP into
  the library. Other listed Nexus games are browse-only; the manager never
  enables or installs a downloaded package automatically.
- State-directory mutations have both an instance guard and nonblocking OS
  ownership lock. The integration checks cover real process contention and
  stale instances; they do not establish native Windows or game-load behavior.
- Earlier service and UI reviews resolved transaction mutation and failed-root
  selection recovery gaps. A later safety review found a race between a live
  install journal and background import recovery; the follow-up lock and
  deterministic concurrency test cover that case.

The exact support evidence and ownership rules are in
[MOD_MANAGER.md](MOD_MANAGER.md). The PR's CI should run the GUI cases on its
Windows display-capable test environment and verify the full source manifest.

## Multi-game implementation follow-up (2026-10-23)

The source now includes a separate `nioh3_pc` installation contract alongside
`nioh2_pc`. Primary source evidence and deliberately limited content scope are
listed in [MOD_MANAGER.md](MOD_MANAGER.md). The former Nioh 2-only audit limit
above describes the original review, not this follow-up.

- Existing manager, Nexus queue and transaction-concurrency checks: **42 cases,
  41 passed, one existing Windows 8.3-alias check skipped on Linux**.
- New `tests.test_mod_manager_multigame`: **12 passed, zero skips**. Generated
  archives cover read-only review/import identity, strict game metadata,
  wrappers and hash filename rules, case/prefix/extension hash aliases, profile
  and unmanaged resource conflicts, loader/executable markers and bounded
  ordinary loader files, per-game library isolation, owned-folder disable and
  redeploy, modified-file refusal, and committed-removal recovery.
- Retained `tests.test_mod_manager_gui_lifecycle` and
  `tests.test_application_shell`: **52 passed, zero skips** on an isolated Tk
  display. Four additional Manager GUI cases also passed, covering game
  switching with independent roots/libraries, transaction-blocked switching,
  declared-game ZIP handoff without installation, and non-Windows deployment
  controls. The complete manager service/queue/transaction/new-adapter/GUI set
  ran **63 cases: 62 passed, one existing native-only skip**.
- Composed new-adapter/Manager GUI/Workshop bridge/Workshop GUI/mod CLI/Nexus
  contract checks: **60 passed, zero skips** on an isolated Tk display.

The loader and executable fixtures contain procedural marker bytes and are
never executed. These checks verify the manager's filesystem behavior, not
loader identity, a working asset format, gameplay, game re-save, or a specific
Nioh 3 build. The adapter does not bundle external loaders, call a patcher or
change original game archives. Nioh 3 DLL/plugin/game execution, Windows native
qualification and Wine/Proton behavior remain unverified by this follow-up.
The GUI permits local package review/import/profile planning on Linux and
blocks its Windows game-deployment actions there.

The new module is discovered automatically by the complete test runner.
Integration must add its reviewed public path and refresh the manifest after
all authors finish. No version, release links or global manifest were changed
by this follow-up.

Final follow-up checks after responsive layout and exception-rollback fixes:
`tests.test_mod_manager_multigame` passed **13 tests** and
`tests.test_mod_manager_gui_lifecycle` passed **10 actual Tk tests**, no skips.
The viewport check uses a 780×680 window, enlarged fonts and long German action
labels: actions remain within the client area, wrap when needed and the form
scrolls. Independent actual-shell review at German 140% also confirmed that all
Manager action buttons remain visible at 780×680. Independent probes covered
conflicting duplicate package IDs, precommit rollback and forged cross-game
journal rejection. Package/game/loader fixtures remain procedural throughout.
