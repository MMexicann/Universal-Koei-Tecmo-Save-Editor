"""Platform-contract double for semantic Vault/Profile tests on non-Windows.

This deliberately does NOT qualify native directory-creation race safety.
Windows tests run the real held-handle creator. Other hosts emulate its
postcondition so format, storage, CLI and real-Tk workflow assertions still run;
the separate owned-directory safety module exercises the actual fail-closed
production dispatch on those hosts. Never import this helper in production.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import stat
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import playthrough_profiles, save_vault


@contextmanager
def owned_directory_contract(directory, name, expected_identity, *, remove_on_close=False):
    """Emulate an owned-directory scope; this is not a POSIX ownership proof."""
    directory = Path(directory)
    if (type(name) is not str or not name or name in ('.', '..')
            or Path(name).name != name or '/' in name or '\\' in name):
        raise SaveError('The contract fixture needs one ordinary child name.')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    parent_fd = os.open(directory, flags)
    child_fd = None
    created = None
    target = directory / name
    try:
        parent = os.fstat(parent_fd)
        if (parent.st_dev, parent.st_ino) != expected_identity:
            raise SaveError('The private output directory changed identity.')
        os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        child_fd = os.open(name, flags, dir_fd=parent_fd)
        created = os.fstat(child_fd)
        if not stat.S_ISDIR(created.st_mode):
            raise SaveError('The contract fixture did not create a directory.')
        yield target, created
    finally:
        try:
            if remove_on_close and created is not None:
                try:
                    current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                    if (current.st_dev, current.st_ino) == (created.st_dev, created.st_ino):
                        os.rmdir(name, dir_fd=parent_fd)
                except OSError:
                    pass
        finally:
            if child_fd is not None:
                os.close(child_fd)
            os.close(parent_fd)


def install_owned_directory_contract(test_case):
    """Use only this explicit primitive double; leave Windows natively tested."""
    if os.name == 'nt':
        return
    for module in (save_vault, playthrough_profiles):
        replacement = patch.object(module, 'new_directory_child_bound',
                                   owned_directory_contract, create=True)
        replacement.start()
        test_case.addCleanup(replacement.stop)


def attempt_namespace_change(test_case, operation):
    """A real Windows held handle may deny the attack before service rechecks."""
    try:
        operation()
        return True
    except OSError as error:
        test_case.assertEqual(os.name, 'nt')
        test_case.assertIn(getattr(error, 'winerror', None), (5, 32, 33))
        return False
