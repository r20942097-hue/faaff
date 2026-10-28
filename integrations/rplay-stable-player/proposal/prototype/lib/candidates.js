// Pure, bounded, de-duplicated candidate registry with TTL.
// Serializable (toJSON/fromJSON) so the MV3 service worker can persist it to chrome.storage.session
// and rebuild after it is suspended.
import { redactUrl } from './url_patterns.js';

export function createCandidateStore({ now = () => Date.now(), ttlMs = 15 * 60 * 1000, maxPerTab = 20, maxTotal = 100 } = {}) {
  /** key = `${tabId}|${url}` */
  const entries = new Map();
  let seq = 0;

  function sweep() {
    const t = now();
    for (const [k, v] of entries) if (t - v.lastSeen >= ttlMs) entries.delete(k);
  }

  function upsert({ tabId, url, mediaType }) {
    sweep();
    const key = `${tabId}|${url}`;
    const existing = entries.get(key);
    if (existing) {
      existing.lastSeen = now();
      existing.hits += 1;
      return { added: false, candidate: existing };
    }
    const perTab = [...entries].filter(([, v]) => v.tabId === tabId);
    if (perTab.length >= maxPerTab) entries.delete(perTab[0][0]);
    while (entries.size >= maxTotal) entries.delete(entries.keys().next().value);
    seq += 1;
    const candidate = {
      id: `c${now().toString(36)}-${seq}`,
      tabId,
      url,
      mediaType,
      firstSeen: now(),
      lastSeen: now(),
      hits: 1,
      status: 'observed',
    };
    entries.set(key, candidate);
    return { added: true, candidate };
  }

  function setStatus(id, status, info = {}) {
    for (const v of entries.values()) if (v.id === id) { Object.assign(v, info, { status }); return true; }
    return false;
  }

  function get(id) {
    sweep();
    for (const v of entries.values()) if (v.id === id) return v;
    return null;
  }

  /** Public view: never exposes query strings (signed tokens). */
  function list(tabId) {
    sweep();
    return [...entries.values()]
      .filter((v) => tabId === undefined || v.tabId === tabId)
      .map(({ url, ...rest }) => ({ ...rest, displayUrl: redactUrl(url) }))
      .reverse();
  }

  function clearTab(tabId) {
    for (const [k, v] of entries) if (v.tabId === tabId) entries.delete(k);
  }

  function toJSON() { sweep(); return { seq, entries: [...entries.values()] }; }

  function load(data) {
    entries.clear();
    if (!data || !Array.isArray(data.entries)) return;
    seq = Number.isInteger(data.seq) ? data.seq : 0;
    for (const e of data.entries) {
      if (e && Number.isInteger(e.tabId) && typeof e.url === 'string') entries.set(`${e.tabId}|${e.url}`, e);
    }
    sweep();
  }

  return { upsert, setStatus, get, list, clearTab, toJSON, load, size: () => entries.size };
}
