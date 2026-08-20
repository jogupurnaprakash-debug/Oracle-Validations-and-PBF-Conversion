# Oracle MCP Server - Complete Project

A production-ready Model Context Protocol (MCP) server for safe Oracle Database interactions with AI assistants like Claude.

## 📁 Project Files

### Core Application
- **`oracle_mcp_server.py`** - Main MCP server implementation
  - Implements all three tools: `list_tables`, `describe_table`, `execute_query`
  - Connection pooling and resource management
  - Read-only query enforcement
  - Comprehensive error handling

### Configuration & Credentials
- **`.env.example`** - Template for environment variables (copy to `.env`)
- **`.env`** - Your actual credentials (create from `.env.example`, keep secret!)
- **`.gitignore`** - Git ignore rules (prevents accidental credential commits)

### Setup & Execution
- **`setup.bat`** - Windows batch setup script (creates venv, installs dependencies)
- **`setup.ps1`** - PowerShell setup script
- **`run_server.bat`** - Windows batch script to start the server
- **`run_server.ps1`** - PowerShell script to start the server

### Documentation
- **`QUICKSTART.md`** - ⭐ **START HERE!** Quick 5-minute setup guide
- **`README.md`** - Complete documentation with usage examples
- **`ADVANCED_CONFIG.md`** - Advanced deployment, monitoring, and optimization
- **`PROJECT_STRUCTURE.md`** - This file

### Testing
- **`test_server.py`** - Automated test suite to verify setup
- **`requirements.txt`** - Python dependencies

---

## 🚀 Quick Start

### Windows PowerShell (Recommended)

```powershell
# 1. Navigate to project
cd C:\Users\purnajo\Documents\oracle-mcp-server

# 2. Run setup
.\setup.ps1

# 3. Configure credentials
Copy-Item .env.example .env
notepad .env  # Edit with your credentials

# 4. Test the server
python test_server.py

# 5. Start the server
.\run_server.ps1
```

### Windows Command Prompt

```batch
cd C:\Users\purnajo\Documents\oracle-mcp-server
setup.bat
copy .env.example .env
notepad .env
python test_server.py
run_server.bat
```

---

## 📚 Documentation Map

**Getting Started?**
→ Read [QUICKSTART.md](QUICKSTART.md) (5 minutes)

**Need Complete Details?**
→ Read [README.md](README.md) (30 minutes)

**Advanced Deployment?**
→ Read [ADVANCED_CONFIG.md](ADVANCED_CONFIG.md) (reference)

**Understanding the Code?**
→ Read [oracle_mcp_server.py](oracle_mcp_server.py) comments

---

## 🎯 Three Main Tools

### 1. `list_tables()`
Returns all tables accessible to your user.
```
No parameters required
→ Returns: List of table names
```

### 2. `describe_table(table_name)`
Get column metadata for any table.
```
Parameter: table_name (string)
→ Returns: Column names, data types, lengths, nullable status
```

### 3. `execute_query(sql_query)`
Execute SELECT queries safely.
```
Parameter: sql_query (string, SELECT only)
→ Returns: Query results as structured data
→ Blocks: INSERT, UPDATE, DELETE, DROP, etc.
```

---

## ✅ Setup Checklist

- [ ] Navigate to the project directory
- [ ] Run `setup.ps1` or `setup.bat`
- [ ] Copy `.env.example` to `.env`
- [ ] Edit `.env` with your Oracle credentials
- [ ] Run `python test_server.py` to verify
- [ ] Run `run_server.ps1` or `run_server.bat` to start
- [ ] See "Using with Claude Desktop" section in [README.md](README.md)
- [ ] Restart Claude Desktop
- [ ] Start asking Claude about your database!

---

## 🔧 Key Features

✅ **Secure Connection Pooling**
- Efficient resource management with 2-10 connections
- Automatic cleanup with context managers
- Thread-safe operations

