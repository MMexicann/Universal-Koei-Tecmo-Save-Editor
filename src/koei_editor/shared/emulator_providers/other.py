"""Emulator capabilities for 3DS, Vita, DS, Xbox 360, and Original Xbox.

The path candidates are bounded Windows hints; PATH and explicit user selection
cover portable installs. Provider records describe only documented entry points.
They never inspect, alter, decrypt, resign, import, or export emulator saves.
"""

from koei_editor.shared.emulator_provider_contract import EmulatorProvider


PROVIDERS = (
    EmulatorProvider(
        id="azahar_3ds",
        name="Azahar / Citra",
        platforms=("Nintendo 3DS",),
        executable_names=("azahar.exe", "Azahar.exe", "citra-qt.exe", "azahar", "citra-qt"),
        install_candidates=(
            r"{PROGRAMFILES}\Azahar\azahar.exe",
            r"{PROGRAMFILES}\Citra\citra-qt.exe",
            r"{LOCALAPPDATA}\Programs\Azahar\azahar.exe",
            r"{LOCALAPPDATA}\Programs\Citra\citra-qt.exe",
        ),
        config_candidates=(
            r"{APPDATA}\Azahar\config\qt-config.ini",
            r"{APPDATA}\Citra\config\qt-config.ini",
            r"{PROGRAMFILES}\Azahar\user\config\qt-config.ini",
            r"{PROGRAMFILES}\Citra\user\config\qt-config.ini",
        ),
        data_candidates=(
            r"{INSTALL_DIR}\user",
            r"{INSTALL_DIR}\portable\user",
            r"{APPDATA}\Azahar",
            r"{APPDATA}\Citra",
            r"{PROGRAMFILES}\Azahar\user",
            r"{PROGRAMFILES}\Citra\user",
        ),
        # The desktop Qt front end starts its game library UI; no verified
        # per-title command-line argument is present in the current source.
        launch_style="gui",
        target_rule="file",
        launch_note=(
            "Launches the Azahar/Citra desktop interface. The documented Qt "
            "front end opens games from its library/menu; this profile does "
            "not pass a game path. Select the title inside the emulator."
        ),
        documentation=(
            "https://github.com/azahar-emu/azahar/blob/master/README.md",
            "https://github.com/azahar-emu/azahar/blob/master/src/common/common_paths.h",
            "https://github.com/azahar-emu/azahar/blob/master/src/citra_qt/citra_qt.cpp",
        ),
    ).validate(),
    EmulatorProvider(
        id="vita3k",
        name="Vita3K",
        platforms=("PlayStation Vita",),
        executable_names=("Vita3K.exe", "vita3k.exe", "Vita3K", "vita3k"),
        install_candidates=(
            r"{PROGRAMFILES}\Vita3K\Vita3K.exe",
            r"{LOCALAPPDATA}\Programs\Vita3K\Vita3K.exe",
        ),
        config_candidates=(
            r"{PROGRAMFILES}\Vita3K\config.yml",
            r"{PROGRAMFILES}\Vita3K\portable\config.yml",
            r"{LOCALAPPDATA}\Programs\Vita3K\config.yml",
            r"{LOCALAPPDATA}\Programs\Vita3K\portable\config.yml",
        ),
        data_candidates=(
            r"{INSTALL_DIR}\ux0",
            r"{INSTALL_DIR}\fs",
            r"{INSTALL_DIR}\portable\fs",
            r"{APPDATA}\Vita3K\Vita3K",
            r"{LOCALAPPDATA}\Programs\Vita3K\ux0",
            r"{LOCALAPPDATA}\Programs\Vita3K\fs",
            r"{PROGRAMFILES}\Vita3K\portable\fs",
        ),
        launch_style="flag",
        launch_flag=("--installed-path",),
        target_rule="vita3k_installed_app",
        launch_note=(
            "Vita3K documents --installed-path <path> (-r) for an app already "
            "installed inside its ux0/app tree. The hub checks that path shape; "
            "Vita3K verifies membership in the selected installation's virtual "
            "tree when launched. This does not install a package or bypass a "
            "license; choose an app folder from that installation."
        ),
        documentation=(
            "https://github.com/Vita3K/Vita3K/blob/master/README.md",
            "https://github.com/Vita3K/Vita3K/blob/master/vita3k/config/src/config.cpp",
            "https://github.com/Vita3K/Vita3K/blob/master/vita3k/app/src/app_init.cpp",
        ),
    ).validate(),
    EmulatorProvider(
        id="melonds",
        name="melonDS",
        platforms=("Nintendo DS",),
        executable_names=("melonDS.exe", "melonDS", "melonds"),
        install_candidates=(
            r"{PROGRAMFILES}\melonDS\melonDS.exe",
            r"{LOCALAPPDATA}\Programs\melonDS\melonDS.exe",
        ),
        config_candidates=(
            r"{APPDATA}\melonDS\melonDS.toml",
            r"{PROGRAMFILES}\melonDS\portable\melonDS.toml",
            r"{PROGRAMFILES}\melonDS\melonDS.toml",
        ),
        data_candidates=(
            r"{INSTALL_DIR}\portable",
            r"{APPDATA}\melonDS",
            r"{PROGRAMFILES}\melonDS\portable",
        ),
        launch_style="positional",
        target_rule="file",
        launch_note=(
            "melonDS documents the first positional argument as an NDS ROM or "
            "archive to load in Slot-1. The hub passes only the selected game "
            "path; optional Slot-2 arguments are not inferred."
        ),
        documentation=(
            "https://github.com/melonDS-emu/melonDS/blob/master/README.md",
            "https://github.com/melonDS-emu/melonDS/blob/master/src/frontend/qt_sdl/CLI.cpp",
            "https://github.com/melonDS-emu/melonDS/blob/master/src/frontend/qt_sdl/main.cpp",
        ),
    ).validate(),
    EmulatorProvider(
        id="xenia",
        name="Xenia",
        platforms=("Xbox 360 / Xenia",),
        executable_names=("xenia.exe", "xenia"),
        install_candidates=(
            r"{PROGRAMFILES}\Xenia\xenia.exe",
            r"{LOCALAPPDATA}\Programs\Xenia\xenia.exe",
        ),
        config_candidates=(
            r"{USERPROFILE}\Documents\Xenia\xenia.config.toml",
            r"{PROGRAMFILES}\Xenia\xenia.config.toml",
        ),
        data_candidates=(
            r"{INSTALL_DIR}\content",
            r"{INSTALL_DIR}",
            r"{USERPROFILE}\Documents\Xenia",
            r"{PROGRAMFILES}\Xenia",
        ),
        launch_style="flag",
        launch_flag=("--target",),
        target_rule="xenia_target",
        launch_note=(
            "Xenia defines the transient --target option for an .xex or .iso. "
            "Storage/config defaults may use a portable.txt beside the "
            "executable; custom roots must be selected explicitly."
        ),
        documentation=(
            "https://github.com/xenia-project/xenia/blob/master/README.md",
            "https://github.com/xenia-project/xenia/blob/master/src/xenia/app/xenia_main.cc",
            "https://github.com/xenia-project/xenia/blob/master/src/xenia/config.cc",
        ),
    ).validate(),
    EmulatorProvider(
        id="xemu",
        name="xemu",
        platforms=("Original Xbox",),
        executable_names=("xemu.exe", "xemu"),
        install_candidates=(
            r"{PROGRAMFILES}\xemu\xemu.exe",
            r"{LOCALAPPDATA}\Programs\xemu\xemu.exe",
        ),
        config_candidates=(
            r"{APPDATA}\xemu\xemu\xemu.toml",
            r"{PROGRAMFILES}\xemu\xemu.toml",
        ),
        data_candidates=(
            r"{INSTALL_DIR}\data",
            r"{INSTALL_DIR}",
            r"{APPDATA}\xemu\xemu",
            r"{PROGRAMFILES}\xemu",
        ),
        # xemu's frontend is configured as a machine with firmware and media;
        # no verified app-specific game-path argument is used here.
        launch_style="gui",
        target_rule="file_or_directory",
        launch_note=(
            "Launches the xemu interface without passing a game path. Booting "
            "depends on the user's configured firmware, storage, and media; "
            "the hub does not supply or alter those files."
        ),
        documentation=(
            "https://github.com/xemu-project/xemu/blob/master/README.md",
            "https://github.com/xemu-project/xemu/blob/master/ui/xemu-settings.cc",
        ),
    ).validate(),
)
