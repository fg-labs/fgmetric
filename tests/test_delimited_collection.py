from pathlib import Path
from typing import Annotated

import pytest
from pydantic import BaseModel
from pydantic import PlainSerializer
from pydantic import ValidationError

from fgmetric import Metric
from fgmetric import MetricReader
from fgmetric import MetricWriter
from fgmetric.converters import DelimitedCollection


def test_comma_delimited_list(tmp_path: Path) -> None:
    """Test that we can read and write comma-delimited lists."""

    class FakeMetric(Metric):
        name: str
        values: list[int]

    assert FakeMetric._collection_fieldnames == {"values"}
    assert FakeMetric._is_collection_field("values")

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

    assert FakeMetric._collection_fieldnames == {"values"}
    assert FakeMetric._is_collection_field("values")

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


def test_metric_is_built_on_delimited_collection() -> None:
    """`DelimitedCollection` is the canonical mixin; `Metric` is built on it."""

    class FakeMetric(Metric):
        values: list[int]

    assert issubclass(Metric, DelimitedCollection)
    assert issubclass(FakeMetric, DelimitedCollection)


def test_collection_handling_is_opt_in() -> None:
    """A model mixing in only `DelimitedCollection` handles collections but not mappings."""

    class CollectionOnly(DelimitedCollection, BaseModel):
        tags: list[int]
        counts: dict[str, int]

    assert CollectionOnly._handles_collections
    assert not CollectionOnly._handles_mappings

    # The list field is split from a string; the dict field is left for Pydantic to handle, so a
    # delimited string is not accepted as a dict.
    m = CollectionOnly.model_validate({"tags": "1,2", "counts": {"a": 1}})
    assert m.tags == [1, 2]
    with pytest.raises(ValidationError):
        CollectionOnly.model_validate({"tags": "1,2", "counts": "a=1"})


def test_set_field_roundtrip() -> None:
    """A set[T] field parses from and serializes to a delimited string."""

    class FakeMetric(Metric):
        values: set[int]

    assert FakeMetric._collection_fieldnames == {"values"}

    m = FakeMetric.model_validate({"values": "3,1,2"})
    assert m.values == {1, 2, 3}

    # Sets have no order, so output is sorted by serialized form for a stable roundtrip.
    assert m.model_dump()["values"] == "1,2,3"


def test_set_output_is_sorted_stably() -> None:
    """Set serialization is stable: sorted by serialized element form regardless of insertion."""

    class FakeMetric(Metric):
        values: set[str]

    assert FakeMetric(values={"banana", "apple", "cherry"}).model_dump()["values"] == (
        "apple,banana,cherry"
    )


def test_empty_set_field() -> None:
    """An empty cell parses to an empty set and serializes back to an empty cell."""

    class FakeMetric(Metric):
        values: set[int]

    m = FakeMetric.model_validate({"values": ""})
    assert m.values == set()
    assert m.model_dump()["values"] == ""


def test_frozenset_field_roundtrip() -> None:
    """A frozenset[T] field parses from and serializes to a sorted delimited string."""

    class FakeMetric(Metric):
        values: frozenset[int]

    assert FakeMetric._collection_fieldnames == {"values"}

    m = FakeMetric.model_validate({"values": "3,1,2"})
    assert m.values == frozenset({1, 2, 3})
    assert m.model_dump()["values"] == "1,2,3"


def test_homogeneous_tuple_field_roundtrip() -> None:
    """A variadic tuple[T, ...] field parses and serializes preserving order."""

    class FakeMetric(Metric):
        values: tuple[int, ...]

    assert FakeMetric._collection_fieldnames == {"values"}

    m = FakeMetric.model_validate({"values": "3,1,2"})
    assert m.values == (3, 1, 2)
    # Tuples are ordered, so order is preserved (not sorted).
    assert m.model_dump()["values"] == "3,1,2"


def test_heterogeneous_tuple_field_roundtrip() -> None:
    """A fixed-arity tuple[int, str] field validates arity and per-position types."""

    class FakeMetric(Metric):
        values: tuple[int, str]

    m = FakeMetric.model_validate({"values": "1,foo"})
    assert m.values == (1, "foo")
    assert m.model_dump()["values"] == "1,foo"


def test_heterogeneous_tuple_arity_is_validated() -> None:
    """A fixed-arity tuple rejects the wrong number of elements."""

    class FakeMetric(Metric):
        values: tuple[int, str]

    with pytest.raises(ValueError):
        FakeMetric.model_validate({"values": "1,foo,extra"})


def test_set_with_optional_elements() -> None:
    """A set[T | None] field maps empty elements to None."""

    class FakeMetric(Metric):
        values: set[int | None]

    m = FakeMetric.model_validate({"values": "1,,3"})
    assert m.values == {1, None, 3}
    # Sorted by serialized form: "" (None) sorts before "1" and "3".
    assert m.model_dump()["values"] == ",1,3"


def test_tuple_with_optional_position() -> None:
    """A fixed tuple maps an empty element to None only at optional positions."""

    class FakeMetric(Metric):
        values: tuple[str, int | None]

    # Position 0 (str) keeps the empty string; position 1 (int | None) becomes None.
    m = FakeMetric.model_validate({"values": ",5"})
    assert m.values == ("", 5)

    m2 = FakeMetric.model_validate({"values": "name,"})
    assert m2.values == ("name", None)
    assert m2.model_dump()["values"] == "name,"
