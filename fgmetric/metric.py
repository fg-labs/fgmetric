from abc import ABC
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar
from typing import Self

from pydantic import BaseModel

from fgmetric.converters import CounterPivotTable
from fgmetric.converters import DelimitedList
from fgmetric.converters import NullSentinels
from fgmetric.metric_reader import MetricReader


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
    1. **Null sentinels.** Empty strings in Optional fields are converted to `None` before field
       validation. The sentinel values converted to `None` can be overridden by the
       `null_sentinels` class variable.
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
        for metric in AlignmentMetric.read("metrics.txt"):
            print(metric.read_name, metric.mapping_quality)
        ```
    """

    null_sentinels: ClassVar[frozenset[str]] = frozenset({""})

    @classmethod
    def read(
        cls,
        path: Path | str,
        # NB: these defaults mirror `MetricReader.open()`; keep them in sync.
        delimiter: str = "\t",
        fieldnames: Sequence[str] | None = None,
        encoding: str = "utf-8-sig",
    ) -> list[Self]:
        """
        Read all Metric instances from a file path.

        Eager wrapper around `MetricReader.open()`: the file is opened, parsed, and closed
        before this method returns, collecting every row into a list. Because reading happens
        up front, IO and validation errors surface here at the call site rather than partway
        through iteration.

        See `MetricReader.open()` for the file-handling behavior shared by both APIs - encoding,
        automatic decompression of `.gz`/`.bz2`/`.xz` files, and how `fieldnames` selects
        header vs. headerless parsing. To stream a large file without holding every row in
        memory, or to read from an already-open handle or other text IO source, use
        `MetricReader` directly.

        Args:
            path: Filesystem path to the input file.
            delimiter: The input file delimiter.
            fieldnames: Optional sequence of field names. If provided, the input is treated as
                headerless and these names are used as the column headers.
            encoding: The text encoding used to decode the file.

        Returns:
            A list of instances of the calling Metric subclass, one per data row.

        Raises:
            FileNotFoundError: If `path` does not exist.
            LookupError: If `encoding` is not a known codec.
            UnicodeDecodeError: If the file's bytes cannot be decoded using `encoding`.
            ValueError: If `fieldnames` is supplied and the first row matches it (a likely
                forgotten header).
            ValidationError: If a row fails `Metric` validation, e.g. a missing required field
                or a value of the wrong type.

        Example:
            `read` is eager and returns a list, so the whole file is available at once:

            ```python
            metrics = AlignmentMetric.read("metrics.txt")
            print(f"read {len(metrics)} rows")
            for m in metrics:
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
            return list(reader)

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
