# GitHub repository identity and release checklist

**Universal Koei Tecmo Game Toolkit v1.0**, by **Mexican**, continues
**Universal Koei Tecmo Save Editor v3.1**. The version reset marks the new product
name; existing save compatibility, repository history and older releases remain.
Keep the existing [repository](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor).

## Public presentation

- [README](../README.md): concise capabilities, grouped game examples, exact
  compatibility links, installation and downloads. Keep its generated inventory
  block intact.
- [Toolkit v1.0 release notes](RELEASE_NOTES.md): the official workflow input.
  [Earlier v3.1 notes](releases/v3.1.md) are archived separately.
- Application title, GUI/CLI descriptions, Python distribution and Windows
  artifact names use the Toolkit identity. The `koei_editor` import package,
  existing `universal-koei-editor` GUI command and preferences location remain
  stable. `universal-koei-toolkit` provides the [headless CLI](CLI.md).
- No reviewed screenshots are tracked. Add genuine, privacy-reviewed captures
  when available; do not substitute mock interfaces or imply that a source
  capture shows the published Windows build. Public archives retain their
  explicit source and privacy policy.

GitHub About description:

> Windows toolkit by Mexican for supported Koei Tecmo saves, build planning, mod management, selected PC settings and read-only assets, with backups and Undo.

Website: <https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases/latest>

Topics: `koei-tecmo`, `game-toolkit`, `save-editor`, `windows`, `python`, `tkinter`.

About description, website and topics are separate repository settings. The
connected integration previously returned HTTP 403 for them; the values above
remain the handoff for an authorized administrator. Verify the settings after
changing them. Do not rename the repository or rewrite old download filenames.

## Release identity

- Application, project, builder and source-manifest version: **1.0**.
- New release tag: **`toolkit-v1.0`**.
- GUI EXE: `UniversalKoeiTecmoGameToolkit-v1.0.exe`.
- Portable GUI ZIP: `UniversalKoeiTecmoGameToolkit-v1.0-Windows.zip`.
- Optional CLI EXE: `UniversalKoeiTecmoGameToolkit-v1.0-CLI.exe`.
- Source ZIP: `UniversalKoeiTecmoGameToolkit-v1.0-Source.zip`.
- Integrity reports: `SHA256SUMS.txt` and `DefenderScan-v1.0.json`.

**Historical tag conflict:** Save Editor's `v1.0` already points to
`b18e57e149ede01967910887f8c2aa7d10b22140`. The Toolkit tag uses a distinct
namespace. Never move or delete the historical tag or release. Publication marks
Toolkit v1.0 as latest despite its lower version number than Save Editor v3.1.

## Publication checks

The user resumed official release work on 2026-10-23 and explicitly confirmed
that all other development agents had finished. That owner confirmation records
completion without inventing a per-agent roster. Release authorization does not
remove the required code and artifact checks. The [qualification record](RELEASE_QUALIFICATION.md)
tracks accepted scope and remaining evidence limits:

1. Retain the owner's completion confirmation for the original 26 workstreams.
   Review every submitted PR and record integration, correction or rejection
   reasons; do not equate unverified proposals with released functionality.
2. Verify final game/platform scope, modular integration, compatibility, regression
   behavior, third-party licensing and attribution. The integrated inventory is
   **98 game/platform profiles, 15 save platforms and 145 scoped routes**.
   File-level checks do not establish edited-save in-game loading.
3. Require the complete source-bound Windows suite, GUI smoke test, portable GUI,
   standalone GUI and CLI builds, frozen-payload privacy/dependency validation,
   active Defender scans, bounded packaged startup and exact final artifact hashes.
   Linux checks remain separate from native Windows qualification.
4. Merge the reviewed release-preparation PR normally, then dispatch the official
   workflow on `main` with `publish=true` and its exact `expected_sha`. Do not use
   `[release]` in that manual preparation merge or start competing publication
   runs. [Other supported workflow paths](BUILDING.md) retain their own guards.
5. After publication, verify the tag/source commit, exact asset set, checksums,
   Defender evidence, release title, latest-release pointer and README download
   links. Repository About settings require the separate administrator handoff.

Do not treat a successful documentation check, push or merge as release
qualification. [Build workflow](BUILDING.md) · [Validation](VALIDATION.md).
