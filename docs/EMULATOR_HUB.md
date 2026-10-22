# Emulator Integration Hub

The Emulator Integration Hub connects emulator installations and game launch
profiles to the save editor's existing game catalog. Open it from **Tools →
Emulator Integration Hub**. It discovers known executables from `PATH` and a
small set of standard Windows locations. It does not recursively search disks,
inspect running processes, or execute an emulator during discovery. Portable
or custom installations can be added by selecting their executable.

## Supported emulator setups

The hub associates launch profiles with the exact platform names already in the
game catalog. It does not add a game entry or infer a platform from a filename.
Where the catalog has no game for an emulator's platform, launch profiles and
save-editor profiles are unavailable for that provider.

| Emulator | Catalog platform | Launch behavior |
| --- | --- | --- |
| RPCS3 | PlayStation 3 | Selected boot target as a positional path |
| PCSX2 | PlayStation 2 | Selected boot filename as a positional path |
| PPSSPP | PlayStation Portable | No currently registered PSP title; installation discovery only |
| Dolphin | GameCube, Wii | `-e <file>`; no supported Koei Tecmo game is currently registered for these platforms |
| Cemu | Wii U | `-g <game path>` |
| Ryujinx-compatible, including Ryubing builds using `Ryujinx.exe` | Nintendo Switch | Opens the emulator interface; per-title launch requires selection in its library |
| Azahar / Citra | Nintendo 3DS | Opens the emulator interface; select the title inside the emulator |
| Vita3K | PlayStation Vita | `--installed-path <app directory>` for an already installed app |
| melonDS | Nintendo DS | Selected NDS path as the first positional argument |
| Xenia | Xbox 360 / Xenia | `--target <file>` |
| xemu | Original Xbox | Opens the emulator interface; boot depends on its configured machine and media |

Launch arguments follow upstream emulator documentation linked in the provider
records under `src/koei_editor/shared/emulator_providers/`. Profiles store the
executable, existing game profile, and content path in a bounded local
preferences sidecar. Launches use a fixed argument list with shell processing
disabled. GUI-only providers do not receive a title path. Profiles contain no
extra shortcut arguments or custom data-root overrides; configure the desired
root in the emulator itself before launching from the hub. Vita3K's profile
check confirms the `ux0/app/<title>` path shape, while Vita3K itself verifies
membership in the selected install's virtual app tree. The hub does not add
undocumented launch flags, emulator configuration changes, firmware, or game
content.

## Detecting and opening exported saves

Use the **Exported save copies** tab to choose an emulator family, an exact
existing scalar editor profile, and a folder containing copies exported by the
emulator's documented workflow. The scan uses the same bounded Save Library
reader as the rest of the editor. It rechecks the selected file before handing
it to the game's normal editor path. It does not guess from the filename or
fall back to a different parser.

Before every scan, select the **Active emulator data root to protect**.
Discovery paths are hints and may not reflect an emulator's custom data-root
override. The hub checks that the chosen exported-copy folder is outside the
active root and all discovered roots. Emulator save states are not game saves
and are not accepted as substitutes.

The editor profile must match the emulator's registered platform. The save
format, revision, and any required companion context must also qualify for that
specific game. A game that appears in the launch profile list may still have no
save editor, or may require an encrypted, signed, account-bound, or otherwise
unsupported export. Those requirements remain in force. The hub does not
decrypt, resign, import, extract, convert, or rewrite emulator-managed saves.

Discovery displays every existing standard configuration and data candidate it
can resolve, including portable install folders and Cemu's documented
`mlc_path` setting. Custom roots can still differ from those locations. Add the
active emulator-managed folder in **Active emulator data root to protect** for
each scan; scanning is blocked if it is missing or cannot be validated. Keep
the separately exported copy folder outside all managed roots.
Scanning and requalification run in a cancellable background worker. The scan
is local and read-only.

## Verification report

The mocked integration suite exercises provider validation, exact platform
matching, mocked installation discovery, argument construction, shell-free
launch invocation, profile persistence, bounded save qualification, protected
data-root rejection, requalification, and the normal editor callback:

```text
PYTHONPATH=src python -m unittest \
  tests.test_emulator_hub \
  tests.test_emulator_sony_providers \
  tests.test_emulator_nintendo_providers \
  tests.test_emulator_other_providers \
  tests.test_application_shell -v
```

The provider tests use temporary mock executable files and mocked process
creation; no emulator binary is started. Tk application-shell cases require a
display server and are skipped on headless systems.
