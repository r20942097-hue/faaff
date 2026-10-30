// Browser infrastructure smoke only. Does NOT test live RPLAY/YouTube add-ons.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, firefox } from 'playwright';

const baseDir = path.dirname(fileURLToPath(import.meta.url));
const extensionDir = path.join(baseDir, 'fixture-mv3');
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'pw-mv3-profile-'));

let context;
let firefoxBrowser;
try {
  context = await chromium.launchPersistentContext(profile, {
    channel: 'chromium',
    headless: true,
    args: [
      `--disable-extensions-except=${extensionDir}`,
      `--load-extension=${extensionDir}`
    ]
  });
  const worker = context.serviceWorkers()[0] ??
    await context.waitForEvent('serviceworker', { timeout: 20000 });
  const extensionId = new URL(worker.url()).host;
  assert.match(extensionId, /^[a-p]{32}$/, 'MV3 extension ID must be valid');
  const popup = await context.newPage();
  await popup.goto(`chrome-extension://${extensionId}/popup.html`);
  assert.equal(await popup.locator('#heading').textContent(), 'Fixture ready');
  await popup.locator('#activate').click();
  assert.equal(await popup.locator('#result').textContent(), 'Activated');
  console.log('PASS: bundled Chromium loaded synthetic MV3 and exercised popup script');
  await context.close();
  context = undefined;

  firefoxBrowser = await firefox.launch({ headless: true });
  const page = await firefoxBrowser.newPage();
  await page.setContent('<!doctype html><html><head><title>Firefox fixture</title></head><body><main id="test">Ready</main></body></html>');
  assert.equal(await page.title(), 'Firefox fixture');
  assert.equal(await page.locator('#test').textContent(), 'Ready');
  console.log('PASS: Playwright-patched Firefox rendered synthetic page (not extension test)');
  await firefoxBrowser.close();
  firefoxBrowser = undefined;
} finally {
  await context?.close();
  await firefoxBrowser?.close();
  fs.rmSync(profile, { recursive: true, force: true });
}
