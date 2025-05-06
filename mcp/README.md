# GitHub MCP Server for Auto_drives

This directory contains the setup for a GitHub Model Context Protocol (MCP) server that enables AI assistants like Claude to interact with the GitHub repository for the Auto_drives project.

## Setup

1. Install dependencies:
   ```
   npm install
   ```

2. Set your GitHub Personal Access Token:
   ```
   export GITHUB_PERSONAL_ACCESS_TOKEN="your_github_token"
   ```
   
   You'll need to create a Personal Access Token with the following permissions:
   - `repo` (Full control of private repositories)
   - `read:user` (Read access to user profile data)
   - `user:email` (Access user email addresses)

3. Start the MCP server:
   ```
   npm start
   ```

4. Get the absolute path to the MCP server script (needed for configuration):
   ```
   npm run path
   ```
   This will print the absolute path to the `start-mcp.js` file, which you'll need for configuring Claude Desktop or Cursor.

## Configuration

The MCP server configuration is stored in `config.json`. You can modify this file to change the server settings.

For your convenience, example configuration files are provided:
- `claude_desktop_config_example.json` - Example configuration for Claude Desktop
- `cursor_config_example.json` - Example configuration for Cursor

These files already contain the correct path to the `start-mcp.js` file. You just need to replace `YOUR_GITHUB_TOKEN` with your actual GitHub Personal Access Token.

## Usage with Claude Desktop

To use this MCP server with Claude Desktop:

1. Open Claude Desktop
2. Go to Settings
3. Navigate to the Developer section
4. Add the following configuration to your `claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "github": {
         "command": "node",
         "args": [
           "/absolute/path/to/start-mcp.js"
         ],
         "env": {
           "GITHUB_PERSONAL_ACCESS_TOKEN": "your_github_token"
         }
       }
     }
   }
   ```
5. Replace `/absolute/path/to/start-mcp.js` with the actual path from the `npm run path` command
6. Replace `your_github_token` with your actual GitHub Personal Access Token

Alternatively, you can copy the contents of `claude_desktop_config_example.json` and just replace `YOUR_GITHUB_TOKEN` with your actual token.

## Usage with Cursor

To use this MCP server with Cursor:

1. Open Cursor
2. Go to Settings > MCP
3. Add a new MCP server with the following configuration:
   ```json
   {
     "command": "node",
     "args": [
       "/absolute/path/to/start-mcp.js"
     ],
     "env": {
       "GITHUB_PERSONAL_ACCESS_TOKEN": "your_github_token"
     }
   }
   ```
4. Replace `/absolute/path/to/start-mcp.js` with the actual path from the `npm run path` command
5. Replace `your_github_token` with your actual GitHub Personal Access Token

Alternatively, you can use the contents of `cursor_config_example.json` and just replace `YOUR_GITHUB_TOKEN` with your actual token.

## Example Prompts and Usage Guide

For examples of how to use the GitHub MCP server with Claude Desktop or Cursor, see the [Usage Guide](USAGE_GUIDE.md).

## Troubleshooting

If you encounter any issues:

1. Check that your GitHub token has the correct permissions
2. Ensure the MCP server is running (you should see "MCP GitHub server started" in the console)
3. Check the console for any error messages

Remember to keep your GitHub token secure and never commit it to version control. 