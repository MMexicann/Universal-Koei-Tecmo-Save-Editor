# Real-game validation and private feedback

The application’s Help Center provides a **Real-game validation** checklist and
**Community feedback** report preview. Both work offline. Export creates a new
JSON file that you can review and choose to share yourself; the application does
not transmit reports, launch games, import console saves or inspect player files
through these panels. The application remains v2.7.

## Evidence stays separate

A passing generated-fixture test proves procedural behavior. A genuine player
save passing the existing copied-save self-test proves those file checks. Neither
proves that the edited save loads in the game. Loading, observing the intended
field, saving in the game, and reloading that game-written save are distinct
observations. A successful load does not establish successful re-saving.

All checklist reports are **user-reported and independently unverified**,
including imported reports. They never update the compatibility catalog or
certify game support. Keep private controlled-action pairs and screenshots
outside the repository; the public report contains no attachments or free text.

## Controlled workflow

1. Close the game and cloud synchronization. Preserve an untouched original and
   prepare a separate working copy outside live save/cloud folders.
2. Select the exact registered game, platform and edition. Confirm region/build
   against the adapter documentation. If known, enter its numeric **format
   revision** (decimal or `0x` hexadecimal); otherwise leave it unspecified.
   This field is not an executable version or a proof of revision qualification.
   The exact registered edition/revision scope is retained separately in JSON.
3. Establish a byte-exact unchanged roundtrip and source preservation using the
   existing copied-save self-test where available; confirm backup restoration.
   See [the contribution workflow](../CONTRIBUTING.md#building-an-edited-save).
4. With an unchanged control alongside it, change one mapped field through the
   existing editor. Review changes, save to a new destination, and re-open the
   edited copy through the same explicitly selected adapter.
5. Import the edited copy through the platform’s documented procedure. Console
   imports/signing remain external. Preserve required original companion files
   such as `PARAM.SFO` or `sce_sys/param.sfo`; never fabricate ownership/signing
   metadata. See the exact game’s format document for companion requirements.
6. Load the test slot in the exact game/build. Record failure for corruption or
   recovery warnings; do not record a parser success as a game-load success.
7. Observe the intended value and related behavior in-game against the unchanged
   control. Keep unqualified mechanics separate.
8. Save normally in the game to a test slot, preserving originals and controls.
9. Restart the game and reload its newly written test slot. Confirm the intended
   value persists. Record missing evidence as **Not run** or **Blocked**.

The workflow enforces prerequisites for both passed and failed observations.
Only a genuine-file source can record actual platform/game observations.
Changing an earlier outcome clears later observations; changing profile,
revision or source resets the entire checklist. This prevents stale successful
results from being carried onto another test context. Reports do not retain
timestamps, save hashes, filenames or player identifiers.

## Privacy and report format

Community reports include only controlled problem/symptom categories, English
or German locale, optional registered game/platform and optional explicitly
allowlisted diagnostic choices. They collect no diagnostics automatically.
The Python API optionally accepts OS family, display-scale bucket and theme;
arbitrary diagnostic fields and values are rejected. A validation report may
be attached only when it matches the same selected game.

No environment variables, paths, machine/account IDs, raw exception messages,
logs, save bytes, digests, private URLs or free-text notes are supported. The
visible preview is the report to be exported. Review it before manually sharing
it. A malicious or mistaken report can still contain false observations; this
is why reports remain unverified and cannot promote compatibility claims.

Imports are limited to 16 KiB of strict UTF-8 JSON. Unknown or duplicate keys,
nonfinite numbers, unsupported versions, wrong platform/edition, impossible
step sequences and unrecognized choices are rejected without echoing their
contents into error dialogs. Numeric revisions are optional unsigned 32-bit
integers. Export uses the existing atomic new-file utility and never overwrites
an existing report. Reports are portable between the English and German UI.

## Developer API

`koei_editor.shared.validation_toolkit.ValidationRecord.create(game_id,
revision=None, provenance='unknown')` creates an immutable record. The source
choices are `unknown`, `procedural`, and `genuine_file`. `record_step(step,
outcome)` returns a new record; outcomes are `not_run`, `passed`, `failed`, or
`blocked`. `STEPS` declares the ordered workflow. `summary()` keeps procedural,
genuine-file, load, re-save and reload observations separate.

`to_json()` / `from_json(data)` and `export(destination)` / `load(source)` use the
closed schema. Imported evidence is always `user_reported_unverified`.
`community_feedback.build_bug_report(...)`, `review_json(report)`,
`import_bug_report(data)` and `export_bug_report(report, destination)` apply the
feedback allowlist again at review/export boundaries.

`validation_gui.ValidationPanel(root, parent, language='en')` and
`FeedbackPanel(root, parent, language='en')` expose `.frame` and
`.apply_theme(palette)` for the application shell. German uses `language='de'`.
Both expose `.set_language(language)` while preserving pending observations,
profile/revision, selected step/outcome, report choices, layout and theme.
They reuse shared ttk styles, keyboard-focusable controls and selectable report
text; step guidance wraps with the available width. They do not modify an open
editor session, its staging or save storage.

Focused checks:

```text
python -m unittest tests.test_validation_toolkit tests.test_community_feedback -v
python -m unittest tests.test_validation_gui -v
```

The GUI module requires a graphical display. These checks exercise schema and
privacy boundaries and UI callbacks using generated reports. They establish no
new genuine-save or real-game validation evidence.
