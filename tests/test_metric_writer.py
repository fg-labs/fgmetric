from collections import Counter
from enum import StrEnum
from enum import unique
from pathlib import Path
from typing import assert_type
from unittest import mock

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
    with MetricWriter(FakeMetric, fpath) as writer:
        assert_type(writer, MetricWriter[FakeMetric])
        writer.write(FakeMetric(foo="abc", bar=1))
        writer.write(FakeMetric(foo="def", bar=2))

    with fpath.open("r") as f:
        assert next(f) == "foo\tbar\n"
        assert next(f) == "abc\t1\n"
        assert next(f) == "def\t2\n"
        with pytest.raises(StopIteration):
            next(f)


def test_init_closes_file_on_failure(tmp_path: Path) -> None:
    """Test that the file handle is closed if __init__ raises after opening."""
    fpath = tmp_path / "test.txt"
    fpath.touch()
    real_fout = fpath.open("w")

    with (
        mock.patch("fgmetric.metric_writer.Path.open", return_value=real_fout),
        mock.patch.object(FakeMetric, "_header_fieldnames", side_effect=ValueError("boom")),
        pytest.raises(ValueError, match="boom"),
    ):
        MetricWriter(FakeMetric, fpath)

    assert real_fout.closed


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

    with MetricWriter(CounterMetric, fpath) as writer:
        writer.write(CounterMetric(name="test", counts=Counter({FakeEnum.FOO: 3, FakeEnum.BAR: 4})))

    with fpath.open("r") as f:
        assert next(f) == "name\tfoo\tbar\n"
        assert next(f) == "test\t3\t4\n"
        with pytest.raises(StopIteration):
            next(f)
