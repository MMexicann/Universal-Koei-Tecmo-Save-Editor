"""Immutable, read-only projections of verified opened-save information.

Progress denominators must be supplied by a reviewed game mapping. A field's
storage ceiling or editor limit is never an implicit progression denominator.
No document, backend or write operation is retained by these display objects.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class DashboardMetric:
    id: str
    label: str
    value: str
    field_id: str | None = None
    current: int | float | None = None
    total: int | float | None = None
    unit: str = ''
    note: str = ''

    def __post_init__(self):
        for name in ('id', 'label', 'value', 'unit', 'note'):
            if not isinstance(getattr(self, name), str):
                raise TypeError(f'Dashboard metric {name} must be display text.')
        if self.field_id is not None and not isinstance(self.field_id, str):
            raise TypeError('Dashboard field navigation requires a stable string ID.')

    @property
    def fraction(self):
        """Return a drawable verified fraction, never clamp unusual values."""
        if (isinstance(self.current, bool) or isinstance(self.total, bool)
                or not isinstance(self.current, (int, float))
                or not isinstance(self.total, (int, float))):
            return None
        try:
            if (not math.isfinite(self.current) or not math.isfinite(self.total)
                    or not 0 <= self.current <= self.total or self.total <= 0):
                return None
            return self.current / self.total
        except (OverflowError, ValueError):
            return None


@dataclass(frozen=True)
class DashboardCard:
    id: str
    title: str
    subtitle: str = ''
    metrics: tuple[DashboardMetric, ...] = ()
    section: str = 'Characters'
    search_text: str = ''

    def __post_init__(self):
        object.__setattr__(self, 'metrics', tuple(self.metrics))


@dataclass(frozen=True)
class DashboardSection:
    id: str
    title: str
    cards: tuple[DashboardCard, ...] = ()
    note: str = ''

    def __post_init__(self):
        object.__setattr__(self, 'cards', tuple(self.cards))


@dataclass(frozen=True)
class ProgressionDashboard:
    title: str
    sections: tuple[DashboardSection, ...] = ()
    note: str = ''

    def __post_init__(self):
        object.__setattr__(self, 'sections', tuple(self.sections))
