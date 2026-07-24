import math
from typing import Annotated
from typing import Any

from pydantic import BeforeValidator

# The tokens HTSJDK's `FormatUtil` writes for non-finite floats. `?` is overloaded: it is
# emitted for both `NaN` and `+Infinity`, so the token alone cannot distinguish them.
NAN_TOKEN = "?"
NEGATIVE_INFINITY_TOKEN = "-?"


def _parse_float(value: Any) -> Any:
    """
    Map Picard's non-finite float tokens to `None`.

    Args:
        value: The raw field value, as read from the metrics file.

    Returns:
        `None` if the value is one of Picard's non-finite tokens, otherwise the value
        unchanged for downstream validation.
    """
    if isinstance(value, str) and value in {NAN_TOKEN, NEGATIVE_INFINITY_TOKEN}:
        return None
    return value


def _parse_log10_p_value(value: Any) -> Any:
    """
    Map Picard's non-finite float tokens to `None`, except `-?`, which is `-Infinity`.

    Args:
        value: The raw field value, as read from the metrics file.

    Returns:
        `-math.inf` for `-?`, `None` for `?`, otherwise the value unchanged for downstream
        validation.
    """
    if isinstance(value, str):
        if value == NEGATIVE_INFINITY_TOKEN:
            return -math.inf
        if value == NAN_TOKEN:
            return None
    return value


def _parse_bool(value: Any) -> Any:
    """
    Parse Picard's `Y`/`N` boolean tokens.

    HTSJDK writes `Y` for true and `N` for false, and on read tests only whether the
    upper-cased first character is `Y`. This mirrors that leniency for `Y…`/`N…` but rejects
    anything else outright rather than coercing it to `False`.

    Args:
        value: The raw field value, as read from the metrics file.

    Returns:
        The parsed boolean, or the value unchanged if it is not a string (e.g. a real `bool`
        supplied when constructing a model in Python).

    Raises:
        ValueError: If the value is a string that starts with neither `Y` nor `N`.
    """
    if isinstance(value, str):
        match value[:1].upper():
            case "Y":
                return True
            case "N":
                return False
            case _:
                raise ValueError(f"Expected a Picard boolean ('Y' or 'N'), got {value!r}")
    return value


PicardFloat = Annotated[float | None, BeforeValidator(_parse_float)]
"""
A Picard float column, where a non-finite value is reported as missing.

Picard writes `?` for both `NaN` and `+Infinity` and `-?` for `-Infinity`; all three become
`None`. `None` is used rather than `math.nan` because `nan` compares unequal to itself, which
breaks model equality, deduplication, and JSON serialization.

Use `PicardLog10PValue` instead for a log10 p-value column, where `-Infinity` is a real value.
"""

PicardLog10PValue = Annotated[float | None, BeforeValidator(_parse_log10_p_value)]
"""
A Picard log10 p-value column, where `-Infinity` is a real value.

Identical to `PicardFloat` except that `-?` becomes `-math.inf` rather than `None`: for a
log10 p-value, `-Infinity` is `log10(p = 0)` — maximally significant, not missing. Unlike
`nan`, `-inf` is equality-safe and round-trips. `?` remains ambiguous and becomes `None`.
"""

PicardBool = Annotated[bool, BeforeValidator(_parse_bool)]
"""
A Picard boolean column, written by HTSJDK as `Y` or `N`.

Only `Y…` and `N…` (any case) are accepted; any other token raises a `ValidationError`. The
strictness is the point: `bool("N")` is `True` in Python, and Pydantic's own coercion would
accept `"true"`/`"1"`/`"0"` — tokens Picard never writes — so a malformed column would parse
silently and wrongly. Annotate the field as `PicardBool | None` for a column that may be blank.
"""
