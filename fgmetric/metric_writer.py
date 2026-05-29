from collections.abc import Iterable
from collections.abc import Iterator
from contextlib import contextmanager
from csv import DictWriter
from pathlib import Path
from typing import Self
from typing import TextIO

from xopen import xopen

from fgmetric._delimiter import infer_delimiter
from fgmetric._paths import path_write_error
from fgmetric.metric import Metric


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

        The header is written on context entry; the file is closed on context exit.

        Args:
            metric_class: Metric class.
            path: Filesystem path to the output file.
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
            FileExistsError: If `path` already exists and `overwrite` is `False`.
            ValueError: If `delimiter` is omitted and the delimiter cannot be inferred from
                the file extension.

        Example:
            ```python
            with MetricWriter.open(AlignmentMetric, "metrics.txt") as writer:
                writer.writeall(metrics)
            ```
        """
        if (error := path_write_error(path, overwrite=overwrite)) is not None:
            raise error
        if delimiter is None:
            delimiter = infer_delimiter(path)
        with xopen(path, mode="wt", encoding=encoding) as handle:
            yield cls(metric_class, handle, delimiter, lineterminator)

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
