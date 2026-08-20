# Agent Instructions - Oracle MCP Server

## Project Overview

This is a **production-ready Model Context Protocol (MCP) server** that exposes three read-only tools for querying an Oracle Database. It's designed to integrate with AI assistants like Claude via the MCP stdio transport.

**Key characteristics:**
- Enforces read-only queries (blocks DROP, DELETE, UPDATE, INSERT, etc.)
- Connection pooling with automatic resource cleanup
- Environment-based credentials (secure, no hardcoded secrets)
- Comprehensive error handling without crashes

## Critical Setup Conventions

### 1. Environment Variables - Mandatory

**All database connection parameters come from environment variables only** — no hardcoded credentials in the repo.

**Required env vars:**
```
ORACLE_HOST      - database hostname (e.g., tpaldiipvd047scan.ebiz.verizon.com)
ORACLE_PORT      - listener port (default: 1521)
ORACLE_SERVICE   - service name (e.g., r2w1st011)
ORACLE_USER      - schema/user (e.g., purnajo)
ORACLE_PASSWORD  - database password
```

### 2. `.env` File Pattern

The codebase uses a `.env` file approach for **local development only**:
- `.env.example` is checked into the repo as a template
- `.env` (actual credentials) is created locally by each developer and **gitignore'd**
- `oracle_mcp_server.py` loads `.env` via `load_dotenv()` if it exists; process env vars are used as fallback
- **Never commit `.env`** — it contains sensitive credentials

**Setup step:**
```powershell
Copy-Item .env.example .env
# Edit .env with actual Oracle credentials
```

### 3. Server vs. Implementation

- **`server.py`** — compatibility entrypoint (thin wrapper)
- **`oracle_mcp_server.py`** — actual implementation with all tool logic
  - Always edit the real implementation file
  - `server.py` should remain minimal

## Project Structure & Key Files

