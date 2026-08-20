# Advanced Configuration Guide

## Overview

This guide covers advanced configurations and deployment scenarios for the Oracle MCP Server.

---

## Transport Modes

The current server uses **stdio transport** (standard input/output), which is compatible with Claude Desktop and most MCP clients.

### Standard Stdio Transport (Current - Recommended)

The server reads MCP requests from stdin and writes responses to stdout.

```bash
python oracle_mcp_server.py
```

**Pros:**
- Simple, no additional configuration
- Works with Claude Desktop out of the box
- Secure communication
- No network port exposure

**Cons:**
- Single client connection only
- Must run locally with the MCP client

---

## Environment Configuration

### Connection Pool Tuning

In `oracle_mcp_server.py`, adjust these values for your workload:

```python
self.connection_pool = oracledb.create_pool(
    user=ORACLE_USER,
    password=ORACLE_PASSWORD,
    dsn=dsn,
    min=2,      # Minimum connections (increase for high concurrency)
    max=10,     # Maximum connections (increase for more concurrent queries)
    increment=1, # Connections added when pool is full
    threaded=True
)
```

**Recommendations:**
- **Light usage**: min=1, max=5
- **Medium usage**: min=2, max=10 (current default)
- **Heavy usage**: min=5, max=50
- **Enterprise**: min=10, max=100+

### Query Timeout Configuration

To add query timeouts (currently unlimited), modify the `execute_query` function:

```python
cursor.execute(sql_query, timeout=300)  # 300 second timeout
```

---

## Logging Configuration

### Change Log Level

In `oracle_mcp_server.py`, modify:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Log to File

Add file logging:

```python
import logging.handlers

file_handler = logging.handlers.RotatingFileHandler(
    'oracle_mcp_server.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
file_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logger.addHandler(file_handler)
```

---

## Claude Desktop Integration

### Configuration File Location

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
C:\Users\<username>\AppData\Roaming\Claude\claude_desktop_config.json
```

**macOS:**
```
~/Library/Application\ Support/Claude/claude_desktop_config.json
```

### Full Configuration Example

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
        "ORACLE_PASSWORD": "your_secure_password"
      }
    }
  }
}
```

### Multiple Database Servers

Connect to multiple Oracle databases:

```json
{
  "mcpServers": {
    "oracle-prod": {
      "command": "python",
      "args": ["c:\\oracle-mcp-server\\oracle_mcp_server.py"],
      "env": {
        "ORACLE_HOST": "prod-db.example.com",
        "ORACLE_PORT": "2056",
        "ORACLE_SERVICE": "prod_service",
        "ORACLE_USER": "prod_user",
        "ORACLE_PASSWORD": "prod_password"
      }
    },
    "oracle-dev": {
      "command": "python",
      "args": ["c:\\oracle-mcp-server-dev\\oracle_mcp_server.py"],
      "env": {
        "ORACLE_HOST": "dev-db.example.com",
        "ORACLE_PORT": "2056",
        "ORACLE_SERVICE": "dev_service",
        "ORACLE_USER": "dev_user",
        "ORACLE_PASSWORD": "dev_password"
      }
    }
  }
}
```

Then in Claude, you can specify which database to query:
```
User: "Using the oracle-prod server, show me the top customers"
```

---

## Security Enhancements

### Credential Management

#### Option 1: Environment Variables (Recommended for Development)

Already implemented with `.env` file.

#### Option 2: AWS Secrets Manager

```python
import boto3

def get_oracle_credentials():
    client = boto3.client('secretsmanager')
    secret = client.get_secret_value(SecretId='oracle-db-credentials')
    return json.loads(secret['SecretString'])

creds = get_oracle_credentials()
ORACLE_USER = creds['username']
ORACLE_PASSWORD = creds['password']
```

#### Option 3: Azure Key Vault

```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def get_oracle_credentials():
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url="https://<vault-name>.vault.azure.net/", credential=credential)
    
    return {
        'user': client.get_secret("oracle-username").value,
        'password': client.get_secret("oracle-password").value
    }
```

### Role-Based Access Control (RBAC)

Create a read-only database user:

```sql
CREATE USER analytics_user IDENTIFIED BY secure_password;
GRANT CONNECT TO analytics_user;
GRANT SELECT ON all_tables TO analytics_user;
-- Don't grant INSERT, UPDATE, DELETE, DROP
```

### IP Whitelisting

Restrict database access to known IPs:

```sql
ALTER SYSTEM SET DB_NATIVE_NETWORK_ENCRYPTION=REQUIRED;
ALTER SYSTEM SET DB_NATIVE_NETWORK_ENCRYPTION_TYPE=SHA512;
```

---

## Performance Optimization

### Query Caching

Add Redis caching for frequently-used queries:

```python
import redis

cache = redis.Redis(host='localhost', port=6379, db=0)

def execute_query_cached(sql_query):
    cache_key = f"query:{hashlib.md5(sql_query.encode()).hexdigest()}"
    cached_result = cache.get(cache_key)
    
    if cached_result:
        return json.loads(cached_result)
    
    # Execute and cache for 1 hour
    results = execute_query(sql_query)
    cache.setex(cache_key, 3600, json.dumps(results))
    return results
```

### Connection Pool Monitoring

Add metrics:

```python
def get_pool_stats():
    """Get current connection pool statistics."""
    return {
        'opened': self.connection_pool.opened,
        'in_use': self.connection_pool.in_use,
        'available': self.connection_pool.opened - self.connection_pool.in_use
    }
```

---

## Deployment Scenarios

### Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY oracle_mcp_server.py .
COPY .env .

EXPOSE 5000

CMD ["python", "oracle_mcp_server.py"]
```

Build and run:

```bash
docker build -t oracle-mcp-server .
docker run -e ORACLE_PASSWORD=$ORACLE_PASSWORD oracle-mcp-server
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: oracle-mcp-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: oracle-mcp-server
  template:
    metadata:
      labels:
        app: oracle-mcp-server
    spec:
      containers:
      - name: oracle-mcp
        image: oracle-mcp-server:latest
        env:
        - name: ORACLE_PASSWORD
          valueFrom:
            secretKeyRef:
              name: oracle-credentials
              key: password
        resources:
          limits:
            memory: "512Mi"
            cpu: "500m"
```

### Systemd Service (Linux)

Create `/etc/systemd/system/oracle-mcp.service`:

```ini
[Unit]
Description=Oracle MCP Server
After=network.target

[Service]
Type=simple
User=mcp-user
WorkingDirectory=/opt/oracle-mcp-server
EnvironmentFile=/opt/oracle-mcp-server/.env
ExecStart=/opt/oracle-mcp-server/.venv/bin/python oracle_mcp_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable oracle-mcp
sudo systemctl start oracle-mcp
sudo systemctl status oracle-mcp
```

---

## Monitoring & Observability

### Application Metrics

Add Prometheus metrics:

```python
from prometheus_client import Counter, Histogram, start_http_server

query_counter = Counter('oracle_queries_total', 'Total queries executed')
query_duration = Histogram('oracle_query_duration_seconds', 'Query duration')
errors_counter = Counter('oracle_errors_total', 'Total errors')

# In execute_query:
with query_duration.time():
    # Execute query
    query_counter.inc()
```

### Health Check Endpoint

Add a health check:

```python
@server.call_tool()
async def health_check() -> ToolResult:
    """Health check endpoint."""
    try:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM dual")
            cursor.close()
        return ToolResult(content=[TextContent(type="text", text="healthy")])
    except:
        return ToolResult(
            content=[TextContent(type="text", text="unhealthy")],
            is_error=True
        )
```

---

## Rate Limiting

Prevent abuse with rate limiting:

```python
from functools import wraps
from time import time

class RateLimiter:
    def __init__(self, calls=100, period=60):
        self.calls = calls
        self.period = period
        self.calls_made = []
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time()
            self.calls_made = [call for call in self.calls_made 
                              if call > now - self.period]
            
            if len(self.calls_made) >= self.calls:
                raise Exception("Rate limit exceeded")
            
            self.calls_made.append(now)
            return func(*args, **kwargs)
        return wrapper

limiter = RateLimiter(calls=100, period=60)

@limiter
async def execute_query(sql_query: str) -> ToolResult:
    # ... existing code
```

---

## Troubleshooting Checklist

- [ ] `.env` file exists and has all required fields
- [ ] Database credentials are correct
- [ ] Network connectivity to database server is working
- [ ] Python virtual environment is activated
- [ ] All dependencies installed: `pip install -r requirements.txt`
- [ ] Server logs show "Oracle connection pool initialized successfully"
- [ ] Claude Desktop configuration is correct
- [ ] Claude Desktop has been restarted after config changes

---

## Performance Benchmarks

Typical performance (varies with system and network):

| Operation | Time | Notes |
|-----------|------|-------|
| Connection pool init | 1-2s | One-time startup |
| list_tables() | 100-500ms | Depends on table count |
| describe_table() | 50-200ms | Fast metadata query |
| execute_query() | 200-5000ms | Depends on query complexity |
| Connection reuse | <10ms | From pool (very fast) |

---

## Support & Debugging

### Enable Debug Logging

```bash
# In .env, add:
LOG_LEVEL=DEBUG

# Then in oracle_mcp_server.py:
log_level = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(level=getattr(logging, log_level))
```

### Database Connection Testing

```bash
# Test with sqlplus
sqlplus username/password@hostname:port/service_name

# Test with oracledb Python directly
python -c "import oracledb; conn = oracledb.connect(...); print('OK')"
```

---

## License & Support

For issues, feature requests, or improvements, refer to the main README.md.
