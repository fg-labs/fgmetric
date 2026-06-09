from abc import ABC
from typing import Any

from pydantic import BaseModel
from pydantic import model_validator

from fgmetric._typing_extensions import is_optional
from fgmetric.collections import CounterPivotTable
from fgmetric.collections import DelimitedList


class Metric(
    DelimitedList,
    CounterPivotTable,
    BaseModel,
    ABC,
):
    """
    Abstract base class for defining structured "metric" data models.

    This class combines Pydantic's `BaseModel` with `ABC` to provide a foundation for creating
    type-safe metric classes that can be easily read from and written to delimited text files (e.g.,
    TSV, CSV). It leverages Pydantic's automatic validation and type conversion while providing
    convenient class methods for parsing metrics from files.

    Metrics are delimited files containing a header and zero or more rows for metric values. When
    using a `Metric` to read a delimited file, the `Metric`'s fields correspond to the columns and
    header of the file. Subclasses should define their fields using Pydantic field annotations.

    `Metric` includes the following custom serialization/deserialization behaviors:
    1. **Empty fields as None.** Any empty field in a file will be represented as `None` on the
       deserialized model.
    2. **Delimited lists.** Any field typed as `list[T]` will be parsed from and serialized to a
       delimited string. The list delimiter may be controlled by the `collection_delimiter` class
       variable.

    Class Variables:
        collection_delimiter: A single-character delimiter used to split and join `list` fields
            during serialization/deserialization.

    Example:
        ```python
        from fgmetric import MetricReader

        class AlignmentMetric(Metric):
            read_name: str
            mapping_quality: int
            is_duplicate: bool = False

        # Read metrics from a TSV file
        with MetricReader.open(AlignmentMetric, "metrics.txt") as reader:
            for metric in reader:
                print(metric.read_name, metric.mapping_quality)
        ```
    """

    # NB: "Before" validators (mode="before") run before field validators such as
    # `DelimitedList._split_lists()`. Empty strings in Optional fields will always be converted to
    # `None` before any field validators.
    # For example, for delimited list parsing:
    #   - When a field is defined as `list[T] | None`, this converts "" → None before _split_lists
    #     sees it.
    #   - When a field is defined as `list[T]`, "" passes through unchanged, then _split_lists
    #     converts "" → [].
    @model_validator(mode="before")
    @classmethod
    def _empty_field_to_none(cls, data: Any) -> Any:
        """Treat any empty fields as None if the field is typed as Optional."""
        if not isinstance(data, dict):
            # short circuit
            return data

        data = dict(data)

        for field, value in data.items():
            info = cls.model_fields.get(field)
            if info is None:
                # Skip fields that aren't defined on the model - let the validation handle it
                continue

            if value == "" and is_optional(info.annotation):
                data[field] = None

        return data

    @classmethod
    def _header_fieldnames(cls) -> list[str]:
        """
        Return the fieldnames to use as a header row when writing metrics to a file.

        This method is used by `MetricWriter` to construct the underlying `csv.DictWriter`.
        It returns the fieldnames that will appear in serialized output, which may differ from
        the model's field names when aliases are used.

        Note:
            This method is deliberately not used during reading/validation; see
            `MetricReader` for the headerless-input path.

        Returns:
            The list of fieldnames to use as the header row.

        Example:
            Given a model with ``name: str`` and ``counts: Counter[Color]`` where
            ``Color`` has members ``RED``, ``GREEN``, ``BLUE``:

            ```python
            cls._header_fieldnames()
            # -> ["name", "red", "green", "blue"]
            ```
        """
        # TODO: support returning the set of fields that would be constructed if the class has a
        # custom model serializer

        # Resolve each field to the key it serializes under (its alias, when one is set), so the
        # header matches the keys produced by `model_dump(by_alias=True)`. The Counter field, if
        # present, is dropped here and replaced by its pivoted enum-member columns below.
        fieldnames: list[str]
        fieldnames = [
            info.serialization_alias or info.alias or name
            for name, info in cls.model_fields.items()
            if name != cls._counter_fieldname
        ]

        if cls._counter_fieldname is None:
            # Short circuit if we don't have a Counter field
            return fieldnames

        # Add the enum members
        assert cls._counter_enum is not None  # type narrowing
        fieldnames += [member.value for member in cls._counter_enum]

        return fieldnames
