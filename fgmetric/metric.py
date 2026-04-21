from abc import ABC
from csv import DictReader
from pathlib import Path
from typing import ClassVar
from typing import Iterator
from typing import Self

from pydantic import BaseModel

from fgmetric.collections import CounterPivotTable
from fgmetric.collections import DelimitedList
from fgmetric.mixins import NullSentinels


class Metric(
    DelimitedList,
    CounterPivotTable,
    NullSentinels,
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
    1. **Null sentinels.** Input strings in the `null_sentinels` class variable are treated as
       `None` on Optional fields before field validation. Defaults to `frozenset({""})`, so any
       empty Optional field is represented as `None` on the deserialized model.
    2. **Delimited lists.** Any field typed as `list[T]` will be parsed from and serialized to a
       delimited string. The list delimiter may be controlled by the `collection_delimiter` class
       variable.

    Class Variables:
        collection_delimiter: A single-character delimiter used to split and join `list` fields
            during serialization/deserialization.
        null_sentinels: The set of input strings that should be treated as `None` on Optional
            fields during validation. Defaults to `frozenset({""})`.

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

    null_sentinels: ClassVar[frozenset[str]] = frozenset({""})

    @classmethod
    def read(cls, path: Path, delimiter: str = "\t") -> Iterator[Self]:
        """
        Read Metric instances from file.

        Example:
            ```python
            for m in AlignmentMetric.read(Path("out.tsv")):
                print(m.read_name, m.mapping_quality)
            ```
        """
        # NOTE: the utf-8-sig encoding is required to auto-remove BOM from input file headers
        with path.open(encoding="utf-8-sig") as fin:
            for record in DictReader(fin, delimiter=delimiter):
                yield cls.model_validate(record)

    @classmethod
    def _header_fieldnames(cls) -> list[str]:
        """
        Return the fieldnames to use as a header row when writing metrics to a file.

        This method is used by `MetricWriter` to construct the underlying `csv.DictWriter`.
        It returns the fieldnames that will appear in serialized output, which may differ from
        the model's field names when aliases are used.

        Note:
            This method is deliberately not used during reading/validation. Note that the `read()`
            method omits the `fieldnames` parameter from `csv.DictReader` so that any missing or
            misspecified fields are handled by pydantic's model validation.

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
