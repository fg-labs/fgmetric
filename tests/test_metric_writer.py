from collections import Counter
from enum import StrEnum
from enum import unique
from io import StringIO
from pathlib import Path
from typing import assert_type

import pytest

from fgmetric import Metric
from fgmetric import MetricReader
from fgmetric import MetricWriter


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


def test_writer_open_respects_encoding(tmp_path: Path) -> None:
    """Test that MetricWriter.open writes with the specified encoding."""
    p = tmp_path / "out.tsv"
    with MetricWriter.open(FakeMetric, p, encoding="latin-1") as writer:
        writer.write(FakeMetric(foo="rené", bar=1))
    assert p.read_bytes() == "foo\tbar\nrené\t1\n".encode("latin-1")


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


@pytest.mark.parametrize("suffix", ["", ".gz", ".bz2", ".xz"])
def test_writer_append_to_empty_file_writes_header_across_formats(
    tmp_path: Path, suffix: str
) -> None:
    """Append-or-create to an existing empty file writes the header first, for every format."""
    p = tmp_path / f"out.tsv{suffix}"
    p.touch()  # 0-byte file
    with MetricWriter.open(FakeMetric, p, mode="a") as writer:
        writer.write(FakeMetric(foo="a", bar=1))

    with MetricReader.open(FakeMetric, p) as reader_:
        assert list(reader_) == [FakeMetric(foo="a", bar=1)]


def test_writer_append_concatenates_when_last_line_lacks_newline(tmp_path: Path) -> None:
    """Appending after a newline-less last line concatenates the new row, as documented."""
    p = tmp_path / "out.tsv"
    p.write_text("foo\tbar\na\t1")  # header + one row, no trailing newline
    with MetricWriter.open(FakeMetric, p, mode="a") as writer:
        writer.write(FakeMetric(foo="b", bar=2))
    assert p.read_text() == "foo\tbar\na\t1b\t2\n"
