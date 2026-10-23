"""Nintendo emulator capabilities backed by emulator documentation/source.

Path values are bounded Windows candidates for the hub to expand against the
current process environment. They are hints, not an instruction to crawl the
filesystem. Portable or custom installations remain user-selectable.

These records describe launch and location conventions only. They never open,
convert, decrypt, resign, import, or write emulator save data.
"""

from koei_editor.shared.emulator_provider_contract import EmulatorProvider


PROVIDERS = (
    EmulatorProvider(
        id="dolphin",
        name="Dolphin",
        platforms=("GameCube", "Wii"),
        executable_names=("Dolphin.exe",),
        install_candidates=(
            r"{PROGRAMFILES}\Dolphin-x64\Dolphin.exe",
            r"{PROGRAMFILES}\Dolphin\Dolphin.exe",
            r"{LOCALAPPDATA}\Programs\Dolphin\Dolphin.exe",
        ),
        config_candidates=(
            r"{INSTALL_DIR}\User\Config\Dolphin.ini",
            r"{APPDATA}\Dolphin Emulator\Config\Dolphin.ini",
            r"{USERPROFILE}\Documents\Dolphin Emulator\Config\Dolphin.ini",
        ),
        data_candidates=(
            r"{INSTALL_DIR}\User",
            r"{APPDATA}\Dolphin Emulator",
            r"{USERPROFILE}\Documents\Dolphin Emulator",
        ),
        launch_style="flag",
        launch_flag=("-e",),
        target_rule="file_or_directory",
        launch_note=(
            "Launch a selected game image with -e <file>. Dolphin's documented "
            "-u option selects a user directory; local portable mode uses a "
            "User directory beside the executable. Resolve an explicitly "
            "selected user directory before showing save locations."
        ),
        documentation=(
            "https://github.com/dolphin-emu/dolphin/blob/master/Readme.md",
            "https://dolphin-emu.org/docs/guides/controlling-global-user-directory/",
        ),
    ).validate(),
    EmulatorProvider(
        id="cemu",
        name="Cemu",
        platforms=("Wii U",),
        executable_names=("Cemu.exe",),
        install_candidates=(
            r"{PROGRAMFILES}\Cemu\Cemu.exe",
            r"{LOCALAPPDATA}\Programs\Cemu\Cemu.exe",
        ),
        config_candidates=(
            r"{INSTALL_DIR}\portable\settings.xml",
            r"{INSTALL_DIR}\settings.xml",
            r"{APPDATA}\Cemu\settings.xml",
            r"{PROGRAMFILES}\Cemu\portable\settings.xml",
            r"{PROGRAMFILES}\Cemu\settings.xml",
            r"{LOCALAPPDATA}\Programs\Cemu\portable\settings.xml",
            r"{LOCALAPPDATA}\Programs\Cemu\settings.xml",
        ),
        data_candidates=(
            r"{INSTALL_DIR}\portable\mlc01",
            r"{INSTALL_DIR}\mlc01",
            r"{APPDATA}\Cemu\mlc01",
            r"{PROGRAMFILES}\Cemu\portable\mlc01",
            r"{PROGRAMFILES}\Cemu\mlc01",
            r"{LOCALAPPDATA}\Programs\Cemu\portable\mlc01",
            r"{LOCALAPPDATA}\Programs\Cemu\mlc01",
        ),
        launch_style="flag",
        launch_flag=("-g",),
        target_rule="file_or_directory",
        launch_note=(
            "Launch a selected title with -g <game path>. Cemu also documents "
            "--title-id/-t and --mlc/-m; a configured mlc_path in settings.xml "
            "takes precedence over default MLC candidates. Read paths only and "
            "hand off copies outside the emulator's MLC tree."
        ),
        documentation=(
            "https://github.com/cemu-project/Cemu/blob/main/src/config/LaunchSettings.cpp",
            "https://github.com/cemu-project/Cemu/blob/main/src/config/CemuConfig.cpp",
            "https://wiki.cemu.info/wiki/Folder_structure",
        ),
    ).validate(),
    EmulatorProvider(
        id="ryujinx_compatible",
        name="Ryujinx-compatible",
        platforms=("Nintendo Switch",),
        executable_names=("Ryujinx.exe",),
        install_candidates=(
            r"{PROGRAMFILES}\Ryujinx\Ryujinx.exe",
            r"{LOCALAPPDATA}\Programs\Ryujinx\Ryujinx.exe",
        ),
        config_candidates=(
            r"{INSTALL_DIR}\portable\Config.json",
            r"{APPDATA}\Ryujinx\Config.json",
        ),
        data_candidates=(
            r"{INSTALL_DIR}\portable",
            r"{APPDATA}\Ryujinx",
            r"{PROGRAMFILES}\Ryujinx\portable",
            r"{LOCALAPPDATA}\Programs\Ryujinx\portable",
        ),
        launch_style="gui",
        target_rule="file_or_directory",
        launch_note=(
            "Per-title launch is GUI-only: the current Ryubing setup guide "
            "documents -r/--root-data-dir and --fullscreen, but no stable "
            "per-title game-path argument. Open the selected title from the "
            "emulator UI. The hub does not replay custom shortcut arguments; "
            "configure the desired root in the emulator's own default "
            "settings. Per-title user/device save directories are "
            "provided by the UI; copy an export and let the exact existing "
            "editor profile qualify it. Fork-specific CLI capabilities require "
            "verified documentation before use."
        ),
        documentation=(
            "https://docs.ryujinx.app/guides/setup-guide/",
            "https://github.com/Ryubing/docs/blob/main/docs/info/faq-%26-troubleshooting.md",
        ),
    ).validate(),
)
