from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import Field
from pydantic import ValidationError

from fgmetric import Metric
from fgmetric import MetricReader
from fgmetric.converters import BoolTokens
from fgmetric.converters import NullSentinels


@pytest.mark.parametrize("token", ["true", "t", "1", "TRUE", "True", "T"])
def test_default_true_tokens(token: str) -> None:
    """The default true tokens resolve to `True`, case-insensitively."""

    class Model(BoolTokens):
        flag: bool

    assert Model.model_validate({"flag": token}).flag is True


@pytest.mark.parametrize("token", ["false", "f", "0", "FALSE", "False", "F"])
def test_default_false_tokens(token: str) -> None:
    """The default false tokens resolve to `False`, case-insensitively."""

    class Model(BoolTokens):
        flag: bool

    assert Model.model_validate({"flag": token}).flag is False


@pytest.mark.parametrize("token", ["yes", "y", "on", "no", "n", "off"])
def test_rejects_pydantic_extra_tokens(token: str) -> None:
    """Tokens Pydantic would accept but fgpyo rejects raise a ValidationError."""

    class Model(BoolTokens):
        flag: bool

    with pytest.raises(ValidationError):
        Model.model_validate({"flag": token})


@pytest.mark.parametrize("token", ["", "2", "x", "maybe"])
def test_rejects_arbitrary_strings(token: str) -> None:
    """Strings outside the configured token sets raise a ValidationError."""

    class Model(BoolTokens):
        flag: bool

    with pytest.raises(ValidationError):
        Model.model_validate({"flag": token})


def test_optional_bool_resolves_tokens() -> None:
    """A `bool | None` field still resolves configured string tokens."""

    class Model(BoolTokens):
        flag: bool | None

    assert Model.model_validate({"flag": "true"}).flag is True
    assert Model.model_validate({"flag": "false"}).flag is False


def test_optional_bool_passes_through_none() -> None:
    """A real `None` on a `bool | None` field is left untouched by the validator."""

    class Model(BoolTokens):
        flag: bool | None

    assert Model.model_validate({"flag": None}).flag is None


def test_real_bool_input_passes_through() -> None:
    """Actual `bool` values (in-memory construction) are not affected."""

    class Model(BoolTokens):
        flag: bool

    assert Model(flag=True).flag is True
    assert Model(flag=False).flag is False


def test_non_bool_string_fields_untouched() -> None:
    """A `str` field whose value matches a bool token is not coerced."""

    class Model(BoolTokens):
        name: str

    assert Model.model_validate({"name": "true"}).name == "true"


def test_int_field_not_treated_as_bool() -> None:
    """`int` fields are untouched even though `bool` is a subclass of `int`."""

    class Model(BoolTokens):
        count: int

    result = Model.model_validate({"count": "1"})
    assert result.count == 1
    assert type(result.count) is int  # not coerced to bool (a subclass of int)


def test_bool_fieldnames_computed() -> None:
    """Only `bool` / `bool | None` fields are recorded in `_bool_fieldnames`."""

    class Model(BoolTokens):
        flag: bool
        maybe_flag: bool | None
        name: str
        count: int
        mixed: bool | str  # a mixed union is not a pure bool field

    assert Model._bool_fieldnames == {"flag", "maybe_flag"}


def test_bool_list_elements_resolve_tokens() -> None:
    """Each element of a `list[bool]` field is resolved from the configured tokens."""

    class Model(BoolTokens):
        flags: list[bool]

    assert Model.model_validate({"flags": ["true", "f", "1", "0"]}).flags == [
        True,
        False,
        True,
        False,
    ]


@pytest.mark.parametrize("token", ["yes", "y", "on", "no", "n", "off", "x", ""])
def test_bool_list_rejects_pydantic_extra_tokens(token: str) -> None:
    """A list element Pydantic would coerce but fgpyo rejects raises a ValidationError."""

    class Model(BoolTokens):
        flags: list[bool]

    with pytest.raises(ValidationError):
        Model.model_validate({"flags": ["true", token]})


def test_optional_element_bool_list_preserves_none() -> None:
    """A `list[bool | None]` resolves string elements but leaves real `None` elements alone."""

    class Model(BoolTokens):
        flags: list[bool | None]

    assert Model.model_validate({"flags": ["true", None, "false"]}).flags == [True, None, False]


def test_real_bool_list_input_passes_through() -> None:
    """Actual `bool` elements (in-memory construction) are not affected."""

    class Model(BoolTokens):
        flags: list[bool]

    assert Model(flags=[True, False]).flags == [True, False]


def test_bool_list_fieldnames_computed() -> None:
    """Only list fields with `bool` / `bool | None` elements are recorded as bool list fields."""

    class Model(BoolTokens):
        flags: list[bool]
        maybe_flags: list[bool | None]
        opt_flags: list[bool] | None
        tags: list[int]
        flag: bool

    assert Model._bool_list_fieldnames == {"flags", "maybe_flags", "opt_flags"}
    assert Model._bool_fieldnames == {"flag"}


