from collections import Counter
from enum import StrEnum
from enum import unique
from pathlib import Path

from fgmetric import Metric
from fgmetric import ModelReader
from fgmetric import ModelWriter


class SimpleMetric(Metric):
    """A Metric with str and int fields."""

    name: str
    value: int


class OptionalScalarMetric(Metric):
    """A Metric with a scalar Optional field."""

    name: str
    value: int | None = None


def test_roundtrip_scalar_optional(tmp_path: Path) -> None:
    """A scalar Optional field round-trips, with None surviving the write-then-read cycle."""
    expected = [
        OptionalScalarMetric(name="alice", value=42),
        OptionalScalarMetric(name="bob", value=None),
    ]

    p = tmp_path / "metrics.tsv"
    with ModelWriter.open(OptionalScalarMetric, p) as writer:
        writer.writeall(expected)

    with ModelReader.open(OptionalScalarMetric, p) as reader:
        assert list(reader) == expected


def test_roundtrip_counter(tmp_path: Path) -> None:
    """A fully-populated Counter[StrEnum] field round-trips through write then read."""

    @unique
    class FakeEnum(StrEnum):
        FOO = "foo"
        BAR = "bar"

    class CounterMetric(Metric):
        name: str
        counts: Counter[FakeEnum]

    # Fully-populated case only; the absent-member path (must serialize as 0) is fixed in #60.
    expected = [
        CounterMetric(name="alice", counts=Counter({FakeEnum.FOO: 1, FakeEnum.BAR: 2})),
        CounterMetric(name="bob", counts=Counter({FakeEnum.FOO: 3, FakeEnum.BAR: 4})),
    ]

    p = tmp_path / "metrics.tsv"
    with ModelWriter.open(CounterMetric, p) as writer:
        writer.writeall(expected)

    with ModelReader.open(CounterMetric, p) as reader:
        assert list(reader) == expected


def test_roundtrip_empty_file(tmp_path: Path) -> None:
    """Writing zero rows produces a header-only file that reads back to an empty list."""
    p = tmp_path / "metrics.tsv"
    with ModelWriter.open(SimpleMetric, p) as writer:
        writer.writeall([])

    # The writer emits the header on context entry, so the file is header-only.
    assert p.read_bytes() == b"name\tvalue\n"

    with ModelReader.open(SimpleMetric, p) as reader:
        assert list(reader) == []
