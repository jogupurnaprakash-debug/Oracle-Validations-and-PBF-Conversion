"""Compatibility entrypoint for launching the Oracle MCP server.

This file exists so older commands like `python server.py` continue to work.
"""

from oracle_mcp_server import main


if __name__ == "__main__":
    main()
