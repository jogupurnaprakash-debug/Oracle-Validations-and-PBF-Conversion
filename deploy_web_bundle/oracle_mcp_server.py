"""
Production-Ready Oracle Database MCP Server

Exposes three read-only tools over the MCP stdio transport so that an AI
agent (or VS Code Copilot) can introspect and query any Oracle database.

All connection parameters come exclusively from environment variables so
that a single script can serve multiple databases (RBM, UBSR, …) by
launching separate instances with different environment variable sets.

Required environment variables
--------------------------------
  ORACLE_HOST      - database host name or IP
  ORACLE_PORT      - listener port (default: 1521)
  ORACLE_SERVICE   - service name
  ORACLE_USER      - schema / user
  ORACLE_PASSWORD  - password

Tools
-----
  list_tables     - SELECT table_name FROM user_tables
  describe_table  - column metadata from user_tab_columns
  execute_query   - arbitrary SELECT (mutation keywords blocked)

Transport: stdio  (compatible with VS Code MCP client and mcp CLI)
"""

import logging
import os
import re
import sys
from pathlib import Path

import oracledb
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

# ---------------------------------------------------------------------------
# Logging  (stderr keeps stdout clean for the MCP stdio framing)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("oracle-mcp-server")


def _load_environment() -> None:
    """Load environment variables from a local .env file when present."""
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
    else:
        # Keep startup flexible: direct env vars still work without a .env file.
        logger.info("No .env file found at %s; using process environment only.", env_path)


_load_environment()

# ---------------------------------------------------------------------------
# Connection parameters - 100 % from environment variables
# ---------------------------------------------------------------------------
ORACLE_HOST     = os.environ.get("ORACLE_HOST",     "").strip()
ORACLE_PORT     = os.environ.get("ORACLE_PORT",     "1521").strip()
ORACLE_SERVICE  = os.environ.get("ORACLE_SERVICE",  "").strip()
ORACLE_USER     = os.environ.get("ORACLE_USER",     "").strip()
ORACLE_PASSWORD = os.environ.get("ORACLE_PASSWORD", "").strip()

_MISSING = [
    name
    for name, val in {
        "ORACLE_HOST":     ORACLE_HOST,
        "ORACLE_SERVICE":  ORACLE_SERVICE,
        "ORACLE_USER":     ORACLE_USER,
        "ORACLE_PASSWORD": ORACLE_PASSWORD,
    }.items()
    if not val
]
if _MISSING:
    logger.critical(
        "Missing required environment variable(s): %s -- server cannot start. "
        "Set them in the process env or create a .env file in %s.",
        ", ".join(_MISSING),
        Path(__file__).resolve().parent,
    )
    sys.exit(1)

# oracledb defaults to Thin mode; no Oracle Client libraries required.

# ---------------------------------------------------------------------------
# FastMCP server instance
# ---------------------------------------------------------------------------
mcp = MCPServer("oracle-db-mcp")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _connect() -> oracledb.Connection:
    """Open a fresh Thin-mode connection using the env-var credentials."""
    dsn = f"{ORACLE_HOST}:{ORACLE_PORT}/{ORACLE_SERVICE}"
    return oracledb.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)


_MUTATION_RE = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|CREATE|ALTER|TRUNCATE|MERGE)\b",
    re.IGNORECASE,
)


def _is_select_only(query: str) -> bool:
    """Return True only when *query* is a bare SELECT with no mutation keywords."""
    stripped = query.strip()
    if not re.match(r"^\s*SELECT\b", stripped, re.IGNORECASE):
        return False
    if _MUTATION_RE.search(stripped):
        return False
    return True


# ---------------------------------------------------------------------------
# Tool: list_tables
# ---------------------------------------------------------------------------

