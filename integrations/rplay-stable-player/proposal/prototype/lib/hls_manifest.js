// Pure HLS / DASH manifest inspection. It reports structure and protection status only.
// Encrypted or DRM-protected media is classified as BLOCKED; this module has no decryption code
// and callers must not attempt to acquire such media.

const MAX_TEXT = 2 * 1024 * 1024;

export function parseAttributes(text) {
  const out = {};
  const re = /([A-Z0-9-]+)=("[^"]*"|[^,]*)/g;
  let m;
  while ((m = re.exec(String(text))) !== null) {
    let v = m[2];
    if (v.startsWith('"') && v.endsWith('"')) v = v.slice(1, -1);
    out[m[1]] = v;
  }
  return out;
}

function assertPlaylist(text) {
  if (typeof text !== 'string' || text.length > MAX_TEXT) throw new Error('HLS_TOO_LARGE_OR_INVALID');
  if (!/^\uFEFF?#EXTM3U(?:\r?\n|$)/.test(text)) throw new Error('HLS_NOT_PLAYLIST');
}

function resolve(uri, base) {
  return new URL(uri, base).href;
}

/** Any EXT-X-KEY / EXT-X-SESSION-KEY with METHOD other than NONE => protected. */
export function hlsProtection(text) {
  for (const raw of String(text).split(/\r?\n/)) {
    const line = raw.trim();
    const idx = line.startsWith('#EXT-X-KEY:') ? 11 : line.startsWith('#EXT-X-SESSION-KEY:') ? 19 : -1;
    if (idx < 0) continue;
    const a = parseAttributes(line.slice(idx));
    if (a.METHOD && a.METHOD !== 'NONE') return { protected: true, method: a.METHOD };
  }
  return { protected: false, method: 'NONE' };
}

/**
 * Inspect a master or media playlist.
 * @returns {{kind:'master'|'media', protected:boolean, status:'OK'|'BLOCKED_ENCRYPTED',
 *   variants:Array, audio:Array, segments:number, durationSec:number, endList:boolean}}
 */
export function inspectHls(text, baseUrl) {
  assertPlaylist(text);
  const lines = text.replace(/^\uFEFF/, '').split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const variants = [];
  const audio = [];
  let pending = null;
  let segments = 0;
  let durationSec = 0;
  let endList = false;
  for (const line of lines) {
    if (line.startsWith('#EXT-X-STREAM-INF:')) {
      if (pending) throw new Error('HLS_MISSING_VARIANT_URI');
      pending = parseAttributes(line.slice(18));
      continue;
    }
    if (line.startsWith('#EXT-X-MEDIA:')) {
      const a = parseAttributes(line.slice(13));
      if (a.TYPE === 'AUDIO' && a.URI) audio.push({ groupId: a['GROUP-ID'] || '', name: a.NAME || '', url: resolve(a.URI, baseUrl) });
      continue;
    }
    if (line.startsWith('#EXTINF:')) {
      const d = Number.parseFloat(line.slice(8));
      if (Number.isFinite(d) && d >= 0) durationSec += d;
      continue;
    }
    if (line === '#EXT-X-ENDLIST') { endList = true; continue; }
    if (line.startsWith('#')) continue;
    if (pending) {
      const bw = Number(pending['AVERAGE-BANDWIDTH'] || pending.BANDWIDTH || 0);
      variants.push({
        url: resolve(line, baseUrl),
        bandwidth: Number.isFinite(bw) ? bw : 0,
        resolution: pending.RESOLUTION || '',
        codecs: pending.CODECS || '',
        audioGroup: pending.AUDIO || '',
      });
      pending = null;
    } else {
      segments += 1;
    }
  }
  if (pending) throw new Error('HLS_MISSING_VARIANT_URI');
  const protection = hlsProtection(text);
  variants.sort((a, b) => b.bandwidth - a.bandwidth);
  return {
    kind: variants.length ? 'master' : 'media',
    protected: protection.protected,
    status: protection.protected ? 'BLOCKED_ENCRYPTED' : 'OK',
    variants,
    audio,
    segments,
    durationSec: Math.round(durationSec * 1000) / 1000,
    endList,
  };
}

/** DASH: detect ContentProtection only (no segment expansion in the prototype). */
export function inspectDash(xml) {
  if (typeof xml !== 'string' || xml.length > MAX_TEXT || !/<MPD[\s>]/.test(xml)) throw new Error('DASH_NOT_MPD');
  const isProtected = /<(?:\w+:)?ContentProtection[\s>/]/.test(xml);
  const dynamic = /<MPD[^>]*\stype\s*=\s*"dynamic"/.test(xml);
  return { protected: isProtected, dynamic, status: isProtected ? 'BLOCKED_DRM' : 'OK' };
}
