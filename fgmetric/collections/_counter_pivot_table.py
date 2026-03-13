from enum import StrEnum
from typing import Any
from typing import ClassVar
from typing import final
from typing import get_args

from pydantic import BaseModel
from pydantic import SerializationInfo
from pydantic import SerializerFunctionWrapHandler
from pydantic import model_serializer
from pydantic import model_validator
from pydantic.fields import FieldInfo

from fgmetric._typing_extensions import is_counter
from fgmetric._typing_extensions import is_optional


class CounterPivotTable(BaseModel):
    """
    A mixin to support pivot table representations of Counters.

    When this mixin is added to `Metric`, a field may be annotated as `Counter[T]`, and will be
    handled specially.

    This mixin permits only *one* field to be annotated as `Counter[T]`, and `T` must be a `StrEnum`
    type.

    During validation, fields in the input which match members of the enum type will be collected
    and included in a `Counter` on the validated model. If any members of the enum type are not
    found as fields in the input, they will be included with a count of 0 in the collected
    `Counter`.

    During serialization, the values of the associated `Counter` will be pivoted out, with one field
    in the output for each member of the enum type.

    **IMPORTANT:** As with all Python mixins, this class must precede `Metric` when declaring a
    *metric's parent classes, in order for its methods to take precedence over `Metric`'s defaults.
    """

    _counter_fieldname: ClassVar[str | None]
    _counter_enum: ClassVar[type[StrEnum] | None]

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)

        cls._counter_fieldname = cls._get_counter_fieldname()
        cls._counter_enum = cls._get_counter_enum()

    @final
    @classmethod
    def _get_counter_fieldname(cls) -> str | None:
        """
        Get and validate the name of a Counter field, if one is defined.

        Models using this mixin may define at most one Counter.

        Returns:
            The name of the single field annotated as `Counter[T]`.
            `None` if no fields are annotated as a `Counter`.

        Raises:
            TypeError: If the user-specified model includes more than one field annotated as
                `Counter[T]`.
        """
        counter_fieldnames = [
            name for name, info in cls.model_fields.items() if is_counter(info.annotation)
        ]

        if len(counter_fieldnames) > 1:
            raise TypeError(
                "Only one Counter per model is currently supported. "
                f"Found multiple fields with Counter types: {', '.join(counter_fieldnames)}"
            )

        counter_fieldname: str | None = counter_fieldnames[0] if counter_fieldnames else None

        if counter_fieldname:
            counter_field_info: FieldInfo = cls.model_fields[counter_fieldname]
            if is_optional(counter_field_info.annotation):
                raise TypeError(f"Optional Counters are not supported: {counter_fieldname}")

        return counter_fieldname

    @final
    @classmethod
    def _get_counter_enum(cls) -> type[StrEnum] | None:  # noqa: C901
        """
        Get and validate the enum type parameter of a Counter field, if one is defined.

        Counter pivot tables are only supported for Counters of StrEnum.

        Returns:
            The type parameter of the single field annotated as `Counter[T]`.
            `None` if no fields are annotated as a `Counter`.

        Raises:
            TypeError: If the user-specified model includes a Counter field with a type parameter
                that is not a subclass of `StrEnum`.
        """
        if cls._counter_fieldname is None:
            # No counter fields -> short-circuit
            return None

        info: FieldInfo = cls.model_fields[cls._counter_fieldname]

        args = get_args(info.annotation)
        if len(args) == 1 and issubclass(args[0], StrEnum):
            enum_cls: type[StrEnum] = args[0]
        else:
            raise TypeError(
                f"Counter fields must have a StrEnum type parameter: {cls._counter_fieldname}"
            )

        return enum_cls

    @final
    @model_validator(mode="before")
    @classmethod
    def _collect_counter_values(cls, data: Any) -> Any:  # noqa: C901
        """Roll up Counters."""
        if not isinstance(data, dict):
            # Short circuit if we don't have a dictionary
            return data

        # Copy to avoid mutating caller's dict
        data = dict(data)

        if cls._counter_fieldname is None:
            # Short circuit if we don't have a Counter field
            return data

        if cls._counter_fieldname in data:
            # Short circuit if a field with our Counter's fieldname already exists.
            # Either it's a dict representation of the Counter, and pydantic will coerce it to
            # Counter for us, or it's something else, and pydantic will reject it for us.
            return data

        # Initialize all members of the enum to zero, in case any members are absent from the input.
        assert cls._counter_enum is not None  # this is not None iff counter_fieldname is not None
        counts = {member: 0 for member in list(cls._counter_enum)}

        # Add counts found in the input. Any fields that correspond to an enum member are removed
        # from `data`
        keys_to_pop = []
        for key, value in data.items():
            if key in cls.model_fields:
                # Skip fields that are modeled explicitly
                continue

            try:
                member = cls._counter_enum(key)
                counts[member] = value
                keys_to_pop.append(key)
            except ValueError:
                # Let pydantic handle any other validation issues, or omit unmodeled fields
                continue

        for key in keys_to_pop:
            data.pop(key)

        data[cls._counter_fieldname] = counts

        return data

    @final
    @model_serializer(mode="wrap")
    def _pivot_counter_values(
        self,
        nxt: SerializerFunctionWrapHandler,  # noqa: ARG002
        info: SerializationInfo,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Pivot the Counter values out wide."""
        # Call the default serializer
        data: dict[str, Any] = nxt(self)

        if self._counter_fieldname is None:
            # Short circuit if we don't have a Counter field
            return data

        # Replace the counter field with keys for each of its enum's members
        counts = data.pop(self._counter_fieldname)
        for key, count in counts.items():
            column_name = key if isinstance(key, str) else key.value
            data[column_name] = count

        return data
