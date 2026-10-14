"""Scoped opt-in numeric limits, independent from native format validation.

Only explicitly described existing numeric fields can expand their supported
range. Native widths, exact encodings, identities and dependencies stay with
the game backend. The context never persists or changes another editor session.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

from koei_editor.games.dw3.models import SaveError


_EXPERIMENTAL = ContextVar('experimental_numeric_limits', default=False)
SIGNED_INT32_MAX = (1 << 31) - 1
UNSIGNED_INT32_MAX = (1 << 32) - 1
FLOAT32_EXACT_INTEGER_MAX = 1 << 24
EXPERIMENTAL_WARNING = (
    'Experimental editing allows existing numeric values above their supported limits. '
    'These values can break the save file or game, and the game may reset or clamp them. '
    'Keep your original save and backups. File encoding limits and required save structure '
    'still apply. Max buttons continue to use supported limits.\n\n'
    'Enable experimental editing for this session?'
)


def experimental_enabled():
    return _EXPERIMENTAL.get()


@contextmanager
def experimental_limits(enabled=True):
    if type(enabled) is not bool:
        raise SaveError('Experimental editing requires an explicit boolean option.')
    token = _EXPERIMENTAL.set(enabled)
    try:
        yield
    finally:
        _EXPERIMENTAL.reset(token)


def within_numeric_limits(value, minimum, supported_maximum, *, storage_maximum=None):
    """Check a whole number without expanding a minimum or guessing storage.

    A None storage ceiling keeps the normal range even in experimental mode.
    This permits numeric base classes to opt out for enumerations/references.
    """
    if type(value) is not int or type(minimum) is not int or type(supported_maximum) is not int:
        return False
    maximum = supported_maximum
    if storage_maximum is not None:
        if type(storage_maximum) is not int or storage_maximum < minimum:
            return False
        maximum = storage_maximum if experimental_enabled() else min(maximum, storage_maximum)
    return minimum <= value <= maximum


def experimental_operation(method):
    """Keep one bound adapter's explicit mode scoped to a complete operation."""
    @wraps(method)
    def scoped(self, *args, **kwargs):
        with experimental_limits(getattr(self, 'experimental', False)):
            return method(self, *args, **kwargs)
    return scoped


def experimental_maximum(field):
    """Return only a backend-declared exact numeric ceiling; never infer it."""
    if getattr(field, 'kind', 'int') not in ('int', 'integer'):
        return None
    maximum = getattr(field, 'experimental_maximum', None)
    return maximum if type(maximum) is int and maximum >= getattr(field, 'minimum', 0) else None


def above_supported(field, value):
    return (type(value) is int and type(getattr(field, 'maximum', None)) is int
            and value > field.maximum)
