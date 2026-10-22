"""Safe discovery, game association, launch and save-copy qualification.

The hub treats emulator installs/configuration as read-only hints. It launches
only through static provider records, never invokes a shell, and qualifies save
exports with one exact existing game/platform reader.
"""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import xml.etree.ElementTree as ET

from koei_editor.game_registry import GAMES, get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.emulator_provider_contract import EmulatorProvider, all_providers
from koei_editor.shared import save_library


_PATH_TEMPLATE = re.compile(r'\{([A-Z][A-Z0-9_]*)\}')
_PROVIDERS = None


@dataclass(frozen=True)
class EmulatorInstallation:
    id: str
    provider_id: str
    executable: str
    config_path: str = ''
    data_path: str = ''
    discovered_by: str = 'known_path'
    additional_data_paths: tuple[str, ...] = ()
    additional_config_paths: tuple[str, ...] = ()

    @property
    def protected_data_paths(self):
        return tuple(dict.fromkeys(path for path in (self.data_path, *self.additional_data_paths) if path))

    @property
    def configuration_paths(self):
        return tuple(dict.fromkeys(path for path in (self.config_path, *self.additional_config_paths) if path))


@dataclass(frozen=True)
class LaunchProfile:
    id: str
    provider_id: str
    executable: str
    game_id: str
    content_path: str


@dataclass(frozen=True)
class LaunchPlan:
    argv: tuple[str, ...]
    content_passed: bool
    note: str = ''


def providers():
    global _PROVIDERS
    if _PROVIDERS is None:
        _PROVIDERS = all_providers()
    return _PROVIDERS


def provider_for(provider_id):
    if type(provider_id) is not str:
        raise SaveError('Choose a supported emulator setup.')
    match = next((item for item in providers() if item.id == provider_id), None)
    if match is None:
        raise SaveError('Choose a supported emulator setup.')
    return match


def games_for_provider(provider_id, *, editors_only=False):
    """Return exact registered game/platform profiles for this emulator."""
    provider = provider_for(provider_id)
    return tuple(game for game in GAMES
                 if game.platform in provider.platforms
                 and (not editors_only or game.scalar_backend is not None))


def _expand_candidate(template, environment):
    names = _PATH_TEMPLATE.findall(template)
    if any(name not in environment or type(environment[name]) is not str or not environment[name]
           for name in names):
        return None
    expanded = _PATH_TEMPLATE.sub(lambda match: environment[match.group(1)], template)
    if '{' in expanded or '}' in expanded or len(expanded) > 4096:
        return None
    return Path(expanded)


def _ordinary(path, *, directory=False):
    try:
        info = path.lstat()
    except (OSError, ValueError):
        return None
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            return None
    elif not stat.S_ISREG(info.st_mode):
        return None
    try:
        return str(path.absolute())
    except (OSError, ValueError):
        return None


def _path_id(provider_id, executable):
    canonical = os.path.normcase(os.path.abspath(executable))
    token = hashlib.sha256((provider_id + '\0' + canonical).encode('utf-8', errors='surrogatepass')).hexdigest()[:20]
    return provider_id + ':' + token


def _supported_executable_name(provider, executable):
    name = Path(executable).name.casefold()
    return name in {item.casefold() for item in provider.executable_names}


def _profile_identity(provider, executable, game_id, content_path):
    identity = '\0'.join((provider.id, os.path.normcase(os.path.abspath(executable)), game_id,
                           os.path.normcase(os.path.abspath(content_path))))
    profile_id = 'launch:' + hashlib.sha256(identity.encode('utf-8', errors='surrogatepass')).hexdigest()[:24]
    return LaunchProfile(profile_id, provider.id, os.path.abspath(executable), game_id,
                         os.path.abspath(content_path))


