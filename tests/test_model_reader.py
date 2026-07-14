from collections.abc import Callable
from io import StringIO
from pathlib import Path
from typing import assert_type

import pytest
from pydantic import Field
from pydantic import ValidationError

from fgmetric import Metric
from fgmetric.model_reader import ModelReader


class ExampleMetric(Metric):
    """Example Metric subclass used in ModelReader tests."""

    name: str
    value: int


def test_reader_iterates_from_iterable() -> None:
    source = StringIO("name\tvalue\nalice\t1\nbob\t2\n")
    reader = ModelReader(ExampleMetric, source)
    assert_type(reader, ModelReader[ExampleMetric])
    metrics = list(reader)
    assert_type(metrics, list[ExampleMetric])
    assert metrics == [
        ExampleMetric(name="alice", value=1),
        ExampleMetric(name="bob", value=2),
    ]


def test_reader_supports_headerless_with_fieldnames() -> None:
    source = StringIO("alice\t1\nbob\t2\n")
    reader = ModelReader(ExampleMetric, source, fieldnames=["name", "value"])
    metrics = list(reader)
    assert metrics == [
        ExampleMetric(name="alice", value=1),
        ExampleMetric(name="bob", value=2),
    ]


def test_reader_rejects_fieldnames_matching_header_at_construction() -> None:
    source = StringIO("name\tvalue\nalice\t1\n")
    with pytest.raises(ValueError, match="appears to be a header"):
        ModelReader(ExampleMetric, source, fieldnames=["name", "value"])


def test_reader_does_not_close_caller_handle() -> None:
    source = StringIO("name\tvalue\nalice\t1\n")
    reader = ModelReader(ExampleMetric, source)
    list(reader)
    assert not source.closed


def test_open_reads_file(tmp_path: Path) -> None:
    p = tmp_path / "metrics.tsv"
    p.write_text("name\tvalue\nalice\t1\nbob\t2\n")
    with ModelReader.open(ExampleMetric, p) as reader:
        assert_type(reader, ModelReader[ExampleMetric])
        metrics = list(reader)
    assert_type(metrics, list[ExampleMetric])
    assert metrics == [
        ExampleMetric(name="alice", value=1),
        ExampleMetric(name="bob", value=2),
    ]


def test_open_does_not_open_file_until_enter(tmp_path: Path) -> None:
    p = tmp_path / "missing.tsv"
    cm = ModelReader.open(ExampleMetric, p)
    with pytest.raises(FileNotFoundError):
        with cm:
            pass


def test_open_requires_context_manager_usage(tmp_path: Path) -> None:
    p = tmp_path / "metrics.tsv"
    p.write_text("name\tvalue\nalice\t1\n")
    cm = ModelReader.open(ExampleMetric, p)
    with pytest.raises(TypeError):
        list(cm)  # type: ignore[call-overload]


def test_open_infers_delimiter_from_extension(tmp_path: Path) -> None:
    """Test that ModelReader.open reads a .csv file as comma-delimited by default."""
    p = tmp_path / "metrics.csv"
    p.write_text("name,value\nalice,1\nbob,2\n")
    with ModelReader.open(ExampleMetric, p) as reader:
        metrics = list(reader)
    assert metrics == [
        ExampleMetric(name="alice", value=1),
        ExampleMetric(name="bob", value=2),
    ]


def test_open_explicit_delimiter_overrides_inference(tmp_path: Path) -> None:
    """Test that an explicit delimiter wins over the extension-inferred one."""
    p = tmp_path / "metrics.csv"
    p.write_text("name\tvalue\nalice\t1\n")
    with ModelReader.open(ExampleMetric, p, delimiter="\t") as reader:
        metrics = list(reader)
    assert metrics == [ExampleMetric(name="alice", value=1)]


def test_open_raises_for_uninferrable_delimiter(tmp_path: Path) -> None:
    """Test that an unrecognized extension raises when no delimiter is given."""
    p = tmp_path / "metrics.dat"
    p.write_text("name\tvalue\nalice\t1\n")
    with pytest.raises(ValueError, match="Could not infer a delimiter"):
        with ModelReader.open(ExampleMetric, p):
            pass


