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
  { jsonrpc: '2.0', id: 4, method: 'tools/call', params: { name: 'echo_text', arguments: { text: 'safe' } } },
  { jsonrpc: '2.0', method: 'notifications/initialized' }
];
const proc = spawnSync(process.execPath, [server], {
  input: cases.map(x => JSON.stringify(x)).join('\n') + '\n',
  encoding: 'utf-8',
  timeout: 10000
});
assert.equal(proc.status, 0, 'Synthetic MCP server must exit normally');
const actual = proc.stdout.trim().split('\n').map(x => JSON.parse(x));
assert.equal(actual.length, 4, 'Notifications without IDs must not receive a response');
assert.equal(actual[0].result && Object.keys(actual[0].result).length, 0);
assert.equal(actual[1].error?.code, -32602);
assert.equal(actual[2].error?.code, -32602);
assert.equal(actual[3].result?.content?.[0]?.text, 'safe');
console.log('PASS: MCP fixture rejects unknown tools and invalid tool arguments');
