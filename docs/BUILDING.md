# Building the Windows executable

This development source prepares the **Universal Koei Tecmo Game Toolkit** name.
The technical version and artifact filenames remain at **3.1** until the v1.0
release gates pass. See the [branding and release handoff](REPOSITORY_METADATA.md)
before changing versions, filenames, tags or publication settings.

Build releases on 64-bit Windows with Python 3.14.7 and Tkinter. Build/package tools
and the development test suite use Python 3.11 or newer; the source application
itself supports Python 3.10. The Windows workflow uses Python 3.14.7, and
`tools/requirements/build.txt` hash-locks the build and asset-preview wheel
dependencies. The application uses pinned miniaudio, trimesh, NumPy, cffi, and
pycparser packages for audio/model inspection; the build retains their complete
runtime notices. PNG/DDS decoding and archive/G1T parsing use in-process code.

```powershell
python -m pip install --force-reinstall --no-cache-dir -r tools/requirements/build.txt
python -m pip install -e . --no-build-isolation
python -m tools.package_release --verify-only
python -m tools.build_windows
python -m tools.build_windows --standalone
```

The default build produces **`dist/UniversalKoeiTecmoSaveEditor-v3.1/`**, a
portable folder containing its launcher EXE and complete `_internal` runtime.
The `--standalone` build produces the self-contained
**`dist-standalone/UniversalKoeiTecmoSaveEditor-v3.1.exe`**. That direct download
needs no side files. Both modes use pinned Python 3.14.7 and `--noupx`, with the
same 98 game/platform profiles, runtime metadata, asset preview modules and
required notices.
Native Windows CNG handles DW3 encryption. Save samples, installed game files
and private reports are excluded.

Both builds retain exact reviewed `METADATA` for the five asset-preview
dependencies so runtime version queries work. After PyInstaller analysis, the
build removes their build-only distribution records, installer markers and
upstream `DELVEWHEEL` logs before assembling either format. These records are not
needed by the previews; their licenses remain in the required runtime notices.
The filter is bound to the complete hash-locked wheel list and rejects unknown
distribution metadata. Package verification checks retained metadata hashes and
continues rejecting personal paths, unreviewed resources and native modules.
Optional CFFI compilation helpers (`setuptools`, `distutils`, `pkg_resources`)
are excluded from the frozen application; previews use the precompiled decoders.
Build tools remain installed in the build environment.
A reviewed pre-import hook preserves these exclusions when PyInstaller resolves
the removed standard-library `distutils` name. It refuses to build if any of
the three required compiler exclusions is missing.

`tools/build_windows.py` requires Windows for compilation. Inspect the build inputs on
any OS with:

```text
python -m tools.build_windows --print-config
python -m tools.build_windows --standalone --print-config
```

## Build checks

```powershell
python -m tools.run_tests --workers 4
python -m koei_editor --smoke-test
python -m tools.package_release --verify-executable
python -m tools.package_release --verify-standalone
```

These verification commands inspect frozen archives without executing either
binary. Before any packaged startup or copied-save test, use the isolated,
elevated Windows release runner to scan both complete candidates:

```powershell
$bundle = python -m tools.package_release --bundle-path
$standalone = python -m tools.package_release --standalone-path
& ./tools/scan_release.ps1 -Path $bundle -ReportPath defender-reports/runtime.json
if ($LASTEXITCODE -ne 0) { throw 'Portable runtime scan failed.' }
& ./tools/scan_release.ps1 -Path $standalone -ReportPath defender-reports/standalone.json
if ($LASTEXITCODE -ne 0) { throw 'Standalone EXE scan failed.' }
$launcher = python -m tools.package_release --executable-path
foreach ($candidate in @($launcher, $standalone)) {
    $smoke = Start-Process -FilePath $candidate -ArgumentList '--smoke-test' -WindowStyle Hidden -Wait -PassThru
    if ($smoke.ExitCode -ne 0) { throw 'Packaged smoke test failed.' }
}
```

Require successful scans with active Defender protection, current signatures,
verified cloud connectivity and unchanged input hashes. A missing engine,
detection, scan error or changed bytes blocks both packaged execution and
publication. Prefer the repository workflow for the complete release gate.

The smoke test initializes the library and registered editors, switches games and
appearance, then exits. Require exit code 0. Save-format and game-load validation
are separate; see [VALIDATION.md](VALIDATION.md) for coverage and limitations.

The Windows workflow runs the complete suite across four independent test jobs,
each using two isolated Python processes. Runtime estimates balance modules;
unknown/new modules are always included. The build checks combined shard
reports against the current sources and complete test inventory before its
source GUI smoke test, both native builds, candidate scans, packaged smoke tests and archive/privacy
validation. Failed, missing or overlapping shards cannot authorize a build or
publication. Reports and individual module logs are downloadable CI artifacts.
Pip caching avoids repeatedly downloading unchanged build dependencies.

Local parallel checks need no extra test dependency. Use fewer workers on small
machines and an existing display or `xvfb-run -a` for Tk on Linux. The serial
`python -m unittest discover -s tests -v` remains available for debugging.

Direct startup accepts a registered game ID, for example `--game dw3`,
`--game dw9emp` or `--game orochiz`. Use `--list-games` for the complete current
inventory of IDs, editions and platforms.

## Copied-save workflow checks

The executable retains the DW3 copied-save self-test:

