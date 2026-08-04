from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Self

from fgmetric.metric_reader import MetricReader

if TYPE_CHECKING:
    # NB: imported for the type parameter's bound only. `PicardMetric.read` delegates back to
    # this reader at runtime, so importing it eagerly here would be circular. This mirrors how
    # `MetricReader` refers to `Metric`.
    from fgmetric.picard._metric import PicardMetric

# Section markers, per HTSJDK's `MetricsFile`. Every section is introduced by a line starting
# with the major-header prefix; a blank line terminates the section that precedes it.
MAJOR_HEADER_PREFIX = "## "
METRICS_CLASS_MARKER = "## METRICS CLASS"


def metrics_block(source: Iterable[str]) -> Iterator[str]:
    """
    Yield the column header and data rows of the first `## METRICS CLASS` block.

    Everything before the marker (the `##`/`#` comment preamble) is dropped, as is everything
    from the end of the block onward — so a trailing `## HISTOGRAM` section, or a second
    metrics section, is not mistaken for more metric rows.

    Args:
        source: The lines of a Picard metrics file.

    Yields:
        The block's column header line, followed by its data rows.

    Raises:
        ValueError: If the source has content but no `## METRICS CLASS` marker. A source with
            no content at all yields nothing instead, so that an empty file reads as zero
            metrics.
    """
    lines = iter(source)

    has_content = False
    for line in lines:
        if line.startswith(METRICS_CLASS_MARKER):
            break
        if line.strip():
            has_content = True
    else:
        if has_content:
            raise ValueError(
                f"No {METRICS_CLASS_MARKER!r} section found. The source has content, so it is "
                "either not a Picard metrics file or holds only a histogram."
            )
        return

    for line in lines:
        if not line.strip() or line.startswith(MAJOR_HEADER_PREFIX):
            return
        yield line


class PicardMetricReader[T: PicardMetric](MetricReader[T]):
    """
    Iterate `PicardMetric` instances from a Picard-formatted metrics file.

    Picard/HTSJDK metrics files are almost plain TSV, but two structural features stop a
    generic reader from parsing them: a comment preamble precedes the column header, and a
    `## HISTOGRAM` section may follow the metrics table. This reader filters the source down to
    the first `## METRICS CLASS` section — its column header and data rows — before the rows
    reach the underlying CSV machinery.

    Files that hold many rows in one section (`AlignmentSummaryMetrics` emits `FIRST_OF_PAIR`,
    `SECOND_OF_PAIR`, and `PAIR`) yield one metric per row. Files that hold many *sections* are
    read down to their first metrics section only.

    Otherwise this behaves exactly like `MetricReader`: construct it over any iterable of
    strings, or use `open` to read a path (with transparent decompression) in one step.

    Example:
        ```python
        path = "example.alignment_summary_metrics"
        with PicardMetricReader.open(AlignmentSummaryMetric, path) as reader:
            for metric in reader:
                print(metric.category, metric.pct_pf_reads)
        ```
    """

    def __init__(
        self,
        metric_class: type[T],
        source: Iterable[str],
        delimiter: str = "\t",
        fieldnames: Sequence[str] | None = None,
    ) -> None:
        """
        Initialize a new `PicardMetricReader`.

        Args:
            metric_class: The `PicardMetric` subclass to validate each row against.
            source: An iterable of strings (e.g., file handle, StringIO) to read from.
            delimiter: The input file delimiter. Picard always writes tabs; this is exposed
                only for the rare hand-edited file.
            fieldnames: Not supported. A Picard section carries its own column header, so
                names are never supplied by the caller.

        Raises:
            ValueError: If `fieldnames` is supplied.
        """
        if fieldnames is not None:
            raise ValueError(
                "`fieldnames` is not supported when reading Picard metrics: the column header "
                "is read from the file's '## METRICS CLASS' section."
            )
        super().__init__(metric_class, metrics_block(source), delimiter, None)

    @classmethod
    @contextmanager
    def open(
        cls,
        metric_class: type[T],
        path: Path | str,
        # NB: unlike `MetricReader.open`, the delimiter defaults to a tab rather than being
        # inferred from the file extension. The Picard metrics format is tab-delimited by
        # definition (HTSJDK `MetricsFile.SEPARATOR`), and Picard names its outputs after the
        # tool that wrote them (`example.MarkDuplicates`), so inference would only ever return
        # a tab or fail on a perfectly valid file. Pass `delimiter=None` to infer anyway.
        delimiter: str | None = "\t",
        fieldnames: Sequence[str] | None = None,
        encoding: str = "utf-8-sig",
    ) -> Iterator[Self]:
        """
        Open `path` and yield a `PicardMetricReader` over its contents.

        This is a context manager: bind it in a `with` statement and iterate the reader it
        yields. See `MetricReader.open` for the file handling shared by both readers —
        encoding, and automatic decompression of `.gz`/`.bz2`/`.xz` files.

        Args:
            metric_class: The `PicardMetric` subclass to validate each row against.
            path: Filesystem path to the input file.
            delimiter: The input file delimiter, a tab by default. Pass `None` to infer it from
                the file extension instead.
            fieldnames: Not supported; see `__init__`.
            encoding: The text encoding used to decode the file.

        Yields:
            A `PicardMetricReader` over the opened file.

        Raises:
            FileNotFoundError: If `path` does not exist.
            IsADirectoryError: If `path` is a directory.
            PermissionError: If `path` is not readable.
            ValueError: If `fieldnames` is supplied, or if `delimiter` is `None` and no
                delimiter can be inferred from the file extension.
        """
        with super().open(
            metric_class,
            path,
            delimiter=delimiter,
            fieldnames=fieldnames,
            encoding=encoding,
        ) as reader:
            yield reader