@mcp.tool()
def list_tables() -> str:
    """
    List all tables owned by the connected Oracle user.

    Returns a newline-separated list of table names sorted alphabetically.
    """
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT table_name FROM user_tables ORDER BY table_name"
                )
                names = [row[0] for row in cur.fetchall()]

        logger.info("list_tables: returned %d tables", len(names))
        if not names:
            return "No tables found for this user."
        return f"Found {len(names)} table(s):\n" + "\n".join(names)

    except oracledb.DatabaseError as exc:
        logger.error("list_tables database error: %s", exc)
        return f"Database error: {exc}"
    except Exception as exc:
        logger.exception("list_tables unexpected error")
        return f"Unexpected error: {exc}"


# ---------------------------------------------------------------------------
# Tool: describe_table
# ---------------------------------------------------------------------------

@mcp.tool()
def describe_table(table_name: str) -> str:
    """
    Return column metadata for a table owned by the connected Oracle user.

    Args:
        table_name: Name of the table to describe (case-insensitive).

    Returns a formatted list of columns with data type, length, and nullability.
    """
    if not table_name or not table_name.strip():
        return "Error: table_name must be a non-empty string."

    table_upper = table_name.strip().upper()

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT column_name,
                           data_type,
                           data_length,
                           nullable
                    FROM   user_tab_columns
                    WHERE  table_name = :tname
                    ORDER  BY column_id
                    """,
                    tname=table_upper,
                )
                rows = cur.fetchall()

        if not rows:
            return f"Table '{table_upper}' not found or has no columns."

        lines = [f"Table: {table_upper}", "", "Columns:"]
        for col_name, data_type, data_length, nullable in rows:
            length_str = f"({data_length})" if data_length else ""
            null_str   = "NULL" if nullable == "Y" else "NOT NULL"
            lines.append(f"  {col_name}: {data_type}{length_str}  {null_str}")

        logger.info("describe_table: %s - %d column(s)", table_upper, len(rows))
        return "\n".join(lines)

    except oracledb.DatabaseError as exc:
        logger.error("describe_table database error for '%s': %s", table_upper, exc)
        return f"Database error: {exc}"
    except Exception as exc:
        logger.exception("describe_table unexpected error for '%s'", table_upper)
        return f"Unexpected error: {exc}"


# ---------------------------------------------------------------------------
# Tool: execute_query
# ---------------------------------------------------------------------------

@mcp.tool()
def execute_query(sql_query: str) -> str:
    """
    Execute a read-only SELECT statement and return results as formatted text.

    Only SELECT statements are permitted.  The following keywords are blocked
    even inside a SELECT to prevent injection via sub-queries or CTEs that
    attempt side-effects: DROP, DELETE, UPDATE, INSERT, CREATE, ALTER,
    TRUNCATE, MERGE.

    Args:
        sql_query: A valid Oracle SELECT statement.

    Returns results as formatted text with one row per block.
    """
    if not sql_query or not sql_query.strip():
        return "Error: sql_query must be a non-empty string."

    if not _is_select_only(sql_query):
        return (
            "Error: Only SELECT statements are permitted. "
            "Mutation keywords (DROP, DELETE, UPDATE, INSERT, "
            "CREATE, ALTER, TRUNCATE, MERGE) are not allowed."
        )

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_query)
                col_names = [d[0] for d in cur.description]
                rows = cur.fetchall()

        if not rows:
            return "Query executed successfully. No rows returned."

        lines = [f"Query returned {len(rows)} row(s):\n"]
        for i, row in enumerate(rows, 1):
            lines.append(f"Row {i}:")
            for col, val in zip(col_names, row):
                lines.append(f"  {col}: {val}")
            lines.append("")

        logger.info("execute_query: returned %d rows", len(rows))
        return "\n".join(lines)

    except oracledb.DatabaseError as exc:
        logger.error("execute_query database error: %s", exc)
        return f"Database error: {exc}"
    except Exception as exc:
        logger.exception("execute_query unexpected error")
        return f"Unexpected error: {exc}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the MCP server on stdio transport."""
    logger.info(
        "Oracle MCP Server starting | host=%s port=%s service=%s user=%s",
        ORACLE_HOST, ORACLE_PORT, ORACLE_SERVICE, ORACLE_USER,
    )
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
