from pathlib import Path
from typing import Annotated

import pytest
from pydantic import PlainSerializer

from fgmetric import Metric
from fgmetric import MetricReader
from fgmetric import MetricWriter


def test_comma_delimited_list(tmp_path: Path) -> None:
    """Test that we can read and write comma-delimited lists."""

    class FakeMetric(Metric):
        name: str
        values: list[int]

    assert FakeMetric._list_fieldnames == {"values"}
    assert FakeMetric._is_list_field("values")

    # Test reading
    fpath_to_read = tmp_path / "test.txt"
    with fpath_to_read.open("w") as fout:
        fout.write("name\tvalues\n")
        fout.write("Nils\t1,2,3\n")
        fout.write("Tim\t\n")

    with MetricReader.open(FakeMetric, fpath_to_read) as reader:
        metrics = list(reader)

    assert len(metrics) == 2
    assert metrics[0].name == "Nils"
    assert metrics[0].values == [1, 2, 3]
    assert metrics[1].name == "Tim"
    assert metrics[1].values == []

    # Test writing
    fpath_to_write = tmp_path / "written.txt"
    writer: MetricWriter[FakeMetric]
    with MetricWriter.open(FakeMetric, fpath_to_write) as writer:
        writer.writeall(metrics)

    with fpath_to_write.open("r") as f:
        assert next(f) == "name\tvalues\n"
        assert next(f) == "Nils\t1,2,3\n"
        assert next(f) == "Tim\t\n"
        with pytest.raises(StopIteration):
            next(f)


def test_other_delimited_list(tmp_path: Path) -> None:
    """Test that we can read and write lists with other delimiters."""

    class FakeMetric(Metric):
        collection_delimiter = ";"

        name: str
        values: list[int]

    # Test reading
    fpath_to_read = tmp_path / "test.txt"
    with fpath_to_read.open("w") as fout:
        fout.write("name\tvalues\n")
        fout.write("Tim\t1;2;3\n")

    with MetricReader.open(FakeMetric, fpath_to_read) as reader:
        metrics = list(reader)

    assert len(metrics) == 1
    assert metrics[0].name == "Tim"
    assert metrics[0].values == [1, 2, 3]

    # Test writing
    fpath_to_write = tmp_path / "written.txt"
    writer: MetricWriter[FakeMetric]
    with MetricWriter.open(FakeMetric, fpath_to_write) as writer:
        writer.write(metrics[0])

    with fpath_to_write.open("r") as f:
        assert next(f) == "name\tvalues\n"
        assert next(f) == "Tim\t1;2;3\n"
        with pytest.raises(StopIteration):
            next(f)


def test_delimited_list_with_complex_types(tmp_path: Path) -> None:
    """Test that we can read and write lists with custom formatting."""

    class FakeMetric(Metric):
        name: str
        values: list[Annotated[float, PlainSerializer(lambda x: f"{x:.3f}")]]

    # Test writing
    fpath_to_write = tmp_path / "written.txt"
    writer: MetricWriter[FakeMetric]
    with MetricWriter.open(FakeMetric, fpath_to_write) as writer:
        writer.write(FakeMetric(name="Clint", values=[0.1, 0.002, 0.00301]))

    with fpath_to_write.open("r") as f:
        assert next(f) == "name\tvalues\n"
        assert next(f) == "Clint\t0.100,0.002,0.003\n"
        with pytest.raises(StopIteration):
            next(f)


def test_delimited_list_with_optional_field(tmp_path: Path) -> None:
    """Test that we can read and write lists with empty Optional fields."""

    class FakeMetric(Metric):
        name: str
        values: list[int] | None

    assert FakeMetric._list_fieldnames == {"values"}
    assert FakeMetric._is_list_field("values")

    # Test reading
    fpath_to_read = tmp_path / "test.txt"
    with fpath_to_read.open("w") as fout:
        fout.write("name\tvalues\n")
        fout.write("Nils\t\n")
        fout.write("Tim\t1,2,3\n")

    with MetricReader.open(FakeMetric, fpath_to_read) as reader:
        metrics = list(reader)

    assert len(metrics) == 2
    assert metrics[0].name == "Nils"
    assert metrics[0].values is None
    assert metrics[1].name == "Tim"
    assert metrics[1].values == [1, 2, 3]

    # Test writing
    fpath_to_write = tmp_path / "written.txt"
    writer: MetricWriter[FakeMetric]
    with MetricWriter.open(FakeMetric, fpath_to_write) as writer:
        writer.writeall(metrics)

    with fpath_to_write.open("r") as f:
        assert next(f) == "name\tvalues\n"
        assert next(f) == "Nils\t\n"
        assert next(f) == "Tim\t1,2,3\n"
        with pytest.raises(StopIteration):
            next(f)


def test_list_with_optional_elements() -> None:
    """Test that list[T | None] handles empty elements as None."""

    class FakeMetric(Metric):
        name: str
        values: list[int | None]

    m = FakeMetric.model_validate({"name": "test", "values": "1,,3"})
    assert m.values == [1, None, 3]


def test_list_with_optional_elements_roundtrip() -> None:
    """Test roundtrip for list[T | None]."""

    class FakeMetric(Metric):
        values: list[int | None]

    m = FakeMetric(values=[1, None, 3])
    serialized = m.model_dump()
    assert serialized["values"] == "1,,3"


def test_list_field_round_trips_through_inferred_csv(tmp_path: Path) -> None:
    """A list field survives the inferred comma CSV delimiter via CSV quoting."""

    class FakeMetric(Metric):
        name: str
        tags: list[str]

    p = tmp_path / "metrics.csv"  # `.csv` infers a comma delimiter
    metric = FakeMetric(name="alice", tags=["x", "y", "z"])
    with MetricWriter.open(FakeMetric, p) as writer:
        writer.write(metric)

    # The list serializes to "x,y,z", whose commas collide with the comma delimiter, so csv
    # quote-protects the field on disk rather than splitting it into extra columns.
    assert p.read_text() == 'name,tags\nalice,"x,y,z"\n'

    with MetricReader.open(FakeMetric, p) as reader:
        assert list(reader) == [metric]
