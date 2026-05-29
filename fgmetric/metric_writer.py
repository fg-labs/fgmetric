from collections.abc import Iterable
from collections.abc import Iterator
from contextlib import contextmanager
from csv import DictWriter
from csv import reader
from pathlib import Path
from typing import Literal
from typing import Self
from typing import TextIO

from xopen import xopen

from fgmetric.metric import Metric


def _read_existing_header(
    path: Path | str,
    delimiter: str,
    encoding: str,
) -> list[str] | None:
    """
    Return the parsed first row of an existing, non-empty file, or `None`.

    Returns `None` when the file is missing or empty. Otherwise the first line is parsed with
    `csv.reader` (so it is interpreted exactly as `DictWriter` would have written it) and the
    resulting list of column names is returned.

    Args:
        path: Filesystem path to inspect.
        delimiter: The delimiter used to parse the header row.
        encoding: The text encoding used to decode the file.

    Returns:
        The parsed header row, or `None` if the file is missing or empty.
    """
    try:
        with xopen(path, mode="rt", encoding=encoding) as handle:
            first_line = handle.readline()
    except FileNotFoundError:
        return None
    if first_line == "":
        return None
    return next(reader([first_line], delimiter=delimiter))


def _append_writes_header(
    metric_class: type[Metric],
    path: Path | str,
    delimiter: str,
    encoding: str,
) -> bool:
    """
    Validate the header of a file opened for appending and report whether to write one.

    Returns `True` when `path` is missing or empty — append-or-create writes a fresh header.
    When `path` already has content, its first row is validated against the metric class's
    fields and a `ValueError` is raised on a mismatch; otherwise `False` is returned so the
    existing header is left untouched.

    Args:
        metric_class: Metric class whose fields the existing header must match.
        path: Filesystem path being opened for appending.
        delimiter: The delimiter used to parse the existing header row.
        encoding: The text encoding used to decode the file.

    Returns:
        Whether a header row must be written.

    Raises:
        ValueError: If `path` is non-empty and its header does not match the metric fields.
    """
    existing = _read_existing_header(path, delimiter, encoding)
    if existing is None:
        return True

    expected = metric_class._header_fieldnames()
    if existing != expected:
        raise ValueError(
            f"Existing header in {path} does not match "
            f"{metric_class.__name__} fields.\n"
            f"  expected: {expected}\n"
            f"  found:    {existing}"
        )

    return False


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
        delimiter: str = "\t",
        lineterminator: str = "\n",
        encoding: str = "utf-8",
    ) -> Iterator[Self]:
        """
        Open `path` for writing and yield a `MetricWriter` over it.

        This is a context manager: bind it in a `with` statement and write through the writer
        it yields. `writer = MetricWriter.open(...)` without `with` binds the context manager
        itself, not a writer.

        Compression is selected automatically based on the output file extension: plaintext, gzip
        (`.gz`), bzip2 (`.bz2`), or xz (`.xz`).

        With `mode="w"` (the default) the file is truncated and the header row is written. With
        `mode="a"` the file is opened for appending: if it is missing or empty the header is
        written first (append-or-create); if it already has content, its first row is validated
        against the metric class's fields (parsed with `delimiter`) and a `ValueError` is raised on
        a mismatch — no header is written in that case. The existing header is read with the same
        `encoding`, so a foreign file written with a different delimiter or a BOM will fail
        validation. `MetricWriter` always terminates rows with `lineterminator`, so appending to a
        foreign file whose last line lacks a trailing newline would concatenate.

        The file is opened lazily on context entry and closed on context exit.

        Args:
            metric_class: Metric class.
            path: Filesystem path to the output file.
            mode: `"w"` to truncate and write, `"a"` to append.
            delimiter: The output file delimiter.
            lineterminator: The string used to terminate lines.
            encoding: The text encoding used to write the file.

        Yields:
            A `MetricWriter` over the opened file.

        Raises:
            ValueError: If `mode="a"` and the existing file's header does not match the metric
                class's fields.

        Example:
            ```python
            with MetricWriter.open(AlignmentMetric, "metrics.txt") as writer:
                writer.writeall(metrics)

            with MetricWriter.open(AlignmentMetric, "metrics.txt", mode="a") as writer:
                writer.writeall(more_metrics)
            ```
        """
        xmode: Literal["wt", "at"]
        if mode == "a":
            xmode = "at"
            write_header = _append_writes_header(metric_class, path, delimiter, encoding)
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
        self._writer.writerow(metric.model_dump(mode="json"))

    def writeall(self, metrics: Iterable[T]) -> None:
        """
        Write multiple `Metric` instances.

        Args:
            metrics: An iterable of instances of the writer's metric class.
        """
        for metric in metrics:
            self.write(metric)
