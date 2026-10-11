# Building the Windows executable

Build on 64-bit Windows with Python 3.11 or newer and Tkinter. Build/package tools
and the development test suite use Python 3.11 or newer; the source application
itself supports Python 3.10. The Windows workflow uses
Python 3.14, and `tools/requirements/build.txt` pins PyInstaller 6.22.3. The application
itself requires no third-party runtime package on Windows.

```powershell
python -m pip install -e .
python -m pip install -r tools/requirements/build.txt
python -m tools.package_release --verify-only
python -m tools.build_windows
```

The output is **`dist/UniversalKoeiTecmoSaveEditor-v1.7.exe`**, a single standalone
executable containing the game library, all registered game editors, Tk runtime and
public application metadata. Native Windows CNG handles DW3 encryption. Save
samples, installed game files and private reports are excluded.

`tools/build_windows.py` requires Windows for compilation. Inspect the build inputs on
any OS with:

```text
python -m tools.build_windows --print-config
```

## Build checks

```powershell
python -m tools.run_tests --workers 4
python -m koei_editor --smoke-test
$smoke = Start-Process -FilePath .\dist\UniversalKoeiTecmoSaveEditor-v1.7.exe -ArgumentList '--smoke-test' -WindowStyle Hidden -Wait -PassThru
$smoke.ExitCode
python -m tools.package_release --verify-executable
```

The smoke test initializes the library and registered editors, switches games and
appearance, then exits. Require exit code 0. Save-format and game-load validation
are separate; see [VALIDATION.md](VALIDATION.md) for coverage and limitations.

The Windows workflow runs the complete suite across four independent test jobs,
each using two isolated Python processes. Runtime estimates balance modules;
unknown/new modules are always included. The build checks combined shard
reports against the current sources and complete test inventory before its
source GUI smoke test, native EXE build, packaged smoke test and archive/privacy
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
$selfTest = Start-Process -FilePath .\dist\UniversalKoeiTecmoSaveEditor-v1.7.exe -ArgumentList '--self-test "D:\SaveCopies\GameStatusData.sav" "D:\SaveCopies\DW3Test"' -WindowStyle Hidden -Wait -PassThru
$selfTest.ExitCode
```

Other editors use an explicit game ID:

```powershell
.\dist\UniversalKoeiTecmoSaveEditor-v1.7.exe --game dw4hyper --self-test "D:\SaveCopies\save.dat" "D:\SaveCopies\DW4Test"
.\dist\UniversalKoeiTecmoSaveEditor-v1.7.exe --game dw8xl --self-test "D:\SaveCopies\save.dat" "D:\SaveCopies\DW8Test"
.\dist\UniversalKoeiTecmoSaveEditor-v1.7.exe --game pw3 --self-test "D:\SaveCopies\OP3WIN0000.dat" "D:\SaveCopies\PW3Test"
.\dist\UniversalKoeiTecmoSaveEditor-v1.7.exe --game dw4xl_ps2 --self-test "D:\SaveCopies\DW4XL.psu" "D:\SaveCopies\DW4XLTest"
.\dist\UniversalKoeiTecmoSaveEditor-v1.7.exe --game atelier_sophie2 --self-test "D:\SaveCopies\data.dat" "D:\SaveCopies\Sophie2Test"
```

Use a separate input copy and a new/empty output folder. Require exit 0,
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
python -m tools.package_release --output work/local-universal-package
```

The packager produces the EXE, Windows ZIP, source ZIP and `SHA256SUMS.txt`.
Existing outputs are never replaced. It checks the embedded archive, metadata and
source hashes, and rejects save/game-file entries and personal paths.

The Windows workflow runs the tests, builds the executable and verifies its
startup and archive before creating downloadable build assets. Building locally
uses the same scripts. A completed build is a prerequisite for packaging.
Manual workflow runs only build artifacts. Pushing a tag matching the application
version, such as `v1.7`, publishes a new release after the native build and checks
succeed. Existing releases are not replaced.

PyInstaller's one-file runtime extracts into a temporary directory at startup.
An already-built executable requires no installer, game-directory access or
administrator privileges.

Release-marked main commits (`[release]` in the commit message) run the same native
build and checks, then create a new matching tag at that tested commit. Existing
tags and releases are never replaced.
