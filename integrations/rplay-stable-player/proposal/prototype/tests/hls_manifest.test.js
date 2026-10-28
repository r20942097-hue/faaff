import test from 'node:test';
import assert from 'node:assert/strict';
import { inspectHls, inspectDash, parseAttributes, hlsProtection } from '../lib/hls_manifest.js';

const MASTER = `#EXTM3U
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud",NAME="ja",URI="audio/ja.m3u8"
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360,CODECS="avc1.4d401e,mp4a.40.2",AUDIO="aud"
low/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=3000000,RESOLUTION=1920x1080
https://cdn.example/high/index.m3u8
`;

test('parseAttributes handles quoted commas', () => {
  assert.deepEqual(parseAttributes('BANDWIDTH=1,CODECS="a,b",X=y'), { BANDWIDTH: '1', CODECS: 'a,b', X: 'y' });
});

test('master playlist: variants sorted, URIs resolved', () => {
  const r = inspectHls(MASTER, 'https://pb3.rplay.live/v/master.m3u8');
  assert.equal(r.kind, 'master');
  assert.equal(r.status, 'OK');
  assert.equal(r.variants.length, 2);
  assert.equal(r.variants[0].resolution, '1920x1080');
  assert.equal(r.variants[1].url, 'https://pb3.rplay.live/v/low/index.m3u8');
  assert.equal(r.audio[0].url, 'https://pb3.rplay.live/v/audio/ja.m3u8');
});

test('media playlist: segments, duration, endlist', () => {
  const r = inspectHls('#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXTINF:6.0,\na.ts\n#EXTINF:4.5,\nb.ts\n#EXT-X-ENDLIST\n', 'https://x/y.m3u8');
  assert.equal(r.kind, 'media');
  assert.equal(r.segments, 2);
  assert.equal(r.durationSec, 10.5);
  assert.equal(r.endList, true);
});

test('encrypted playlists are BLOCKED, METHOD=NONE is OK', () => {
  const enc = '#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="k"\n#EXTINF:6,\na.ts\n';
  assert.equal(inspectHls(enc, 'https://x/').status, 'BLOCKED_ENCRYPTED');
  assert.equal(hlsProtection('#EXTM3U\n#EXT-X-SESSION-KEY:METHOD=SAMPLE-AES,URI="skd://x"\n').protected, true);
  assert.equal(inspectHls('#EXTM3U\n#EXT-X-KEY:METHOD=NONE\n#EXTINF:1,\na.ts\n', 'https://x/').status, 'OK');
});

test('invalid input is rejected', () => {
  assert.throws(() => inspectHls('<html>', 'https://x/'), /HLS_NOT_PLAYLIST/);
  assert.throws(() => inspectHls('#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1\n', 'https://x/'), /HLS_MISSING_VARIANT_URI/);
  assert.throws(() => inspectHls('#EXTM3U\n' + 'x'.repeat(2 * 1024 * 1024), 'https://x/'), /HLS_TOO_LARGE/);
});

test('DASH ContentProtection => BLOCKED_DRM', () => {
  assert.equal(inspectDash('<MPD type="static"><Period/></MPD>').status, 'OK');
  assert.equal(inspectDash('<MPD type="dynamic"><Period/></MPD>').dynamic, true);
  assert.equal(inspectDash('<MPD><Period><AdaptationSet><ContentProtection schemeIdUri="x"/></AdaptationSet></Period></MPD>').status, 'BLOCKED_DRM');
  assert.throws(() => inspectDash('<html/>'), /DASH_NOT_MPD/);
});
