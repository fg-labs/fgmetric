from collections import Counter
from collections.abc import Callable
from enum import StrEnum
from enum import unique
from io import StringIO
from pathlib import Path
from typing import ClassVar
from typing import assert_type

import pytest
from pydantic import Field
from pytest_mock import MockerFixture

from fgmetric import Metric
from fgmetric import MetricReader
from fgmetric import MetricWriter
from fgmetric import metric_writer


class FakeMetric(Metric):
    """A fake Metric to use in tests."""

    foo: str
    bar: int


def test_writer(tmp_path: Path) -> None:
    """Test we can write a Metric to file."""
    fpath = tmp_path / "test.txt"

    writer: MetricWriter[FakeMetric]
    with MetricWriter.open(FakeMetric, fpath) as writer:
        assert_type(writer, MetricWriter[FakeMetric])
        writer.write(FakeMetric(foo="abc", bar=1))
        writer.write(FakeMetric(foo="def", bar=2))

    with fpath.open("r") as f:
        assert next(f) == "foo\tbar\n"
        assert next(f) == "abc\t1\n"
        assert next(f) == "def\t2\n"
        with pytest.raises(StopIteration):
            next(f)


def test_writer_with_counter_metric(tmp_path: Path) -> None:
    """Test we can write a Counter metric through MetricWriter."""

    @unique
    class FakeEnum(StrEnum):
        FOO = "foo"
        BAR = "bar"

    class CounterMetric(Metric):
        name: str
        counts: Counter[FakeEnum]

    fpath = tmp_path / "test.txt"

    with MetricWriter.open(CounterMetric, fpath) as writer:
        writer.write(CounterMetric(name="test", counts=Counter({FakeEnum.FOO: 3, FakeEnum.BAR: 4})))

    with fpath.open("r") as f:
        assert next(f) == "name\tfoo\tbar\n"
        assert next(f) == "test\t3\t4\n"
        with pytest.raises(StopIteration):
            next(f)


def test_writer_accepts_text_io_and_writes_to_it() -> None:
    """A writer constructed with a TextIO sink writes to that sink."""
    sink = StringIO()
    writer = MetricWriter(FakeMetric, sink)
    writer.write(FakeMetric(foo="abc", bar=1))
    assert sink.getvalue() == "foo\tbar\nabc\t1\n"


def test_writer_writes_header_at_construction() -> None:
    """The header row is written immediately on construction."""
    sink = StringIO()
    MetricWriter(FakeMetric, sink)
    assert sink.getvalue() == "foo\tbar\n"


def test_writer_does_not_close_caller_handle() -> None:
    """A caller-supplied sink is not closed by the writer."""
    sink = StringIO()
    writer = MetricWriter(FakeMetric, sink)
    writer.write(FakeMetric(foo="abc", bar=1))
    assert not sink.closed


def test_writer_uses_field_aliases() -> None:
    """A field alias appears in both the header and the rows."""

    class AliasMetric(Metric):
        name: str
        read_count: int = Field(alias="count")

    sink = StringIO()
    writer = MetricWriter(AliasMetric, sink)
    # `read_count` must be populated via its alias.
    writer.write(AliasMetric(name="foo", count=100))
    assert sink.getvalue() == "name\tcount\nfoo\t100\n"


def test_writer_uses_custom_column_delimiter() -> None:
    """
    A custom column delimiter is applied to the header and rows.

    The column delimiter is independent of `collection_delimiter`, which joins list elements
    *within* a single cell.
    """

    class ListMetric(Metric):
        collection_delimiter: ClassVar[str] = ";"
        name: str
        tags: list[int]

    sink = StringIO()
    writer = MetricWriter(ListMetric, sink, delimiter=",")
    writer.write(ListMetric(name="x", tags=[1, 2, 3]))
    # Columns are separated by the writer's "," delimiter; elements inside the `tags` cell are
    # joined by the ";" collection_delimiter.
    assert sink.getvalue() == "name,tags\nx,1;2;3\n"


def test_writer_uses_custom_lineterminator() -> None:
    """A custom line terminator ends both the header and the rows."""
    sink = StringIO()
    writer = MetricWriter(FakeMetric, sink, lineterminator="\r\n")
    writer.write(FakeMetric(foo="abc", bar=1))
    assert sink.getvalue() == "foo\tbar\r\nabc\t1\r\n"


def test_writer_open_writes_header_and_rows(tmp_path: Path) -> None:
    """Test that MetricWriter.open opens a file, writes the header, and writes rows."""
    p = tmp_path / "out.tsv"
    with MetricWriter.open(FakeMetric, p) as writer:
        writer.write(FakeMetric(foo="abc", bar=1))
    assert p.read_text() == "foo\tbar\nabc\t1\n"


