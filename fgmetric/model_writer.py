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
from fgmetric.record_model import RecordModel


class ModelWriter[T: RecordModel]:
    """
    Write `RecordModel` instances to a text IO sink.

    Construction takes a writable text IO and writes the header row immediately.
    The writer does not own the sink; callers manage its lifecycle. Use the
    `open` classmethod to open and write to a file in one step; unlike direct
    construction, `open` owns the file it opens and closes it on context exit.
    """

    _model_class: type[T]
    _writer: DictWriter[str]

    def __init__(
        self,
        model_class: type[T],
        sink: TextIO,
        delimiter: str = "\t",
        lineterminator: str = "\n",
    ) -> None:
        """
        Initialize a new `ModelWriter` and write the header row to `sink`.

        Args:
            model_class: The `RecordModel` subclass whose instances will be written.
            sink: Writable text IO (e.g., file handle, StringIO) to write to.
            delimiter: The output file delimiter.
            lineterminator: The string used to terminate lines.
        """
        self._model_class = model_class
        self._writer = DictWriter(
            f=sink,
            fieldnames=model_class._header_fieldnames(),
            delimiter=delimiter,
            lineterminator=lineterminator,
        )
        self._writer.writeheader()

    @classmethod
    @contextmanager
    def open(
        cls,
        model_class: type[T],
        path: Path | str,
        delimiter: str | None = None,
        lineterminator: str = "\n",
        encoding: str = "utf-8",
        overwrite: bool = False,
    ) -> Iterator[Self]:
        """
        Open `path` for writing and yield a `ModelWriter` over it.

        This is a context manager: bind it in a `with` statement and write through the writer
        it yields. `writer = ModelWriter.open(...)` without `with` binds the context manager
        itself, not a writer.

        Compression is selected automatically based on the output file extension: plaintext, gzip
        (`.gz`), bzip2 (`.bz2`), or xz (`.xz`).

        The header is written on context entry; the file is closed on context exit.

        Args:
            model_class: The `RecordModel` subclass whose instances will be written.
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
            A `ModelWriter` over the opened file.

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
            with ModelWriter.open(AlignmentMetric, "metrics.txt") as writer:
                writer.writeall(metrics)
            ```
        """
        if (error := path_write_error(path, overwrite=overwrite)) is not None:
            raise error
        if delimiter is None:
            delimiter = infer_delimiter(path)
        with xopen(path, mode="wt", encoding=encoding) as handle:
            yield cls(model_class, handle, delimiter, lineterminator)

    def write(self, model: T) -> None:
        """
        Write a single `RecordModel` instance.

        Args:
            model: An instance of the writer's model class.
        """
        self._writer.writerow(model.model_dump(mode="json", by_alias=True))

    def writeall(self, models: Iterable[T]) -> None:
        """
        Write multiple `RecordModel` instances.

        Args:
            models: An iterable of instances of the writer's model class.
        """
        for model in models:
            self.write(model)