def test_metric_bool_list_is_strict() -> None:
    """A `list[bool]` column on a `Metric` rejects the same tokens a scalar `bool` column does."""

    class FlagMetric(Metric):
        flags: list[bool]

    # The strict tokens resolve, splitting on the collection delimiter first.
    assert FlagMetric.model_validate({"flags": "true,false,1,0"}).flags == [
        True,
        False,
        True,
        False,
    ]
    # Tokens Pydantic would coerce are rejected, matching scalar `bool` behavior.
    with pytest.raises(ValidationError):
        FlagMetric.model_validate({"flags": "yes,on,no"})


def test_metric_optional_element_bool_list() -> None:
    """Empty cells in a `list[bool | None]` column become `None`; the rest are tokenized."""

    class FlagMetric(Metric):
        flags: list[bool | None]

    assert FlagMetric.model_validate({"flags": "1,,0"}).flags == [True, None, False]


def test_custom_tokens() -> None:
    """Custom token sets replace the defaults."""

    class Model(BoolTokens):
        true_tokens: ClassVar[frozenset[str]] = frozenset({"yes", "y"})
        false_tokens: ClassVar[frozenset[str]] = frozenset({"no", "n"})

        flag: bool

    assert Model.model_validate({"flag": "yes"}).flag is True
    assert Model.model_validate({"flag": "n"}).flag is False
    # The defaults are no longer accepted once overridden.
    with pytest.raises(ValidationError):
        Model.model_validate({"flag": "true"})


def test_custom_tokens_matched_case_insensitively() -> None:
    """Tokens configured in mixed case are still matched case-insensitively."""

    class Model(BoolTokens):
        true_tokens: ClassVar[frozenset[str]] = frozenset({"YES"})
        false_tokens: ClassVar[frozenset[str]] = frozenset({"NO"})

        flag: bool

    assert Model.model_validate({"flag": "yes"}).flag is True
    assert Model.model_validate({"flag": "no"}).flag is False


def test_aliased_bool_field_is_resolved() -> None:
    """A bool field supplied under its alias is resolved from tokens."""

    class Model(BoolTokens):
        flag: bool = Field(alias="Flag")

    assert Model.model_validate({"Flag": "1"}).flag is True


def test_subclass_can_override_tokens() -> None:
    """A subclass may override the token sets, leaving the parent unaffected."""

    class Parent(BoolTokens):
        flag: bool

    class Child(Parent):
        true_tokens: ClassVar[frozenset[str]] = frozenset({"yes"})
        false_tokens: ClassVar[frozenset[str]] = frozenset({"no"})

    assert Parent.model_validate({"flag": "true"}).flag is True
    assert Child.model_validate({"flag": "yes"}).flag is True
    with pytest.raises(ValidationError):
        Child.model_validate({"flag": "true"})


def test_overlapping_tokens_rejected_at_class_definition() -> None:
    """Declaring a token in both `true_tokens` and `false_tokens` is an error."""
    with pytest.raises(ValueError, match="disjoint"):

        class Model(BoolTokens):
            true_tokens: ClassVar[frozenset[str]] = frozenset({"1", "t"})
            false_tokens: ClassVar[frozenset[str]] = frozenset({"0", "t"})

            flag: bool


def test_overlap_is_detected_case_insensitively() -> None:
    """Overlap detection case-folds tokens, so `T` and `t` collide."""
    with pytest.raises(ValueError, match="disjoint"):

        class Model(BoolTokens):
            true_tokens: ClassVar[frozenset[str]] = frozenset({"T"})
            false_tokens: ClassVar[frozenset[str]] = frozenset({"t"})

            flag: bool


def test_metric_governs_bool_parsing_by_default(tmp_path: Path) -> None:
    """`Metric` applies BoolTokens by default, governing bool parsing on the read path."""

    class FlagMetric(Metric):
        name: str
        flag: bool

    fpath = tmp_path / "metrics.txt"
    with fpath.open("w") as fout:
        fout.write("name\tflag\n")
        fout.write("ok\t1\n")
        fout.write("nope\tyes\n")  # rejected by the default tokens

    with MetricReader.open(FlagMetric, fpath) as reader:
        rows = iter(reader)
        assert next(rows).flag is True
        with pytest.raises(ValidationError):
            next(rows)


def test_metric_rejects_pydantic_tokens_by_default() -> None:
    """A plain `Metric` rejects tokens Pydantic would accept (e.g. `yes`), by default."""

    class FlagMetric(Metric):
        flag: bool

    assert FlagMetric.model_validate({"flag": "true"}).flag is True
    with pytest.raises(ValidationError):
        FlagMetric.model_validate({"flag": "yes"})


def test_interaction_with_null_sentinels() -> None:
    """With `""` a null sentinel, an empty `bool | None` cell becomes None, not an error."""

    class FlagMetric(Metric):
        null_sentinels: ClassVar[frozenset[str]] = frozenset({""})

        flag: bool | None

    # Null substitution runs first, so "" -> None before BoolTokens sees it.
    assert FlagMetric.model_validate({"flag": ""}).flag is None
    # Non-empty tokens still resolve through BoolTokens.
    assert FlagMetric.model_validate({"flag": "0"}).flag is False


def test_empty_bool_cell_rejected_without_sentinel() -> None:
    """Without a null sentinel, an empty `bool` cell is rejected as an invalid token."""

    class Model(BoolTokens, NullSentinels):
        flag: bool

    with pytest.raises(ValidationError):
        Model.model_validate({"flag": ""})
