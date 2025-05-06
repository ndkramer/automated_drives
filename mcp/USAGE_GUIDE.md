# GitHub MCP Server Usage Guide

This guide provides examples of how to use the GitHub MCP server with Claude Desktop or Cursor.

## Available Tools

The GitHub MCP server provides the following tools:

1. **Repository Management**
   - Create, read, update repositories
   - Search repositories
   - List repositories

2. **Issues and Pull Requests**
   - Create, read, update issues
   - Search issues
   - Create, read, update pull requests
   - Review pull requests

3. **File Operations**
   - Read files from repositories
   - Create or update files
   - Compare files

4. **User Management**
   - Get user information
   - List user repositories

## Example Prompts

Here are some example prompts you can use with Claude Desktop or Cursor:

### Repository Management

- "Search for repositories related to automated driving"
- "List my repositories"
- "Create a new repository called 'test-repo' with a description 'A test repository'"

### Issues and Pull Requests

- "Create an issue in the repository 'ndkramer/automated_drives' with the title 'Update documentation' and the body 'The documentation needs to be updated to include the new features'"
- "Search for issues related to documentation in the repository 'ndkramer/automated_drives'"
- "List open pull requests in the repository 'ndkramer/automated_drives'"
- "Review pull request #1 in the repository 'ndkramer/automated_drives'"

### File Operations

- "Read the file 'README.md' in the repository 'ndkramer/automated_drives'"
- "Create a new file 'docs/CONTRIBUTING.md' in the repository 'ndkramer/automated_drives' with the content '# Contributing Guide\n\nThank you for your interest in contributing to this project!'"
- "Compare the file 'app.py' with the file 'app.py' in the branch 'main' of the repository 'ndkramer/automated_drives'"

### User Management

- "Get information about the user 'ndkramer'"
- "List repositories owned by the user 'ndkramer'"

## Tips for Using the GitHub MCP Server

1. **Be specific**: When asking Claude to perform actions on GitHub, be as specific as possible. Include the repository name, branch name, file path, etc.

2. **Use the correct syntax**: The GitHub MCP server expects certain parameters for each tool. Make sure you're providing all the required parameters.

3. **Check permissions**: Make sure your GitHub Personal Access Token has the necessary permissions for the actions you want to perform.

4. **Keep your token secure**: Never share your GitHub Personal Access Token with anyone or commit it to version control.

5. **Start small**: If you're new to using the GitHub MCP server, start with simple actions like reading files or searching repositories before moving on to more complex actions like creating issues or pull requests.

## Troubleshooting

If you encounter issues with the GitHub MCP server:

1. **Check the console**: The MCP server outputs error messages to the console. Check the console for any error messages.

2. **Check your token**: Make sure your GitHub Personal Access Token is valid and has the necessary permissions.

3. **Check your connection**: Make sure you have an internet connection and can access GitHub.

4. **Restart the server**: Sometimes simply restarting the MCP server can resolve issues.

5. **Check the GitHub API status**: If GitHub's API is experiencing issues, the MCP server may not work correctly. Check the [GitHub Status page](https://www.githubstatus.com/) for any reported issues. 