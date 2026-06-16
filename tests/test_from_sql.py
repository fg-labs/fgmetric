import sys
from pathlib import Path
from typing import assert_type

import duckdb
import pytest
from pydantic import Field
from pydantic import ValidationError

from fgmetric import Metric
from fgmetric._duckdb import query_rows
from fgmetric.metric_reader import MetricReader


def test_query_rows_returns_column_keyed_dicts() -> None:
    rows = query_rows("SELECT 'alice' AS name, 1 AS value")
    assert rows == [{"name": "alice", "value": 1}]


def test_query_rows_uses_transient_connection_when_none() -> None:
    # No connection passed: query_rows opens and closes its own in-memory connection.
    rows = query_rows("SELECT * FROM (VALUES (1), (2)) AS v(n) ORDER BY n")
    assert rows == [{"n": 1}, {"n": 2}]


def test_query_rows_does_not_close_caller_connection() -> None:
    conn = duckdb.connect()
    query_rows("SELECT 1 AS x", conn)
    # Still usable -> query_rows did not close a connection it does not own.
    assert conn.sql("SELECT 2 AS y").fetchall() == [(2,)]
    conn.close()


def test_query_rows_returns_empty_list_for_no_rows() -> None:
    rows = query_rows("SELECT 1 AS x WHERE false")
    assert rows == []


def test_query_rows_raises_friendly_error_when_duckdb_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Setting the module to None makes `import duckdb` raise ImportError.
    monkeypatch.setitem(sys.modules, "duckdb", None)
    with pytest.raises(ImportError, match=r"fgmetric\[duckdb\]"):
        query_rows("SELECT 1")


class ExampleMetric(Metric):
    """Two required fields of distinct scalar types."""

    name: str
    value: int


class TypedMetric(Metric):
    """Exercises native float/bool validation without string coercion."""

    name: str
    rate: float
    flag: bool


class OptionalMetric(Metric):
    """Optional field to exercise SQL NULL -> None."""

    name: str
    note: str | None = None


class AliasedMetric(Metric):
    """Field whose serialized column name differs from the attribute name."""

    name: str
    mapping_quality: int = Field(alias="mapq")


def test_from_sql_validates_query_rows() -> None:
    query = "SELECT * FROM (VALUES ('alice', 1), ('bob', 2)) AS v(name, value) ORDER BY value"
    reader = MetricReader.from_sql(ExampleMetric, query)
    assert_type(reader, MetricReader[ExampleMetric])
    metrics = list(reader)
    assert metrics == [
        ExampleMetric(name="alice", value=1),
        ExampleMetric(name="bob", value=2),
    ]


def test_from_sql_validates_native_typed_values() -> None:
    metrics = list(
        MetricReader.from_sql(TypedMetric, "SELECT 'a' AS name, 0.5 AS rate, true AS flag")
    )
    assert metrics == [TypedMetric(name="a", rate=0.5, flag=True)]


def test_from_sql_renames_columns_to_fields_with_as() -> None:
    query = "SELECT label AS name, score AS value FROM (SELECT 'x' AS label, 5 AS score)"
    metrics = list(MetricReader.from_sql(ExampleMetric, query))
    assert metrics == [ExampleMetric(name="x", value=5)]


def test_from_sql_null_becomes_none() -> None:
    metrics = list(MetricReader.from_sql(OptionalMetric, "SELECT 'a' AS name, NULL AS note"))
    assert metrics == [OptionalMetric(name="a", note=None)]


def test_from_sql_resolves_field_alias() -> None:
    metrics = list(MetricReader.from_sql(AliasedMetric, "SELECT 'a' AS name, 60 AS mapq"))
    assert metrics == [AliasedMetric(name="a", mapq=60)]


def test_from_sql_missing_required_column_raises() -> None:
    # The `value` column is absent, so validation of the required field fails.
    with pytest.raises(ValidationError):
        list(MetricReader.from_sql(ExampleMetric, "SELECT 'a' AS name"))


def test_from_sql_returns_empty_for_no_rows() -> None:
    query = "SELECT 'a' AS name, 1 AS value WHERE false"
    metrics = list(MetricReader.from_sql(ExampleMetric, query))
    assert metrics == []


def test_from_sql_does_not_close_caller_connection() -> None:
    conn = duckdb.connect()
    conn.execute("CREATE TABLE t AS SELECT 'a' AS name, 1 AS value")
    metrics = list(MetricReader.from_sql(ExampleMetric, "SELECT * FROM t", connection=conn))
    assert metrics == [ExampleMetric(name="a", value=1)]
    # Connection still usable -> from_sql did not close a borrowed connection.
    assert conn.sql("SELECT 1 AS x").fetchall() == [(1,)]
    conn.close()


def test_from_sql_reads_parquet_file(tmp_path: Path) -> None:
    parquet = tmp_path / "metrics.parquet"
    writer = duckdb.connect()
    writer.execute(
        f"COPY (SELECT 'a' AS name, 1 AS value UNION ALL SELECT 'b', 2) "
        f"TO '{parquet}' (FORMAT parquet)"
    )
    writer.close()
    metrics = list(
        MetricReader.from_sql(ExampleMetric, f"SELECT * FROM '{parquet}' ORDER BY value")
    )
    assert metrics == [
        ExampleMetric(name="a", value=1),
        ExampleMetric(name="b", value=2),
    ]


def test_metric_from_sql_returns_list() -> None:
    metrics = ExampleMetric.from_sql("SELECT 'a' AS name, 1 AS value")
    assert_type(metrics, list[ExampleMetric])
    assert metrics == [ExampleMetric(name="a", value=1)]


def test_metric_from_sql_passes_connection_through() -> None:
    conn = duckdb.connect()
    conn.execute("CREATE TABLE t AS SELECT 'a' AS name, 1 AS value")
    metrics = ExampleMetric.from_sql("SELECT * FROM t", connection=conn)
    assert metrics == [ExampleMetric(name="a", value=1)]
    conn.close()