def _validate_content_target(provider, content_path):
    target = Path(content_path)
    try:
        target_info = target.lstat()
        resolved = target.resolve(strict=True)
    except (OSError, ValueError):
        raise SaveError('The associated game content path is missing.')
    is_file = stat.S_ISREG(target_info.st_mode)
    is_directory = stat.S_ISDIR(target_info.st_mode)
    if stat.S_ISLNK(target_info.st_mode) or not (is_file or is_directory):
        raise SaveError('The associated game content must be an ordinary file or folder.')
    if provider.target_rule == 'file' and not is_file:
        raise SaveError(f'{provider.name} requires a game content file.')
    if provider.target_rule == 'vita3k_installed_app':
        parts = tuple(part.casefold() for part in resolved.parts)
        if not is_directory or len(parts) < 3 or parts[-2] != 'app' or parts[-3] != 'ux0':
            raise SaveError('Vita3K requires an existing app folder inside ux0/app.')
    if provider.target_rule == 'xenia_target':
        if not is_file or target.suffix.casefold() not in {'.xex', '.iso'}:
            raise SaveError('Xenia requires an .xex or .iso game file.')
    return resolved


def _first_path(templates, environment, *, directory=False):
    for template in templates:
        candidate = _expand_candidate(template, environment)
        if candidate is None:
            continue
        ordinary = _ordinary(candidate, directory=directory)
        if ordinary is not None:
            return ordinary
    return ''


def _existing_paths(templates, environment, *, directory=False):
    found = []
    for template in templates:
        candidate = _expand_candidate(template, environment)
        if candidate is None:
            continue
        ordinary = _ordinary(candidate, directory=directory)
        if ordinary is not None and ordinary not in found:
            found.append(ordinary)
    return tuple(found)


def _cemu_config_data_paths(provider, config_path):
    """Read only Cemu's documented ``mlc_path`` preference, with strict bounds."""
    if provider.id != 'cemu' or not config_path or _ordinary(Path(config_path)) is None:
        return ()
    try:
        with Path(config_path).open('rb') as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            return ()
        text = raw.decode('utf-8-sig')
        upper = text.upper()
        if '<!DOCTYPE' in upper or '<!ENTITY' in upper:
            return ()
        root = ET.fromstring(text)
    except (OSError, UnicodeDecodeError, ValueError, ET.ParseError):
        return ()
    for element in root.iter():
        if element.tag.rsplit('}', 1)[-1].casefold() != 'mlc_path':
            continue
        value = (element.text or '').strip()
        if not value or len(value) > 4096:
            return ()
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            return ()
        ordinary = _ordinary(candidate, directory=True)
        return (ordinary,) if ordinary is not None else ()
    return ()


def _ppsspp_installed_data_paths(provider, executable):
    """Read PPSSPP's bounded Windows installed.txt memory-stick override."""
    if provider.id != 'ppsspp':
        return ()
    installed_file = Path(executable).parent / 'installed.txt'
    if _ordinary(installed_file) is None:
        return ()
    try:
        with installed_file.open('rb') as stream:
            raw = stream.read(2049)
        if len(raw) > 2048:
            return ()
        first_line = raw.splitlines()[0] if raw.splitlines() else b''
        value = first_line.decode('utf-8-sig').rstrip('\r\n')
        if not value or '\0' in value:
            return ()
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = Path(executable).parent / candidate
        ordinary = _ordinary(candidate, directory=True)
        return (ordinary,) if ordinary is not None else ()
    except (OSError, UnicodeDecodeError, ValueError):
        return ()


def _ppsspp_installed_config_paths(provider, data_paths):
    if provider.id != 'ppsspp':
        return ()
    found = []
    for data_path in data_paths:
        config = Path(data_path) / 'PSP' / 'SYSTEM' / 'ppsspp.ini'
        ordinary = _ordinary(config)
        if ordinary is not None and ordinary not in found:
            found.append(ordinary)
    return tuple(found)


def _installation_hints(provider, executable, environment):
    install_environment = dict(environment)
    install_environment['INSTALL_DIR'] = str(Path(executable).parent)
    ppsspp_data_paths = _ppsspp_installed_data_paths(provider, executable)
    config_paths = list(_ppsspp_installed_config_paths(provider, ppsspp_data_paths))
    config_paths.extend(_existing_paths(provider.config_candidates, install_environment))
    data_paths = list(_existing_paths(provider.data_candidates, install_environment, directory=True))
    if ppsspp_data_paths:
        data_paths = list(ppsspp_data_paths) + data_paths
    for config_path in config_paths:
        data_paths.extend(_cemu_config_data_paths(provider, config_path))
    return tuple(config_paths), tuple(dict.fromkeys(data_paths))


