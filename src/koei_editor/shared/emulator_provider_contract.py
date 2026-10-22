"""Small, documented capability records for emulator integrations.

Provider modules contain public executable/configuration conventions and
documented launch argument shapes. They do not open game saves or alter emulator
data. The hub owns discovery, persistence, launching, and editor handoff.
"""
from dataclasses import dataclass
import re


_KEY = re.compile(r'[a-z][a-z0-9_]{0,63}\Z')
_LAUNCH_STYLES = frozenset({'positional', 'flag', 'gui'})
_TARGET_RULES = frozenset({'file', 'file_or_directory', 'vita3k_installed_app', 'xenia_target'})


@dataclass(frozen=True)
class EmulatorProvider:
    id: str
    name: str
    platforms: tuple[str, ...]
    executable_names: tuple[str, ...]
    install_candidates: tuple[str, ...]
    config_candidates: tuple[str, ...]
    data_candidates: tuple[str, ...]
    launch_style: str
    launch_flag: tuple[str, ...] = ()
    launch_note: str = ''
    documentation: tuple[str, ...] = ()
    target_rule: str = 'file_or_directory'

    def validate(self):
        if (type(self.id) is not str or not _KEY.fullmatch(self.id)
                or type(self.name) is not str or not self.name.strip()
                or type(self.platforms) is not tuple or not self.platforms
                or any(type(value) is not str or not value.strip() for value in self.platforms)
                or len(set(self.platforms)) != len(self.platforms)
                or type(self.executable_names) is not tuple or not self.executable_names
                or any(type(value) is not str or not value or '/' in value or '\\' in value
                       for value in self.executable_names)
                or type(self.install_candidates) is not tuple
                or any(type(value) is not str or len(value) > 512 for value in self.install_candidates)
                or type(self.config_candidates) is not tuple
                or any(type(value) is not str or len(value) > 512 for value in self.config_candidates)
                or type(self.data_candidates) is not tuple
                or any(type(value) is not str or len(value) > 512 for value in self.data_candidates)
                or type(self.launch_style) is not str or self.launch_style not in _LAUNCH_STYLES
                or type(self.target_rule) is not str or self.target_rule not in _TARGET_RULES
                or type(self.launch_flag) is not tuple
                or any(type(value) is not str or not value.startswith('-') for value in self.launch_flag)
                or (self.launch_style == 'flag' and not self.launch_flag)
                or (self.launch_style != 'flag' and self.launch_flag)
                or type(self.launch_note) is not str or len(self.launch_note) > 1000
                or type(self.documentation) is not tuple
                or any(type(value) is not str or not value.startswith('https://') or len(value) > 2048
                       for value in self.documentation)):
            raise ValueError('Invalid emulator provider capability record.')
        return self


def all_providers():
    """Return the reviewed static provider catalog in stable display order."""
    from koei_editor.shared.emulator_providers.nintendo import PROVIDERS as nintendo
    from koei_editor.shared.emulator_providers.other import PROVIDERS as other
    from koei_editor.shared.emulator_providers.sony import PROVIDERS as sony

    providers = tuple(sony) + tuple(nintendo) + tuple(other)
    if any(type(item) is not EmulatorProvider for item in providers):
        raise ValueError('Emulator provider modules must return contract records.')
    for item in providers:
        item.validate()
    if len({item.id for item in providers}) != len(providers):
        raise ValueError('Emulator provider IDs must be unique.')
    return providers
