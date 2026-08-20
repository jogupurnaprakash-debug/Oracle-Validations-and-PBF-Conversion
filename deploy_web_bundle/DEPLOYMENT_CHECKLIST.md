# Deployment Checklist

Use this checklist to ensure your Oracle MCP Server is ready for production use with Claude Desktop or other MCP clients.

## ✅ Pre-Deployment Verification

### Environment Setup
- [ ] Python 3.8+ installed (`python --version`)
- [ ] Virtual environment created (`.venv` directory exists)
- [ ] Virtual environment activated
- [ ] All dependencies installed (`pip list` shows mcp, oracledb, python-dotenv)

### Credentials Configuration
- [ ] `.env` file created (from `.env.example`)
- [ ] All required environment variables set:
  - [ ] `ORACLE_HOST` = tpaldiipvd047scan.ebiz.verizon.com
  - [ ] `ORACLE_PORT` = 2056
  - [ ] `ORACLE_SERVICE` = r2w1st011
  - [ ] `ORACLE_USER` = purnajo
  - [ ] `ORACLE_PASSWORD` = (securely set)
- [ ] `.env` file is in `.gitignore`
- [ ] `.env` is NOT tracked by git

### Database Connectivity
- [ ] Oracle database hostname is reachable (`ping tpaldiipvd047scan.ebiz.verizon.com`)
- [ ] Port 2056 is accessible (can connect from your machine)
- [ ] Database credentials work (tested with SQL Developer or sqlplus)
- [ ] Database user has SELECT permissions

### Server Testing
- [ ] `python test_server.py` runs without errors
- [ ] test_server.py shows "All tests passed successfully!"
- [ ] `list_tables()` returns table names
- [ ] `describe_table()` returns column metadata
- [ ] `execute_query()` returns results
- [ ] Mutation queries are properly blocked

### Code Review
- [ ] [oracle_mcp_server.py](oracle_mcp_server.py) has been reviewed
- [ ] Connection pool settings are appropriate for your workload
- [ ] Error messages are clear
- [ ] Logging is configured as needed

---

## 🔒 Security Checklist

- [ ] `.env` file contains only placeholder passwords in `.env.example`
- [ ] Real credentials are ONLY in local `.env` (never committed)
- [ ] `.gitignore` includes `.env`
- [ ] Database user has only SELECT permissions (read-only)
- [ ] Query validation is enforced (mutation blocking works)
- [ ] No passwords appear in logs
- [ ] Connection pool is thread-safe

---

## 📦 File Integrity

Verify all required files exist:
- [ ] `oracle_mcp_server.py` - Main server
- [ ] `requirements.txt` - Dependencies list
- [ ] `.env.example` - Credentials template
- [ ] `.env` - Local credentials (not in repo)
- [ ] `.gitignore` - Git ignore rules
- [ ] `setup.ps1` / `setup.bat` - Setup scripts
- [ ] `run_server.ps1` / `run_server.bat` - Startup scripts
- [ ] `test_server.py` - Test suite
- [ ] `README.md` - Documentation
- [ ] `QUICKSTART.md` - Quick start guide
- [ ] `ADVANCED_CONFIG.md` - Advanced config reference
- [ ] `PROJECT_STRUCTURE.md` - File descriptions
- [ ] `DEPLOYMENT_CHECKLIST.md` - This file

---

## 🚀 Pre-Claude Integration

Before adding to Claude Desktop, verify:

### Windows/PowerShell
- [ ] `.\run_server.ps1` starts the server
- [ ] Server shows "Oracle MCP Server started successfully"
- [ ] No error messages appear in the logs
- [ ] Can stop server with Ctrl+C without errors

### Command Prompt
- [ ] `run_server.bat` starts the server
- [ ] Server shows "Oracle MCP Server started successfully"
- [ ] No error messages appear in the logs
- [ ] Can stop server with Ctrl+C without errors

### Server Behavior
- [ ] Server starts within 5 seconds
- [ ] No connection timeouts occur
- [ ] Connection pool initializes with 2-10 connections
- [ ] Tools are ready to receive requests

---

## 🔌 Claude Desktop Integration

### Configuration File
- [ ] Located at: `%APPDATA%\Claude\claude_desktop_config.json`
- [ ] Contains `mcpServers` section
- [ ] Has `oracle-db` entry configured

### MCP Server Configuration
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
        "ORACLE_PASSWORD": "your_password"
      }
    }
  }
}
```

Verify:
- [ ] File path is correct (absolute path to oracle_mcp_server.py)
- [ ] All environment variables are set
- [ ] JSON syntax is valid (use jsonlint.com if unsure)
- [ ] No trailing commas in JSON

### Claude Desktop Restart
- [ ] Close Claude Desktop completely
- [ ] Wait 5 seconds
- [ ] Restart Claude Desktop
- [ ] Wait for initial load (20-30 seconds)
- [ ] No error messages in Claude interface

---

## ✨ Functional Testing with Claude

After Claude Desktop starts, test the integration:

### Test 1: List Tables
```
User: "What tables are available in the database?"
Expected: Claude shows list of tables
          Response includes table names in JSON or text format
          No errors
