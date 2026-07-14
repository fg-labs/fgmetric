from abc import ABC
from collections.abc import Sequence
from pathlib import Path
from typing import Self
from typing import final

from pydantic import BaseModel

from fgmetric.model_reader import DEFAULT_ENCODING
from fgmetric.model_reader import ModelReader


class RecordModel(BaseModel, ABC):
    """
    Abstract base class for record-oriented data models read from and written to delimited files.

    `RecordModel` combines Pydantic's `BaseModel` with `ABC` to provide a foundation for type-safe
    models that map one-to-one onto the rows of a delimited text file (e.g., TSV, CSV). It performs
    the default tabular parsing only: each model field corresponds to a column, with Pydantic
    handling validation and type conversion. It carries none of the optional conversion behaviors
    (delimited lists, counter pivot tables, null sentinels) layered on by `Metric` and the
    `fgmetric.converters` mixins.

    Use `RecordModel` directly when you want plain field-per-column parsing without the mixin
    machinery; use `Metric` when you want the batteries-included behaviors. `ModelReader` and
    `ModelWriter` operate on any `RecordModel` subclass.

    Subclasses should define their fields using Pydantic field annotations.

    Note:
        `RecordModel` applies no null-sentinel handling, so `T | None` fields do not round-trip
        `None`. On write, `None` serializes to an empty cell; on read, that empty cell comes back
        as `""` - for a `str | None` field it validates to `""` (not `None`), and for a non-string
        optional (e.g. `int | None`) it raises a `ValidationError`. Use `Metric`, or add the
        `NullSentinels` mixin, if you need `None` preserved across a write/read cycle.

    Example:
        ```python
        class AlignmentRecord(RecordModel):
            read_name: str
            mapping_quality: int
            is_duplicate: bool = False

        # Read records from a TSV file
        for record in AlignmentRecord.read("records.txt"):
            print(record.read_name, record.mapping_quality)
        ```
    """

    @classmethod
    def read(
        cls,
        path: Path | str,
        # NB: `encoding` mirrors `ModelReader.open`. Unlike `open`, `read` does not infer the
        # delimiter from the file extension - it defaults to a literal tab.
        delimiter: str = "\t",
        fieldnames: Sequence[str] | None = None,
        encoding: str = DEFAULT_ENCODING,
    ) -> list[Self]:
        """
        Read all instances from a file path.

        Eager wrapper around `ModelReader.open()`: the file is opened, parsed, and closed
        before this method returns, collecting every row into a list. Because reading happens
        up front, IO and validation errors surface here at the call site rather than partway
        through iteration.

        See `ModelReader.open()` for the file-handling behavior shared by both APIs - encoding,
        automatic decompression of `.gz`/`.bz2`/`.xz` files, and how `fieldnames` selects
        header vs. headerless parsing. To stream a large file without holding every row in
        memory, or to read from an already-open handle or other text IO source, use
        `ModelReader` directly.

        Args:
            path: Filesystem path to the input file.
            delimiter: The input file delimiter.
            fieldnames: Optional sequence of field names. If provided, the input is treated as
                headerless and these names are used as the column headers.
            encoding: The text encoding used to decode the file.

        Returns:
            A list of instances of the calling subclass, one per data row.

        Raises:
            FileNotFoundError: If `path` does not exist.
            LookupError: If `encoding` is not a known codec.
            UnicodeDecodeError: If the file's bytes cannot be decoded using `encoding`.
            ValueError: If `fieldnames` is supplied and the first row matches it (a likely
                forgotten header).
            ValidationError: If a row fails validation, e.g. a missing required field
                or a value of the wrong type.

        Example:
            `read` is eager and returns a list, so the whole file is available at once:

            ```python
            records = AlignmentRecord.read("records.txt")
            print(f"read {len(records)} rows")
            for r in records:
                print(r.read_name, r.mapping_quality)
            ```
        """
        with ModelReader.open(
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
        Return the fieldnames to use as a header row when writing records to a file.

        This method is used by `ModelWriter` to construct the underlying `csv.DictWriter`.
        It returns the fieldnames that will appear in serialized output, which may differ from
        the model's field names when aliases are used.

        Subclasses and mixins (e.g., `CounterPivotTable`) may override this method to adjust the
        header to match a custom serializer. Such overrides should build on
        `_default_header_fieldnames` (the plain field-per-column header) rather than `super()`,
        so they do not depend on their position in the model's MRO.

        Note:
            This method is deliberately not used during reading/validation; see
            `ModelReader` for the headerless-input path.

        Returns:
            The list of fieldnames to use as the header row.
        """
        # TODO: support returning the set of fields that would be constructed if the class has a
        # custom model serializer
        return cls._default_header_fieldnames()

    @final
    @classmethod
    def _default_header_fieldnames(cls) -> list[str]:
        """
        Return the plain field-per-column header: one column per field, in declaration order.

        Each field resolves to the key it serializes under (its alias, when one is set), so the
        header matches the keys produced by `model_dump(by_alias=True)`. This method is `@final`
        so header-rewriting mixins can call it directly instead of routing through `super()`,
        which would otherwise depend on MRO ordering.

        Returns:
            The list of fieldnames to use as the header row.
        """
        return [
            info.serialization_alias or info.alias or name
            for name, info in cls.model_fields.items()
        ]
