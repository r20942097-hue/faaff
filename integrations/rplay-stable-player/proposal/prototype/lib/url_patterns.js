// Pure URL classification for RPLAY media requests and supported tabs.
// Independent implementation (design reference only; no third-party code copied).

export const RPLAY_HOSTS = Object.freeze(['rplay.live', 'rplay-cdn.com']);
export const YOUTUBE_HOSTS = Object.freeze(['youtube.com']);

function parseHttp(value) {
  if (typeof value !== 'string' || value.length > 16384) return null;
  let url;
  try {
    url = new URL(value);
  } catch {
    return null;
  }
  if (url.protocol !== 'https:' && url.protocol !== 'http:') return null;
  if (url.username || url.password) return null;
  return url;
}

export function hostMatches(hostname, roots) {
  const host = String(hostname || '').toLowerCase();
  return roots.some((root) => host === root || host.endsWith(`.${root}`));
}

/** Returns 'hls' | 'dash' | 'mp4' | null for a request URL (+ optional Content-Type). */
export function classifyMediaUrl(value, contentType = '') {
  const url = parseHttp(value);
  if (!url) return null;
  const type = String(contentType || '').split(';')[0].trim().toLowerCase();
  const path = url.pathname;
  if (/\.m3u8$/i.test(path)
    || ['application/vnd.apple.mpegurl', 'application/x-mpegurl', 'audio/mpegurl'].includes(type)) return 'hls';
  if (/\.mpd$/i.test(path) || type === 'application/dash+xml') return 'dash';
  if (/\.(mp4|m4a)$/i.test(path) || ['video/mp4', 'audio/mp4'].includes(type)) return 'mp4';
  return null;
}

/** Only RPLAY-origin media is considered by the detector (least privilege). */
export function isRplayMediaRequest({ url, tabId, method = 'GET', type = '' } = {}) {
  if (!Number.isInteger(tabId) || tabId < 0 || method !== 'GET') return false;
  if (type && !['xmlhttprequest', 'media', 'other'].includes(type)) return false;
  const parsed = parseHttp(url);
  if (!parsed || !hostMatches(parsed.hostname, RPLAY_HOSTS)) return false;
  return classifyMediaUrl(url) !== null;
}

/** Classify a tab URL into a site kind used by the tab adapter. */
export function classifyTabUrl(value) {
  const url = parseHttp(value);
  if (!url || url.protocol !== 'https:') return null;
  if (hostMatches(url.hostname, ['rplay.live'])) return 'rplay';
  if (hostMatches(url.hostname, YOUTUBE_HOSTS)) return 'youtube';
  return null;
}

/** Remove query/fragment so that URLs (which may carry signed tokens) are never shown or persisted. */
export function redactUrl(value) {
  const url = parseHttp(value);
  if (!url) return '';
  return `${url.origin}${url.pathname}`;
}
