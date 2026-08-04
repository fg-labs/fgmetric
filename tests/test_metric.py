"""
Tests for the `Metric.read` convenience classmethod.

`Metric.read` is a thin wrapper over `ModelReader.open`; parsing behavior is covered in
`test_model_reader.py`. These tests cover only the wrapper contract: delegation of each
keyword argument, accepted path types, and eager evaluation.
"""

import gzip
from pathlib import Path
from typing import assert_type

import pytest

from fgmetric import Metric


class ExampleMetric(Metric):
    """Example Metric subclass used in Metric.read tests."""

    name: str
    value: int


def test_read_tsv_with_header(tmp_path: Path) -> None:
    """Test Metric.read parses a headered TSV into validated instances."""
    p = tmp_path / "metrics.tsv"
    p.write_text("name\tvalue\nalice\t1\nbob\t2\n")
    metrics = ExampleMetric.read(p)
    assert_type(metrics, list[ExampleMetric])
    assert metrics == [
        ExampleMetric(name="alice", value=1),
        ExampleMetric(name="bob", value=2),
    ]


def test_read_accepts_str_path(tmp_path: Path) -> None:
    """Test Metric.read accepts a str path as well as a Path."""
    p = tmp_path / "metrics.tsv"
    p.write_text("name\tvalue\nalice\t1\n")
    assert ExampleMetric.read(str(p)) == [ExampleMetric(name="alice", value=1)]


def test_read_delegates_delimiter(tmp_path: Path) -> None:
    """Test Metric.read passes `delimiter` through to the reader."""
    p = tmp_path / "metrics.csv"
    p.write_text("name,value\nalice,1\n")
    assert ExampleMetric.read(p, delimiter=",") == [ExampleMetric(name="alice", value=1)]


def test_read_delegates_fieldnames(tmp_path: Path) -> None:
    """Test Metric.read passes `fieldnames` through for headerless input."""
    p = tmp_path / "metrics.tsv"
    p.write_text("alice\t1\nbob\t2\n")
    assert ExampleMetric.read(p, fieldnames=["name", "value"]) == [
        ExampleMetric(name="alice", value=1),
        ExampleMetric(name="bob", value=2),
    ]


def test_read_rejects_fieldnames_matching_header(tmp_path: Path) -> None:
    """Test Metric.read raises if `fieldnames` is supplied but the file has a matching header."""
    p = tmp_path / "metrics.tsv"
    p.write_text("name\tvalue\nalice\t1\n")
    with pytest.raises(ValueError, match="appears to be a header"):
        ExampleMetric.read(p, fieldnames=["name", "value"])


def test_read_delegates_encoding(tmp_path: Path) -> None:
    """Test Metric.read passes `encoding` through to the reader."""
    p = tmp_path / "metrics.tsv"
    p.write_bytes("name\tvalue\nzoë\t1\n".encode("utf-16"))
    assert ExampleMetric.read(p, encoding="utf-16") == [ExampleMetric(name="zoë", value=1)]


def test_read_gzipped_file(tmp_path: Path) -> None:
    """Test Metric.read transparently decompresses .gz files."""
    p = tmp_path / "metrics.tsv.gz"
    with gzip.open(p, mode="wt", encoding="utf-8") as f:
        f.write("name\tvalue\nalice\t1\n")
    assert ExampleMetric.read(p) == [ExampleMetric(name="alice", value=1)]


def test_read_is_eager(tmp_path: Path) -> None:
    """Test Metric.read opens and reads the file at call time, not on iteration."""
    missing = tmp_path / "does-not-exist.tsv"
    with pytest.raises(FileNotFoundError):
        ExampleMetric.read(missing)
