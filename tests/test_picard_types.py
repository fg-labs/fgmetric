import math

import pytest
from pydantic import BaseModel
from pydantic import ValidationError

from fgmetric.picard import PicardBool
from fgmetric.picard import PicardFloat
from fgmetric.picard import PicardLog10PValue


def test_picard_float_parses_a_finite_value() -> None:
    """An ordinary numeric token parses as a float."""

    class Model(BaseModel):
        value: PicardFloat

    assert Model.model_validate({"value": "2366152.0"}).value == 2366152.0


def test_picard_float_maps_question_mark_to_none() -> None:
    """Picard's `?` (NaN or +Infinity) is not a usable value, so it becomes None."""

    class Model(BaseModel):
        value: PicardFloat

    assert Model.model_validate({"value": "?"}).value is None


def test_picard_float_maps_negative_question_mark_to_none() -> None:
    """Picard's `-?` (-Infinity) is also not a usable value on a plain float field."""

    class Model(BaseModel):
        value: PicardFloat

    assert Model.model_validate({"value": "-?"}).value is None


def test_log10_p_value_parses_a_finite_value() -> None:
    """An ordinary numeric token parses as a float, as it does for `PicardFloat`."""

    class Model(BaseModel):
        value: PicardLog10PValue

    assert Model.model_validate({"value": "-3.5"}).value == -3.5


def test_log10_p_value_maps_negative_question_mark_to_negative_infinity() -> None:
    """`-?` is `log10(p=0)`, a real and maximally significant value rather than missing."""

    class Model(BaseModel):
        value: PicardLog10PValue

    value = Model.model_validate({"value": "-?"}).value
    assert value == -math.inf


def test_log10_p_value_maps_question_mark_to_none() -> None:
    """`?` is still ambiguous (NaN or +Infinity), so it remains missing."""

    class Model(BaseModel):
        value: PicardLog10PValue

    assert Model.model_validate({"value": "?"}).value is None


@pytest.mark.parametrize("token", ["Y", "y", "Yes"])
def test_picard_bool_accepts_yes_tokens(token: str) -> None:
    """HTSJDK writes `Y` for true and tests only the first character, case-insensitively."""

    class Model(BaseModel):
        value: PicardBool

    assert Model.model_validate({"value": token}).value is True


@pytest.mark.parametrize("token", ["N", "n", "No"])
def test_picard_bool_accepts_no_tokens(token: str) -> None:
    """HTSJDK writes `N` for false and tests only the first character, case-insensitively."""

    class Model(BaseModel):
        value: PicardBool

    assert Model.model_validate({"value": token}).value is False


@pytest.mark.parametrize("token", ["", "1", "0", "true", "false", "maybe"])
def test_picard_bool_rejects_tokens_that_are_not_yes_or_no(token: str) -> None:
    """
    A token that is neither `Y…` nor `N…` raises rather than silently coercing.

    This is the failure mode the type exists to prevent: `bool("N")` is `True` in Python, and
    Pydantic would happily read `"true"`/`"1"` as booleans that Picard never writes.
    """

    class Model(BaseModel):
        value: PicardBool

    with pytest.raises(ValidationError):
        Model.model_validate({"value": token})


def test_picard_bool_passes_through_real_booleans() -> None:
    """A model constructed in Python, rather than parsed from a file, still validates."""

    class Model(BaseModel):
        value: PicardBool

    assert Model(value=True).value is True
