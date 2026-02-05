#!/usr/bin/env python3
"""
Questers MCP Server
Track game quester activity and analyze weekly trends

Structure:
- server.py    : Entry point (this file)
- resources.py : Context for AI (definitions, tables, analysis guide)
- prompts.py   : Pre-defined analysis workflows
- tools.py     : Actions (query_bigquery)
"""
from fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("Questers Tracker")

# Register components from separate files
import resources
import prompts
import tools

resources.register(mcp)
prompts.register(mcp)
tools.register(mcp)


if __name__ == "__main__":
    mcp.run()
