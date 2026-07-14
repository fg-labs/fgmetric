from collections.abc import Iterable
from collections.abc import Iterator
from contextlib import contextmanager
from csv import DictReader
from csv import DictWriter
from pathlib import Path
from typing import Literal
from typing import Self
from typing import TextIO

from pydantic import ValidationError
from xopen import xopen

from fgmetric._delimiter import infer_delimiter
from fgmetric._paths import path_write_error
from fgmetric.metric import Metric


def _read_first_row(
    path: Path | str,
    delimiter: str,
    encoding: str,
) -> list[str] | None:
    """
    Return the first row of an existing, non-empty file as a list of cells, or `None`.

    Returns `None` when the file is missing or empty. Otherwise the first row is parsed with
    `csv.DictReader` — the symmetric counterpart to the `DictWriter` used to write metrics — so it
    is interpreted exactly as it was written. The row may be a header or a data record; the caller
    decides which by comparing it to the expected column names and validating it against the model.

    Args:
        path: Filesystem path to inspect.
        delimiter: The delimiter used to parse the row.
        encoding: The text encoding used to decode the file.

    Returns:
        The parsed first row, or `None` if the file is missing or empty.
    """
    file = Path(path)
    # A zero-byte file is not a valid compressed stream; checking the size first avoids the
    # bz2/xz decompressors raising EOFError when xopen tries to read an empty `.bz2`/`.xz`.
    if not file.exists() or file.stat().st_size == 0:
        return None
    with xopen(path, mode="rt", encoding=encoding) as handle:
        fieldnames = DictReader(handle, delimiter=delimiter).fieldnames
        return None if fieldnames is None else list(fieldnames)


def _row_validates_as_record(
    metric_class: type[Metric],
    fieldnames: list[str],
    row: list[str],
) -> bool:
    """
    Whether `row`, zipped onto `fieldnames`, validates as a record of `metric_class`.

    The cells are mapped to `fieldnames` and validated with `model_validate`, the same path
    `MetricReader` uses to parse a row. A row with the wrong number of cells cannot be a record,
    so it is rejected without attempting validation.

    Args:
        metric_class: Metric class to validate against.
        fieldnames: The expected column names (the metric's header fields).
        row: The parsed cells of the row to validate.

    Returns:
        `True` if the row validates as a record, `False` otherwise.
    """
    if len(row) != len(fieldnames):
        return False
    try:
        metric_class.model_validate(dict(zip(fieldnames, row, strict=True)))
    except ValidationError:
        return False
    return True


def _append_needs_header(
    metric_class: type[Metric],
    path: Path | str,
    delimiter: str,
    encoding: str,
) -> bool:
    """
    Inspect a file opened for appending and report whether to write a header.

    Returns `True` when `path` is missing or empty — append-or-create writes a fresh header.
    When `path` already has content, its first row is accepted if it either matches the expected
    header or validates as a record of the metric class (a headerless data file); in both cases
    `False` is returned so no header is written into the middle of the file. A `ValueError` is
    raised only when the first row is neither.

    Args:
        metric_class: Metric class whose header/records the file must be consistent with.
        path: Filesystem path being opened for appending.
        delimiter: The delimiter used to parse the first row.
        encoding: The text encoding used to decode the file.

    Returns:
        Whether a header row must be written.

    Raises:
        ValueError: If `path` is non-empty and its first row is neither the expected header nor a
            valid record.
    """
    first_row = _read_first_row(path, delimiter, encoding)
    if first_row is None:
        return True

    expected = metric_class._header_fieldnames()
    # A matching header, or a headerless file whose first row validates as a record: append after
    # the existing content without writing a header.
    if first_row == expected or _row_validates_as_record(metric_class, expected, first_row):
        return False

    raise ValueError(
        f"First row of {path} is neither a {metric_class.__name__} header nor a valid record.\n"
        f"  expected header: {expected}\n"
        f"  found:           {first_row}"
    )


