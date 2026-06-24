"""
Tests for `RecordModel`, the mixin-free base class.

`RecordModel` performs the default tabular parsing only: one model field per column, with no
converter behaviors (null sentinels, delimited lists, counter pivot tables). These tests cover
that base contract and contrast it with `Metric`, which layers the converters on top.
"""

from pathlib import Path
from typing import assert_type

from pydantic import Field

from fgmetric import Metric
from fgmetric import ModelReader
from fgmetric import ModelWriter
from fgmetric import RecordModel


class PlainRecord(RecordModel):
    """A plain record with one field per column."""

    name: str
    note: str | None


class AliasRecord(RecordModel):
    """A record whose field serializes under an alias."""

    name: str
    read_count: int = Field(alias="count")


class SentinelMetric(Metric):
    """A `Metric` mirroring `PlainRecord`, used to contrast converter behavior."""

    name: str
    note: str | None


def test_header_fieldnames_are_plain_columns() -> None:
    """Test `_header_fieldnames` returns one column per field, in declaration order."""
    assert PlainRecord._header_fieldnames() == ["name", "note"]


def test_header_fieldnames_respect_alias() -> None:
    """Test `_header_fieldnames` resolves each field to its serialized (aliased) name."""
    assert AliasRecord._header_fieldnames() == ["name", "count"]


def test_does_not_apply_null_sentinels() -> None:
    """Test `RecordModel` leaves empty Optional fields untouched (no null-sentinel converter)."""
    record = PlainRecord.model_validate({"name": "a", "note": ""})
    assert record.note == ""


def test_metric_applies_null_sentinels_where_record_model_does_not() -> None:
    """Test the same empty Optional field becomes `None` on `Metric` but `""` on `RecordModel`."""
    record = PlainRecord.model_validate({"name": "a", "note": ""})
    metric = SentinelMetric.model_validate({"name": "a", "note": ""})
    assert record.note == ""
    assert metric.note is None


def test_read_classmethod(tmp_path: Path) -> None:
    """Test the inherited `read` classmethod parses a file into the calling subclass."""
    p = tmp_path / "records.tsv"
    p.write_text("name\tnote\na\tfoo\n")
    records = PlainRecord.read(p)
    assert_type(records, list[PlainRecord])
    assert records == [PlainRecord(name="a", note="foo")]


def test_roundtrip_through_model_reader_and_writer(tmp_path: Path) -> None:
    """Test a bare `RecordModel` round-trips through `ModelWriter` and `ModelReader`."""
    p = tmp_path / "records.tsv"
    records = [PlainRecord(name="a", note="foo"), PlainRecord(name="b", note=None)]

    with ModelWriter.open(PlainRecord, p) as writer:
        writer.writeall(records)

    with ModelReader.open(PlainRecord, p) as reader:
        # An empty cell deserializes to "" on a plain RecordModel, not None.
        assert list(reader) == [PlainRecord(name="a", note="foo"), PlainRecord(name="b", note="")]
