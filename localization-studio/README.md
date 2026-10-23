# Koei Tecmo Localization Studio

An offline-first browser workspace in the Universal Koei Tecmo toolkit repository for inspecting and translating narrow, verified text interchange profiles. The current version supports CSV/TSV catalogs, the Studio JSON catalog, basic SubRip subtitles, WebVTT text cues, and a line-oriented TXT catalog. It runs in the browser and does not register save-editing profiles.

The packaged Toolkit opens it from **Editing and Research → Localization Studio**
using its managed local server; no separate Python or Node installation is needed.
Keep the Toolkit open and export your edits before closing the browser tab.
[Bundled companion guide](../docs/BROWSER_COMPANIONS.md).

**This is not a native Koei Tecmo game-package editor.** No game package, executable, save, or proprietary string table is supported. Community-reported extensions do not establish support for a particular game, platform, or revision; see [the research notes](docs/RESEARCH.md) and [supported profiles](docs/SUPPORTED_FORMATS.md).

## Run locally

The app has no runtime dependencies, account, or translation-service calls. Serve the folder over localhost so the browser can load ES modules:

```sh
python -m http.server 8000
```

Open <http://localhost:8000/>. To try the interface without importing a file, choose **Explore with a sample project**. The sample strings are fictional.

## Use

1. Import a UTF-8 file that matches one of the exact profiles in [SUPPORTED_FORMATS.md](docs/SUPPORTED_FORMATS.md).
2. Review source strings and context, enter target translations, and check placeholder/tag warnings.
3. Choose **Export copy**. The browser downloads a new file with `.localized` added to its name.

The uploaded file is read-only. This app does not write to the imported path or a game directory. Edits live only in the current tab and are lost when it is closed. For SRT, WebVTT, and line TXT, unedited strings pass through unchanged; empty target fields keep the original cue/line in the exported copy. Subtitle translations cannot contain blank lines because those separate cues. For CSV/TSV and JSON, the existing source values stay in place while target values are patched.

Language selectors label the source and target languages. Translation is entered by the user; the app does not send text to machine-translation services. The app works offline after the files are present.

## Tests

Node.js 20 or later is required for the self-contained format tests:

```sh
npm test
```

No test fixture contains extracted or copyrighted game assets. A generated validation report is stored in `reports/validation-report.json`.

For the browser smoke test, install Chromium and use Node.js 22 or later (for its built-in WebSocket client):

```sh
npm run test:browser
```

Set `BROWSER_BIN` to the Chromium executable path when it is not named `chromium`.

## License

The original code in this project is available under the MIT License; see [LICENSE](LICENSE). Third-party tools and source references are documented in [docs/RESEARCH.md](docs/RESEARCH.md). No third-party runtime code is bundled.