def test_open_respects_encoding(tmp_path: Path) -> None:
    """Test that ModelReader.open decodes the file with the specified encoding."""
    p = tmp_path / "metrics.tsv"
    p.write_bytes("name\tvalue\nrené\t1\n".encode("latin-1"))
    with ModelReader.open(ExampleMetric, p, encoding="latin-1") as reader:
        metrics = list(reader)
    assert metrics == [ExampleMetric(name="rené", value=1)]


def test_open_raises_file_not_found_for_missing_file(tmp_path: Path) -> None:
    """ModelReader.open raises FileNotFoundError when the file does not exist."""
    with pytest.raises(FileNotFoundError, match="does not exist"):
        with ModelReader.open(ExampleMetric, tmp_path / "missing.tsv"):
            pass


def test_open_raises_file_not_found_for_missing_compressed_file(tmp_path: Path) -> None:
    """ModelReader.open raises FileNotFoundError for a missing compressed file too."""
    with pytest.raises(FileNotFoundError, match="does not exist"):
        with ModelReader.open(ExampleMetric, tmp_path / "missing.tsv.gz"):
            pass


def test_open_raises_is_a_directory_for_directory(tmp_path: Path) -> None:
    """ModelReader.open raises IsADirectoryError when the path is a directory."""
    with pytest.raises(IsADirectoryError, match="is a directory"):
        with ModelReader.open(ExampleMetric, tmp_path):
            pass


def test_open_raises_permission_error_for_unreadable_file(
    tmp_path: Path, chmod: Callable[[Path, int], None]
) -> None:
    """ModelReader.open raises PermissionError when the file is not readable."""
    p = tmp_path / "metrics.tsv"
    p.write_text("name\tvalue\nalice\t1\n")
    chmod(p, 0o000)
    with pytest.raises(PermissionError, match="not readable"):
        with ModelReader.open(ExampleMetric, p):
            pass


# ======================================================================================
# Metric subclasses used by the file-reading tests below.
# ======================================================================================


class SimpleMetric(Metric):
    """A simple Metric for testing."""

    name: str
    count: int


class MetricWithOptional(Metric):
    """A Metric with optional fields."""

    name: str
    value: int | None = None


class MetricWithFloat(Metric):
    """A Metric with a float field."""

    name: str
    score: float


class MetricWithBool(Metric):
    """A Metric with a bool field."""

    name: str
    is_active: bool


class MetricWithAlias(Metric):
    """A Metric with a field alias."""

    name: str
    read_count: int = Field(alias="count")


class MetricWithDefault(Metric):
    """A Metric with a default value."""

    name: str
    count: int = 0


class ParentMetric(Metric):
    """A parent Metric class."""

    name: str
    value: int


class ChildMetric(ParentMetric):
    """A child Metric with extra fields."""

    extra_field: str
    another_field: int | None = None


# ======================================================================================
# Basic functionality tests
# ======================================================================================


def test_open_tsv(tmp_path: Path) -> None:
    """Test reading metrics from a TSV file."""
    fpath = tmp_path / "metrics.tsv"
    fpath.write_text("name\tcount\nfoo\t1\n")

    with ModelReader.open(SimpleMetric, fpath) as reader:
        metrics = list(reader)

    assert len(metrics) == 1
    assert metrics[0].name == "foo"
    assert metrics[0].count == 1


def test_open_csv(tmp_path: Path) -> None:
    """Test reading metrics with comma delimiter."""
    fpath = tmp_path / "metrics.csv"
    fpath.write_text("name,count\nfoo,1\n")

    with ModelReader.open(SimpleMetric, fpath, delimiter=",") as reader:
        metrics = list(reader)

    assert len(metrics) == 1
    assert metrics[0].name == "foo"
    assert metrics[0].count == 1


def test_open_yields_correct_type(tmp_path: Path) -> None:
    """Test that ModelReader yields instances of the correct Metric subclass."""
    fpath = tmp_path / "metrics.tsv"
    fpath.write_text("name\tcount\nfoo\t1\n")

    with ModelReader.open(SimpleMetric, fpath) as reader:
        for metric in reader:
            assert_type(metric, SimpleMetric)
            assert isinstance(metric, SimpleMetric)


