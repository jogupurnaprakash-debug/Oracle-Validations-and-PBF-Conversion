# Oracle Database MCP Server

A production-ready Model Context Protocol (MCP) server that exposes safe, read-only tools for querying an Oracle Database. Perfect for integrating with AI assistants like Claude.

## Features

âœ… **Secure Connection Pooling**: Efficient connection management with automatic resource cleanup  
âœ… **Read-Only Enforcement**: Prevents accidental or malicious data mutations (DROP, DELETE, UPDATE, INSERT, etc.)  
âœ… **Comprehensive Error Handling**: Clear error messages without crashing the server  
âœ… **Environment-Based Credentials**: Secure credential management using `.env` files  
âœ… **Three Powerful Tools**:
- `list_tables`: List all accessible tables
- `describe_table`: Get column metadata for any table
- `execute_query`: Run SELECT queries safely

## Prerequisites

- Python 3.8+
- Oracle Database 11g or later (compatible with Thin client mode)
- Network access to the Oracle Database server

## Installation

### 1. Clone or Copy Project

```bash
cd c:\Users\purnajo\Documents\oracle-mcp-server
```

### 2. Create Python Virtual Environment

```powershell
# In PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Or for Bash/Git Bash:
```bash
python -m venv .venv
source .venv/Scripts/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example environment file and add your credentials:

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your actual Oracle credentials
# Use your favorite editor (notepad, VS Code, etc.)
```

**Important**: Your `.env` file contains sensitive credentials. Never commit it to version control.

### Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `ORACLE_HOST` | Oracle database hostname | `tpaldiipvd047scan.ebiz.verizon.com` |
| `ORACLE_PORT` | Oracle database port | `2056` |
| `ORACLE_SERVICE` | Oracle service name | `r2w1st011` |
| `ORACLE_USER` | Database username | `purnajo` |
| `ORACLE_PASSWORD` | Database password | (from env var) |

## Running the Server

### Basic Usage

```bash
# Ensure virtual environment is activated
python oracle_mcp_server.py
```

The server will:
1. Load credentials from `.env`
2. Initialize a connection pool with 2-10 connections
3. Register the three tools
4. Start listening for MCP requests via stdio

### Example Output

```
2025-08-12 10:30:45,123 - __main__ - INFO - Oracle connection pool initialized successfully
2025-08-12 10:30:46,456 - __main__ - INFO - Oracle MCP Server started successfully
```

### Server Logs

The server logs important events and errors to help with debugging:

```
2025-08-12 10:35:12,789 - __main__ - INFO - Executing query for table listing
2025-08-12 10:35:13,100 - __main__ - INFO - Query executed successfully, returned 15 tables
```

## Using with Claude or AI Assistants

### 1. Configure in Claude Desktop (MacOS/Windows)

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

Tip: You can start from `mcp.template.json` in this repository and copy the `mcpServers` block.

You can also generate `mcp.json` in one command from environment variables:

```powershell
$env:ORACLE_HOST="tpaldiipvd047scan.ebiz.verizon.com"
$env:ORACLE_PORT="2056"
$env:ORACLE_USER="purnajo"
$env:ORACLE_RBM_SERVICE="r2w1st011"
$env:ORACLE_UBSR_SERVICE="ub2wst011"
$env:ORACLE_RBM_PASSWORD="your_rbm_password"
$env:ORACLE_UBSR_PASSWORD="your_ubsr_password"
.\\generate_mcp.ps1
```

For Command Prompt users:

```bat
set ORACLE_HOST=tpaldiipvd047scan.ebiz.verizon.com
set ORACLE_PORT=2056
set ORACLE_USER=purnajo
set ORACLE_RBM_SERVICE=r2w1st011
set ORACLE_UBSR_SERVICE=ub2wst011
set ORACLE_RBM_PASSWORD=your_rbm_password
set ORACLE_UBSR_PASSWORD=your_ubsr_password
generate_mcp.bat
```

```json
{
  "mcpServers": {
    "oracle-db": {
      "command": "python",
      "args": ["c:\\Users\\purnajo\\Documents\\oracle-mcp-server\\oracle_mcp_server.py"],
      "env": {
        "ORACLE_HOST": "tpaldiipvd047scan.ebiz.verizon.com",
        "ORACLE_PORT": "2056",
        "ORACLE_SERVICE": "r2w1st011",
        "ORACLE_USER": "purnajo",
        "ORACLE_PASSWORD": "your_password_here"
      }
    }
  }
}
```

### 2. Using with MCP Tools

Once connected, you can use these tools in conversations:

**List Tables:**
```
User: "What tables are available in the database?"
Claude uses list_tables tool â†’ Returns all accessible tables
```

**Describe Table:**
```
User: "Show me the structure of the CUSTOMERS table"
Claude uses describe_table(table_name="CUSTOMERS") â†’ Returns column metadata
```

**Execute Query:**
```
User: "Give me the top 10 customers by balance"
Claude uses execute_query(sql_query="SELECT * FROM CUSTOMERS WHERE BALANCE > 1000 LIMIT 10")
â†’ Returns results as structured data
```

## Tool Specifications

### `list_tables`

Returns all tables accessible to the current user.

**Parameters**: None

**Returns**: List of table names

**Example**:
```
list_tables()
â†’ "Found 42 tables:
   ACCOUNTS
   CUSTOMERS
   ORDERS
   PRODUCTS
   ..."