def test_writer_open_does_not_touch_file_until_enter(tmp_path: Path) -> None:
    """Test that MetricWriter.open does not open the file until the context is entered."""
    p = tmp_path / "out.tsv"
    p.write_text("existing content\n")
    MetricWriter.open(FakeMetric, p)
    # Construction alone must not truncate or rewrite the file.
    assert p.read_text() == "existing content\n"


def test_writer_open_infers_delimiter_from_extension(tmp_path: Path) -> None:
    """Test that MetricWriter.open writes a .csv file as comma-delimited by default."""
    p = tmp_path / "out.csv"
    with MetricWriter.open(FakeMetric, p) as writer:
        writer.write(FakeMetric(foo="abc", bar=1))
    assert p.read_text() == "foo,bar\nabc,1\n"


def test_writer_open_explicit_delimiter_overrides_inference(tmp_path: Path) -> None:
    """Test that an explicit delimiter wins over the extension-inferred one."""
    p = tmp_path / "out.csv"
    with MetricWriter.open(FakeMetric, p, delimiter="\t") as writer:
        writer.write(FakeMetric(foo="abc", bar=1))
    assert p.read_text() == "foo\tbar\nabc\t1\n"


def test_writer_open_raises_for_uninferrable_delimiter(tmp_path: Path) -> None:
    """Test that an unrecognized extension raises when no delimiter is given."""
    p = tmp_path / "out.dat"
    with pytest.raises(ValueError, match="Could not infer a delimiter"):
        with MetricWriter.open(FakeMetric, p):
            pass
    # The file must not be created when inference fails.
    assert not p.exists()


def test_writer_open_respects_encoding(tmp_path: Path) -> None:
    """Test that MetricWriter.open writes with the specified encoding."""
    p = tmp_path / "out.tsv"
    with MetricWriter.open(FakeMetric, p, encoding="latin-1") as writer:
        writer.write(FakeMetric(foo="rené", bar=1))
    assert p.read_bytes() == "foo\tbar\nrené\t1\n".encode("latin-1")


def test_writer_open_closes_owned_file(tmp_path: Path, mocker: MockerFixture) -> None:
    """MetricWriter.open closes the file it owns when the context exits."""
    spy = mocker.spy(metric_writer, "xopen")
    p = tmp_path / "out.tsv"
    with MetricWriter.open(FakeMetric, p) as writer:
        writer.write(FakeMetric(foo="abc", bar=1))
    # `open` opened exactly one file; spy_return is that handle, which must now be closed.
    assert spy.spy_return.closed


def test_writer_open_closes_owned_file_on_exception(tmp_path: Path, mocker: MockerFixture) -> None:
    """MetricWriter.open closes the file it owns even when the context body raises."""
    spy = mocker.spy(metric_writer, "xopen")
    p = tmp_path / "out.tsv"
    with pytest.raises(RuntimeError, match="boom"):
        with MetricWriter.open(FakeMetric, p) as writer:
            writer.write(FakeMetric(foo="abc", bar=1))
            raise RuntimeError("boom")
    assert spy.spy_return.closed


def test_writer_open_raises_file_not_found_for_missing_parent(tmp_path: Path) -> None:
    """MetricWriter.open raises FileNotFoundError when the parent directory does not exist."""
    with pytest.raises(FileNotFoundError, match="does not exist"):
        with MetricWriter.open(FakeMetric, tmp_path / "missing" / "out.tsv"):
            pass


def test_writer_open_raises_is_a_directory_for_directory(tmp_path: Path) -> None:
    """MetricWriter.open raises IsADirectoryError when the path is a directory."""
    with pytest.raises(IsADirectoryError, match="is a directory"):
        with MetricWriter.open(FakeMetric, tmp_path):
            pass


def test_writer_open_raises_permission_error_for_readonly_file(
    tmp_path: Path, chmod: Callable[[Path, int], None]
) -> None:
    """MetricWriter.open raises PermissionError when the target file is not writable."""
    p = tmp_path / "out.tsv"
    p.write_text("locked\n")
    chmod(p, 0o444)
    with pytest.raises(PermissionError, match="not writable"):
        with MetricWriter.open(FakeMetric, p):
            pass
    # The check must fire before the file is opened, so the contents are untouched.
    assert p.read_text() == "locked\n"


def test_writer_open_raises_permission_error_for_readonly_parent(
    tmp_path: Path, chmod: Callable[[Path, int], None]
) -> None:
    """MetricWriter.open raises PermissionError when the parent directory is not writable."""
    d = tmp_path / "readonly"
    d.mkdir()
    chmod(d, 0o555)
    with pytest.raises(PermissionError, match="not writable"):
        with MetricWriter.open(FakeMetric, d / "out.tsv"):
            pass


