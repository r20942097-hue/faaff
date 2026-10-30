// Synthetic stdio-only MCP server. No filesystem or network access, credentials or real tools.
// Uses newline-delimited JSON-RPC as required by MCP stdio transport.
import readline from 'node:readline';

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
function respond(value) {
  process.stdout.write(JSON.stringify(value) + '\n');
}
rl.on('line', (line) => {
  let req;
  try {
    req = JSON.parse(line);
  } catch {
    // Only stderr may contain diagnostics. Never print non-JSON bytes to stdout.
    process.stderr.write('Malformed JSON input\n');
    return;
  }
  if (!req || typeof req !== 'object' || req.id === undefined) return;
  const envelope = { jsonrpc: '2.0', id: req.id };
  switch (req.method) {
    case 'initialize':
      respond({
        ...envelope,
        result: {
          protocolVersion: req.params?.protocolVersion ?? '2025-06-18',
          capabilities: { tools: {} },
          serverInfo: { name: 'synthetic-mcp-echo', version: '1.0.0' }
        }
      });
      break;
    case 'ping':
      respond({ ...envelope, result: {} });
      break;
    case 'tools/list':
      respond({
        ...envelope,
        result: {
          tools: [{
            name: 'echo_text',
            title: 'Echo text',
            description: 'Echoes the provided string without side effects',
            inputSchema: {
              type: 'object',
              properties: { text: { type: 'string', description: 'Text to echo' } },
              required: ['text'],
              additionalProperties: false
            }
          }]
        }
      });
      break;
    case 'tools/call':
      if (req.params?.name !== 'echo_text' || typeof req.params?.arguments?.text !== 'string') {
        respond({ ...envelope, error: { code: -32602, message: 'Invalid tool arguments' } });
      } else {
        respond({
          ...envelope,
          result: { content: [{ type: 'text', text: req.params.arguments.text }], isError: false }
        });
      }
      break;
    default:
      respond({ ...envelope, error: { code: -32601, message: 'Method not found' } });
  }
});
