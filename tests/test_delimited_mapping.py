from collections import Counter
from enum import StrEnum
from pathlib import Path

import pytest
from pydantic import BaseModel
from pydantic import ValidationError

from fgmetric import Metric
from fgmetric import MetricReader
from fgmetric import MetricWriter
from fgmetric.converters import DelimitedMapping


def test_metric_is_built_on_delimited_mapping() -> None:
    """`DelimitedMapping` is mixed into `Metric`, so `dict` fields are supported by default."""

    class FakeMetric(Metric):
        counts: dict[str, int]

    assert issubclass(Metric, DelimitedMapping)
    assert FakeMetric._mapping_fieldnames == {"counts"}
    assert FakeMetric._is_mapping_field("counts")


def test_mapping_handling_is_opt_in() -> None:
    """A model mixing in only `DelimitedMapping` handles mappings but not collections."""

    class MappingOnly(DelimitedMapping, BaseModel):
        tags: list[int]
        counts: dict[str, int]

    assert MappingOnly._handles_mappings
    assert not MappingOnly._handles_collections

    # The dict field is split from a string; the list field is left for Pydantic to handle, so a
    # delimited string is not accepted as a list.
    m = MappingOnly.model_validate({"tags": [1, 2], "counts": "a=1"})
    assert m.counts == {"a": 1}
    with pytest.raises(ValidationError):
        MappingOnly.model_validate({"tags": "1,2", "counts": "a=1"})


def test_dict_field_roundtrip() -> None:
    """A dict[K, V] field parses from and serializes to a delimited string of pairs."""

    class FakeMetric(Metric):
        counts: dict[str, int]

    m = FakeMetric.model_validate({"counts": "a=1,b=2"})
    assert m.counts == {"a": 1, "b": 2}
    assert m.model_dump()["counts"] == "a=1,b=2"


def test_dict_field_coerces_key_and_value_types() -> None:
    """Keys and values are validated as the declared types."""

    class FakeMetric(Metric):
        counts: dict[int, float]

    m = FakeMetric.model_validate({"counts": "1=1.5,2=2.5"})
    assert m.counts == {1: 1.5, 2: 2.5}
    assert all(isinstance(k, int) for k in m.counts)


def test_dict_field_preserves_insertion_order() -> None:
    """Dict serialization preserves insertion order (unlike unordered sets)."""

    class FakeMetric(Metric):
        counts: dict[str, int]

    m = FakeMetric(counts={"z": 1, "a": 2, "m": 3})
    assert m.model_dump()["counts"] == "z=1,a=2,m=3"


def test_empty_dict_field() -> None:
    """An empty cell parses to an empty dict and serializes back to an empty cell."""

    class FakeMetric(Metric):
        counts: dict[str, int]

    m = FakeMetric.model_validate({"counts": ""})
    assert m.counts == {}
    assert m.model_dump()["counts"] == ""


def test_optional_dict_field() -> None:
    """An optional dict field treats an empty cell as None."""

    class FakeMetric(Metric):
        counts: dict[str, int] | None

    assert FakeMetric.model_validate({"counts": ""}).counts is None
    assert FakeMetric.model_validate({"counts": "a=1"}).counts == {"a": 1}
    assert FakeMetric(counts=None).model_dump()["counts"] is None


def test_dict_field_with_optional_values() -> None:
    """A dict[K, V | None] field maps empty values to None."""

    class FakeMetric(Metric):
        counts: dict[str, int | None]

    m = FakeMetric.model_validate({"counts": "a=,b=2"})
    assert m.counts == {"a": None, "b": 2}
    assert m.model_dump()["counts"] == "a=,b=2"


def test_dict_field_with_custom_key_value_delimiter() -> None:
    """The key/value delimiter is configurable."""

    class FakeMetric(Metric):
        key_value_delimiter = ":"
        counts: dict[str, int]

    m = FakeMetric.model_validate({"counts": "a:1,b:2"})
    assert m.counts == {"a": 1, "b": 2}
    assert m.model_dump()["counts"] == "a:1,b:2"


def test_dict_field_with_custom_collection_delimiter() -> None:
    """The pair delimiter is shared with collections via `collection_delimiter`."""

    class FakeMetric(Metric):
        collection_delimiter = ";"
        counts: dict[str, int]

    m = FakeMetric.model_validate({"counts": "a=1;b=2"})
    assert m.counts == {"a": 1, "b": 2}
    assert m.model_dump()["counts"] == "a=1;b=2"


def test_dict_value_may_contain_key_value_delimiter() -> None:
    """Only the first key/value delimiter splits a pair, so values may contain it."""

    class FakeMetric(Metric):
        counts: dict[str, str]

    m = FakeMetric.model_validate({"counts": "url=http://x=y"})
    assert m.counts == {"url": "http://x=y"}


def test_dict_field_raises_on_malformed_pair() -> None:
    """A pair missing the key/value delimiter raises a clear error."""

    class FakeMetric(Metric):
        counts: dict[str, int]

    with pytest.raises(ValueError, match="key/value pair"):
        FakeMetric.model_validate({"counts": "a=1,b"})


def test_dict_field_file_roundtrip(tmp_path: Path) -> None:
    """A dict field reads from and writes to a delimited file."""

    class FakeMetric(Metric):
        name: str
        counts: dict[str, int]

    fpath = tmp_path / "test.txt"
    with fpath.open("w") as fout:
        fout.write("name\tcounts\n")
        fout.write("Nils\ta=1,b=2\n")

    with MetricReader.open(FakeMetric, fpath) as reader:
        metrics = list(reader)

    assert metrics == [FakeMetric(name="Nils", counts={"a": 1, "b": 2})]

    out = tmp_path / "out.txt"
    writer: MetricWriter[FakeMetric]
    with MetricWriter.open(FakeMetric, out) as writer:
        writer.writeall(metrics)

    assert out.read_text() == "name\tcounts\nNils\ta=1,b=2\n"


def test_raises_if_key_value_delimiter_not_single_char() -> None:
    """A multi-character key/value delimiter is rejected at class-definition time."""
    with pytest.raises(ValueError, match="key_value_delimiter must be a single character"):

        class FakeMetric(Metric):
            key_value_delimiter = "::"
            counts: dict[str, int]


def test_raises_if_key_value_delimiter_equals_collection_delimiter() -> None:
    """The two delimiters must differ, else pairs cannot be unambiguously split."""
    with pytest.raises(ValueError, match="must differ"):

        class FakeMetric(Metric):
            collection_delimiter = ":"
            key_value_delimiter = ":"
            counts: dict[str, int]


def test_counter_is_not_treated_as_a_mapping() -> None:
    """A `Counter` field is handled by `CounterPivotTable`, not `DelimitedMapping`."""

    class Color(StrEnum):
        RED = "red"
        BLUE = "blue"

    class FakeMetric(Metric):
        counts: Counter[Color]

    assert FakeMetric._mapping_fieldnames == set()
