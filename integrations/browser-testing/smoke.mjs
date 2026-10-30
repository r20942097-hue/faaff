// Browser infrastructure smoke only. Does NOT test live RPLAY/YouTube add-ons.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, firefox } from 'playwright';

const baseDir = path.dirname(fileURLToPath(import.meta.url));
const extensionDir = path.join(baseDir, 'fixture-mv3');
const fixtureManifest = JSON.parse(fs.readFileSync(path.join(extensionDir, 'manifest.json'), 'utf8'));
assert.equal(fixtureManifest.manifest_version, 3);
assert.equal(fixtureManifest.background?.service_worker, 'background.js');
assert.deepEqual(fixtureManifest.background?.scripts, ['background.js'],
  'Firefox MV3 event-page fallback must be present');
assert.deepEqual(fixtureManifest.permissions, [], 'Fixture must use zero privileges');
assert.equal(fixtureManifest.host_permissions, undefined, 'Fixture must not request host permissions');
assert.equal(fixtureManifest.content_scripts, undefined, 'Fixture must not inject content scripts');
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
  await popup.waitForFunction(() => document.querySelector('#result')?.textContent === 'Activated');
  console.log('PASS: Chromium MV3 popup sent a real runtime message and worker responded');
  await context.close();
  context = undefined;

  // Restart the actual browser process with the SAME isolated profile.
  // This is a persistence/extension registration regression check, not a crash-recovery test.
  context = await chromium.launchPersistentContext(profile, {
    channel: 'chromium',
    headless: true,
    args: [
      `--disable-extensions-except=${extensionDir}`,
      `--load-extension=${extensionDir}`
    ]
  });
  const resumedWorker = context.serviceWorkers()[0] ??
    await context.waitForEvent('serviceworker', { timeout: 20000 });
  const resumedId = new URL(resumedWorker.url()).host;
  assert.equal(resumedId, extensionId, 'Reopened profile must retain the same extension ID');
  const resumedPopup = await context.newPage();
  await resumedPopup.goto(`chrome-extension://${resumedId}/popup.html`);
  assert.equal(await resumedPopup.locator('#heading').textContent(), 'Fixture ready');
  await resumedPopup.locator('#activate').click();
  await resumedPopup.waitForFunction(() => document.querySelector('#result')?.textContent === 'Activated');
  console.log('PASS: MV3 ID and popup-worker messaging survive profile reopen');
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