class MetricWriter[T: Metric]:
    """
    Write `Metric` instances to a text IO sink.

    Construction takes a writable text IO and writes the header row immediately.
    The writer does not own the sink; callers manage its lifecycle. Use the
    `open` classmethod to open and write to a file in one step; unlike direct
    construction, `open` owns the file it opens and closes it on context exit.
    """

    _metric_class: type[T]
    _writer: DictWriter[str]

    def __init__(
        self,
        metric_class: type[T],
        sink: TextIO,
        delimiter: str = "\t",
        lineterminator: str = "\n",
        write_header: bool = True,
    ) -> None:
        """
        Initialize a new `MetricWriter`.

        By default the header row is written to `sink` immediately on construction. Pass
        `write_header=False` to suppress it — e.g. when appending to a sink that already
        contains a header.

        Args:
            metric_class: Metric class.
            sink: Writable text IO (e.g., file handle, StringIO) to write to.
            delimiter: The output file delimiter.
            lineterminator: The string used to terminate lines.
            write_header: Whether to write the header row on construction.
        """
        self._metric_class = metric_class
        self._writer = DictWriter(
            f=sink,
            fieldnames=metric_class._header_fieldnames(),
            delimiter=delimiter,
            lineterminator=lineterminator,
        )
        if write_header:
            self._writer.writeheader()

    @classmethod
    @contextmanager
    def open(
        cls,
        metric_class: type[T],
        path: Path | str,
        mode: Literal["w", "a"] = "w",
        delimiter: str | None = None,
        lineterminator: str = "\n",
        encoding: str = "utf-8",
        overwrite: bool = False,
    ) -> Iterator[Self]:
        """
        Open `path` for writing and yield a `MetricWriter` over it.

        This is a context manager: bind it in a `with` statement and write through the writer
        it yields. `writer = MetricWriter.open(...)` without `with` binds the context manager
        itself, not a writer.

        Compression is selected automatically based on the output file extension: plaintext, gzip
        (`.gz`), bzip2 (`.bz2`), or xz (`.xz`).

        With `mode="w"` (the default) the file is truncated and the header row is written (refused
        with `FileExistsError` if the file already exists and `overwrite` is `False`). With
        `mode="a"` the file is opened for appending: if it is missing or empty the header is
        written first (append-or-create); if it already has content, its first row is inspected and
        rows are appended without writing a header when that row either matches the expected header
        or validates as a record of the metric class (a headerless data file). A `ValueError` is
        raised only when the first row is neither. The first row is parsed with the same `delimiter`
        and `encoding`, so a foreign file written with a different delimiter or a BOM will fail to
        validate (`MetricReader.open` defaults to `utf-8-sig`, which strips a BOM; the writer does
        not). `MetricWriter` always terminates rows with `lineterminator`, so appending to a foreign
        file whose last line lacks a trailing newline would concatenate.

        The file is opened lazily on context entry and closed on context exit.

        Args:
            metric_class: Metric class.
            path: Filesystem path to the output file.
            mode: `"w"` to truncate and write, `"a"` to append. Append is non-destructive, so the
                `overwrite` guard does not apply.
            delimiter: The output file delimiter. When `None` (the default), the delimiter is
                inferred from the file extension: `.csv` → comma; `.tsv`, `.txt`, `.tab`, or
                any extension ending in `metrics` → tab — ignoring any trailing compression
                suffix. Unrecognized extensions raise `ValueError`.
            lineterminator: The string used to terminate lines.
            encoding: The text encoding used to write the file.
            overwrite: By default, opening an existing file for writing will raise
                `FileExistsError`. Pass `True` to destructively overwrite an existing file.

        Yields:
            A `MetricWriter` over the opened file.

        Raises:
            FileNotFoundError: If the parent directory of `path` does not exist.
            NotADirectoryError: If the parent of `path` exists but is not a directory.
            IsADirectoryError: If `path` is a directory.
            PermissionError: If `path` exists but is not writable, or if `path` cannot be
                created in its parent directory.
            FileExistsError: If `path` already exists, `mode="w"`, and `overwrite` is `False`.
            ValueError: If `delimiter` is omitted and cannot be inferred from the file
                extension, or if `mode="a"` and the existing file's first row is neither the
                expected header nor a valid record.

        Example:
            ```python
            with MetricWriter.open(AlignmentMetric, "metrics.txt") as writer:
                writer.writeall(metrics)

            with MetricWriter.open(AlignmentMetric, "metrics.txt", mode="a") as writer:
                writer.writeall(more_metrics)
            ```
        """
        if (error := path_write_error(path, overwrite=overwrite or mode == "a")) is not None:
            raise error
        if delimiter is None:
            delimiter = infer_delimiter(path)

        xmode: Literal["wt", "at"]
        if mode == "a":
            xmode = "at"
            write_header = _append_needs_header(metric_class, path, delimiter, encoding)
        else:
            xmode = "wt"
            write_header = True

        with xopen(path, mode=xmode, encoding=encoding) as handle:
            yield cls(metric_class, handle, delimiter, lineterminator, write_header=write_header)

    def write(self, metric: T) -> None:
        """
        Write a single `Metric` instance.

        Args:
            metric: An instance of the writer's metric class.
        """
        self._writer.writerow(metric.model_dump(mode="json", by_alias=True))

    def writeall(self, metrics: Iterable[T]) -> None:
        """
        Write multiple `Metric` instances.

        Args:
            metrics: An iterable of instances of the writer's metric class.
        """
        for metric in metrics:
            self.write(metric)