def test_writer_open_refuses_to_overwrite_existing_file_by_default(tmp_path: Path) -> None:
    """MetricWriter.open refuses to clobber an existing file unless `overwrite=True`."""
    p = tmp_path / "out.tsv"
    p.write_text("existing\n")
    with pytest.raises(FileExistsError, match="already exists"):
        with MetricWriter.open(FakeMetric, p):
            pass
    # The refusal must fire before the file is opened, so the contents are untouched.
    assert p.read_text() == "existing\n"


def test_writer_open_overwrites_existing_file_when_overwrite_true(tmp_path: Path) -> None:
    """With `overwrite=True`, MetricWriter.open truncates and rewrites an existing file."""
    p = tmp_path / "out.tsv"
    p.write_text("stale\tcontent\nto be replaced\n")
    with MetricWriter.open(FakeMetric, p, overwrite=True) as writer:
        writer.write(FakeMetric(foo="abc", bar=1))
    assert p.read_text() == "foo\tbar\nabc\t1\n"


def test_writer_constructor_can_skip_header() -> None:
    """A writer constructed with write_header=False writes no header row."""
    sink = StringIO()
    writer = MetricWriter(FakeMetric, sink, write_header=False)
    writer.write(FakeMetric(foo="abc", bar=1))
    assert sink.getvalue() == "abc\t1\n"


def test_writer_append_skips_header_on_existing_file(tmp_path: Path) -> None:
    """Appending to a file that already has a matching header does not rewrite it."""
    p = tmp_path / "out.tsv"
    with MetricWriter.open(FakeMetric, p, mode="w") as writer:
        writer.write(FakeMetric(foo="a", bar=1))
    with MetricWriter.open(FakeMetric, p, mode="a") as writer:
        writer.write(FakeMetric(foo="b", bar=2))
    assert p.read_text() == "foo\tbar\na\t1\nb\t2\n"


def test_writer_append_writes_header_when_file_missing(tmp_path: Path) -> None:
    """Append-or-create: appending to a missing file writes the header first."""
    p = tmp_path / "out.tsv"  # does not exist
    with MetricWriter.open(FakeMetric, p, mode="a") as writer:
        writer.write(FakeMetric(foo="a", bar=1))
    assert p.read_text() == "foo\tbar\na\t1\n"


def test_writer_append_writes_header_when_file_empty(tmp_path: Path) -> None:
    """Appending to an existing empty file writes the header first."""
    p = tmp_path / "out.tsv"
    p.touch()
    with MetricWriter.open(FakeMetric, p, mode="a") as writer:
        writer.write(FakeMetric(foo="a", bar=1))
    assert p.read_text() == "foo\tbar\na\t1\n"


def test_writer_append_accepts_matching_header(tmp_path: Path) -> None:
    """Appending to a file whose header matches the metric fields succeeds."""
    p = tmp_path / "out.tsv"
    p.write_text("foo\tbar\n")
    with MetricWriter.open(FakeMetric, p, mode="a") as writer:
        writer.write(FakeMetric(foo="a", bar=1))
    assert p.read_text() == "foo\tbar\na\t1\n"


def test_writer_append_raises_on_header_mismatch(tmp_path: Path) -> None:
    """Appending to a file whose header does not match the metric fields raises."""
    p = tmp_path / "out.tsv"
    p.write_text("wrong\theader\n")
    with pytest.raises(ValueError, match="does not match"):
        with MetricWriter.open(FakeMetric, p, mode="a"):
            pass


def test_writer_open_append_does_not_touch_file_until_enter(tmp_path: Path) -> None:
    """open(mode="a") must not read or write the file until the context is entered."""
    p = tmp_path / "out.tsv"
    p.write_text("foo\tbar\n")
    MetricWriter.open(FakeMetric, p, mode="a")
    assert p.read_text() == "foo\tbar\n"


@pytest.mark.parametrize("suffix", ["", ".gz", ".bz2", ".xz"])
def test_writer_append_round_trips_across_formats(tmp_path: Path, suffix: str) -> None:
    """Write then append then read back yields all rows, header-once, for every format."""
    p = tmp_path / f"out.tsv{suffix}"
    with MetricWriter.open(FakeMetric, p, mode="w") as writer:
        writer.write(FakeMetric(foo="a", bar=1))
    with MetricWriter.open(FakeMetric, p, mode="a") as writer:
        writer.write(FakeMetric(foo="b", bar=2))

    with MetricReader.open(FakeMetric, p) as reader_:
        got = list(reader_)

    assert got == [FakeMetric(foo="a", bar=1), FakeMetric(foo="b", bar=2)]