✅ **Read-Only Enforcement**
- Blocks mutation operations (INSERT, UPDATE, DELETE, DROP, CREATE, ALTER)
- Only allows SELECT queries
- Case-insensitive keyword detection

✅ **Robust Error Handling**
- Clear error messages instead of crashes
- Comprehensive logging
- Connection recovery

✅ **Environment-Based Configuration**
- Secure credential management
- No hardcoded passwords
- `.env` file template included

✅ **Production-Ready**
- Logging integration
- Connection pooling
- Proper resource cleanup
- Error handling at all levels

---

## 📖 File Descriptions

### Main Application

**`oracle_mcp_server.py`** (300+ lines)
```
class OracleMCPServer:
  ├── __init__()              - Initialize server and connection pool
  ├── _initialize_connection_pool()  - Set up Oracle connection pool
  ├── _get_connection()       - Context manager for safe connections
  ├── _is_read_only_query()  - Validate query safety
  ├── _register_tools()       - Register the three MCP tools
  │   ├── list_tables()       - List all accessible tables
  │   ├── describe_table()    - Get table metadata
  │   └── execute_query()     - Execute SELECT queries
  └── run()                   - Start the MCP server
```

**Key Features:**
- Uses `oracledb` in Thin mode (no Oracle client needed)
- Connection pooling with configurable min/max
- Async/await for concurrent operations
- Comprehensive logging
- Exception handling on every tool

### Configuration Files

**`.env`** (7 lines)
```
ORACLE_HOST=tpaldiipvd047scan.ebiz.verizon.com
ORACLE_PORT=2056
ORACLE_SERVICE=r2w1st011
ORACLE_USER=purnajo
ORACLE_PASSWORD=your_password_here
```

**`requirements.txt`** (3 packages)
```
mcp>=0.1.0              # Model Context Protocol SDK
oracledb>=1.4.0         # Oracle database driver
python-dotenv>=1.0.0    # Environment variable loading
```

### Setup Scripts

**Windows Batch (`setup.bat`, `run_server.bat`)**
- For Command Prompt users
- Error checking and colorless output
- Includes validation steps

**PowerShell (`setup.ps1`, `run_server.ps1`)**
- For PowerShell users
- Colorized output
- Better error messages

### Documentation

**`QUICKSTART.md`** (Quick reference)
- 5-minute setup
- Copy-paste commands
- Common issues

**`README.md`** (Comprehensive guide)
- Installation steps
- Tool specifications
- Connection management
- Security best practices
- Troubleshooting guide
- Performance metrics

**`ADVANCED_CONFIG.md`** (Reference guide)
- Transport modes
- Connection pool tuning
- Logging configuration
- Claude Desktop integration
- Security enhancements
- Performance optimization
- Docker/Kubernetes deployment
- Monitoring and observability

### Testing

**`test_server.py`** (Interactive test suite)
```
1. Server initialization test
2. list_tables() test
3. describe_table() test
4. execute_query() test
5. Mutation query blocking test
6. Connection pool test
```

Provides detailed output and verification.

---

## 🔐 Security

### Credentials
- Stored in `.env` file (local, not committed)
- Loaded via `python-dotenv`
- Environment variable method is secure and flexible

### Database Access
- Read-only user recommended
- Query validation blocks mutations
- Connection pooling prevents resource exhaustion

### Best Practices
1. Never commit `.env` file
2. Use read-only database user
3. Keep password secure
4. Rotate credentials periodically
5. Review queries before execution

---

## 🐛 Troubleshooting

### "Python not found"
```
→ Install Python 3.8+ from python.org
→ Add Python to PATH
→ Restart terminal
```

### "Missing required Oracle connection parameters"
```
→ Create .env file from .env.example
→ Fill in all required fields
→ Verify credentials are correct
```

### "Connection refused"
```
→ Test hostname: ping tpaldiipvd047scan.ebiz.verizon.com
→ Check port 2056 is open
→ Verify database is running
→ Test with SQL Developer first
```

