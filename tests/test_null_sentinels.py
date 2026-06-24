from typing import ClassVar

import pytest
from pydantic import AliasChoices
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationError

from fgmetric import Metric
from fgmetric.converters import NullSentinels


def test_default_does_not_substitute() -> None:
    """Default `null_sentinels = frozenset()` means no substitution happens."""

    class Model(NullSentinels):
        name: str
        value: str | None

    result = Model.model_validate({"name": "foo", "value": ""})
    assert result.value == ""


def test_empty_string_treated_as_null() -> None:
    """Empty strings become None on Optional fields when `""` is a configured sentinel."""

    class Model(NullSentinels):
        null_sentinels: ClassVar[frozenset[str]] = frozenset({""})

        name: str
        value: int | None

    result = Model.model_validate({"name": "foo", "value": ""})
    assert result.value is None


def test_aliased_optional_field_is_substituted() -> None:
    """An Optional field supplied under its alias is recognized for substitution."""

    class Model(NullSentinels):
        null_sentinels: ClassVar[frozenset[str]] = frozenset({""})

        value: int | None = Field(alias="Value")

    # Input is keyed by the alias, as a delimited-file row would be.
    result = Model.model_validate({"Value": ""})
    assert result.value is None


def test_alias_choices_optional_field_is_substituted() -> None:
    """An Optional field reachable via `AliasChoices` is substituted under any of its choices."""

    class Model(NullSentinels):
        null_sentinels: ClassVar[frozenset[str]] = frozenset({""})

        value: int | None = Field(validation_alias=AliasChoices("v", "Value"))

    assert Model.model_validate({"v": ""}).value is None
    assert Model.model_validate({"Value": ""}).value is None


def test_non_optional_fields_are_not_substituted() -> None:
    """Non-Optional fields are not touched even when their input matches a sentinel."""

    class Model(NullSentinels):
        null_sentinels: ClassVar[frozenset[str]] = frozenset({"NA"})

        name: str
        status: str

    result = Model.model_validate({"name": "foo", "status": "NA"})
    assert result.status == "NA"


def test_arbitrary_sentinels_are_supported() -> None:
    """Sentinels other than `""` work, provided the field is Optional."""

    class Model(NullSentinels):
        null_sentinels: ClassVar[frozenset[str]] = frozenset({"NA"})

        status: str | None

    result = Model.model_validate({"status": "NA"})
    assert result.status is None


def test_multiple_sentinels() -> None:
    """Multiple strings can be configured as null sentinels."""

    class Model(NullSentinels):
        null_sentinels: ClassVar[frozenset[str]] = frozenset({"", "NA", "None"})

        value: int | None

    assert Model.model_validate({"value": ""}).value is None
    assert Model.model_validate({"value": "NA"}).value is None
    assert Model.model_validate({"value": "None"}).value is None


def test_non_string_inputs_are_untouched() -> None:
    """Non-string values are never substituted even if they would equal a sentinel."""

    class Model(NullSentinels):
        null_sentinels: ClassVar[frozenset[str]] = frozenset({""})

        value: int | None

    result = Model.model_validate({"value": 0})
    assert result.value == 0


def test_extra_fields_in_input_are_ignored() -> None:
    """Keys in the input dict that aren't declared fields are not touched by the mixin."""

    class Model(NullSentinels):
        model_config = ConfigDict(extra="allow")
        null_sentinels: ClassVar[frozenset[str]] = frozenset({""})

        name: str

    result = Model.model_validate({"name": "foo", "extra_field": ""})
    assert result.model_extra == {"extra_field": ""}


def test_subclass_can_opt_out() -> None:
    """A subclass can override `null_sentinels` to an empty frozenset to disable substitution."""

    class Parent(NullSentinels):
        null_sentinels: ClassVar[frozenset[str]] = frozenset({""})

        value: str | None

    class Child(Parent):
        null_sentinels: ClassVar[frozenset[str]] = frozenset()

    assert Parent.model_validate({"value": ""}).value is None
    assert Child.model_validate({"value": ""}).value == ""


def test_sentinel_on_required_field_still_raises() -> None:
    """A required field whose value matches a sentinel is not substituted, so pydantic raises."""

    class Model(NullSentinels):
        null_sentinels: ClassVar[frozenset[str]] = frozenset({""})

        value: int

    with pytest.raises(ValidationError):
        Model.model_validate({"value": ""})


def test_optional_list_empties_to_none_but_required_list_empties_to_empty_list() -> None:
    """
    Null-sentinel substitution and `DelimitedList` splitting compose correctly on `""`.

    `_substitute_null_sentinels` (model `mode="before"`) runs before `_split_lists` (a field
    validator), so an empty string in an Optional list field becomes `None`, while an empty
    string in a required list field is left untouched and `_split_lists` turns it into `[]`.
    """

    class FakeMetric(Metric):
        required: list[int]
        optional: list[int] | None

    result = FakeMetric.model_validate({"required": "", "optional": ""})
    assert result.required == []  # not Optional -> untouched -> split to []
    assert result.optional is None  # Optional -> "" substituted to None before splitting

    # Non-empty values still parse as delimited lists in both cases.
    populated = FakeMetric.model_validate({"required": "1,2", "optional": "3,4"})
    assert populated.required == [1, 2]
    assert populated.optional == [3, 4]
