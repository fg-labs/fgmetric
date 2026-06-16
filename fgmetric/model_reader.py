from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Sequence
from contextlib import contextmanager
from csv import DictReader
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Self

from xopen import xopen

from fgmetric._delimiter import infer_delimiter
from fgmetric._paths import path_read_error

if TYPE_CHECKING:
    from fgmetric.record_model import RecordModel


class ModelReader[T: RecordModel]:
    """
    Iterate `RecordModel` instances from a text IO source.

    Constructed with any iterable of strings (file handle, StringIO, list of
    lines). The reader does not own the source; callers manage its lifecycle.
    Use the `open` classmethod to open and read a file in one step; unlike direct
    construction, `open` owns the file it opens and closes it on context exit.
    """

    _model_class: type[T]
    _records: Iterator[dict[str, str | None]]

    def __init__(
        self,
        model_class: type[T],
        source: Iterable[str],
        delimiter: str = "\t",
        fieldnames: Sequence[str] | None = None,
    ) -> None:
        """
        Initialize a new `ModelReader`.

        Args:
            model_class: The `RecordModel` subclass to validate each row into.
            source: An iterable of strings (e.g., file handle, StringIO) to read from.
            delimiter: The input file delimiter.
            fieldnames: Optional sequence of field names. If provided, the input is treated as
                headerless and these names are used as the column headers.

        Raises:
            ValueError: If `fieldnames` is supplied and the first row appears to be a header
                that matches it.
        """
        self._model_class = model_class
        records: Iterator[dict[str, str | None]] = DictReader(
            source,
            fieldnames=fieldnames,
            delimiter=delimiter,
        )
        if fieldnames is not None:
            first = next(records, None)
            if first is not None:
                # NB: only a full match flags a header. A partial match is ambiguous —
                # a single field value happening to equal its name is plausible data.
                if all(first[f] == f for f in fieldnames):
                    raise ValueError(
                        "First row appears to be a header that matches `fieldnames`. "
                        "Omit `fieldnames` to read with the existing header."
                    )
                records = chain([first], records)
        self._records = records

    @classmethod
    @contextmanager
    def open(
        cls,
        model_class: type[T],
        path: Path | str,
        delimiter: str | None = None,
        fieldnames: Sequence[str] | None = None,
        encoding: str = "utf-8-sig",
    ) -> Iterator[Self]:
        """
        Open `path` and yield a `ModelReader` over its contents.

        This is a context manager: bind it in a `with` statement and iterate the reader it
        yields. `reader = ModelReader.open(...)` without `with` binds the context manager
        itself, not a reader, so it will not iterate.

        The file is opened with the given encoding and closed on context exit. The default encoding,
        `utf-8-sig`, will cleanly open Excel-generated CSVs by removing any UTF-8 BOM (if present).

        Compression is detected automatically from the file extension: `.gz`, `.bz2`, and `.xz`
        files are transparently decompressed.

        Args:
            model_class: The `RecordModel` subclass to validate each row into.
            path: Filesystem path to the input file.
            delimiter: The input file delimiter. When `None` (the default), the delimiter is
                inferred from the file extension: `.csv` → comma; `.tsv`, `.txt`, `.tab`, or
                any extension ending in `metrics` → tab — ignoring any trailing compression
                suffix. Unrecognized extensions raise `ValueError`.
            fieldnames: Optional sequence of field names. If provided, the input is
                treated as headerless and these names are used as the column
                headers.
            encoding: The text encoding used to decode the file.

        Yields:
            A `ModelReader` over the opened file.

        Raises:
            FileNotFoundError: If `path` does not exist.
            IsADirectoryError: If `path` is a directory.
            PermissionError: If `path` is not readable.
            ValueError: If `delimiter` is omitted and the delimiter cannot be inferred from
                the file extension.

        Example:
            ```python
            with ModelReader.open(AlignmentMetric, "metrics.txt") as reader:
                for metric in reader:
                    ...
            ```
        """
        if (error := path_read_error(path)) is not None:
            raise error
        if delimiter is None:
            delimiter = infer_delimiter(path)
        with xopen(path, mode="rt", encoding=encoding) as handle:
            yield cls(model_class, handle, delimiter, fieldnames)

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> T:
        return self._model_class.model_validate(next(self._records))
