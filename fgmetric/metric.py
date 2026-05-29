from abc import ABC
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from typing import Iterator
from typing import Self

from pydantic import BaseModel
from pydantic import model_validator

from fgmetric._typing_extensions import is_optional
from fgmetric.collections import CounterPivotTable
from fgmetric.collections import DelimitedList
from fgmetric.metric_reader import MetricReader


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
        class AlignmentMetric(Metric):
            read_name: str
            mapping_quality: int
            is_duplicate: bool = False

        # Read metrics from a TSV file
        for metric in AlignmentMetric.read(Path("metrics.txt")):
            print(metric.read_name, metric.mapping_quality)
        ```
    """

    @classmethod
    def read(
        cls,
        path: Path,
        delimiter: str = "\t",
        fieldnames: Sequence[str] | None = None,
        encoding: str = "utf-8-sig",
    ) -> Iterator[Self]:
        """
        Read Metric instances from a file path.

        Thin wrapper around `MetricReader.open()`.

        By default, when `fieldnames` is omitted, the first row of the input file is read as
        the header.

        When `fieldnames` is supplied, the file is assumed to be headerless and every row is
        read as data. Rows shorter than `fieldnames` produce `None` for the missing fields,
        which then go through normal model validation (raising `ValidationError` for required
        fields).

        As a safeguard, if the first row exactly matches `fieldnames` it is treated as a
        forgotten header and `ValueError` is raised. Passing `fieldnames` is not a way to
        override an existing header - to map differently-named header columns to model fields,
        declare Pydantic field aliases on the `Metric` subclass.

        Args:
            path: Filesystem path to the input file.
            delimiter: The input file delimiter.
            fieldnames: Optional sequence of field names. If provided, the input
                is treated as headerless and these names are used as the column
                headers.
            encoding: The text encoding used to decode the file.

        Yields:
            Instances of the calling Metric subclass, one per data row.

        Raises:
            ValueError: If `fieldnames` is supplied and the first row appears to be a header
                that matches it.

        Example:
            Reading a file that has a header row:

            ```python
            for m in AlignmentMetric.read(Path("out.tsv")):
                print(m.read_name, m.mapping_quality)
            ```

            Reading a headerless file by supplying column names:

            ```python
            for m in AlignmentMetric.read(
                Path("out.tsv"),
                fieldnames=["read_name", "mapping_quality"],
            ):
                print(m.read_name, m.mapping_quality)
            ```
        """
        with MetricReader.open(
            cls,
            path,
            delimiter=delimiter,
            fieldnames=fieldnames,
            encoding=encoding,
        ) as reader:
            yield from reader

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
            This method is deliberately not used during reading/validation; see `read()` for
            the headerless-input path.

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

        fieldnames: list[str]
        fieldnames = list(cls.model_fields.keys())

        if cls._counter_fieldname is None:
            # Short circuit if we don't have a Counter field
            return fieldnames

        # Remove the declared Counter field
        fieldnames = [f for f in fieldnames if f != cls._counter_fieldname]

        # Add the enum members
        assert cls._counter_enum is not None  # type narrowing
        fieldnames += [member.value for member in cls._counter_enum]

        return fieldnames