```

---

### `describe_table`

Get detailed column metadata for a specific table.

**Parameters**:
- `table_name` (string, required): Name of the table

**Returns**: Column names, data types, lengths, and nullable status

**Example**:
```
describe_table(table_name="CUSTOMERS")
â†’ "Table: CUSTOMERS

   Columns:
     CUSTOMER_ID: NUMBER (nullable: NO)
     NAME: VARCHAR2(100) (nullable: NO)
     EMAIL: VARCHAR2(255) (nullable: YES)
     CREATED_DATE: DATE (nullable: NO)"
```

---

### `execute_query`

Execute a read-only SELECT query.

**Parameters**:
- `sql_query` (string, required): SELECT query to execute

**Returns**: Query results as list of dictionaries (rows)

**Security**:
- Only SELECT queries allowed
- Blocks: INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, MERGE
- Case-insensitive validation

**Example**:
```
execute_query(sql_query="SELECT customer_id, name FROM CUSTOMERS WHERE status='ACTIVE' LIMIT 5")
â†’ "Query returned 5 rows:

   Row 1:
     CUSTOMER_ID: 1001
     NAME: John Smith

   Row 2:
     CUSTOMER_ID: 1002
     NAME: Jane Doe
   ..."
```

## Connection Management

### Connection Pool Details

The server uses an Oracle connection pool with these defaults:

- **Minimum connections**: 2
- **Maximum connections**: 10
- **Auto-increment**: 1 connection at a time
- **Threading**: Enabled for concurrent requests

### Connection Lifecycle

Each tool call:
1. Acquires a connection from the pool (or waits if pool is full)
2. Executes the query
3. Returns the connection to the pool
4. Ensures cleanup even if an error occurs

This design prevents connection leaks and supports multiple concurrent requests.

## Error Handling

The server handles various error scenarios gracefully:

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Missing required Oracle connection parameters` | Missing `.env` file or incomplete config | Copy `.env.example` to `.env` and fill in all fields |
| `ORA-12514: TNS:listener does not currently know of service` | Wrong service name | Verify `ORACLE_SERVICE` in `.env` |
| `ORA-01017: invalid username/password` | Wrong credentials | Verify `ORACLE_USER` and `ORACLE_PASSWORD` |
| `ORA-12170: TNS:Connect timeout occurred` | Network unreachable | Check hostname and port, network connectivity |
| `Error: Only SELECT queries are allowed` | Attempted mutation query | Use only SELECT statements |
| `Table 'XXX' not found or has no columns` | Table doesn't exist | Check table name spelling and user permissions |

### Debugging

Check server logs for detailed error messages:

```bash
# Run with verbose output
python oracle_mcp_server.py

# Look for ERROR or WARNING messages
```

## Security Best Practices

âœ… **DO:**
- Store passwords in `.env` file (excluded from git)
- Use strong database passwords
- Limit database user permissions to read-only access
- Review queries before execution
- Rotate credentials periodically

âŒ **DON'T:**
- Commit `.env` file to version control
- Hardcode passwords in code
- Share your `.env` file
- Give the database user write permissions
- Run in production without proper security review

## Performance Optimization

### Query Performance Tips

1. **Use LIMIT clauses** for large tables:
   ```sql
   SELECT * FROM LARGE_TABLE LIMIT 1000
   ```

2. **Add filtering conditions**:
   ```sql
   SELECT * FROM CUSTOMERS WHERE status='ACTIVE'
   ```

3. **Use SELECT with specific columns**:
   ```sql
   SELECT customer_id, name FROM CUSTOMERS  -- Not SELECT *
   ```

4. **Connection pool is already optimized** with 2-10 connections

### Monitoring

The server logs key events:
- Connection pool initialization
- Successful queries
- Errors and exceptions

## Troubleshooting

### "Connection refused" Error

```
Cause: Cannot connect to the Oracle database
Solution:
1. Verify hostname: ping tpaldiipvd047scan.ebiz.verizon.com
2. Verify port is open: Test network connectivity to port 2056
3. Check firewall rules
4. Verify Oracle database is running
```

### "Table not found" Error

```
Cause: Table doesn't exist or user doesn't have permissions
Solution:
1. Run list_tables() to see accessible tables
2. Check table name spelling (case-sensitive in Oracle)
3. Verify user permissions: SELECT on the table
```

### No Output from Server

```
Cause: Server started but not receiving requests
Solution:
1. Ensure MCP configuration is correct
2. Check server logs for errors
3. Verify network connectivity
4. Restart the server
```

## Development & Testing

### Testing Locally

```powershell
# Run in development mode
python oracle_mcp_server.py

# In another terminal, you can manually test by examining logs
# or integrate with an MCP client
```

### Code Structure

```
oracle-mcp-server/
â”œâ”€â”€ oracle_mcp_server.py      # Main server implementation
â”œâ”€â”€ requirements.txt           # Python dependencies
â”œâ”€â”€ .env.example              # Environment variables template
â”œâ”€â”€ .env                       # Local credentials (not in git)
â””â”€â”€ README.md                 # This file
```

## Performance Metrics

Typical response times (varies with query complexity):
- `list_tables()`: 100-500ms
- `describe_table()`: 50-200ms
- `execute_query()`: 200-2000ms (depends on query complexity and data volume)

## License

This project is provided as-is for internal use.

## Support & Contribution

For issues, improvements, or questions:
1. Check the Troubleshooting section above
2. Review server logs
3. Verify database connectivity
4. Test with `sqlplus` or Oracle SQL Developer to confirm database access

## Version History

### v1.0.0 (Initial Release)
- Core MCP server with three tools
- Connection pooling
- Read-only query enforcement
- Environment-based configuration
- Comprehensive error handling