| File | Purpose | Notes |
|------|---------|-------|
| `oracle_mcp_server.py` | Main MCP server implementation | All three tools defined here; read-only enforcement logic |
| `server.py` | Compatibility entrypoint | Thin wrapper, keep minimal |
| `.env.example` | Environment template | Copy to `.env` for local development |
| `.env` | Local credentials (gitignore'd) | User-specific, never commit |
| `mcp.json` | MCP client config | Generated from `mcp.template.json` by `generate_mcp.ps1` |
| `mcp.template.json` | Template for `mcp.json` | Uses `{ENV_VAR}` syntax for substitution |
| `streamlit_app.py` | Guided validation workbench UI | Includes RBM/UBSR playbook for DT/recon checks |
| `requirements.txt` | Python dependencies | mcp, oracledb, streamlit, pandas, etc. |
| `setup.ps1` / `setup.bat` | Bootstrap scripts | Creates venv, installs dependencies |
| `run_server.ps1` / `run_server.bat` | Server startup scripts | Windows-friendly execution |
| `.venv/` | Virtual environment | Managed by setup scripts; never commit |
| `deploy_web_bundle/` | Heroku/web deployment bundle | Has its own Dockerfile, runtime.txt, Procfile |

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for full details.

## Three Core Tools

### `list_tables()`
- **Purpose:** Enumerate all accessible tables in the user's schema
- **Signature:** No parameters
- **Returns:** Array of table names
- **Implementation location:** `oracle_mcp_server.py` (search for `list_tables` tool definition)

### `describe_table(table_name: str)`
- **Purpose:** Retrieve column metadata (name, type, nullable, precision, scale)
- **Signature:** Takes single string parameter `table_name`
- **Returns:** Column metadata from `user_tab_columns`
- **Implementation location:** `oracle_mcp_server.py`

### `execute_query(sql: str)`
- **Purpose:** Run SELECT queries safely against the database
- **Signature:** Takes single string parameter `sql` (SELECT statement)
- **Returns:** Query results as rows
- **Safety enforcement:** Blocks keywords: DROP, DELETE, UPDATE, INSERT, CREATE, ALTER, etc.
- **Implementation location:** `oracle_mcp_server.py` — see the `_is_mutation_query()` regex pattern
- **Key gotcha:** The regex pattern in `_is_mutation_query()` must be kept in sync with blocked keywords

## Common Tasks & Commands

### Setup & Installation
```powershell
# Windows PowerShell (recommended)
cd c:\Users\purnajo\Documents\oracle-mcp-server
.\setup.ps1                    # Create venv, install dependencies
Copy-Item .env.example .env    # Create local .env
# Edit .env with your Oracle credentials
```

### Run the Server
```powershell
# Activate venv first (setup.ps1 does this, but if starting fresh):
.\.venv\Scripts\Activate.ps1

# Start the MCP server (stdio transport)
python oracle_mcp_server.py
```

Or use the convenience script:
```powershell
.\run_server.ps1
```

### Test the Setup
```powershell
# After setup.ps1, test the connection
python test_server.py
```

### Generate MCP Client Config
```powershell
# Generates mcp.json from mcp.template.json using current env vars
.\generate_mcp.ps1
```

The script:
- Reads `ORACLE_HOST`, `ORACLE_PORT`, `ORACLE_SERVICE`, `ORACLE_USER`, `ORACLE_PASSWORD`
- Substitutes them into `mcp.template.json`
- Writes `mcp.json` with **UTF-8 without BOM** encoding

### Run Streamlit Validation App
```powershell
streamlit run streamlit_app.py
```

Opens an interactive validation workbench with:
- **Guided Playbook** tab for RBM/UBSR split validation
- Templates for DT (data transfer), reconciliation, pricing, billing calcs checks

## Important Implementation Details

### Connection Pooling & Resource Management
- `oracle_mcp_server.py` maintains a connection pool
- Always ensure connections are properly closed to avoid resource leaks
- The MCP transport (stdio) is responsible for lifecycle management

### Read-Only Query Enforcement
- The `_is_mutation_query()` function (in `oracle_mcp_server.py`) uses regex to detect mutation keywords
- **Current blocked keywords:** DROP, DELETE, UPDATE, INSERT, CREATE, ALTER, TRUNCATE, GRANT, REVOKE, etc.
- Pattern is case-insensitive and handles comment-stripped SQL
- When modifying this list, keep sync'd with all docs mentioning "read-only"

### Logging
- All logging goes to **stderr** (stdout is reserved for MCP framing)
- Log level: INFO by default
- Format: timestamp [LEVEL] logger_name: message

### Error Handling
- Errors should **not** crash the server
- Wrap tool implementations in try-except blocks
- Return user-friendly error messages in MCP tool responses

## Deployment & Advanced Topics

For deployment to Heroku or cloud platforms, see [ADVANCED_CONFIG.md](ADVANCED_CONFIG.md):
- Deployment checklist
- Monitoring & logging strategies
- Performance tuning
- Multi-instance setup (RBM, UBSR, COMMON databases)

## Streamlit App (`streamlit_app.py`)

Provides a **guided validation workbench**:
- Multi-page UI for database validation checks
- DT (data transfer), reconciliation, pricing, and billing calculation validation
- RBM-specific and UBSR-specific split validation templates
- Connects to multiple databases via separate MCP instances

When modifying:
- Maintain the `DbConfig` and `QueryResult` dataclasses
- RBM/UBSR prefixes drive table name resolution
- Keep validation logic in the playbook templates to avoid hardcoding

## Gotchas & Common Pitfalls

1. **Forgot to create `.env`?** → Setup will fail with "missing env vars" error. Copy `.env.example` and fill in credentials.

2. **Python version mismatch** → Requires Python 3.8+. Check with `python --version`.

3. **Oracle client libraries** → `oracledb` (Oracle's pure Python driver) should handle most cases, but some environments need the Oracle Instant Client. See [QUICKSTART.md](QUICKSTART.md).

4. **Connection timeout** → If the server hangs on startup, check `ORACLE_HOST` and network connectivity.

5. **Mutation query not blocked?** → The `_is_mutation_query()` regex may need updating. Test with `python -c "from oracle_mcp_server import _is_mutation_query; print(_is_mutation_query('DELETE FROM table'))"`.

6. **MCP transport issues** → If the server starts but doesn't respond to requests, verify stdio framing is correct (MCPServer from `mcp.server.mcpserver`).

## Documentation Map

| Document | When to Read | Duration |
|----------|--------------|----------|
| [QUICKSTART.md](QUICKSTART.md) | First time setup | 5 min |
| [README.md](README.md) | Full feature overview & usage | 30 min |
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | Understanding file organization | 10 min |
| [ADVANCED_CONFIG.md](ADVANCED_CONFIG.md) | Deployment, multi-instance, monitoring | 20 min |
| This file | Agent-specific guidance | 10 min |

---

**Last updated:** August 2026  
**For questions about extending this codebase:** Review the tool implementations in `oracle_mcp_server.py` and see examples in `streamlit_app.py` for multi-database patterns.
