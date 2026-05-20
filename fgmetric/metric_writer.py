from collections.abc import Iterable
from collections.abc import Iterator
from contextlib import contextmanager
from csv import DictWriter
from pathlib import Path
from typing import Self
from typing import TextIO

from fgmetric.metric import Metric


class MetricWriter[T: Metric]:
    """
    Write `Metric` instances to a text IO sink.

    Construction takes a writable text IO and writes the header row immediately.
    The writer does not own the sink; callers manage its lifecycle. Use the
    `open` classmethod to open and write to a file in one step.
    """

    _metric_class: type[T]
    _writer: DictWriter[str]

    def __init__(
        self,
        metric_class: type[T],
        sink: TextIO,
        delimiter: str = "\t",
        lineterminator: str = "\n",
    ) -> None:
        """
        Initialize a new `MetricWriter` and write the header row to `sink`.

        Args:
            metric_class: Metric class.
            sink: Writable text IO (e.g., file handle, StringIO) to write to.
            delimiter: The output file delimiter.
            lineterminator: The string used to terminate lines.
        """
        self._metric_class = metric_class
        self._writer = DictWriter(
            f=sink,
            fieldnames=metric_class._header_fieldnames(),
            delimiter=delimiter,
            lineterminator=lineterminator,
        )
        self._writer.writeheader()

    @classmethod
    @contextmanager
    def open(
        cls,
        metric_class: type[T],
        path: Path | str,
        delimiter: str = "\t",
        lineterminator: str = "\n",
    ) -> Iterator[Self]:
        """
        Open `path` for writing and yield a `MetricWriter` over it.

        The file is opened with `encoding="utf-8"`. The header is written on
        context entry; the file is closed on context exit. Compression is not
        yet supported.

        Args:
            metric_class: Metric class.
            path: Filesystem path to the output file.
            delimiter: The output file delimiter.
            lineterminator: The string used to terminate lines.

        Yields:
            A `MetricWriter` over the opened file.
        """
        with Path(path).open("w", encoding="utf-8") as handle:
            yield cls(metric_class, handle, delimiter, lineterminator)

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