def test_open_multiple_rows(tmp_path: Path) -> None:
    """Test reading a file with multiple metric rows."""
    fpath = tmp_path / "metrics.tsv"
    fpath.write_text("name\tcount\nfoo\t1\nbar\t2\nbaz\t3\n")

    with ModelReader.open(SimpleMetric, fpath) as reader:
        metrics = list(reader)

    assert len(metrics) == 3
    assert metrics[0].name == "foo"
    assert metrics[1].name == "bar"
    assert metrics[2].name == "baz"
    assert metrics[0].count == 1
    assert metrics[1].count == 2
    assert metrics[2].count == 3


# ======================================================================================
# Type coercion tests
# ======================================================================================


def test_open_coerces_string_to_int(tmp_path: Path) -> None:
    """Test that string values are coerced to int fields."""
    fpath = tmp_path / "metrics.tsv"
    fpath.write_text("name\tcount\nfoo\t42\n")

    with ModelReader.open(SimpleMetric, fpath) as reader:
        metrics = list(reader)

    assert metrics[0].count == 42
    assert isinstance(metrics[0].count, int)


def test_open_coerces_string_to_float(tmp_path: Path) -> None:
    """Test that string values are coerced to float fields."""
    fpath = tmp_path / "metrics.tsv"
    fpath.write_text("name\tscore\nfoo\t3.14\n")

    with ModelReader.open(MetricWithFloat, fpath) as reader:
        metrics = list(reader)

    assert metrics[0].score == pytest.approx(3.14)
    assert isinstance(metrics[0].score, float)


def test_open_coerces_string_to_bool(tmp_path: Path) -> None:
    """Test that string values like 'true'/'false' are coerced to bool."""
    fpath = tmp_path / "metrics.tsv"
    fpath.write_text("name\tis_active\nfoo\ttrue\nbar\tfalse\n")

    with ModelReader.open(MetricWithBool, fpath) as reader:
        metrics = list(reader)

    assert metrics[0].is_active is True
    assert metrics[1].is_active is False


# ======================================================================================
# Empty field handling tests
# ======================================================================================


def test_open_empty_field_becomes_none(tmp_path: Path) -> None:
    """Test that empty string fields are converted to None."""
    fpath = tmp_path / "metrics.tsv"
    fpath.write_text("name\tvalue\nfoo\t\n")

    with ModelReader.open(MetricWithOptional, fpath) as reader:
        metrics = list(reader)

    assert metrics[0].value is None


def test_open_empty_field_with_optional_type(tmp_path: Path) -> None:
    """Test that empty fields work with Optional[T] annotations."""
    fpath = tmp_path / "metrics.tsv"
    fpath.write_text("name\tvalue\nfoo\t\nbar\t42\n")

    with ModelReader.open(MetricWithOptional, fpath) as reader:
        metrics = list(reader)

    assert metrics[0].value is None
    assert metrics[1].value == 42


def test_open_empty_field_with_required_type_raises(tmp_path: Path) -> None:
    """Test that empty fields on required (non-Optional) fields raise ValidationError."""
    fpath = tmp_path / "metrics.tsv"
    fpath.write_text("name\tcount\nfoo\t\n")

    with pytest.raises(ValidationError):
        with ModelReader.open(SimpleMetric, fpath) as reader:
            list(reader)


# ======================================================================================
# BOM handling tests
# ======================================================================================


def test_open_handles_utf8_bom(tmp_path: Path) -> None:
    """Test that UTF-8 BOM is stripped from file header."""
    fpath = tmp_path / "metrics.tsv"
    # Write file with BOM prefix
    fpath.write_bytes(b"\xef\xbb\xbfname\tcount\nfoo\t1\n")

    with ModelReader.open(SimpleMetric, fpath) as reader:
        metrics = list(reader)

    assert len(metrics) == 1
    assert metrics[0].name == "foo"
    assert metrics[0].count == 1


# ======================================================================================
# Field alias tests
# ======================================================================================


