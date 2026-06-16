import sys

import duckdb
import pytest

from fgmetric._duckdb import query_rows


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
