// Common tab adapter: normalizes chrome.tabs.Tab objects from RPLAY and YouTube into one shape.
import { classifyTabUrl } from './url_patterns.js';

export const TAB_QUERY_PATTERNS = Object.freeze([
  'https://rplay.live/*',
  'https://*.rplay.live/*',
  'https://www.youtube.com/*',
  'https://m.youtube.com/*',
  'https://music.youtube.com/*',
]);

/** @returns {{tabId:number, windowId:number, site:'rplay'|'youtube', title:string, audible:boolean, tabMuted:boolean, active:boolean, discarded:boolean}|null} */
export function normalizeTab(tab) {
  if (!tab || !Number.isInteger(tab.id) || tab.id < 0) return null;
  const site = classifyTabUrl(tab.url || tab.pendingUrl || '');
  if (!site) return null;
  return {
    tabId: tab.id,
    windowId: Number.isInteger(tab.windowId) ? tab.windowId : -1,
    site,
    title: String(tab.title || '').slice(0, 200),
    audible: Boolean(tab.audible),
    tabMuted: Boolean(tab.mutedInfo && tab.mutedInfo.muted),
    active: Boolean(tab.active),
    discarded: Boolean(tab.discarded),
  };
}

export function normalizeTabs(tabs, { site } = {}) {
  return (Array.isArray(tabs) ? tabs : [])
    .map(normalizeTab)
    .filter(Boolean)
    .filter((t) => !site || t.site === site)
    .sort((a, b) => a.windowId - b.windowId || a.tabId - b.tabId);
}

/** Merge per-tab media status (from executeScript) into the tab list. */
export function mergeStatus(tabs, results) {
  const byId = new Map((results || []).map((r) => [r.tabId, r]));
  return tabs.map((t) => ({ ...t, media: byId.get(t.tabId)?.media ?? null, error: byId.get(t.tabId)?.error ?? null }));
}
