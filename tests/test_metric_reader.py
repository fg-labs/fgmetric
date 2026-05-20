from io import StringIO
from pathlib import Path
from typing import assert_type

import pytest

from fgmetric.metric import Metric
from fgmetric.metric_reader import MetricReader


class ExampleMetric(Metric):
    """Example Metric subclass used in MetricReader tests."""

    name: str
    value: int


def test_reader_iterates_from_iterable() -> None:
    source = StringIO("name\tvalue\nalice\t1\nbob\t2\n")
    reader = MetricReader(ExampleMetric, source)
    assert_type(reader, MetricReader[ExampleMetric])
    metrics = list(reader)
    assert_type(metrics, list[ExampleMetric])
    assert metrics == [
        ExampleMetric(name="alice", value=1),
        ExampleMetric(name="bob", value=2),
    ]


def test_reader_supports_headerless_with_fieldnames() -> None:
    source = StringIO("alice\t1\nbob\t2\n")
    reader = MetricReader(ExampleMetric, source, fieldnames=["name", "value"])
    metrics = list(reader)
    assert metrics == [
        ExampleMetric(name="alice", value=1),
        ExampleMetric(name="bob", value=2),
    ]


def test_reader_rejects_fieldnames_matching_header_at_construction() -> None:
    source = StringIO("name\tvalue\nalice\t1\n")
    with pytest.raises(ValueError, match="appears to be a header"):
        MetricReader(ExampleMetric, source, fieldnames=["name", "value"])


def test_reader_does_not_close_caller_handle() -> None:
    source = StringIO("name\tvalue\nalice\t1\n")
    reader = MetricReader(ExampleMetric, source)
    list(reader)
    assert not source.closed


def test_open_reads_file(tmp_path: Path) -> None:
    p = tmp_path / "metrics.tsv"
    p.write_text("name\tvalue\nalice\t1\nbob\t2\n")
    with MetricReader.open(ExampleMetric, p) as reader:
        assert_type(reader, MetricReader[ExampleMetric])
        metrics = list(reader)
    assert_type(metrics, list[ExampleMetric])
    assert metrics == [
        ExampleMetric(name="alice", value=1),
        ExampleMetric(name="bob", value=2),
    ]


def test_open_does_not_open_file_until_enter(tmp_path: Path) -> None:
    p = tmp_path / "missing.tsv"
    cm = MetricReader.open(ExampleMetric, p)
    with pytest.raises(FileNotFoundError):
        with cm:
            pass


def test_open_requires_context_manager_usage(tmp_path: Path) -> None:
    p = tmp_path / "metrics.tsv"
    p.write_text("name\tvalue\nalice\t1\n")
    cm = MetricReader.open(ExampleMetric, p)
    with pytest.raises(TypeError):
        list(cm)  # type: ignore[call-overload]
