"""Documented Windows provider records for Sony platform emulators.

The catalog describes executable, config and data path conventions only. It
does not inspect or alter emulator saves, and launch targets are passed as one
positional argument by the hub.
"""

from koei_editor.shared.emulator_provider_contract import EmulatorProvider


_RPCS3_DOCS = (
    "https://github.com/RPCS3/rpcs3/blob/master/rpcs3/rpcs3.cpp",
    "https://github.com/RPCS3/rpcs3/blob/master/Utilities/File.cpp",
    "https://github.com/RPCS3/rpcs3/blob/master/rpcs3/Emu/vfs_config.h",
    "https://github.com/RPCS3/rpcs3/blob/master/rpcs3/Emu/vfs_config.cpp",
)

_PCSX2_DOCS = (
    "https://github.com/PCSX2/pcsx2/blob/master/pcsx2-qt/QtHost.cpp",
    "https://github.com/PCSX2/pcsx2/blob/master/pcsx2/Pcsx2Config.cpp",
)

_PPSSPP_DOCS = (
    "https://github.com/hrydgard/ppsspp/blob/master/docs/command-line.md",
    "https://github.com/hrydgard/ppsspp/blob/master/Core/CmdLine.cpp",
    "https://github.com/hrydgard/ppsspp/blob/master/Windows/main.cpp",
    "https://github.com/hrydgard/ppsspp/blob/master/Core/Util/PathUtil.cpp",
)


PROVIDERS = (
    EmulatorProvider(
        id="rpcs3",
        name="RPCS3",
        platforms=("PlayStation 3",),
        executable_names=("rpcs3.exe",),
        install_candidates=(
            r"{PROGRAMFILES}\RPCS3\rpcs3.exe",
            r"{APPDATA}\RPCS3\rpcs3.exe",
        ),
        config_candidates=(
            r"{INSTALL_DIR}\portable\config\config.yml",
            r"{INSTALL_DIR}\portable\config\vfs.yml",
            r"{RPCS3_CONFIG_DIR}\config\config.yml",
            r"{RPCS3_CONFIG_DIR}\config\vfs.yml",
            r"{INSTALL_DIR}\config\config.yml",
            r"{INSTALL_DIR}\config\vfs.yml",
        ),
        data_candidates=(
            r"{INSTALL_DIR}\portable\dev_hdd0",
            r"{RPCS3_CONFIG_DIR}\dev_hdd0",
            r"{INSTALL_DIR}\dev_hdd0",
        ),
        launch_style="positional",
        target_rule="file_or_directory",
        launch_note=(
            "Pass the selected boot target as a positional path. The documented "
            "--no-gui and --fullscreen options are not added by default; "
            "--fullscreen requires --no-gui. Never use --decrypt or savestate "
            "options for save discovery or editor handoff."
        ),
        documentation=_RPCS3_DOCS,
    ),
    EmulatorProvider(
        id="pcsx2",
        name="PCSX2",
        platforms=("PlayStation 2",),
        executable_names=("pcsx2-qt.exe",),
        install_candidates=(
            r"{PROGRAMFILES}\PCSX2\pcsx2-qt.exe",
        ),
        config_candidates=(
            r"{USERPROFILE}\Documents\PCSX2\inis\PCSX2.ini",
            r"{PROGRAMFILES}\PCSX2\inis\PCSX2.ini",
        ),
        data_candidates=(
            r"{USERPROFILE}\Documents\PCSX2\memcards",
            r"{PROGRAMFILES}\PCSX2\memcards",
        ),
        launch_style="positional",
        target_rule="file",
        launch_note=(
            "Pass the selected boot filename as a positional path. The documented "
            "-nogui option hides the main window and implies batch mode, so it is "
            "not added by default. Memory-card directories are configurable; "
            "-state and -statefile use emulator save states, not exported game saves."
        ),
        documentation=_PCSX2_DOCS,
    ),
    EmulatorProvider(
        id="ppsspp",
        name="PPSSPP",
        platforms=("PlayStation Portable",),
        executable_names=("PPSSPPWindows64.exe", "PPSSPPWindows.exe"),
        install_candidates=(
            r"{PROGRAMFILES}\PPSSPP\PPSSPPWindows64.exe",
            r"{PROGRAMFILES}\PPSSPP\PPSSPPWindows.exe",
        ),
        config_candidates=(
            r"{PROGRAMFILES}\PPSSPP\memstick\PSP\SYSTEM\ppsspp.ini",
            r"{USERPROFILE}\Documents\PPSSPP\PSP\SYSTEM\ppsspp.ini",
        ),
        data_candidates=(
            r"{INSTALL_DIR}\memstick\PSP\SAVEDATA",
            r"{PROGRAMFILES}\PPSSPP\memstick\PSP\SAVEDATA",
            r"{USERPROFILE}\Documents\PPSSPP\PSP\SAVEDATA",
        ),
        launch_style="positional",
        target_rule="file",
        launch_note=(
            "Pass the selected game filename as a positional path. --memstick "
            "<root> is documented for an explicitly selected memory-stick root "
            "and is not added automatically. --state and --save-state refer to "
            "emulator state files, not PSP savedata."
        ),
        documentation=_PPSSPP_DOCS,
    ),
)


for _provider in PROVIDERS:
    _provider.validate()
