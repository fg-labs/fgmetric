from contextlib import AbstractContextManager
from csv import DictWriter
from io import TextIOWrapper
from pathlib import Path
from types import TracebackType
from typing import Iterable
from typing import Self

from fgmetric.metric import Metric


class MetricWriter[T: Metric](AbstractContextManager):
    """
    Context manager for writing Metric instances to delimited text files.

    This class provides a convenient interface for serializing Metric objects to TSV, CSV, or other
    delimited file formats. It automatically writes column headers based on the Metric class fields
    and handles the conversion from Pydantic models to dictionary rows. The writer implements the
    context manager protocol for safe file handling and supports both single and batch writing
    operations. Field aliases are respected when writing headers and data.

    Example:
        ```python
        class AlignmentMetric(Metric):
            read_name: str
            mapping_quality: int
            is_duplicate: bool = False

        # Write metrics to a TSV file
        metrics = [
            AlignmentMetric(read_name="read1", mapping_quality=60, is_duplicate=False),
            AlignmentMetric(read_name="read2", mapping_quality=30, is_duplicate=True),
        ]

        with MetricWriter(AlignmentMetric, "output.txt") as writer:
            writer.writeall(metrics)
        ```

    Note:
        The file is opened immediately upon initialization and the header row is written
        automatically. Use the context manager interface to ensure proper file closure.
    """

    _metric_class: type[T]
    _fout: TextIOWrapper
    _writer: DictWriter[str]

    def __init__(
        self,
        metric_class: type[T],
        filename: Path | str,
        delimiter: str = "\t",
        lineterminator: str = "\n",
    ) -> None:
        """
        Initialize a new `MetricWriter`.

        Args:
            filename: Path to the file to write.
            metric_class: Metric class.
            delimiter: The output file delimiter.
            lineterminator: The string used to terminate lines produced by the MetricWriter.
        """
        self._metric_class = metric_class
        self._fout = Path(filename).open("w", encoding="utf-8")

        try:
            self._writer = DictWriter(
                f=self._fout,
                fieldnames=self._metric_class._header_fieldnames(),
                delimiter=delimiter,
                lineterminator=lineterminator,
            )

            self._writer.writeheader()
        except Exception:
            self._fout.close()
            raise

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> None:
        self.close()
        super().__exit__(exc_type, exc_value, traceback)

    def close(self) -> None:
        """Close the underlying file handle."""
        self._fout.close()

    def write(self, metric: T) -> None:
        """
        Write a single Metric instance to file.

        The Metric is serialized using ``model_dump(mode="json")`` and then written using the
        underlying `DictWriter`. JSON mode ensures that all field values (e.g., enums) are
        converted to JSON-compatible types before writing.

        Args:
            metric: An instance of the specified Metric.

        Raises:
            TypeError: If the provided `metric` is not an instance of the Metric class used to
                parametrize the writer.
        """
        self._writer.writerow(metric.model_dump(mode="json"))

    def writeall(self, metrics: Iterable[T]) -> None:
        """
        Write multiple Metric instances to file.

        Each Metric is converted to a dictionary and then written using the underlying `DictWriter`.

        Args:
            metrics: A sequence of instances of the specified Metric.
        """
        for metric in metrics:
            self.write(metric)
