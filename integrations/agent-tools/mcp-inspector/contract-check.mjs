// Negative-path contract checks for the synthetic stdio fixture.
// No third-party code, host credentials, files or network involved.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const server = fileURLToPath(new URL('./mock-stdio-server.mjs', import.meta.url));
const cases = [
  { jsonrpc: '2.0', id: 1, method: 'ping' },
  { jsonrpc: '2.0', id: 2, method: 'tools/call', params: { name: 'not_authorized', arguments: { text: 'x' } } },
  { jsonrpc: '2.0', id: 3, method: 'tools/call', params: { name: 'echo_text', arguments: { text: 12 } } },
  { jsonrpc: '2.0', id: 4, method: 'tools/call', params: { name: 'echo_text', arguments: { text: 'safe', unexpected: 'reject' } } },
  { jsonrpc: '2.0', id: 5, method: 'tools/call', params: { name: 'echo_text', arguments: {} } },
  { jsonrpc: '2.0', id: 6, method: 'tools/call', params: { name: 'echo_text', arguments: { text: 'safe\n日本語\t{"a":1}' } } },
  { jsonrpc: '2.0', id: 7, method: 'unknown/method' },
  { jsonrpc: '2.0', method: 'notifications/initialized' }
];
const proc = spawnSync(process.execPath, [server], {
  input: cases.map(x => JSON.stringify(x)).join('\n') + '\n',
  encoding: 'utf-8',
  timeout: 10000
});
assert.equal(proc.status, 0, 'Synthetic MCP server must exit normally');
const actual = proc.stdout.trim().split('\n').map(x => JSON.parse(x));
assert.equal(actual.length, 7, 'Notifications without IDs must not receive a response');
assert.equal(actual[0].result && Object.keys(actual[0].result).length, 0);
for (let i = 1; i <= 4; i++) assert.equal(actual[i].error?.code, -32602);
assert.equal(actual[5].result?.content?.[0]?.text, 'safe\n日本語\t{"a":1}');
assert.equal(actual[6].error?.code, -32601);
console.log('PASS: MCP fixture enforces strict args, JSON text escaping and no-notification response');
