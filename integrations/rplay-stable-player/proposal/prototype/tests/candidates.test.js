import test from 'node:test';
import assert from 'node:assert/strict';
import { createCandidateStore } from '../lib/candidates.js';

test('dedupe by tab+url, hits counted', () => {
  let t = 1000;
  const s = createCandidateStore({ now: () => t });
  const a = s.upsert({ tabId: 1, url: 'https://x/a.m3u8?sig=1', mediaType: 'hls' });
  const b = s.upsert({ tabId: 1, url: 'https://x/a.m3u8?sig=1', mediaType: 'hls' });
  assert.equal(a.added, true);
  assert.equal(b.added, false);
  assert.equal(b.candidate.hits, 2);
  assert.equal(s.upsert({ tabId: 2, url: 'https://x/a.m3u8?sig=1', mediaType: 'hls' }).added, true);
  assert.equal(s.size(), 2);
});

test('public list never exposes query strings', () => {
  const s = createCandidateStore();
  s.upsert({ tabId: 1, url: 'https://x/a.m3u8?token=secret', mediaType: 'hls' });
  const [c] = s.list();
  assert.equal(c.displayUrl, 'https://x/a.m3u8');
  assert.equal('url' in c, false);
  assert.equal(JSON.stringify(s.list()).includes('secret'), false);
});

test('TTL expiry and per-tab cap', () => {
  let t = 0;
  const s = createCandidateStore({ now: () => t, ttlMs: 100, maxPerTab: 2 });
  s.upsert({ tabId: 1, url: 'https://x/1.m3u8', mediaType: 'hls' });
  s.upsert({ tabId: 1, url: 'https://x/2.m3u8', mediaType: 'hls' });
  s.upsert({ tabId: 1, url: 'https://x/3.m3u8', mediaType: 'hls' });
  assert.equal(s.list(1).length, 2);
  t = 200;
  assert.equal(s.list(1).length, 0);
});

test('serialize / restore across worker restart', () => {
  const s = createCandidateStore({ now: () => 5 });
  const { candidate } = s.upsert({ tabId: 1, url: 'https://x/a.mpd', mediaType: 'dash' });
  s.setStatus(candidate.id, 'inspected');
  const s2 = createCandidateStore({ now: () => 6 });
  s2.load(JSON.parse(JSON.stringify(s.toJSON())));
  assert.equal(s2.get(candidate.id).status, 'inspected');
  assert.equal(s2.upsert({ tabId: 1, url: 'https://x/a.mpd', mediaType: 'dash' }).added, false);
  s2.clearTab(1);
  assert.equal(s2.size(), 0);
});
