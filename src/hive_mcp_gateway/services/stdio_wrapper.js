#!/usr/bin/env node
/**
 * STDIO wrapper that prevents console output from corrupting MCP protocol.
 * Uses mcps-logger to redirect console output to a separate channel.
 * 
 * Usage: node stdio_wrapper.js <command> [args...]
 * Example: node stdio_wrapper.js uvx basic-memory mcp
 */

// Import mcps-logger to patch console methods and redirect output
// This prevents console.log from corrupting the stdio protocol
if (process.env.NODE_ENV !== 'production') {
  try {
    require('mcps-logger/console');
  } catch (e) {
    // If mcps-logger is not installed, we'll handle it differently
    // Redirect console to stderr instead of stdout
    const originalLog = console.log;
    const originalWarn = console.warn;
    const originalError = console.error;
    const originalDebug = console.debug;
    
    console.log = (...args) => {
      process.stderr.write(`[LOG] ${args.join(' ')}\n`);
    };
    console.warn = (...args) => {
      process.stderr.write(`[WARN] ${args.join(' ')}\n`);
    };
    console.error = (...args) => {
      process.stderr.write(`[ERROR] ${args.join(' ')}\n`);
    };
    console.debug = (...args) => {
      process.stderr.write(`[DEBUG] ${args.join(' ')}\n`);
    };
  }
}

const { spawn } = require('child_process');

// Get command and arguments from command line
const [,, command, ...args] = process.argv;

if (!command) {
  console.error('Usage: node stdio_wrapper.js <command> [args...]');
  process.exit(1);
}

// Environment variables to suppress banners
const env = {
  ...process.env,
  PYTHONUNBUFFERED: '1',
  FASTMCP_NO_BANNER: '1',
  FASTMCP_DISABLE_BANNER: '1',
  FASTMCP_QUIET: '1',
  NO_COLOR: '1',
  CI: '1',
  NODE_NO_WARNINGS: '1',
};

// Spawn the actual MCP server process
const child = spawn(command, args, {
  stdio: ['pipe', 'pipe', 'pipe'],
  env: env
});

// Create a simple filter to remove banner lines
// This is a backup in case environment variables don't work
function filterBannerLines(data) {
  const lines = data.toString().split('\n');
  const filtered = lines.filter(line => {
    // Filter out common banner patterns
    if (line.includes('╭─') || line.includes('│') || line.includes('╰─')) return false;
    if (line.includes('FastMCP') || line.includes('🖥️') || line.includes('📦')) return false;
    if (line.includes('====') || line.includes('----')) return false;
    if (line.trim() === '') return false;
    
    // Keep lines that look like JSON
    const trimmed = line.trim();
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) return true;
    
    // Filter out everything else by default
    return false;
  });
  
  return filtered.join('\n');
}

// Forward stdin to child process
process.stdin.pipe(child.stdin);

// Forward stdout from child, with optional filtering
child.stdout.on('data', (data) => {
  // Try to detect if this is JSON-RPC or banner text
  const str = data.toString();
  if (str.includes('{') && (str.includes('jsonrpc') || str.includes('method') || str.includes('id'))) {
    // Looks like JSON-RPC, forward as-is
    process.stdout.write(data);
  } else if (str.trim().startsWith('{') || str.trim().startsWith('[')) {
    // Looks like JSON, forward as-is
    process.stdout.write(data);
  } else {
    // Might be banner text, try to filter
    const filtered = filterBannerLines(data);
    if (filtered.trim()) {
      process.stdout.write(filtered + '\n');
    }
  }
});

// Forward stderr from child to our stderr
child.stderr.on('data', (data) => {
  process.stderr.write(data);
});

// Handle child process exit
child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
  } else {
    process.exit(code || 0);
  }
});

// Handle errors
child.on('error', (err) => {
  console.error('Failed to start subprocess:', err);
  process.exit(1);
});

// Forward signals to child
process.on('SIGTERM', () => child.kill('SIGTERM'));
process.on('SIGINT', () => child.kill('SIGINT'));
