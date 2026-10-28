// Versioned message schema + validation shared by popup, service worker and content script.
import { MEDIA_COMMANDS } from './media_control.js';

export const PROTOCOL_VERSION = 1;

export const MSG = Object.freeze({
  TABS_LIST: 'tabs.list',               // popup -> SW : list RPLAY + YouTube tabs (+ media status)
  MEDIA_COMMAND: 'media.command',       // popup -> SW : play/pause/mute... for tabIds or a site
  TAB_MUTE: 'tab.mute',                 // popup -> SW : browser-level tab mute (chrome.tabs.update)
  CANDIDATES_LIST: 'candidates.list',   // popup -> SW : detected RPLAY media candidates
  DOWNLOAD_REQUEST: 'download.request', // popup -> SW : explicit user download of one candidate
  JOBS_LIST: 'jobs.list',               // popup -> SW
  SETTINGS_GET: 'settings.get',
  SETTINGS_SET: 'settings.set',
  PAGE_INFO: 'rplay.pageInfo',          // content (rplay) -> SW : page title only
});

const EXTENSION_PAGE_TYPES = new Set(Object.values(MSG).filter((t) => t !== MSG.PAGE_INFO));

function isTabIdList(v) {
  return Array.isArray(v) && v.length <= 100 && v.every((x) => Number.isInteger(x) && x >= 0);
}

/**
 * @param {object} msg
 * @param {{fromExtensionPage:boolean, fromContentScript:boolean}} sender
 * @returns {{ok:true}|{ok:false,error:string}}
 */
export function validateMessage(msg, sender) {
  if (!msg || typeof msg !== 'object') return { ok: false, error: 'BAD_MESSAGE' };
  if (msg.v !== PROTOCOL_VERSION) return { ok: false, error: 'BAD_VERSION' };
  const { type } = msg;
  if (EXTENSION_PAGE_TYPES.has(type) && !sender?.fromExtensionPage) return { ok: false, error: 'FORBIDDEN_SENDER' };
  if (type === MSG.PAGE_INFO && !sender?.fromContentScript) return { ok: false, error: 'FORBIDDEN_SENDER' };
  switch (type) {
    case MSG.TABS_LIST:
      return msg.site === undefined || ['rplay', 'youtube'].includes(msg.site) ? { ok: true } : { ok: false, error: 'BAD_SITE' };
    case MSG.MEDIA_COMMAND:
      if (!MEDIA_COMMANDS.includes(msg.command)) return { ok: false, error: 'BAD_COMMAND' };
      if (msg.tabIds !== undefined && !isTabIdList(msg.tabIds)) return { ok: false, error: 'BAD_TAB_IDS' };
      if (msg.site !== undefined && !['rplay', 'youtube'].includes(msg.site)) return { ok: false, error: 'BAD_SITE' };
      return { ok: true };
    case MSG.TAB_MUTE:
      return isTabIdList(msg.tabIds) && typeof msg.muted === 'boolean' ? { ok: true } : { ok: false, error: 'BAD_ARGS' };
    case MSG.CANDIDATES_LIST:
    case MSG.JOBS_LIST:
    case MSG.SETTINGS_GET:
      return { ok: true };
    case MSG.DOWNLOAD_REQUEST:
      return typeof msg.candidateId === 'string' && msg.candidateId.length <= 64 ? { ok: true } : { ok: false, error: 'BAD_ARGS' };
    case MSG.SETTINGS_SET:
      return msg.settings && typeof msg.settings === 'object' && Object.keys(msg.settings).every((k) => k in DEFAULT_SETTINGS)
        ? { ok: true } : { ok: false, error: 'BAD_SETTINGS' };
    case MSG.PAGE_INFO:
      return typeof msg.title === 'string' && msg.title.length <= 300 ? { ok: true } : { ok: false, error: 'BAD_ARGS' };
    default:
      return { ok: false, error: 'UNKNOWN_TYPE' };
  }
}

export const DEFAULT_SETTINGS = Object.freeze({
  detectionEnabled: true,
  // Downloads stay OFF until the user confirms rights / terms of service in the popup (NEEDS_HUMAN).
  downloadsEnabled: false,
  termsAcknowledged: false,
});

export function senderInfo(sender, extensionId) {
  const fromExtension = Boolean(sender && sender.id === extensionId);
  return {
    fromExtensionPage: fromExtension && !sender.tab,
    fromContentScript: fromExtension && Boolean(sender.tab) && /^https:\/\/(?:[\w-]+\.)*rplay\.live\//.test(sender.url || ''),
  };
}

/** Pure filename sanitizer for downloads (no path traversal, no reserved chars). */
export function safeFilename(title, ext) {
  const base = String(title || 'rplay').replace(/[\\/:*?"<>|\x00-\x1f]/g, '_').replace(/^\.+/, '').trim().slice(0, 120) || 'rplay';
  const e = String(ext || '').replace(/[^a-z0-9]/gi, '').slice(0, 5);
  return `RPLAY/${base}${e ? `.${e}` : ''}`;
}
