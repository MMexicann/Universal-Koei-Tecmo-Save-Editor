# GitHub repository identity and release handoff

The development application is **Universal Koei Tecmo Game Toolkit**, by
**Mexican**, continuing **Universal Koei Tecmo Save Editor v3.1**. Keep the existing
[repository](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor), development history
and historical releases. The planned Toolkit **1.0** is a branding version reset.

## Public presentation

- README: concise capabilities, grouped game examples, exact compatibility links,
  installation and downloads. Keep its generated inventory block intact.
- [Pending Toolkit v1.0 notes](TOOLKIT_V1_RELEASE_NOTES.md): summarize only integrated
  changes; distinguish new features from retained v3.1 functionality.
- [Published v3.1 notes](RELEASE_NOTES.md): remain the active release-workflow input
  until final release preparation. Do not publish pending Toolkit notes as v3.1.
- Source application title, CLI description and Python distribution metadata use
  the Toolkit name. The `koei_editor` package, existing command and preferences
  location remain stable to preserve existing use; `universal-koei-toolkit` is
  also available after installation.
- No reviewed screenshots are currently tracked. Add genuine, privacy-reviewed
  application captures when available; do not substitute mock interfaces or
  imply that a development capture shows the published Windows build.

GitHub About description:

> Windows toolkit by Mexican for supported Koei Tecmo saves: editing, comparison, conversion, backups and automation. Toolkit v1.0 in preparation; v3.1 available.

Website: <https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases/latest>

Topics: `koei-tecmo`, `game-toolkit`, `save-editor`, `windows`, `python`, `tkinter`.

The About description, website and topics are separate repository settings;
verify them on GitHub after changing them. Do not rename the repository or
rewrite old download filenames as part of this presentation update.

## Current release boundary

On 2026-10-22, the latest published release is **Save Editor v3.1**. Its assets are
an EXE, Windows ZIP, Source ZIP, `SHA256SUMS.txt` and `DefenderScan-v3.1.json`.
The README links to those existing assets and labels v1.0 as pending.

The reviewed source baseline is `c77e1beeddc195298c68ce18301d27373408d46e`.
It includes read-only Scenario View cards for six existing strategy profiles,
the opt-in DW3 Steam achievement backend, and Three Hopes/Hyrule Warriors Wii U
reference data. There is no achievement-lookup UI, encyclopedia browser or
Character Workshop yet. Coverage remains 98 game/platform editing profiles,
15 save platforms and 145 scoped conversion routes. Other development PRs
remain outside these notes until accepted and reviewed.
This is a presentation review, not completion evidence for all 26 workstreams.

**Historical tag conflict:** `v1.0` already points to
`b18e57e149ede01967910887f8c2aa7d10b22140`. Preserve it. A distinct new Toolkit
release tag and the corresponding workflow checks must be agreed before
publication; never move/delete the historical tag or release.

## Final release checklist

1. Account explicitly for all 26 workstreams and review every submitted PR.
   Refresh the final game inventory, route counts, integrations and concise notes
   from the actual accepted code; do not claim unfinished features.
2. Complete integration, compatibility, GUI, regression and license reviews.
   Require the full source-bound Windows suite, both Windows builds, active
   Defender scans, packaged startup and final artifact hash verification.
3. In a dedicated release-preparation change, set application, builder, project
   and source-manifest versions to `1.0` together. Change the build/package prefix,
   workflow asset paths, commit/title strings, tag validation and packaging tests
   together for the new Toolkit identity and agreed non-conflicting tag.
4. Archive the v3.1 workflow notes under `docs/releases/v3.1.md`, then put the
   reviewed final Toolkit notes in `docs/RELEASE_NOTES.md`. Update the docs index
   and source manifest. Remove pending language only when its claims are true.
5. Publish through the official workflow after every gate passes. Verify the
   release's source commit, exact assets, hashes and scan reports. Update README
   download links and About metadata to the verified Toolkit release.

Do not treat a successful documentation check, push or merge as release
qualification. [Build workflow](BUILDING.md) · [Validation](VALIDATION.md).
