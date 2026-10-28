import test from 'node:test';
import assert from 'node:assert/strict';
import { classifyMediaUrl, isRplayMediaRequest, classifyTabUrl, redactUrl, hostMatches } from '../lib/url_patterns.js';

test('classifyMediaUrl by extension and content-type', () => {
  assert.equal(classifyMediaUrl('https://a.rplay-cdn.com/x/master.m3u8?token=1'), 'hls');
  assert.equal(classifyMediaUrl('https://a.rplay-cdn.com/x/stream', 'application/vnd.apple.mpegurl; charset=utf-8'), 'hls');
  assert.equal(classifyMediaUrl('https://a.rplay-cdn.com/x/v.mpd'), 'dash');
  assert.equal(classifyMediaUrl('https://a.rplay-cdn.com/x/v.mp4'), 'mp4');
  assert.equal(classifyMediaUrl('https://a.rplay-cdn.com/x/seg.ts'), null);
  assert.equal(classifyMediaUrl('ftp://a/x.m3u8'), null);
  assert.equal(classifyMediaUrl('https://u:p@a/x.m3u8'), null);
  assert.equal(classifyMediaUrl('not a url'), null);
});

test('isRplayMediaRequest restricts host, tab and method', () => {
  assert.equal(isRplayMediaRequest({ url: 'https://pb3.rplay.live/a.m3u8', tabId: 3 }), true);
  assert.equal(isRplayMediaRequest({ url: 'https://cdn.rplay-cdn.com/a.mpd', tabId: 3, type: 'xmlhttprequest' }), true);
  assert.equal(isRplayMediaRequest({ url: 'https://evil-rplay.live.example.com/a.m3u8', tabId: 3 }), false);
  assert.equal(isRplayMediaRequest({ url: 'https://notrplay.live/a.m3u8', tabId: 3 }), false);
  assert.equal(isRplayMediaRequest({ url: 'https://rplay.live/a.m3u8', tabId: -1 }), false);
  assert.equal(isRplayMediaRequest({ url: 'https://rplay.live/a.m3u8', tabId: 1, method: 'POST' }), false);
  assert.equal(isRplayMediaRequest({ url: 'https://rplay.live/a.m3u8', tabId: 1, type: 'image' }), false);
});

test('hostMatches requires dot boundary', () => {
  assert.equal(hostMatches('a.rplay.live', ['rplay.live']), true);
  assert.equal(hostMatches('xrplay.live', ['rplay.live']), false);
});

test('classifyTabUrl', () => {
  assert.equal(classifyTabUrl('https://rplay.live/live/abc'), 'rplay');
  assert.equal(classifyTabUrl('https://www.youtube.com/watch?v=x'), 'youtube');
  assert.equal(classifyTabUrl('http://www.youtube.com/watch?v=x'), null);
  assert.equal(classifyTabUrl('https://example.com'), null);
  assert.equal(classifyTabUrl(undefined), null);
});

test('redactUrl drops query and fragment', () => {
  assert.equal(redactUrl('https://a.rplay-cdn.com/p/master.m3u8?sig=abc#x'), 'https://a.rplay-cdn.com/p/master.m3u8');
  assert.equal(redactUrl('bad'), '');
});