```

### Test 2: Describe Table
```
User: "Describe the structure of the [TABLE_NAME] table"
Expected: Claude shows columns, data types, nullable status
          Response is formatted clearly
          No errors
```

### Test 3: Execute Query
```
User: "Show me the results of: SELECT * FROM [TABLE] LIMIT 10"
Expected: Claude executes query and returns results
          Results formatted as table or list
          No errors
```

### Test 4: Query Blocking
```
User: "Delete all records from [TABLE]"
Expected: Claude explains mutation queries are not allowed
          Error message is clear
          No actual query executed
```

---

## 📊 Performance Baseline

After deployment, measure:

| Metric | Baseline | Goal |
|--------|----------|------|
| Server startup time | < 5s | < 5s |
| list_tables() response | 100-500ms | < 1s |
| describe_table() response | 50-200ms | < 500ms |
| execute_query() response | 200-5000ms | < 10s for typical queries |
| Connection pool efficiency | 2-10 active | Stable |

---

## 🐛 Troubleshooting During Deployment

### Server won't start
```
1. Check .env file exists and is complete
2. Verify ORACLE_PASSWORD is not empty
3. Check Python dependencies: pip install -r requirements.txt
4. Review error message in console
5. Run test_server.py to identify specific issue
```

### Claude Desktop won't detect server
```
1. Check claude_desktop_config.json syntax
2. Verify absolute path to oracle_mcp_server.py
3. Check file permissions (should be readable)
4. Restart Claude Desktop
5. Check Claude Desktop logs for errors
```

### Queries fail in Claude
```
1. Run test_server.py to verify server works standalone
2. Check database connectivity
3. Verify user permissions
4. Check for network issues
5. Review server logs for detailed errors
```

### Slow query performance
```
1. Check query complexity (add LIMIT, WHERE clauses)
2. Verify database indexes
3. Check network latency
4. Review connection pool settings
5. See ADVANCED_CONFIG.md for optimization tips
```

---

## 📈 Post-Deployment Monitoring

### Daily Checks
- [ ] Server starts cleanly
- [ ] No connection errors in logs
- [ ] Claude can query database successfully
- [ ] Response times are acceptable

### Weekly Checks
- [ ] Review logs for errors or warnings
- [ ] Test each tool at least once
- [ ] Check query performance trends
- [ ] Verify database connectivity

### Monthly Checks
- [ ] Run full test suite (test_server.py)
- [ ] Review connection pool statistics
- [ ] Check for any performance degradation
- [ ] Update credentials if needed

---

## 🔄 Rollback Plan

If issues arise, here's how to rollback:

### Immediate Rollback
```
1. Remove oracle-db from claude_desktop_config.json
2. Restart Claude Desktop
3. Verify Claude is working without MCP server
```

### Restore Previous Version
```
1. Keep backup of working oracle_mcp_server.py
2. If version fails, restore from backup
3. Test with test_server.py
4. Reconfigure Claude Desktop
```

---

## 📋 Sign-Off

### Development Sign-Off
- [ ] Developer: ____________________
- [ ] Date: ____________________
- [ ] All tests passed: Yes / No
- [ ] Code reviewed: Yes / No

### QA Sign-Off (if applicable)
- [ ] QA: ____________________
- [ ] Date: ____________________
- [ ] All acceptance criteria met: Yes / No
- [ ] No critical issues found: Yes / No

### Production Sign-Off
- [ ] Product Owner: ____________________
- [ ] Date: ____________________
- [ ] Approved for production: Yes / No
- [ ] Rollback plan reviewed: Yes / No

---

## 📞 Support Contacts

For issues during deployment:

1. **Check documentation:**
   - QUICKSTART.md - Getting started
   - README.md - Full guide
   - ADVANCED_CONFIG.md - Advanced topics

2. **Run diagnostics:**
   - `python test_server.py` - Automated test suite
   - Check logs in server console

3. **Verify basics:**
   - Database connectivity with SQL Developer
   - Python environment with `pip list`
   - Network connectivity with ping

---

## ✅ Final Sign-Off

Once all checks pass:

- [ ] **Development Ready** - Code complete and tested
- [ ] **Deployment Ready** - All systems verified and configured
- [ ] **Production Ready** - Integrated with Claude Desktop and working
- [ ] **Monitored** - Logging in place and baseline metrics established

---

**Status:** ✓ Ready for Production Use

**Version:** 1.0.0  
**Date:** August 2025  
**Approved By:** ____________________

---

For additional support, refer to the complete documentation files in the project directory.
