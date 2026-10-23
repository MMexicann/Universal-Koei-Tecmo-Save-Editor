# Supported text profiles

The studio accepts UTF-8 text files that match one of the profiles below. These are **interchange profiles**, not Koei Tecmo game-package formats. A matching filename by itself is not enough: the file contents are checked and ambiguous or malformed inputs are rejected.

| Extension | Accepted profile | What is editable | Export behavior |
|---|---|---|---|
| `.csv` | Header row containing unique `source` and `target` columns; optional `id` and `context`. RFC 4180-style quoting and commas. | The `target` field | Patches only the target field tokens. Other fields, quote style, line endings, and spacing stay as imported. |
| `.tsv` | Same headers as CSV, separated by tab characters. This is the studio's tab-delimited catalog convention. | The `target` field | Patches only target field tokens. |
| `.json` | Studio catalog: `{"segments":[{"id":"...","source":"...","target":"...","context":"..."}]}`. `id` and `context` are optional; `source` and `target` must be strings. | The `target` JSON string | Patches only target string tokens; all other source text and JSON formatting remains as imported. |
| `.srt` | Basic SubRip cues with an optional numeric cue index, `HH:MM:SS,mmm` timing, and one or more text lines. | Cue text | Replaces cue text while preserving cue numbers, time ranges, blank-line separators, and original line endings. |
| `.vtt` | WebVTT file with a `WEBVTT` header and text cues. Optional cue identifiers, cue settings, `NOTE`, `STYLE`, and `REGION` blocks are retained. | Caption/subtitle cue text | Replaces cue text while preserving identifiers, timing, settings, metadata blocks, and original line endings. |
| `.txt` | Studio line catalog: each non-empty line is one string. A translation must remain on one line. Blank lines are preserved. | Non-empty lines | Replaces translated lines and preserves untouched line endings and blank lines. |

Every import is limited to 5 MiB and 5,000 strings. Text profiles also stop after 50,000 physical lines. CSV/TSV rows and JSON objects are limited to 64 columns/properties; JSON nesting is limited to 64 levels and the scanned JSON document to 65,000 values and object keys. These limits keep parsing and rendering within a bounded browser workspace.

## Safety and boundaries

- Files are decoded as UTF-8 with strict error handling. The studio does not guess legacy encodings.
- The original upload is read-only. Edits remain in memory in the current browser tab. **Export always downloads a differently named copy**; it does not write to the imported path or a game directory.
- CSV, TSV, JSON, and TXT are generic exchange formats. The JSON/TSV/TXT shapes above are studio-defined profiles, not claims about native game files.
- When a CSV/TSV target changes, that field is re-escaped with valid delimiter quoting. All other source spans remain as imported.
- SRT is a commonly used SubRip text format. The accepted profile uses comma-separated millisecond timestamps with an increasing start/end range and is intentionally narrower than every SRT variant in the wild.
- WebVTT is parsed as a subtitle/caption format, not as a general metadata or chapter editor. Only cue text is exposed for translation.
- No Koei Tecmo archive, package, executable, resource table, proprietary string table, or save format is supported. Tools in the community mention game-specific families such as `XL`, `ECB`, `EM`, and `MESC`; those names alone do not establish which games, platforms, revisions, or files are safe to edit.
- The app does not call translation services. Translators type or paste target text themselves. Source and target language selectors label the current translation direction.

## Placeholder checks

The inspector compares the occurrence counts of common format tokens: brace placeholders such as `{0}` and `{player_name}`, printf-style placeholders such as `%s` and `%1$d`, HTML-like tags such as `<i>` and `</i>`, and bracket tokens such as `[PLAYER]`. A mismatch is a review warning, not a format parser error. Some games use additional control codes that this general check does not recognize; review strings in their game context before using a translation.

## Format references

- [RFC 4180: Common Format and MIME Type for CSV Files](https://www.rfc-editor.org/rfc/rfc4180.html) describes common CSV syntax and notes that implementations vary.
- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) defines JSON syntax, not a localization catalog schema.
- [W3C WebVTT: The Web Video Text Tracks Format](https://www.w3.org/TR/webvtt1/) defines caption, subtitle, chapter, and metadata cue structures.
- [Library of Congress SubRip description](https://www.loc.gov/preservation/digital/formats/fdd/fdd000569.shtml) describes SRT as a text subtitle format and documents its community/de facto status.
