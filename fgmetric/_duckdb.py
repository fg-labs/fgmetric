from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

_MISSING_DUCKDB_MESSAGE = (
    "DuckDB is required to read metrics from SQL. Install it with: pip install 'fgmetric[duckdb]'"
)


def query_rows(
    query: str,
    connection: "DuckDBPyConnection | None" = None,
) -> list[dict[str, Any]]:
    """
    Run a DuckDB SQL query and return its rows as column-keyed dicts.

    When `connection` is omitted, a transient in-memory DuckDB connection is opened for the
    query and closed before returning. A supplied connection is used as-is and never closed,
    so the caller may pre-configure extensions, secrets, or `ATTACH` and reuse it across calls.

    Args:
        query: A DuckDB SQL query. The query names its own source, e.g.
            `SELECT * FROM 'data.parquet'`.
        connection: An open DuckDB connection to run the query against. When `None`, a
            transient in-memory connection is created and closed internally.

    Returns:
        One dict per result row, keyed by the query's output column names. Values are DuckDB's
        native Python types (e.g. `int`, `float`, `Decimal`, `bool`, `None` for SQL NULL).

    Raises:
        ImportError: If the optional `duckdb` dependency is not installed.
    """
    try:
        import duckdb
    except ImportError as error:
        raise ImportError(_MISSING_DUCKDB_MESSAGE) from error

    conn = connection if connection is not None else duckdb.connect()
    try:
        relation = conn.sql(query)
        columns = relation.columns
        return [dict(zip(columns, row, strict=True)) for row in relation.fetchall()]
    finally:
        if connection is None:
            conn.close()
