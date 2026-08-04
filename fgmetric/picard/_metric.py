from abc import ABC
from collections.abc import Sequence
from pathlib import Path
from typing import Self

from pydantic import ConfigDict

from fgmetric.metric import Metric
from fgmetric.picard._reader import PicardMetricReader


class PicardMetric(Metric, ABC):
    """
    Abstract base class for a metric read from a Picard-formatted metrics file.

    Adds the two conventions that hold across every Picard metrics table to the behavior
    `Metric` already provides (null sentinels, delimited lists):

    1. **Column names are UPPER_SNAKE.** Fields are declared in idiomatic snake_case and
       aliased to their uppercased name, so `pct_pf_reads` reads the `PCT_PF_READS` column.
       Fields may still be supplied by their Python name when constructing a model directly.
    2. **Unexpected columns are an error.** A column in the file that the model does not
       declare raises a `ValidationError`, which catches the common mistake of reading a file
       with the wrong metric class. Columns *missing* from the file are permitted when the
       field declares a default, since Picard's column set varies across versions.

    Subclasses annotate float columns as `PicardFloat` (or `PicardLog10PValue`) and boolean
    columns as `PicardBool` so that Picard's `?`/`-?`/`Y`/`N` encodings parse correctly.

    Example:
        ```python
        class AlignmentSummaryMetric(PicardMetric):
            category: str               # CATEGORY
            total_reads: int            # TOTAL_READS
            pct_pf_reads: PicardFloat   # PCT_PF_READS ("?" -> None)
        ```
    """

    model_config = ConfigDict(
        alias_generator=str.upper,
        populate_by_name=True,
        extra="forbid",
    )

    @classmethod
    def read(
        cls,
        path: Path | str,
        # NB: these defaults mirror `PicardMetricReader.open()`; keep them in sync.
        delimiter: str = "\t",
        fieldnames: Sequence[str] | None = None,
        encoding: str = "utf-8-sig",
    ) -> list[Self]:
        """
        Read all metrics from a Picard-formatted file.

        Overrides `Metric.read` to route through `PicardMetricReader` rather than the generic
        reader, which would otherwise parse the file's comment preamble as its column header.
        Like `Metric.read` this is eager: the file is opened, parsed, and closed before it
        returns, so IO and validation errors surface here rather than partway through
        iteration. Use `PicardMetricReader` directly to stream a large file.

        Args:
            path: Filesystem path to the input file.
            delimiter: The input file delimiter. Picard always writes tabs.
            fieldnames: Not supported; see `PicardMetricReader.__init__`.
            encoding: The text encoding used to decode the file.

        Returns:
            A list of instances of the calling class, one per data row of the file's first
            `## METRICS CLASS` section.

        Raises:
            FileNotFoundError: If `path` does not exist.
            ValueError: If `fieldnames` is supplied, or if the file has content but no
                `## METRICS CLASS` section.
            ValidationError: If a row fails validation, e.g. a column the model does not
                declare or a value of the wrong type.

        Example:
            ```python
            metrics = AlignmentSummaryMetric.read("example.alignment_summary_metrics")
            print(f"read {len(metrics)} rows")
            ```
        """
        with PicardMetricReader.open(
            cls,
            path,
            delimiter=delimiter,
            fieldnames=fieldnames,
            encoding=encoding,
        ) as reader:
            return list(reader)
