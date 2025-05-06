/**
 * This script prints the absolute path to the start-mcp.js file,
 * which is needed for configuring MCP clients like Claude Desktop or Cursor.
 */

const path = require('path');

// Get the absolute path to the start-mcp.js file
const startMcpPath = path.resolve(__dirname, 'start-mcp.js');

console.log('\nCopy the path below for your MCP client configuration:\n');
console.log(startMcpPath);
console.log('\n'); 