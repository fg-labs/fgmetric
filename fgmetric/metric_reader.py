from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Sequence
from contextlib import contextmanager
from csv import DictReader
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Self

if TYPE_CHECKING:
    from fgmetric.metric import Metric


class MetricReader[T: Metric]:
    """
    Iterate `Metric` instances from a text IO source.

    Constructed with any iterable of strings (file handle, StringIO, list of
    lines). The reader does not own the source; callers manage its lifecycle.
    Use the `open` classmethod to open and read a file in one step.
    """

    _metric_class: type[T]
    _records: Iterator[dict[str, str | None]]

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
        delimiter: str = "\t",
        fieldnames: Sequence[str] | None = None,
    ) -> Iterator[Self]:
        """
        Open `path` and yield a `MetricReader` over its contents.

        The file is opened with `encoding="utf-8-sig"` (strips a UTF-8 BOM if
        present) and closed on context exit. Compression is not yet supported.

        Args:
            metric_class: Metric class.
            path: Filesystem path to the input file.
            delimiter: The input file delimiter.
            fieldnames: Optional sequence of field names. If provided, the input is
                treated as headerless and these names are used as the column
                headers.

        Yields:
            A `MetricReader` over the opened file.
        """
        with Path(path).open(encoding="utf-8-sig") as handle:
            yield cls(metric_class, handle, delimiter, fieldnames)

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> T:
        return self._metric_class.model_validate(next(self._records))
