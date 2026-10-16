# Universal Koei Tecmo Save Editor v2.5.4

Fix **Cannot Export Review: Choose a .changes.json review file.** when exporting
Review Changes from WO3 Ultimate or another scalar editor.

The export dialog now suggests a source-based review filename and completes the
`.changes.json` suffix automatically. Plain names, `.json` names, partial
`.changes` suffixes and save-style names work. Choosing `APP.BIN` exports a
separate `APP.BIN.changes.json` report; it preserves `APP.BIN`. Existing report
files are never overwritten, and the status shows the actual exported filename.

**Export Review** writes a JSON report of the reviewed changes. **Save As...**
in the editor writes an edited game-save copy. Filtering the review or changing
pending edits afterward still leaves its complete exported snapshot frozen.

The exact error was reproduced and the fix verified with the supplied decrypted
WO3 Ultimate US PS3 export. All original save and context files remained
unchanged. Regression coverage includes filename variants, cancellation,
existing reports, source preservation and export after Undo.

No gameplay mapping or support scope changes: 96 game/platform profiles across
15 platforms and 139 directed conversion routes. This fix does not establish
in-game loading or add the previously unimplemented Origins writers or arbitrary
DW7 XL weapon attack/element edits.

The Windows standalone EXE and complete portable ZIP include the updated offline
workspace guide. Publication requires full Windows tests, both packaged startup
checks, active Defender scans and checksums of the exact downloadable payloads.