def test_open_with_field_alias(tmp_path: Path) -> None:
    """Test reading a file where headers match field aliases."""
    fpath = tmp_path / "metrics.tsv"
    # Header uses alias "count" instead of field name "read_count"
    fpath.write_text("name\tcount\nfoo\t100\n")

    with ModelReader.open(MetricWithAlias, fpath) as reader:
        metrics = list(reader)

    assert metrics[0].name == "foo"
    assert metrics[0].read_count == 100


# ======================================================================================
# Edge case tests
# ======================================================================================


def test_open_empty_file_no_rows(tmp_path: Path) -> None:
    """Test reading a file with only a header row (no data)."""
    fpath = tmp_path / "metrics.tsv"
    fpath.write_text("name\tcount\n")

    with ModelReader.open(SimpleMetric, fpath) as reader:
        metrics = list(reader)

    assert len(metrics) == 0


def test_open_file_not_found_raises(tmp_path: Path) -> None:
    """Test that opening a non-existent file raises FileNotFoundError."""
    fpath = tmp_path / "does_not_exist.tsv"

    with pytest.raises(FileNotFoundError):
        with ModelReader.open(SimpleMetric, fpath):
            pass


# ======================================================================================
# Validation error tests
# ======================================================================================


def test_open_missing_required_field_raises(tmp_path: Path) -> None:
    """Test that missing required fields raise ValidationError."""
    fpath = tmp_path / "metrics.tsv"
    # Missing "count" column
    fpath.write_text("name\nfoo\n")

    with pytest.raises(ValidationError):
        with ModelReader.open(SimpleMetric, fpath) as reader:
            list(reader)


def test_open_invalid_type_raises(tmp_path: Path) -> None:
    """Test that values that can't be coerced raise ValidationError."""
    fpath = tmp_path / "metrics.tsv"
    fpath.write_text("name\tcount\nfoo\tnot_an_int\n")

    with pytest.raises(ValidationError):
        with ModelReader.open(SimpleMetric, fpath) as reader:
            list(reader)


def test_open_extra_columns_ignored(tmp_path: Path) -> None:
    """Test that extra columns in the file are ignored."""
    fpath = tmp_path / "metrics.tsv"
    fpath.write_text("name\tcount\textra\nfoo\t1\tignored\n")

    with ModelReader.open(SimpleMetric, fpath) as reader:
        metrics = list(reader)

    assert len(metrics) == 1
    assert metrics[0].name == "foo"
    assert metrics[0].count == 1
    assert not hasattr(metrics[0], "extra")


# ======================================================================================
# Headerless file tests (explicit fieldnames)
# ======================================================================================


def test_open_headerless_with_fieldnames(tmp_path: Path) -> None:
    """Reading a headerless TSV with `fieldnames` treats every row as data."""
    fpath = tmp_path / "metrics.tsv"
    # Three data rows, no header
    fpath.write_text("foo\t1\nbar\t2\nbaz\t3\n")

    with ModelReader.open(SimpleMetric, fpath, fieldnames=["name", "count"]) as reader:
        metrics = list(reader)

    assert [m.name for m in metrics] == ["foo", "bar", "baz"]
    assert [m.count for m in metrics] == [1, 2, 3]


def test_open_headerless_with_alias(tmp_path: Path) -> None:
    """`fieldnames` may reference a field's alias, mirroring header-based reading."""
    fpath = tmp_path / "metrics.tsv"
    fpath.write_text("foo\t100\n")

    with ModelReader.open(MetricWithAlias, fpath, fieldnames=["name", "count"]) as reader:
        metrics = list(reader)

    assert metrics[0].name == "foo"
    assert metrics[0].read_count == 100


def test_open_headerless_missing_required_field_raises(tmp_path: Path) -> None:
    """A headerless file missing a required field still raises ValidationError."""
    fpath = tmp_path / "metrics.tsv"
    fpath.write_text("foo\n")

    with pytest.raises(ValidationError):
        with ModelReader.open(SimpleMetric, fpath, fieldnames=["name"]) as reader:
            list(reader)