def discover_installations(*, environment=None, which=None):
    """Find exact known emulator executables from PATH and bounded known paths.

    No recursive file search, process inspection, config mutation, or emulator
    execution occurs. Portable/custom installs can be added from the GUI.
    """
    catalog = providers()
    variables = {'PATH'}
    for provider in catalog:
        for template in provider.install_candidates + provider.config_candidates + provider.data_candidates:
            variables.update(_PATH_TEMPLATE.findall(template))
    if environment is None:
        environment = {name: os.environ.get(name, '') for name in variables}
    elif type(environment) is not dict or any(type(key) is not str or type(value) is not str
                                               for key, value in environment.items()):
        raise SaveError('Emulator discovery requires ordinary environment strings.')
    else:
        environment = {name: environment.get(name, '') for name in variables}
    path_value = environment.get('PATH', '')
    which = shutil.which if which is None else which
    found = {}
    for provider in catalog:
        for executable_name in provider.executable_names:
            candidate = None
            try:
                located = which(executable_name, path=path_value)
                if located:
                    ordinary = _ordinary(Path(located))
                    if ordinary is not None:
                        candidate = (ordinary, 'PATH')
            except (OSError, TypeError, ValueError):
                candidate = None
            if candidate is None:
                for template in provider.install_candidates:
                    path = _expand_candidate(template, environment)
                    if path is None:
                        continue
                    ordinary = _ordinary(path)
                    if ordinary is not None:
                        candidate = (ordinary, 'known_path')
                        break
            if candidate is None:
                continue
            executable, discovered_by = candidate
            installation_id = _path_id(provider.id, executable)
            if installation_id in found:
                continue
            config_paths, data_paths = _installation_hints(provider, executable, environment)
            data = data_paths[0] if data_paths else ''
            found[installation_id] = EmulatorInstallation(
                installation_id, provider.id, executable,
                config_paths[0] if config_paths else '', data, discovered_by, data_paths, config_paths)
    return tuple(found.values())


def manual_installation(provider_id, executable, *, config_path='', data_path=''):
    """Represent a user-selected executable without probing or running it."""
    provider = provider_for(provider_id)
    if type(executable) is not str or not executable or len(executable) > 4096:
        raise SaveError('Choose an emulator executable path.')
    path = Path(executable).expanduser()
    ordinary = _ordinary(path)
    if ordinary is None or not _supported_executable_name(provider, ordinary):
        raise SaveError('Choose an ordinary executable for the selected emulator family.')
    if type(config_path) is not str or type(data_path) is not str or len(config_path) > 4096 or len(data_path) > 4096:
        raise SaveError('Emulator configuration and data paths must be ordinary bounded paths.')
    variables = {'PATH'}
    for template in provider.config_candidates + provider.data_candidates:
        variables.update(_PATH_TEMPLATE.findall(template))
    environment = {name: os.environ.get(name, '') for name in variables}
    detected_configs, discovered_data = _installation_hints(provider, ordinary, environment)
    protected_data = discovered_data
    if data_path:
        ordinary_data = _ordinary(Path(data_path).expanduser(), directory=True)
        if ordinary_data is None:
            raise SaveError('Choose an existing ordinary emulator-managed data folder.')
        protected_data = tuple(dict.fromkeys((*protected_data, ordinary_data)))
    if config_path:
        config_ordinary = _ordinary(Path(config_path).expanduser())
        if config_ordinary is None:
            raise SaveError('Choose an existing ordinary emulator configuration file.')
        detected_configs = tuple(dict.fromkeys((*detected_configs, config_ordinary)))
        protected_data = tuple(dict.fromkeys((*protected_data,
                                             *_cemu_config_data_paths(provider, config_ordinary))))
    config_path = config_path or (detected_configs[0] if detected_configs else '')
    return EmulatorInstallation(_path_id(provider.id, ordinary), provider.id, ordinary,
                                str(config_path), protected_data[0] if protected_data else '', 'manual',
                                protected_data, detected_configs)


def create_launch_profile(provider_id, executable, game_id, content_path):
    provider = provider_for(provider_id)
    game = get_game(game_id)
    if game not in GAMES or game.platform not in provider.platforms:
        raise SaveError('Choose a registered game/platform that matches this emulator.')
    if type(executable) is not str or not executable or len(executable) > 4096:
        raise SaveError('Choose an emulator executable path.')
    if not _supported_executable_name(provider, executable):
        raise SaveError('Choose an executable name supported by the selected emulator family.')
    if type(content_path) is not str or not content_path or len(content_path) > 4096:
        raise SaveError('Choose a game content path for this launch profile.')
    _validate_content_target(provider, content_path)
    return _profile_identity(provider, executable, game.id, content_path)


