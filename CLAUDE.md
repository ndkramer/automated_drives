# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Auto_drives is a Flask web application with GitHub MCP (Model Context Protocol) server integration. The project consists of:

1. **Flask Web Application** - A simple "Hello World" web app
2. **GitHub MCP Server** - Enables AI assistants to interact with GitHub repositories

## Common Commands

### Web Application
```bash
# Install Python dependencies
pip install -r requirements.txt

# Run the Flask application
python app.py

# Access the web app at http://127.0.0.1:5000/
```

### MCP Server Setup
```bash
# Navigate to MCP directory
cd mcp

# Install Node.js dependencies
npm install

# Set GitHub Personal Access Token (required)
export GITHUB_PERSONAL_ACCESS_TOKEN="your_github_token"

# Start the MCP server
npm start

# Get absolute path for configuration
npm run path
```

## Architecture

### Web Application Layer
- **app.py** - Main Flask application with single route handler
- **requirements.txt** - Python dependencies (Flask, Werkzeug)

### MCP Integration Layer
- **mcp/start-mcp.js** - MCP server startup script
- **mcp/config.json** - MCP server configuration
- **mcp/get-path.js** - Utility to get absolute paths for configuration
- **mcp/package.json** - Node.js dependencies (@modelcontextprotocol/server-github)

### Configuration Files
- **mcp/claude_desktop_config_example.json** - Example Claude Desktop configuration
- **mcp/cursor_config_example.json** - Example Cursor configuration

## GitHub MCP Server Capabilities

The MCP server provides GitHub integration with the following capabilities:
- Repository management (create, read, update, search)
- Issues and pull requests (create, read, update, review)
- File operations (read, create, update, compare)
- User management (get info, list repositories)

## Required Environment Variables

- `GITHUB_PERSONAL_ACCESS_TOKEN` - GitHub Personal Access Token with repo permissions

## GitHub Token Permissions Required

- `repo` (Full control of private repositories)
- `read:user` (Read access to user profile data)
- `user:email` (Access user email addresses)

## Development Notes

- Flask app runs in debug mode by default
- MCP server requires Node.js runtime
- All GitHub operations require valid authentication token
- Configuration examples provided for both Claude Desktop and Cursor integration