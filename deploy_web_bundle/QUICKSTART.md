# Quick Start Guide - Oracle MCP Server

## 5-Minute Setup

### Windows PowerShell Users (Recommended)

```powershell
# 1. Navigate to the project directory
cd c:\Users\purnajo\Documents\oracle-mcp-server

# 2. Run setup to create virtual environment and install dependencies
.\setup.ps1

# 3. Copy the environment template and edit with your credentials
Copy-Item .env.example .env
# Edit .env with your Oracle password and connection details

# 4. Start the server
.\run_server.ps1
```

### Windows Command Prompt Users

```batch
# 1. Navigate to the project directory
cd c:\Users\purnajo\Documents\oracle-mcp-server

# 2. Run setup
setup.bat

# 3. Copy and edit environment file
copy .env.example .env
notepad .env

# 4. Start the server
run_server.bat
```

### Manual Setup (All Platforms)

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/Scripts/activate  # On Windows
# or: .\.venv\Scripts\Activate.ps1  # PowerShell

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials
cp .env.example .env
# Edit .env with your credentials

# 4. Run the server
python oracle_mcp_server.py
```

---

## Expected Output

When the server starts successfully, you should see:

```
2025-08-12 10:30:45,123 - __main__ - INFO - Oracle connection pool initialized successfully
2025-08-12 10:30:46,456 - __main__ - INFO - Oracle MCP Server started successfully
```

The server is now ready to accept requests. Leave it running in the terminal.

---

## Using with Claude Desktop

1. **Find your Claude configuration file:**
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - macOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`

2. **Add the MCP server:**

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

3. **Restart Claude Desktop** - it will now detect the MCP server

4. **Start asking Claude about your database!**

```
User: "What tables are available?"
Claude: [Uses list_tables tool] "I found 42 tables in your database..."

User: "Describe the CUSTOMERS table"
Claude: [Uses describe_table tool] "The CUSTOMERS table has the following columns..."

User: "Show me the top 10 active customers"
Claude: [Uses execute_query tool] "SELECT * FROM CUSTOMERS WHERE status='ACTIVE' LIMIT 10"
```

---

## Troubleshooting

### Issue: "Missing required Oracle connection parameters"

**Solution:** Make sure your `.env` file exists and has all required fields:
```
ORACLE_HOST=tpaldiipvd047scan.ebiz.verizon.com
ORACLE_PORT=2056
ORACLE_SERVICE=r2w1st011
ORACLE_USER=purnajo
ORACLE_PASSWORD=your_actual_password
```

### Issue: "Connection refused" or "ORA-12514"

**Solutions:**
1. Verify hostname is correct: `ping tpaldiipvd047scan.ebiz.verizon.com`
2. Check network connectivity to port 2056
3. Verify you can connect with SQL Developer or sqlplus first

### Issue: "ORA-01017: invalid username/password"

**Solution:** Double-check your Oracle username and password in `.env`

### Issue: Virtual environment not found

**Solution:** Run `setup.ps1` or `setup.bat` to create it

---

## File Structure

```
oracle-mcp-server/
├── oracle_mcp_server.py          # Main server (read this to understand the code)
├── requirements.txt               # Python dependencies
├── .env.example                  # Template for credentials
├── .env                          # Your actual credentials (keep secret!)
├── .gitignore                    # Git ignore rules
├── README.md                     # Full documentation
├── QUICKSTART.md                 # This file
├── setup.bat                     # Windows batch setup script
├── setup.ps1                     # PowerShell setup script
├── run_server.bat                # Windows batch startup script
└── run_server.ps1               # PowerShell startup script
```

---

## Next Steps

1. ✅ Run setup
2. ✅ Configure `.env` with your credentials
3. ✅ Start the server with `run_server.ps1` or `run_server.bat`
4. ✅ Integrate with Claude Desktop using the configuration above
5. ✅ Test by asking Claude about your database!

---

## Need Help?

- **Read the full README.md** for detailed information
- **Check server logs** for error messages (they're very helpful!)
- **Verify database connectivity** with SQL Developer or sqlplus first
- **Review oracle_mcp_server.py** comments for code details

## Key Features at a Glance

✅ **list_tables** - See all your tables  
✅ **describe_table** - Inspect table structure  
✅ **execute_query** - Run SELECT queries safely  
✅ **Connection pooling** - Efficient resource management  
✅ **Read-only enforcement** - Prevents accidental data changes  
✅ **Error handling** - Clear error messages  

Happy querying! 🚀
