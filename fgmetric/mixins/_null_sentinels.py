from typing import Any
from typing import ClassVar
from typing import final

from pydantic import BaseModel
from pydantic import model_validator

from fgmetric._typing_extensions import is_optional


# NB: Inheriting from BaseModel is necessary to declare model validators on the mixin, and for the
# class-level initialization in `__pydantic_init_subclass__` to work.
class NullSentinels(BaseModel):
    """
    Treat configured input strings as null on Optional fields.

    When this mixin is added to a model, the `null_sentinels` class variable declares the set of
    input strings that represent null. Any field annotated as `T | None` whose incoming value is
    one of the configured sentinels will be substituted with `None` before downstream field
    validators run.

    The substitution is scoped to Optional fields. Non-Optional fields are not touched, which
    keeps this mixin composable with field-specific handling (e.g., `DelimitedList`'s treatment
    of `list[T]` fields).

    Class Variables:
        null_sentinels: The set of input strings that should be treated as null on Optional
            fields. Defaults to an empty set (no substitution).

    Examples:
        Treat empty strings as null:

        ```python
        class MyMetric(Metric):
            null_sentinels = frozenset({""})
            name: str
            count: int | None

        MyMetric.model_validate({"name": "foo", "count": ""}).count  # -> None
        ```

        Treat multiple sentinels as null:

        ```python
        class MyMetric(Metric):
            null_sentinels = frozenset({"", "NA"})
            count: int | None

        MyMetric.model_validate({"count": "NA"}).count  # -> None
        ```
    """

    null_sentinels: ClassVar[frozenset[str]] = frozenset()
    _optional_fieldnames: ClassVar[set[str]]

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Record the names of Optional-typed fields for use in null-sentinel substitution."""
        super().__pydantic_init_subclass__(**kwargs)
        cls._optional_fieldnames = {
            name for name, info in cls.model_fields.items() if is_optional(info.annotation)
        }

    @final
    @model_validator(mode="before")
    @classmethod
    def _substitute_null_sentinels(cls, data: Any) -> Any:
        """Substitute incoming sentinel strings on Optional fields with `None`."""
        if not cls.null_sentinels:
            return data

        if not isinstance(data, dict):
            return data

        data = dict(data)

        for field in cls._optional_fieldnames:
            if field not in data:
                continue
            value = data[field]
            if isinstance(value, str) and value in cls.null_sentinels:
                data[field] = None

        return data
