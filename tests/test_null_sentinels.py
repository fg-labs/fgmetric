from typing import ClassVar

import pytest
from pydantic import ConfigDict
from pydantic import ValidationError

from fgmetric.mixins import NullSentinels


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
