#!/bin/bash

# Change to the mcp directory
cd "$(dirname "$0")/mcp" || exit

# Start the MCP server
npm start 