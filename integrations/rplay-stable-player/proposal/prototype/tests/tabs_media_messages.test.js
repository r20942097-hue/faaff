import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeTab, normalizeTabs, mergeStatus } from '../lib/tab_adapter.js';
import { mediaCommand } from '../lib/media_control.js';
import { validateMessage, senderInfo, safeFilename } from '../lib/messages.js';

test('normalizeTabs filters and sorts', () => {
  const tabs = normalizeTabs([
    { id: 5, windowId: 1, url: 'https://www.youtube.com/watch?v=a', title: 'Y', audible: true, mutedInfo: { muted: true } },
    { id: 2, windowId: 1, url: 'https://rplay.live/live/x', title: 'R' },
    { id: 3, windowId: 1, url: 'https://example.com' },
    { id: -1, url: 'https://rplay.live/' },
  ]);
  assert.deepEqual(tabs.map((t) => t.tabId), [2, 5]);
  assert.equal(tabs[1].tabMuted, true);
  assert.equal(normalizeTabs(tabs.map((t) => ({ id: t.tabId, url: t.site === 'rplay' ? 'https://rplay.live/' : 'https://www.youtube.com/' })), { site: 'youtube' }).length, 1);
  assert.equal(normalizeTab(null), null);
});

test('mergeStatus attaches media and error', () => {
  const merged = mergeStatus([{ tabId: 1 }, { tabId: 2 }], [{ tabId: 1, media: [], error: null }]);
  assert.deepEqual(merged[0].media, []);
  assert.equal(merged[1].media, null);
});

function fakeDoc(n) {
  const els = Array.from({ length: n }, () => ({
    tagName: 'VIDEO', paused: true, muted: false, volume: 1, currentTime: 12.7, duration: Infinity,
    play() { this.paused = false; return Promise.resolve(); },
    pause() { this.paused = true; },
  }));
  return { els, querySelectorAll: () => els };
}

test('mediaCommand play/pause/mute/status', () => {
  const d = fakeDoc(2);
  assert.equal(mediaCommand('play', d).media.every((m) => !m.paused), true);
  assert.equal(mediaCommand('mute', d).media.every((m) => m.muted), true);
  assert.equal(mediaCommand('toggleMute', d).media.every((m) => !m.muted), true);
  const s = mediaCommand('pause', d);
  assert.equal(s.media[0].paused, true);
  assert.equal(s.media[0].live, true);
  assert.equal(s.media[0].currentTime, 12);
  assert.equal(mediaCommand('eval', d).error, 'UNKNOWN_COMMAND');
});

test('mediaCommand is self-contained (serializable for executeScript)', () => {
  const src = mediaCommand.toString();
  assert.equal(/\bimport\b|\brequire\(/.test(src), false);
  assert.equal(/fetch\(|cookie|localStorage/.test(src), false);
});

test('validateMessage enforces sender and schema', () => {
  const page = { fromExtensionPage: true, fromContentScript: false };
  const cs = { fromExtensionPage: false, fromContentScript: true };
  assert.equal(validateMessage({ v: 1, type: 'tabs.list' }, page).ok, true);
  assert.equal(validateMessage({ v: 1, type: 'tabs.list' }, cs).error, 'FORBIDDEN_SENDER');
  assert.equal(validateMessage({ v: 2, type: 'tabs.list' }, page).error, 'BAD_VERSION');
  assert.equal(validateMessage({ v: 1, type: 'media.command', command: 'play', tabIds: [1, 2] }, page).ok, true);
  assert.equal(validateMessage({ v: 1, type: 'media.command', command: 'exec' }, page).error, 'BAD_COMMAND');
  assert.equal(validateMessage({ v: 1, type: 'media.command', command: 'play', tabIds: ['1'] }, page).error, 'BAD_TAB_IDS');
  assert.equal(validateMessage({ v: 1, type: 'settings.set', settings: { evil: 1 } }, page).error, 'BAD_SETTINGS');
  assert.equal(validateMessage({ v: 1, type: 'rplay.pageInfo', title: 't' }, cs).ok, true);
  assert.equal(validateMessage({ v: 1, type: 'rplay.pageInfo', title: 't' }, page).error, 'FORBIDDEN_SENDER');
  assert.equal(validateMessage({ v: 1, type: 'nope' }, page).error, 'UNKNOWN_TYPE');
});

test('senderInfo distinguishes popup and rplay content script', () => {
  assert.deepEqual(senderInfo({ id: 'E' }, 'E'), { fromExtensionPage: true, fromContentScript: false });
  assert.deepEqual(senderInfo({ id: 'E', tab: { id: 1 }, url: 'https://rplay.live/x' }, 'E'), { fromExtensionPage: false, fromContentScript: true });
  assert.deepEqual(senderInfo({ id: 'E', tab: { id: 1 }, url: 'https://www.youtube.com/' }, 'E'), { fromExtensionPage: false, fromContentScript: false });
  assert.deepEqual(senderInfo({ id: 'X' }, 'E'), { fromExtensionPage: false, fromContentScript: false });
});

test('safeFilename', () => {
  assert.equal(safeFilename('../a/b:c', 'mp4'), 'RPLAY/_a_b_c.mp4');
  assert.equal(safeFilename('', ''), 'RPLAY/rplay');
});
