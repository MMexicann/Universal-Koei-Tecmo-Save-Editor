# Existing tools and license review

Research checked 2026-10-22. This project uses independently written adapters and no third-party runtime packages. The tools below informed the workflow and fidelity boundaries; their source code and bundled game data were not copied.

## Existing localization tools

| Tool | License / scope | What is useful here | Reuse decision |
|---|---|---|---|
| [SWERY Localization Tool](https://github.com/LittleBitUA/SWERY-Localization-Tool) | MIT; its README describes support for five named games and JSON/binary text workflows. | Game-specific string inspection, tag checks, and a clear boundary around publisher-owned game content. | Workflow reference only. Its adapters are tied to specific titles and assets, so no parser or game data is imported. |
| [Toucan](https://github.com/rasyidf/Toucan) | MIT; general translation-file editor with a broad format list. Its README labels the project preview and documents round-trip metadata loss for some formats. | A useful reminder that accepting a format does not guarantee a faithful export. | Workflow reference only. This studio has a smaller profile list and patches target spans where possible. |
| [Supervertaler Workbench](https://github.com/Supervertaler/Supervertaler-Workbench) | MIT computer-assisted translation software. | Translation-oriented terminology and review workflow. | Workflow reference only; no code used. |
| [Papa Parse](https://github.com/mholt/PapaParse) | MIT CSV parser/generator. | A well-known browser CSV implementation and reference for escaped field handling. | Not included. Re-serializing whole records can normalize source layout; the studio's small profile patches only target field spans. |
| [subtitle.js](https://github.com/gsantiago/subtitle.js) | MIT; supports SRT and partial WebVTT parsing. | Subtitle parsing and normalized cue structures. | Not included. A normalized parser does not promise byte-preserving round trips, and its WebVTT coverage is partial. |
| [W3C webvtt.js](https://github.com/w3c/webvtt.js) | CC0 parser/serializer for WebVTT. Its README notes that the default parser recognizes only a subset of HTML entities unless entity data is supplied. | A permissively licensed WebVTT reference implementation. | Not included. The studio only edits text cue spans and leaves timing and metadata bytes in place. |
| [Weblate](https://github.com/WeblateOrg/weblate) | GPL-3.0. | Translation review and collaboration ideas. | No code reused; the license is not permissive. |
| [RenForge](https://github.com/foulnike/RenForge) | GPL-3.0. | Visual-novel translation workflow comparison. | No code reused; the license is not permissive. |

## Koei Tecmo community tools

- [Kybernes-Tools](https://github.com/PythWare/Kybernes-Tools) describes Festum Conversion for files named `XL`, `ECB`, `EM`, and `MESC`, with JSON import/export. Its [license](https://github.com/PythWare/Kybernes-Tools/blob/main/LICENSE) is non-commercial and prohibits redistribution; it is not a permissive implementation to copy or bundle.
- [GokonSoftworks](https://github.com/PythWare/GokonSoftworks) has similarly restrictive terms and documents game-specific support differences. These repositories are useful leads for targeted future research, not proof that those extensions are interchangeable across Koei Tecmo games.

No native Koei Tecmo format is enabled by this version. A future adapter needs a named game, platform, game revision, independently licensed implementation, and reproducible fixtures covering unchanged round trips and edited-file validation before it can be called supported.

## Standards used for the narrow profile list

- [RFC 4180](https://www.rfc-editor.org/rfc/rfc4180.html) provides the common CSV grammar used by the studio's catalog profile.
- [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259.html) defines JSON syntax; the `segments` catalog shape in this app is studio-defined.
- [W3C WebVTT](https://www.w3.org/TR/webvtt1/) defines WebVTT headers, cues, cue settings, and metadata blocks.
- The [Library of Congress SRT description](https://www.loc.gov/preservation/digital/formats/fdd/fdd000569.shtml) documents the common SubRip structure and its de facto status. This app accepts a basic subset and rejects other structures.

## Why the implementation stays small

The app has no network calls or external runtime dependencies. Generic interchange formats are handled using exact input schemas; subtitle formats expose only text payloads. CSV/TSV and JSON export patch target value spans, while SRT, WebVTT, and line text patch cue/line spans. The imported file remains in browser memory and the download gets a `.localized` filename. This avoids a false claim that a generic file extension proves a native game's format.
