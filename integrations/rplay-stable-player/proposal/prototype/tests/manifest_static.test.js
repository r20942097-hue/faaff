import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const m = JSON.parse(readFileSync(join(root, 'manifest.json'), 'utf8'));

test('MV3 with module service worker', () => {
  assert.equal(m.manifest_version, 3);
  assert.equal(m.background.service_worker, 'background.js');
  assert.equal(m.background.type, 'module');
});

test('least privilege: allowlisted permissions, no broad hosts', () => {
  const allowed = new Set(['webRequest', 'storage', 'alarms', 'downloads', 'scripting']);
  for (const p of m.permissions) assert.ok(allowed.has(p), `unexpected permission ${p}`);
  for (const forbidden of ['cookies', 'webRequestBlocking', 'debugger', 'declarativeNetRequest', 'tabs', '<all_urls>']) assert.equal(m.permissions.includes(forbidden), false);
  for (const h of m.host_permissions) {
    assert.ok(h.startsWith('https://'), h);
    assert.equal(/^https:\/\/\*\/|<all_urls>/.test(h), false, h);
  }
  assert.equal(JSON.stringify(m).includes('widevine'), false);
});

test('chrome.alarms is used only with the alarms permission', () => {
  const bg = readFileSync(join(root, 'background.js'), 'utf8');
  if (bg.includes('chrome.alarms')) assert.ok(m.permissions.includes('alarms'));
  if (bg.includes('chrome.scripting')) assert.ok(m.permissions.includes('scripting'));
  if (bg.includes('chrome.downloads')) assert.ok(m.permissions.includes('downloads'));
  if (bg.includes('chrome.webRequest')) assert.ok(m.permissions.includes('webRequest'));
});

test('all referenced files exist', () => {
  const files = [m.background.service_worker, m.action.default_popup, ...m.content_scripts.flatMap((c) => c.js)];
  for (const f of files) assert.ok(existsSync(join(root, f)), f);
});
