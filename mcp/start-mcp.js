const { spawn } = require('child_process');
const path = require('path');

// Path to the MCP server executable
const serverPath = path.join(__dirname, 'node_modules', '@modelcontextprotocol', 'server-github', 'dist', 'index.js');

// Start the MCP server
const server = spawn('node', [serverPath], {
  env: {
    ...process.env,
    GITHUB_PERSONAL_ACCESS_TOKEN: process.env.GITHUB_PERSONAL_ACCESS_TOKEN || 'YOUR_GITHUB_TOKEN'
  },
  stdio: 'inherit'
});

console.log('MCP GitHub server started');

// Handle server exit
server.on('close', (code) => {
  console.log(`MCP GitHub server exited with code ${code}`);
});

// Handle CTRL+C to gracefully shut down
process.on('SIGINT', () => {
  console.log('Shutting down MCP GitHub server...');
  server.kill();
  process.exit(0);
}); 