def test_open_headerless_row_missing_column_raises(tmp_path: Path) -> None:
    """When a row has fewer values than `fieldnames`, missing required fields raises."""
    fpath = tmp_path / "metrics.tsv"
    # Row only has "name", "count" is missing
    fpath.write_text("foo\n")

    with pytest.raises(ValidationError):
        with ModelReader.open(SimpleMetric, fpath, fieldnames=["name", "count"]) as reader:
            list(reader)


def test_open_headerless_short_row_among_valid_rows_raises(tmp_path: Path) -> None:
    """A single short row among otherwise-valid rows still raises ValidationError."""
    fpath = tmp_path / "metrics.tsv"
    # The middle row is missing the "count" value
    fpath.write_text("foo\t1\nbar\nbaz\t3\n")

    with pytest.raises(ValidationError):
        with ModelReader.open(SimpleMetric, fpath, fieldnames=["name", "count"]) as reader:
            list(reader)


def test_open_headerless_row_extra_column_ignored(tmp_path: Path) -> None:
    """When a row has more values than `fieldnames`, the extras are ignored."""
    fpath = tmp_path / "metrics.tsv"
    # Row has an extra value not covered by fieldnames
    fpath.write_text("foo\t1\textra\n")

    with ModelReader.open(SimpleMetric, fpath, fieldnames=["name", "count"]) as reader:
        metrics = list(reader)

    assert len(metrics) == 1
    assert metrics[0].name == "foo"
    assert metrics[0].count == 1


def test_open_headerless_detects_header_row_raises(tmp_path: Path) -> None:
    """Passing `fieldnames` for a file that already has a matching header row raises."""
    fpath = tmp_path / "metrics.tsv"
    # File has a real header row that matches the supplied fieldnames
    fpath.write_text("name\tcount\nfoo\t1\n")

    with pytest.raises(ValueError, match="header"):
        with ModelReader.open(SimpleMetric, fpath, fieldnames=["name", "count"]):
            pass


def test_open_headerless_first_row_coincidentally_matching_value_is_data(
    tmp_path: Path,
) -> None:
    """A single field whose value happens to match its fieldname is not flagged."""
    fpath = tmp_path / "metrics.tsv"
    fpath.write_text("name\t1\nbar\t2\n")

    with ModelReader.open(SimpleMetric, fpath, fieldnames=["name", "count"]) as reader:
        metrics = list(reader)

    assert [m.name for m in metrics] == ["name", "bar"]
    assert [m.count for m in metrics] == [1, 2]


def test_open_headerless_detects_header_row_with_aliased_field_raises(tmp_path: Path) -> None:
    """Header detection compares against supplied fieldnames, not model field names."""
    fpath = tmp_path / "metrics.tsv"
    # `MetricWithAlias` declares `read_count` aliased to "count"; the supplied fieldnames
    # use the alias, and the file's header row matches those fieldnames.
    fpath.write_text("name\tcount\nfoo\t1\n")

    with pytest.raises(ValueError, match="header"):
        with ModelReader.open(MetricWithAlias, fpath, fieldnames=["name", "count"]):
            pass


def test_open_headerless_empty_file(tmp_path: Path) -> None:
    """An empty headerless file yields no metrics and does not raise."""
    fpath = tmp_path / "metrics.tsv"
    fpath.write_text("")

    with ModelReader.open(SimpleMetric, fpath, fieldnames=["name", "count"]) as reader:
        metrics = list(reader)

    assert metrics == []


# ======================================================================================
# Parent/subclass tests
# ======================================================================================


def test_open_parent_class_discards_subclass_fields(tmp_path: Path) -> None:
    """
    Test that reading with parent class discards extra subclass fields.

    When a file was written by a subclass (with extra fields), reading it with
    the parent class should silently discard the extra columns.
    """
    fpath = tmp_path / "metrics.tsv"
    # File has columns for ChildMetric but we read with ParentMetric
    fpath.write_text("name\tvalue\textra_field\tanother_field\nfoo\t42\textra\t99\n")

    with ModelReader.open(ParentMetric, fpath) as reader:
        metrics = list(reader)

    assert len(metrics) == 1
    assert metrics[0].name == "foo"
    assert metrics[0].value == 42
    assert not hasattr(metrics[0], "extra_field")
    assert not hasattr(metrics[0], "another_field")