def validate_launch_profile(profile):
    if type(profile) is not LaunchProfile:
        raise SaveError('A saved emulator launch profile is required.')
    provider = provider_for(profile.provider_id)
    game = get_game(profile.game_id)
    if (game not in GAMES or game.platform not in provider.platforms
            or type(profile.executable) is not str or not profile.executable or len(profile.executable) > 4096
            or not _supported_executable_name(provider, profile.executable)
            or type(profile.content_path) is not str or not profile.content_path or len(profile.content_path) > 4096):
        raise SaveError('The saved emulator launch profile is invalid.')
    expected = _profile_identity(provider, profile.executable, game.id, profile.content_path)
    if profile.id != expected.id:
        raise SaveError('The emulator launch profile identity is invalid.')
    return expected


def build_launch_plan(profile):
    profile = validate_launch_profile(profile)
    provider = provider_for(profile.provider_id)
    executable = Path(profile.executable)
    if _ordinary(executable) is None or not _supported_executable_name(provider, executable):
        raise SaveError('The configured emulator executable is missing or is not an ordinary file.')
    argv = [str(executable.absolute())]
    resolved_target = _validate_content_target(provider, profile.content_path)
    if provider.launch_style != 'gui':
        if provider.launch_style == 'positional':
            argv.append(str(resolved_target))
        else:
            argv.extend(provider.launch_flag)
            argv.append(str(resolved_target))
        return LaunchPlan(tuple(argv), True, provider.launch_note)
    return LaunchPlan(tuple(argv), False, provider.launch_note)


def launch(profile, *, popen=None):
    """Launch a profile using a fixed argv vector and no shell."""
    plan = build_launch_plan(profile)
    popen = subprocess.Popen if popen is None else popen
    try:
        process = popen(list(plan.argv), cwd=str(Path(plan.argv[0]).parent), shell=False)
    except (OSError, ValueError) as error:
        raise SaveError('The emulator could not be started: ' + str(error)) from error
    return plan, process


def scan_export_folder(game_id, folder, *, provider_id=None, active_data_root=None,
                       recursive=False, cancel=None, protected_roots=()):
    """Qualify exported copies through one exact existing scalar profile."""
    game = get_game(game_id)
    if game not in GAMES or game.scalar_backend is None:
        raise SaveError('Save handoff requires an existing scalar editor profile.')
    if provider_id is None:
        raise SaveError('Choose the emulator family before scanning exported saves.')
    if game.platform not in provider_for(provider_id).platforms:
        raise SaveError('The selected editor profile does not match this emulator platform.')
    if type(active_data_root) is not str or not active_data_root or len(active_data_root) > 4096:
        raise SaveError('Select the active emulator-managed data folder to protect before scanning exports.')
    if type(protected_roots) not in (tuple, list) or len(protected_roots) > 128:
        raise SaveError('Emulator save-folder protection requires bounded paths.')
    roots = [active_data_root, *protected_roots]
    for item in discover_installations():
        if item.provider_id == provider_id:
            roots.extend(item.protected_data_paths)
    protected = []
    for root in roots:
        if type(root) is not str or not root or len(root) > 4096:
            raise SaveError('Emulator-managed data folders must be existing ordinary paths.')
        candidate = Path(root).expanduser()
        ordinary = _ordinary(candidate, directory=True)
        if ordinary is None:
            raise SaveError('Choose an existing ordinary emulator-managed data folder.')
        protected.append(candidate.resolve(strict=True))
    try:
        selected = Path(folder).resolve(strict=True)
    except (OSError, ValueError):
        selected = None
    if selected is not None:
        for live in protected:
            if selected == live or selected in live.parents or live in selected.parents:
                raise SaveError('Choose an exported-copy folder outside emulator-managed save data.')
    return save_library.scan(game_id, folder, recursive=recursive, cancel=cancel)


def qualify_export(result, entry, *, cancel=None):
    """Recheck a selected candidate; callers still open through the normal editor."""
    return save_library.requalify(result, entry, cancel=cancel)
