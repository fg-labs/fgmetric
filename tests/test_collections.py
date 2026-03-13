from collections import Counter
from enum import StrEnum
from enum import unique
from pathlib import Path
from typing import Annotated

import pytest
from pydantic import PlainSerializer

from fgmetric import Metric
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

    metrics = list(FakeMetric.read(fpath_to_read))

    assert len(metrics) == 2
    assert metrics[0].name == "Nils"
    assert metrics[0].values == [1, 2, 3]
    assert metrics[1].name == "Tim"
    assert metrics[1].values == []

    # Test writing
    fpath_to_write = tmp_path / "written.txt"
    writer: MetricWriter[FakeMetric]
    with MetricWriter(FakeMetric, fpath_to_write) as writer:
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

    metrics = list(FakeMetric.read(fpath_to_read))

    assert len(metrics) == 1
    assert metrics[0].name == "Tim"
    assert metrics[0].values == [1, 2, 3]

    # Test writing
    fpath_to_write = tmp_path / "written.txt"
    writer: MetricWriter[FakeMetric]
    with MetricWriter(FakeMetric, fpath_to_write) as writer:
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
    with MetricWriter(FakeMetric, fpath_to_write) as writer:
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

    metrics = list(FakeMetric.read(fpath_to_read))

    assert len(metrics) == 2
    assert metrics[0].name == "Nils"
    assert metrics[0].values is None
    assert metrics[1].name == "Tim"
    assert metrics[1].values == [1, 2, 3]

    # Test writing
    fpath_to_write = tmp_path / "written.txt"
    writer: MetricWriter[FakeMetric]
    with MetricWriter(FakeMetric, fpath_to_write) as writer:
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


def test_counter_pivot_table_of_enum(tmp_path: Path) -> None:
    """Test that we can read and write Counters as pivot tables."""

    @unique
    class FakeEnum(StrEnum):
        FOO = "foo"
        BAR = "bar"

    class FakeMetric(Metric):
        name: str
        counts: Counter[FakeEnum]

    # Test reading
    fpath_to_read = tmp_path / "test.txt"
    with fpath_to_read.open("w") as fout:
        fout.write("name\tfoo\tbar\n")
        fout.write("Nils\t1\t2\n")

    metrics = list(FakeMetric.read(fpath_to_read))

    assert len(metrics) == 1
    metric = metrics[0]
    assert metric.name == "Nils"
    assert metric.counts == Counter({FakeEnum.FOO: 1, FakeEnum.BAR: 2})

    # Test writing
    fpath_to_write = tmp_path / "written.txt"

    writer: MetricWriter[FakeMetric]
    with MetricWriter(FakeMetric, fpath_to_write) as writer:
        writer.write(FakeMetric(name="Tim", counts=Counter({FakeEnum.FOO: 3, FakeEnum.BAR: 4})))

    with fpath_to_write.open("r") as f:
        assert next(f) == "name\tfoo\tbar\n"
        assert next(f) == "Tim\t3\t4\n"
        with pytest.raises(StopIteration):
            next(f)


def test_counter_pivot_table_model_dump_json_mode() -> None:
    """Test that model_dump(mode='json') works with Counter pivot tables."""

    @unique
    class FakeEnum(StrEnum):
        FOO = "foo"
        BAR = "bar"

    class FakeMetric(Metric):
        name: str
        counts: Counter[FakeEnum]

    metric = FakeMetric(name="test", counts=Counter({FakeEnum.FOO: 1, FakeEnum.BAR: 2}))
    result = metric.model_dump(mode="json")

    assert result == {"name": "test", "foo": 1, "bar": 2}


def test_counter_pivot_table_missing_enum_members_default_to_zero(tmp_path: Path) -> None:
    """Test that missing enum members in input default to 0."""

    @unique
    class FakeEnum(StrEnum):
        FOO = "foo"
        BAR = "bar"
        BAZ = "baz"

    class FakeMetric(Metric):
        name: str
        counts: Counter[FakeEnum]

    # Input only has "foo" column, missing "bar" and "baz"
    fpath = tmp_path / "test.txt"
    with fpath.open("w") as fout:
        fout.write("name\tfoo\n")
        fout.write("test\t5\n")

    metrics = list(FakeMetric.read(fpath))

    assert len(metrics) == 1
    metric = metrics[0]
    assert metric.counts[FakeEnum.FOO] == 5
    assert metric.counts[FakeEnum.BAR] == 0
    assert metric.counts[FakeEnum.BAZ] == 0


def test_counter_pivot_table_raises_if_not_enum() -> None:
    """Test we can flag type errors when declaring class."""
    with pytest.raises(TypeError) as excinfo:

        class FakeMetric(Metric):
            name: str
            counts: Counter[str]

    assert str(excinfo.value) == "Counter fields must have a StrEnum type parameter: counts"


def test_counter_pivot_table_raises_if_multiple_counters() -> None:

    @unique
    class FooEnum(StrEnum):
        FOO = "foo"

    @unique
    class BarEnum(StrEnum):
        BAR = "bar"

    with pytest.raises(TypeError) as excinfo:

        class FakeMetric(Metric):
            name: str
            foo_counts: Counter[FooEnum]
            bar_counts: Counter[BarEnum]

    assert str(excinfo.value) == (
        "Only one Counter per model is currently supported. "
        "Found multiple fields with Counter types: foo_counts, bar_counts"
    )


def test_counter_pivot_table_raises_if_optional_counter() -> None:

    @unique
    class FakeEnum(StrEnum):
        FOO = "foo"

    with pytest.raises(TypeError) as excinfo:

        class FakeMetric(Metric):
            name: str
            counts: Counter[FakeEnum] | None

    assert str(excinfo.value) == "Optional Counters are not supported: counts"
