import bz2
import gzip
import lzma
from pathlib import Path

import pytest

from fgmetric.metric import Metric
from fgmetric.metric_reader import MetricReader
from fgmetric.metric_writer import MetricWriter


class ExampleMetric(Metric):
    """Test Metric used in compression round-trip tests."""

    name: str
    value: int


def test_reader_open_reads_gzipped_file(tmp_path: Path) -> None:
    """Test MetricReader.open transparently decompresses .gz files."""
    p = tmp_path / "metrics.tsv.gz"
    with gzip.open(p, mode="wt", encoding="utf-8") as f:
        f.write("name\tvalue\nalice\t1\nbob\t2\n")
    with MetricReader.open(ExampleMetric, p) as reader:
        metrics = list(reader)
    assert metrics == [
        ExampleMetric(name="alice", value=1),
        ExampleMetric(name="bob", value=2),
    ]


def test_writer_open_writes_gzipped_file(tmp_path: Path) -> None:
    """Test MetricWriter.open transparently compresses .gz files."""
    p = tmp_path / "out.tsv.gz"
    with MetricWriter.open(ExampleMetric, p) as writer:
        writer.write(ExampleMetric(name="alice", value=1))
    with gzip.open(p, mode="rt", encoding="utf-8") as f:
        assert f.read() == "name\tvalue\nalice\t1\n"


@pytest.mark.parametrize("ext", ["", ".gz", ".bz2", ".xz"])
def test_round_trip_compressed(tmp_path: Path, ext: str) -> None:
    """Test write-then-read round trip across plain text and supported compression formats."""
    p = tmp_path / f"metrics.tsv{ext}"
    expected = [ExampleMetric(name="alice", value=1), ExampleMetric(name="bob", value=2)]
    with MetricWriter.open(ExampleMetric, p) as writer:
        writer.writeall(expected)
    with MetricReader.open(ExampleMetric, p) as reader:
        assert list(reader) == expected


@pytest.mark.parametrize("ext", ["", ".gz", ".bz2", ".xz"])
def test_round_trip_csv_with_inferred_delimiter(tmp_path: Path, ext: str) -> None:
    """Test that delimiter inference composes with compression suffixes on round trip."""
    p = tmp_path / f"metrics.csv{ext}"
    expected = [ExampleMetric(name="alice", value=1), ExampleMetric(name="bob", value=2)]
    with MetricWriter.open(ExampleMetric, p) as writer:
        writer.writeall(expected)
    with MetricReader.open(ExampleMetric, p) as reader:
        assert list(reader) == expected


def test_gzipped_csv_is_comma_delimited(tmp_path: Path) -> None:
    """A .csv.gz file written without an explicit delimiter is comma-delimited inside."""
    p = tmp_path / "out.csv.gz"
    with MetricWriter.open(ExampleMetric, p) as writer:
        writer.write(ExampleMetric(name="alice", value=1))
    with gzip.open(p, mode="rt", encoding="utf-8") as f:
        assert f.read() == "name,value\nalice,1\n"


def test_gzipped_file_is_actually_gzipped(tmp_path: Path) -> None:
    """A .gz file written by MetricWriter.open has the gzip magic bytes."""
    p = tmp_path / "out.tsv.gz"
    with MetricWriter.open(ExampleMetric, p) as writer:
        writer.write(ExampleMetric(name="alice", value=1))
    assert p.read_bytes()[:2] == b"\x1f\x8b"


def test_bz2_file_is_actually_bz2(tmp_path: Path) -> None:
    """A .bz2 file written by MetricWriter.open has the bz2 magic bytes."""
    p = tmp_path / "out.tsv.bz2"
    with MetricWriter.open(ExampleMetric, p) as writer:
        writer.write(ExampleMetric(name="alice", value=1))
    assert p.read_bytes()[:3] == b"BZh"
    # Sanity: stdlib decompresses cleanly.
    assert bz2.decompress(p.read_bytes()).decode() == "name\tvalue\nalice\t1\n"


def test_xz_file_is_actually_xz(tmp_path: Path) -> None:
    """An .xz file written by MetricWriter.open has the xz magic bytes."""
    p = tmp_path / "out.tsv.xz"
    with MetricWriter.open(ExampleMetric, p) as writer:
        writer.write(ExampleMetric(name="alice", value=1))
    assert p.read_bytes()[:6] == b"\xfd7zXZ\x00"
    # Sanity: stdlib decompresses cleanly.
    assert lzma.decompress(p.read_bytes()).decode() == "name\tvalue\nalice\t1\n"
