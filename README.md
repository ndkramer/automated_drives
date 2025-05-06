# Auto_drives Project

A simple Flask web application that displays "Hello World!" on a webpage. This project also includes a GitHub MCP (Model Context Protocol) server setup that enables AI assistants like Claude to interact with the GitHub repository.

## Web App Setup

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run the application:
   ```
   python app.py
   ```

3. Open your web browser and navigate to:
   ```
   http://127.0.0.1:5000/
   ```

## GitHub MCP Server Setup

The `mcp` directory contains a GitHub MCP server setup that enables AI assistants to interact with this repository.

1. Navigate to the MCP directory:
   ```
   cd mcp
   ```

2. Follow the instructions in the [MCP README](mcp/README.md) to set up and use the GitHub MCP server.

## Project Structure
- `app.py` - Main application file
- `requirements.txt` - Web app dependencies
- `mcp/` - GitHub MCP server setup
  - `start-mcp.js` - Script to start the MCP server
  - `config.json` - MCP server configuration
  - `package.json` - Node.js dependencies

Remember to commit your changes to GitHub regularly. 