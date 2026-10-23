# Linux edition

The native Linux edition provides the graphical toolkit and a separate headless
CLI. It uses the same game profiles, validation, Undo and copied-save workflows
as the source application. A native Linux build does not run Windows games or
make Windows-specific integrations available.

## Install and run

Use the **Linux x86_64 `.tar.gz`** from a release that lists a Linux download.
The existing v1.0 Windows downloads do not contain a Linux binary. Linux artifacts
on GitHub Actions are development builds until published in a release.
Download the archive, its Linux `.SHA256SUMS` file and
`LinuxVerification-vVERSION.json` together. The Linux checksum file verifies
both the archive and the verification report.

The release build targets Ubuntu 22.04 x86_64 and newer compatible glibc systems.
ARM, 32-bit Linux and musl distributions such as Alpine are not release targets.
A graphical session and ordinary X11/font libraries are required for the GUI.
The verified interpreter and Tcl/Tk 9.0 libraries are bundled. On Ubuntu:

```sh
sudo apt install libx11-6 libxext6 libxrender1 libxft2 libfontconfig1 libfreetype6 libstdc++6 libgcc-s1
sha256sum -c UniversalKoeiTecmoGameToolkit-vVERSION-Linux-x86_64.SHA256SUMS
tar -xzf UniversalKoeiTecmoGameToolkit-vVERSION-Linux-x86_64.tar.gz
cd UniversalKoeiTecmoGameToolkit-vVERSION-Linux-x86_64
./UniversalKoeiTecmoGameToolkit-vVERSION-Linux-x86_64
./cli/UniversalKoeiTecmoGameToolkit-vVERSION-Linux-x86_64-CLI --help
```

Replace `VERSION` with the downloaded release number. Keep the `_internal/`
folder beside each executable; the CLI has its own complete folder. No separate
Python installation, Wine, root access or installer is needed to run the toolkit.
CLI commands work without a display. See the [CLI guide](CLI.md) for examples.

## Scope and safeguards

- Save editing, comparison, qualified conversions, research tools, reports and
  offline browser companions retain their documented per-game evidence limits.
  Registered game/platform names describe save formats, not host operating systems.
- Use separate copies outside live save and Steam Cloud folders. Existing output
  files are never silently replaced. Linux atomic publication requires a local
  filesystem supporting the checked native operations; unsupported destinations
  fail closed. Do not assume a network, FUSE or removable filesystem qualifies.
- Save Vault, Smart Playthrough Profiles' managed environments and Windows mod
  deployment remain Windows-only where their native safety checks require it.
  A visible profile or read-only preview does not qualify installation/deployment.
- Game launching, discovery and configuration integrations retain their exact
  documented host/platform limits. Linux availability does not validate a game
  installation, Proton prefix or emulator automatically.
- Support reports are local and path-free. No games, account folders or private
  files are scanned by diagnostics, and no report is uploaded automatically.

## Build from source

Use native x86_64 Linux and the exact reviewed CPython 3.13.13 build interpreter.
Ubuntu 22.04 is the CI build baseline; building on a newer distribution may produce a newer glibc requirement.
Use the CI artifact for the supported baseline instead of assuming a locally built
binary runs on older distributions.

```sh
sudo apt install xvfb xauth libx11-6 libxext6 libxrender1 libxft2 libfontconfig1 libfreetype6
python3 -m tools.install_linux_python
work/linux-python/python/bin/python3.13 -m venv work/linux-venv
. work/linux-venv/bin/activate
python -m pip install -r tools/requirements/linux-build.txt
python -m pip install -e . --no-build-isolation --no-deps
xvfb-run -a python -m tools.run_tests --workers 4 --report test-results/linux.json
python -m tools.package_release --verify-only
python -m tools.build_linux
python -m tools.build_linux --cli
python -m tools.package_linux --verify-only
python -m tools.package_linux
```

Build and package commands verify the reviewed public source manifest. Runtime
data, dependency metadata, wheel-native libraries and licenses are checked before
packaging. Unknown resources, player data, private modules, escaping aliases,
wrong-architecture executables and personal home paths are refused. Archives
contain ordinary files with fixed permissions, no owner names or timestamps;
existing release outputs are refused. CI extracts the produced archive and runs
the GUI smoke test plus headless CLI checks from that extracted copy.

The bootstrap downloads only the pinned python-build-standalone 20260602
CPython 3.13.13 x86_64 GNU archive, verifies its exact SHA-256 on every download
and cache hit, and extracts it into a new `work/` folder. It does not replace a
system interpreter or create global launchers. Archive paths, links and sizes
are checked before extraction; filesystem writes use retained directory handles.
CI caches only the verified archive and recreates the interpreter and virtual
environment for each run. The standard library, native provider and all frozen
resources remain subject to the same privacy checks as application data.

## Linux dependency notices

Linux additionally bundles the reviewed PyCryptodome AES provider under its
BSD/public-domain notices and the NumPy Linux wheel's complete combined license, including
OpenBLAS, LAPACK, GCC runtime and runtime exceptions. These texts are embedded in
`_internal/licenses/` alongside the existing [third-party notices](THIRD_PARTY_NOTICES.md).
The interpreter additionally contains reviewed static dependencies, including
OpenSSL, libffi, zlib, bzip2, Expat, SQLite, libedit/ncurses and selected X11 code.
Their complete upstream notices are retained in `python-standalone-3.13.txt`.
The actual Tcl/Tk 9.0 libraries are bundled; optional Berkeley DB, Itcl, Thread
and Tix native plugins are excluded. Other distribution libraries remain supplied
and updated by the operating system. Windows CNG is never emulated.

CI smoke and procedural tests qualify the toolkit runtime and safety behavior;
they do not claim every edited file has been loaded and re-saved in a real game.
