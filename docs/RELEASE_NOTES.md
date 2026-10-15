# Universal Koei Tecmo Save Editor v2.5.1

Fixes the missing offline guides in the v2.5 Windows ZIP. The builder now collects
seven explicitly reviewed guides into both Windows builds, and the portable ZIP
exposes them under **`_internal/guides/`**:

- Editor workspace and Origins request status.
- Save Converter, Compare Saves and Batch Converter.
- DW6 conversion scope and US PS3 format/controls.

Their exact bytes are bound to the source manifest and verified as runtime
metadata. Missing, changed or unreviewed guide resources fail packaging. Tests
inspect the actual generated Windows ZIP contents, including the guide bytes;
repository/developer documents remain confined to the Source ZIP.

The v2.5 public description has been corrected. Its original downloads and tag
are unchanged. This patch carries forward the category sidebar, open-editor
selector, pending-row highlighting, keyboard controls and Origins copy-safety
fixes from v2.5.

**Origins proficiency levels and Old Coin editing remain unimplemented.** No new
game profile or gameplay mapping is added. The library remains **94 profiles
across 15 platforms**, with **20 scoped conversion routes**. The existing
in-game validation limitations and console import/signing requirements remain.

Publication requires the complete native Windows suite, both packaged startup
checks, all exact-payload active Defender scans and actual public-download
verification. Download **UniversalKoeiTecmoSaveEditor-v2.5.1.exe**, the complete
**Windows ZIP**, or **Source ZIP**, with SHA256SUMS and Defender evidence.

[Workspace guide](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/blob/v2.5.1/docs/EDITOR_WORKSPACE.md)
and [Origins request status](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/blob/v2.5.1/docs/ORIGINS_REQUEST_STATUS.md).
