from collections import Counter
from enum import StrEnum
from enum import unique
from pathlib import Path

import pytest
from pydantic import Field

from fgmetric import Metric
from fgmetric import MetricReader
from fgmetric import MetricWriter


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

    with MetricReader.open(FakeMetric, fpath_to_read) as reader:
        metrics = list(reader)

    assert len(metrics) == 1
    metric = metrics[0]
    assert metric.name == "Nils"
    assert metric.counts == Counter({FakeEnum.FOO: 1, FakeEnum.BAR: 2})

    # Test writing
    fpath_to_write = tmp_path / "written.txt"

    writer: MetricWriter[FakeMetric]
    with MetricWriter.open(FakeMetric, fpath_to_write) as writer:
        writer.write(FakeMetric(name="Tim", counts=Counter({FakeEnum.FOO: 3, FakeEnum.BAR: 4})))

    with fpath_to_write.open("r") as f:
        assert next(f) == "name\tfoo\tbar\n"
        assert next(f) == "Tim\t3\t4\n"
        with pytest.raises(StopIteration):
            next(f)


def test_counter_pivot_table_roundtrip_with_absent_member(tmp_path: Path) -> None:
    """A Counter missing an enum member serializes that member as 0 and reads back cleanly."""

    @unique
    class FakeEnum(StrEnum):
        FOO = "foo"
        BAR = "bar"

    class FakeMetric(Metric):
        name: str
        counts: Counter[FakeEnum]

    # BAR is absent on construction; it must be written as 0, not as an empty cell. Otherwise the
    # header's "bar" column is left empty on disk and read-back fails parsing "" as an int.
    fpath = tmp_path / "test.txt"
    writer: MetricWriter[FakeMetric]
    with MetricWriter.open(FakeMetric, fpath) as writer:
        writer.write(FakeMetric(name="Nils", counts=Counter({FakeEnum.FOO: 5})))

    assert fpath.read_text() == "name\tfoo\tbar\nNils\t5\t0\n"

    with MetricReader.open(FakeMetric, fpath) as reader:
        metrics = list(reader)

    assert metrics == [
        FakeMetric(name="Nils", counts=Counter({FakeEnum.FOO: 5, FakeEnum.BAR: 0})),
    ]


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

    with MetricReader.open(FakeMetric, fpath) as reader:
        metrics = list(reader)

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

    assert str(excinfo.value) == (
        "Counter fields must have a StrEnum type parameter,"
        " got collections.Counter[str] for field 'counts'"
    )


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
        "Found multiple Counter fields: foo_counts, bar_counts"
    )


def test_counter_pivot_table_raises_if_optional_counter() -> None:

    @unique
    class FakeEnum(StrEnum):
        FOO = "foo"

    with pytest.raises(TypeError) as excinfo:

        class FakeMetric(Metric):
            name: str
            counts: Counter[FakeEnum] | None

    assert str(excinfo.value) == "Optional Counter fields are not supported: 'counts'"


def test_counter_pivot_table_raises_if_aliased_counter() -> None:
    """
    A Counter field may not declare an alias of any kind.

    A Counter pivots into one column per enum member, so its field name never appears as a column
    on disk. An alias would therefore have nothing to rename, and (under ``by_alias=True``) would
    desync the serializer's lookup key from the dumped dict. Reject all three alias forms at
    class-definition time rather than crash later during serialization.
    """

    @unique
    class FakeEnum(StrEnum):
        FOO = "foo"

    expected = (
        "Aliased Counter fields are not supported: 'counts'. A Counter pivots into one column per "
        "enum member, so it has no on-disk column for an alias to rename."
    )

    with pytest.raises(TypeError) as excinfo:

        class AliasMetric(Metric):
            name: str
            counts: Counter[FakeEnum] = Field(alias="cts")

    assert str(excinfo.value) == expected

    with pytest.raises(TypeError) as excinfo:

        class ValidationAliasMetric(Metric):
            name: str
            counts: Counter[FakeEnum] = Field(validation_alias="cts")

    assert str(excinfo.value) == expected

    with pytest.raises(TypeError) as excinfo:

        class SerializationAliasMetric(Metric):
            name: str
            counts: Counter[FakeEnum] = Field(serialization_alias="cts")

    assert str(excinfo.value) == expected
