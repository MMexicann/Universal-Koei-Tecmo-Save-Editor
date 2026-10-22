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

The reviewed development changes are collected in
[integration PR #146](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/pull/146).
It includes the new save, planning, mod, asset, installation and reference tools
summarized in the pending notes. Coverage remains 98 game/platform profiles,
15 save platforms and 145 scoped conversion routes. Validation results are recorded with that PR; final publication still requires
the source-bound Windows and artifact checks below. The six review areas have
been covered; the original 26-workstream roster remains unverified.

**Publication is on hold at the user's request.** Continue reviewed development
merges into `main`. Do not reset versions, create release tags or publish assets
until release work resumes. This does not block ordinary development merges.

**Historical tag conflict:** `v1.0` already points to
`b18e57e149ede01967910887f8c2aa7d10b22140`. Preserve it. Use a distinct
`toolkit-v1.0` namespace for the new product's release and update official
workflow tag checks consistently before publication. Never move or delete the
historical tag or release.

GitHub About settings require repository administration access. The connected
integration returned HTTP 403 for those settings; the exact description,
website and topics above remain the handoff for an authorized administrator.

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
   together for the new Toolkit identity and non-conflicting Toolkit tag.
4. Archive the v3.1 workflow notes under `docs/releases/v3.1.md`, then put the
   reviewed final Toolkit notes in `docs/RELEASE_NOTES.md`. Update the docs index
   and source manifest. Remove pending language only when its claims are true.
5. Publish through the official workflow after every gate passes. Verify the
   release's source commit, exact assets, hashes and scan reports. Update README
   download links and About metadata to the verified Toolkit release.

Do not treat a successful documentation check, push or merge as release
qualification. [Build workflow](BUILDING.md) · [Validation](VALIDATION.md).
