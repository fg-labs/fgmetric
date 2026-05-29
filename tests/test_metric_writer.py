from collections import Counter
from enum import StrEnum
from enum import unique
from io import StringIO
from pathlib import Path
from typing import assert_type

import pytest

from fgmetric import Metric
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
