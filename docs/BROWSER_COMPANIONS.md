# Localization Studio and Mod Testing Sandbox

Open **Editing and Research → Localization Studio** or **Mod Testing Sandbox**
in the Toolkit. The real tool opens in your default browser. Packaged builds
include the HTML, styles and JavaScript; no Python installation, Node server or
internet connection is required. A system browser must be available.

Keep the Toolkit running while using these tools. Their local address belongs
to the current Toolkit session. Closing the Toolkit stops its local server;
reopen the tool from the menu for a new session.

## Localization Studio

Import a supported UTF-8 text file, review its strings and enter translations.
The Studio checks common placeholder tokens and exports a separately named
copy. Its **Supported formats** link describes the accepted CSV, TSV, JSON,
SRT, VTT and TXT profiles.

These are documented text interchange profiles. Native Koei Tecmo archives,
proprietary string tables, executables and saves are not supported. Language
selectors label the translation direction; no online translation service is
called. Edits remain in the browser tab until export.

## Mod Testing Sandbox

Choose an exact game/build profile, then import a supported manifest and its
user-selected mod folder. Review path, dependency, version, hash and conflict
findings before exporting. The Sandbox stages browser-local data and downloads
a package only after separate confirmation. It does not install mods or execute
imported files.

Manager packages, profile components, audit reports and Workshop handoffs retain
their existing contracts. Import the intended output in the receiving Toolkit
tool and review it there; opening a companion does not apply a handoff to the
native application automatically. Mod Manager installation support remains
limited to its documented game-specific adapters and loader requirements.

## Keep your work

Keep the original input files and export the results you need before closing
the browser or Toolkit. The Sandbox may use browser IndexedDB, with memory
fallback when storage is unavailable. Its storage is tied to the browser's
local origin; a later Toolkit session can use a different address. A report or
deployment package does not guarantee a complete workspace restore.

The Toolkit does not read, migrate or clear the browser's storage. Browser
storage settings control retained browser data. Localization edits remain in
the current tab until exported.

## Local serving and troubleshooting

The managed server listens only on IPv4 loopback and serves an explicit list
of bundled text assets. It accepts bounded read-only requests under a private
session address, checks Host/Origin headers and provides no upload, game-file
or arbitrary filesystem endpoint. User-selected files remain in the browser's
existing file APIs. Closing the Toolkit releases its listener and client
connections.

If the default browser cannot open, check the operating system's browser
association. Missing or redirected bundled assets are refused; reinstall the
complete Toolkit download. Running from source requires the complete checkout
with its original companion assets and an editable installation. Moving just
the Python package out of that source tree does not supply those assets.
