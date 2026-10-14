"""Verified bodyguard growth rules; no save I/O or GUI dependencies.

The six saved levels are HP, Attack, Defense, Count, Bow/Moveset and AI.
Only HP, Attack, Defense and Bow/Moveset consume the shared growth budget.
Derived values below are growth base values. Equipment, formation/order,
bodyguard type and battle modifiers are intentionally excluded.
Experimental Merit uses the same shipped gates and budget. Growth levels remain
bounded table indexes, including Count, Bow/Moveset and AI.
"""
from koei_editor.resources import read_json
from koei_editor.shared.experimental_limits import SIGNED_INT32_MAX, within_numeric_limits

from bisect import bisect_right


_DATA = read_json('bodyguard_growth.json')
MERIT_CAP = _DATA["merit_cap"]
MERIT_STORAGE_MAXIMUM = SIGNED_INT32_MAX
LEVEL_NAMES = tuple(slot["label"] for slot in _DATA["slots"])
LEVEL_CAPS = tuple(slot["maximum"] for slot in _DATA["slots"])
ALLOCATED_SLOTS = tuple(_DATA["allocated_slots"])
BUDGET_THRESHOLDS = tuple(_DATA["budget_thresholds"])
PRESET_NAMES = {"balanced": "Balanced", "life": "Favor Life", "attack": "Favor Attack", "defense": "Favor Defense"}


def merit_numeric_limits() -> tuple[int, int, int]:
    """Minimum, supported maximum and signed IntProperty storage ceiling."""
    return 0, MERIT_CAP, MERIT_STORAGE_MAXIMUM


def _merit(merit: int) -> int:
    if not within_numeric_limits(merit, 0, MERIT_CAP, storage_maximum=MERIT_STORAGE_MAXIMUM):
        raise ValueError(f"Bodyguard Merit must be an integer from 0 to {MERIT_CAP:,}.")
    return merit


def budget(merit: int) -> int:
    """Shared allocation points earned at this Merit, from the shipped table."""
    return bisect_right(BUDGET_THRESHOLDS, _merit(merit)) - 1


def earned_caps(merit: int) -> tuple[int, ...]:
    """Level limits including the separate Merit gates for Count, Bow and AI."""
    _merit(merit)
    caps = list(LEVEL_CAPS)
    for index in (3, 4, 5):
        caps[index] = bisect_right(_DATA["slots"][index]["merit_thresholds"], merit) - 1
    return tuple(caps)


def _levels(levels) -> tuple[int, ...]:
    if not isinstance(levels, (list, tuple)) or len(levels) != 6:
        raise ValueError("Bodyguard growth must contain exactly six levels.")
    result = tuple(levels)
    for index, (value, cap) in enumerate(zip(result, LEVEL_CAPS)):
        if type(value) is not int or not 0 <= value <= cap:
            raise ValueError(f"{LEVEL_NAMES[index]} growth must be an integer from 0 to {cap}.")
    return result


def spent(levels) -> int:
    """Points consumed by the four manually allocated growth levels."""
    values = _levels(levels)
    return sum(values[index] for index in ALLOCATED_SLOTS)


def validate_growth(merit: int, levels) -> tuple[int, ...]:
    """Validate the final Merit/level combination; return immutable levels.

    Existing underdeveloped Count/AI levels are accepted. UI presets can bring
    those automatically advancing levels up to their earned ranks.
    """
    values = _levels(levels)
    caps = earned_caps(merit)
    for index, (value, cap) in enumerate(zip(values, caps)):
        if value > cap:
            raise ValueError(f"{LEVEL_NAMES[index]} growth {value} requires more Bodyguard Merit (current limit {cap}).")
    used = spent(values)
    available = budget(merit)
    if used > available:
        raise ValueError(f"Bodyguard growth uses {used} points, but {merit:,} Merit permits only {available}.")
    return values


def validate_saved_growth(merit: int, levels) -> tuple[int, ...]:
    """Check a saved profile without treating earning gates as load invariants.

    The native automatic growth updater gates allocations by current Merit.
    A real supplied save has Bow/Moveset above that automatic gate. Its cause
    is not assumed: reading or preserving it must not reallocate saved levels.
    Newly authored allocations still use conservative ``validate_growth``.
    """
    if type(merit) is not int or not 0 <= merit <= MERIT_STORAGE_MAXIMUM:
        raise ValueError("Saved Bodyguard Merit must fit its nonnegative IntProperty.")
    return _levels(levels)


def advance_automatic_levels(merit: int, levels) -> list[int]:
    """Advance earned Count/AI while preserving historical allocations.

    Used for Merit-only increases. Existing higher automatic levels are also
    kept: this helper never demotes previously saved growth.
    """
    values = list(validate_saved_growth(merit, levels))
    caps = earned_caps(merit)
    for index in (3, 5):
        values[index] = max(values[index], caps[index])
    return values


def derive_stats(levels) -> dict[str, int]:
    """Return proven growth base values, without equipment/context modifiers.

    Bow is a percentage multiplier, and movement/jump use table units rather
    than Unreal's converted world units. AI limit is the native behavior-table
    selection limit; it is not an attack/defense stat.
    """
    hp, attack, defense, count, style, ai = _levels(levels)
    basic = _DATA["level_rows"]
    member = _DATA["member_rows"]
    life = min(400, basic[hp]["HP_Special"] + member[style]["HP_Add"])
    return {
        "base_hp": life,
        "base_musou": life,
        "base_attack": min(250, basic[attack]["Attack"]),
        "base_defense": min(250, basic[defense]["Defence"]),
        "member_count": member[count]["MemberNum"],
        "jump": basic[attack]["Jump"],
        "move": basic[defense]["Move"],
        "shift_move": basic[defense]["ShiftMove"],
        "bow_percent": member[style]["Bow"],
        "motion_level": member[style]["MotionLv"],
        "ai_limit": member[ai]["AlgoLimit"],
    }


def automatic_levels(merit: int, levels) -> list[int]:
    """Set automatic Count/AI to their earned ranks; preserve four allocations."""
    values = list(_levels(levels))
    caps = earned_caps(merit)
    values[3], values[5] = caps[3], caps[5]
    validate_growth(merit, values)
    return values


def safe_preset(merit: int = MERIT_CAP, mode: str = "balanced") -> list[int]:
    """Spend the legal budget with max earned Bow/Moveset and Count/AI.

    These are editor allocation choices, not claims of one optimal build.
    At 99,999 Merit the balanced preset is [8, 7, 7, 3, 3, 3].
    """
    if mode not in PRESET_NAMES:
        raise ValueError("Unknown bodyguard allocation preset.")
    caps = earned_caps(merit)
    levels = [0, 0, 0, caps[3], min(caps[4], budget(merit)), caps[5]]
    remaining = budget(merit) - levels[4]
    preferred = {"life": 0, "attack": 1, "defense": 2}.get(mode)
    if preferred is not None:
        levels[preferred] = min(caps[preferred], remaining)
        remaining -= levels[preferred]
    order = [index for index in (0, 1, 2) if index != preferred]
    while remaining:
        progressed = False
        for index in order:
            if remaining and levels[index] < caps[index]:
                levels[index] += 1
                remaining -= 1
                progressed = True
        if not progressed:
            raise ValueError("Growth table budget exceeds supported level caps.")
    validate_growth(merit, levels)
    return levels