```powershell
$selfTest = Start-Process -FilePath $launcher -ArgumentList '--self-test "D:\SaveCopies\GameStatusData.sav" "D:\SaveCopies\DW3Test"' -WindowStyle Hidden -Wait -PassThru
$selfTest.ExitCode
```

Other editors use an explicit game ID:

```powershell
& $launcher --game dw4hyper --self-test "D:\SaveCopies\save.dat" "D:\SaveCopies\DW4Test"
& $launcher --game dw8xl --self-test "D:\SaveCopies\save.dat" "D:\SaveCopies\DW8Test"
& $launcher --game pw3 --self-test "D:\SaveCopies\OP3WIN0000.dat" "D:\SaveCopies\PW3Test"
& $launcher --game dw4xl_ps2 --self-test "D:\SaveCopies\DW4XL.psu" "D:\SaveCopies\DW4XLTest"
& $launcher --game atelier_sophie2 --self-test "D:\SaveCopies\data.dat" "D:\SaveCopies\Sophie2Test"
```

The scanned standalone EXE accepts the same arguments. Use a separate input
copy and a new/empty output folder. Require exit 0,
`success: true` in `self-test-report.json` and preservation of the input hash.
These workflows create edited copies, backups and restored copies. Source
invocations use `python -m koei_editor` in place of the executable. They do not
establish actual game loading.

## Package integrity

`tools/SOURCE_MANIFEST.json` records public source file versions, lengths and SHA-256
hashes. Refresh it after reviewed edits with `python -m tools.refresh_manifest`; use
`--add FILE...` only for reviewed public sources. Then run:

```powershell
python -m tools.package_release --verify-only
python -m tools.package_release --verify-executable
python -m tools.package_release --verify-standalone
python -m tools.package_release --output work/local-universal-package
```

The packager produces the direct standalone EXE, complete Windows ZIP, Source
ZIP and `SHA256SUMS.txt`. The Windows ZIP root contains only the versioned
application folder, with its launcher and `_internal` runtime. Required project,
Python, Tcl/Tk, PyInstaller and adapted-code notices are retained under
`_internal/licenses`; the standalone EXE embeds the same notices. Developer
guides, `AGENTS.md`, `CONTRIBUTING.md` and the documentation tree belong in the
Source ZIP. The release workflow adds the Defender report and its checksum only
after scanning the exact final EXE and both final ZIPs successfully.
Existing outputs are never replaced. It checks the embedded archive, metadata and
source hashes, and rejects save/game-file entries and personal paths.

The Windows workflow runs the tests, builds the executable and verifies its
startup and archives before creating downloadable build assets. Building locally
uses the same scripts. A completed build is a prerequisite for packaging.
The build job uses `windows-2022` as a diagnostic comparison after hosted
`windows-latest` runners stopped reporting during packaging; this does not
establish the cause or guarantee a remedy. The four full-suite test shards
continue to use `windows-latest`. Portable and standalone builds each have a
10-minute step limit, and their separate frozen-payload verification steps each
have a 3-minute limit, within the unchanged 30-minute job limit. Runtime scans,
packaged startup and packaging remain separate bounded steps.
After both runtime scans pass, `tools/smoke_windows.ps1` gives each
packaged startup 180 seconds and records its exit status and executable hashes.
On timeout it records bounded descendant metadata, reads window text only from
the retained launched process, and terminates its process tree. Startup and
Defender diagnostics are workflow artifacts,
separate from the release downloads; a timeout still blocks publication.
Manual workflow runs build artifacts by default. To publish a prepared main
commit, dispatch with `publish=true` and `expected_sha` matching that exact
commit. Pushing a tag matching the application version, such as `v3.1`, also
publishes after the native build and checks succeed. Existing releases are not replaced.

The portable runtime loads from the adjacent `_internal` folder. Users extract
the entire Windows ZIP and keep that folder beside its launcher. The direct EXE
contains its runtime and extracts it temporarily at startup; users need no
adjacent files. Neither download requires an installed Python or administrator
privileges to run.

Release-marked main commits (`[release]` in the commit message) run the same native
build and checks, then create a new matching tag at that tested commit. Existing
tags and releases are never replaced.

The normal automated preparation path uses a reviewed `[release]` commit on
`codex/release-v<version>`. Its successful native build opens and normally merges
a release PR at the matched head, then dispatches a fresh main build with
`publish=true` and the exact merged SHA. That main build creates the matching
tag and release only after its own checks pass. Do not pre-create the tag or
dispatch a second publication while this path is running.

## Defender release gate

See [Defender verification and the withdrawn 2.0 artifact](DEFENDER_RELEASE_GUARD.md).
Hosted Windows runners start with antivirus exclusions/protection disabled; do
not treat their defaults as a clean scan. The workflow enables protection in the
isolated runner, updates signatures, verifies cloud connectivity and scans the
complete portable runtime and standalone EXE before either packaged startup.
It then scans the exact final direct EXE and both final ZIPs and checks their
recorded hashes again at publication. Any unavailable protection, detection,
scan error or changed input blocks the release. Reports are retained for review.

## Reviewed offline user guides

`tools.package_release.RUNTIME_GUIDES` is the explicit user-document allowlist.
The Windows builder collects these reviewed files into `guides` for both build forms.
The portable ZIP exposes them under `_internal/guides/`. Their exact bytes are
bound to the reviewed source manifest and verified alongside other runtime
metadata; missing, altered or unreviewed guide files fail packaging. Repository
and developer documents remain confined to the Source ZIP. Only the explicitly
allowlisted guides are embedded in both executable forms.
