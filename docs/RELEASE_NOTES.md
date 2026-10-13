# Universal Koei Tecmo Save Editor v2.01

Version 2.0 was withdrawn after Microsoft Defender reported
`Trojan:Win32/Sabsik.TE.A!ml` during its standalone EXE download.

This update changes Windows distribution to a **complete portable ZIP**. Extract
all files, open the versioned application folder and run its EXE. Keep the
`_internal` folder beside it. No Python installation or administrator privileges
are needed. All 90 game/platform profiles and existing editing features remain.

The release pipeline now requires an active Microsoft Defender engine, current
signatures and verified cloud connectivity. It scans the complete runtime before
executing it, then scans both exact downloadable archives. Missing protection,
scan errors, detections or changed bytes block publication. The downloadable
`DefenderScan-v2.01.json` records engine/signature versions, verdicts and file
hashes. Build dependencies are pinned to verified official wheel hashes.

Source and binary review found no newly introduced malicious behavior, and the
2.0 bootloader/native libraries match the reviewed official/previous versions.
That does not establish why Microsoft's classifier flagged the old download.
The packaging change removes runtime self-extraction; Defender verdicts reflect
the signatures and cloud state recorded in the report, not every future verdict.
Version 2.0 remains withdrawn.

Download **UniversalKoeiTecmoSaveEditor-v2.01-Windows.zip** for the app or the
**Source ZIP** for development. A loose EXE is no longer offered.
