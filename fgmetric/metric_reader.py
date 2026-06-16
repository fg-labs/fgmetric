from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Mapping
from collections.abc import Sequence
from contextlib import contextmanager
from csv import DictReader
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Self

from xopen import xopen

from fgmetric._delimiter import infer_delimiter
from fgmetric._duckdb import query_rows
from fgmetric._paths import path_read_error

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

    from fgmetric.metric import Metric


class MetricReader[T: Metric]:
    """
    Iterate `Metric` instances from a text IO source.

    Constructed with any iterable of strings (file handle, StringIO, list of
    lines). The reader does not own the source; callers manage its lifecycle.
    Use the `open` classmethod to open and read a file in one step; unlike direct
    construction, `open` owns the file it opens and closes it on context exit.
    """

    _metric_class: type[T]
    # Widened to Mapping[str, Any]: the SQL path yields already-typed values (int, float,
    # Decimal, bool, None), not the strings the text/DictReader path produces.
    _records: Iterator[Mapping[str, Any]]

    def __init__(
        self,
        metric_class: type[T],
        source: Iterable[str],
        delimiter: str = "\t",
        fieldnames: Sequence[str] | None = None,
    ) -> None:
        """
        Initialize a new `MetricReader`.

        Args:
            metric_class: Metric class.
            source: An iterable of strings (e.g., file handle, StringIO) to read from.
            delimiter: The input file delimiter.
            fieldnames: Optional sequence of field names. If provided, the input is treated as
                headerless and these names are used as the column headers.

        Raises:
            ValueError: If `fieldnames` is supplied and the first row appears to be a header
                that matches it.
        """
        self._metric_class = metric_class
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
        metric_class: type[T],
        path: Path | str,
        delimiter: str | None = None,
        fieldnames: Sequence[str] | None = None,
        encoding: str = "utf-8-sig",
    ) -> Iterator[Self]:
        """
        Open `path` and yield a `MetricReader` over its contents.

        This is a context manager: bind it in a `with` statement and iterate the reader it
        yields. `reader = MetricReader.open(...)` without `with` binds the context manager
        itself, not a reader, so it will not iterate.

        The file is opened with the given encoding and closed on context exit. The default encoding,
        `utf-8-sig`, will cleanly open Excel-generated CSVs by removing any UTF-8 BOM (if present).

        Compression is detected automatically from the file extension: `.gz`, `.bz2`, and `.xz`
        files are transparently decompressed.

        Args:
            metric_class: Metric class.
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
            A `MetricReader` over the opened file.

        Raises:
            FileNotFoundError: If `path` does not exist.
            IsADirectoryError: If `path` is a directory.
            PermissionError: If `path` is not readable.
            ValueError: If `delimiter` is omitted and the delimiter cannot be inferred from
                the file extension.

        Example:
            ```python
            with MetricReader.open(AlignmentMetric, "metrics.txt") as reader:
                for metric in reader:
                    ...
            ```
        """
        if (error := path_read_error(path)) is not None:
            raise error
        if delimiter is None:
            delimiter = infer_delimiter(path)
        with xopen(path, mode="rt", encoding=encoding) as handle:
            yield cls(metric_class, handle, delimiter, fieldnames)

    @classmethod
    def _from_records(
        cls,
        metric_class: type[T],
        records: Iterator[Mapping[str, Any]],
    ) -> Self:
        """
        Construct a reader directly from an iterator of column-keyed record dicts.

        Shared tail for the text path (`__init__`, via `csv.DictReader`) and the SQL path
        (`from_sql`). Bypasses `__init__` because the records are already dicts; there is no
        text source to parse or header to detect.

        Args:
            metric_class: Metric class.
            records: An iterator of column-keyed record dicts to validate on iteration.

        Returns:
            A `MetricReader` over the given records.
        """
        reader = cls.__new__(cls)
        reader._metric_class = metric_class
        reader._records = records
        return reader

    @classmethod
    def from_sql(
        cls,
        metric_class: type[T],
        query: str,
        *,
        connection: "DuckDBPyConnection | None" = None,
    ) -> Self:
        """
        Read metrics from the rows returned by a DuckDB SQL query.

        Unlike `open`, this is not a context manager: it owns no file handle and returns a
        reader directly. The query names its own source, so any backend DuckDB can read works
        — Parquet, Arrow, JSON, CSV, SQLite, Postgres, and S3-hosted files. Use SQL `AS` to
        align a source's column names to the metric class's field names (or aliases).

        Rows are fetched eagerly from DuckDB (so a transient connection's lifecycle is fully
        contained), then validated lazily, one row per iteration, by `model_validate`.

        Requires the optional `duckdb` dependency: `pip install 'fgmetric[duckdb]'`.

        Args:
            metric_class: Metric class.
            query: A DuckDB SQL query whose output columns match the metric class's fields.
            connection: An open DuckDB connection to run the query against. When `None` (the
                default), a transient in-memory connection is opened and closed internally,
                which covers local files and remote sources reachable with ambient
                credentials. Pass a pre-configured connection to use extensions, secrets, or
                `ATTACH`ed databases (e.g. Postgres); a supplied connection is never closed.

        Returns:
            A `MetricReader` over the query's rows.

        Raises:
            ImportError: If the optional `duckdb` dependency is not installed.
            ValidationError: If a row fails `Metric` validation, e.g. a missing required
                column or a value of the wrong type. Raised during iteration.

        Example:
            ```python
            for metric in MetricReader.from_sql(AlignmentMetric, "SELECT * FROM 'm.parquet'"):
                ...
            ```
        """
        rows = query_rows(query, connection)
        return cls._from_records(metric_class, iter(rows))

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> T:
        return self._metric_class.model_validate(next(self._records))
