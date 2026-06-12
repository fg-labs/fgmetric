from pathlib import Path

import pytest

from fgmetric._delimiter import infer_delimiter


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("metrics.csv", ","),
        ("metrics.tsv", "\t"),
        ("metrics.txt", "\t"),
        ("metrics.tab", "\t"),
        ("sample.insert_size_metrics", "\t"),
        ("metrics.csv.gz", ","),
        ("metrics.csv.bz2", ","),
        ("metrics.csv.xz", ","),
        ("metrics.tsv.gz", "\t"),
        ("metrics.tsv.bz2", "\t"),
        ("metrics.tsv.xz", "\t"),
        ("sample.alignment_summary_metrics.gz", "\t"),
        ("METRICS.CSV.GZ", ","),
        ("Metrics.Tsv", "\t"),
    ],
)
def test_infer_delimiter(filename: str, expected: str) -> None:
    """Test delimiter inference across data extensions and compression suffixes."""
    assert infer_delimiter(filename) == expected
    assert infer_delimiter(Path("/some/dir") / filename) == expected


@pytest.mark.parametrize(
    "filename",
    [
        "metrics.dat",
        "metrics",
        "metrics.gz",  # bare compression suffix with no data extension underneath
        "metrics.gz.gz",  # only a single compression suffix is stripped
        "metrics.csv.zip",  # unrecognized outer suffix is not treated as compression
    ],
)
def test_infer_delimiter_raises_for_unrecognized_extension(filename: str) -> None:
    """Test that unrecognized extensions raise instead of silently defaulting."""
    with pytest.raises(ValueError, match="Could not infer a delimiter"):
        infer_delimiter(filename)