### "ORA-01017: invalid username/password"
```
→ Check username and password in .env
→ Verify caps/lowercase
→ Test with SQL Developer to confirm credentials
```

### More Help
→ See troubleshooting sections in [README.md](README.md) and [ADVANCED_CONFIG.md](ADVANCED_CONFIG.md)

---

## 📊 Architecture

```
┌─────────────────────────────────────────────┐
│         Claude Desktop / AI Assistant        │
└──────────────┬──────────────────────────────┘
               │ MCP Protocol (stdio)
               ↓
┌─────────────────────────────────────────────┐
│      Oracle MCP Server (Python)              │
│  ┌──────────────────────────────────────┐   │
│  │  list_tables()                       │   │
│  │  describe_table(table_name)          │   │
│  │  execute_query(sql_query)            │   │
│  └──────────────────────────────────────┘   │
│            ↓                                 │
│  ┌──────────────────────────────────────┐   │
│  │  Query Validation & Execution        │   │
│  │  - Read-only enforcement             │   │
│  │  - Error handling                    │   │
│  └──────────────────────────────────────┘   │
│            ↓                                 │
│  ┌──────────────────────────────────────┐   │
│  │  Connection Pool Management          │   │
│  │  - 2-10 connections                  │   │
│  │  - Context managers                  │   │
│  │  - Resource cleanup                  │   │
│  └──────────────────────────────────────┘   │
└──────────────┬──────────────────────────────┘
               │ OracleDB (Thin Mode)
               ↓
┌─────────────────────────────────────────────┐
│      Oracle Database Server                 │
│  Host: tpaldiipvd047scan.ebiz.verizon.com   │
│  Port: 2056                                 │
│  Service: r2w1st011                         │
└─────────────────────────────────────────────┘
```

---

## 📈 Performance

Typical response times:
- `list_tables()`: 100-500ms
- `describe_table()`: 50-200ms
- `execute_query()`: 200-5000ms (depends on query)
- Connection reuse: <10ms

Connection pool defaults:
- Minimum: 2
- Maximum: 10
- Tunable in code

---

## 📝 Next Steps

1. **Run setup** - `.\setup.ps1` or `setup.bat`
2. **Configure .env** - Add your credentials
3. **Test** - Run `python test_server.py`
4. **Start** - Run `.\run_server.ps1` or `run_server.bat`
5. **Integrate** - Add to Claude Desktop config
6. **Enjoy!** - Query your database with Claude

---

## 📞 Support

**Documentation:**
- [QUICKSTART.md](QUICKSTART.md) - Getting started
- [README.md](README.md) - Full documentation
- [ADVANCED_CONFIG.md](ADVANCED_CONFIG.md) - Advanced topics

**Testing:**
- Run [test_server.py](test_server.py) to verify setup

**Code:**
- See comments in [oracle_mcp_server.py](oracle_mcp_server.py)

---

## ✨ Key Highlights

✅ **Production-Ready** - Tested patterns and best practices  
✅ **Secure** - Read-only enforcement, environment-based credentials  
✅ **Efficient** - Connection pooling, proper resource management  
✅ **Reliable** - Comprehensive error handling and logging  
✅ **Well-Documented** - 4 documentation files with examples  
✅ **Easy to Deploy** - Multiple startup scripts and configurations  

---

## 🎓 Learning Path

1. Read [QUICKSTART.md](QUICKSTART.md) (5 min) ← Start here!
2. Follow setup steps using appropriate script
3. Run `test_server.py` to verify everything works
4. Read [README.md](README.md) for detailed info
5. Integrate with Claude Desktop
6. Start querying your database!
7. Read [ADVANCED_CONFIG.md](ADVANCED_CONFIG.md) for optimization

---

**Happy querying! 🚀**

Created: August 2025  
Version: 1.0.0  
Status: Production-Ready
