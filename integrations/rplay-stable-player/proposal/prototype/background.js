// MV3 service worker (ES module). Stateless between wake-ups: every piece of state is
// re-loaded from chrome.storage on wake and persisted after each mutation.
import { classifyMediaUrl, isRplayMediaRequest } from './lib/url_patterns.js';
import { inspectHls, inspectDash } from './lib/hls_manifest.js';
import { createCandidateStore } from './lib/candidates.js';
import { createQueue } from './lib/download_queue.js';
import { normalizeTabs, mergeStatus, TAB_QUERY_PATTERNS } from './lib/tab_adapter.js';
import { mediaCommand } from './lib/media_control.js';
import { MSG, validateMessage, senderInfo, DEFAULT_SETTINGS, safeFilename } from './lib/messages.js';

const TICK_ALARM = 'rsp-proposal-tick';
const K_CANDIDATES = 'candidates.v1'; // chrome.storage.session (cleared with the browser session)
const K_JOBS = 'jobs.v1';             // chrome.storage.local
const K_SETTINGS = 'settings.v1';     // chrome.storage.local
const K_TITLES = 'titles.v1';         // chrome.storage.session

const candidates = createCandidateStore();
const queue = createQueue();
let settings = { ...DEFAULT_SETTINGS };
let titles = {};
let ready = null;

function load() {
  if (!ready) {
    ready = (async () => {
      const [s, l] = await Promise.all([
        chrome.storage.session.get([K_CANDIDATES, K_TITLES]),
        chrome.storage.local.get([K_JOBS, K_SETTINGS]),
      ]);
      candidates.load(s[K_CANDIDATES]);
      titles = s[K_TITLES] || {};
      queue.load(l[K_JOBS]);
      settings = { ...DEFAULT_SETTINGS, ...(l[K_SETTINGS] || {}) };
    })();
  }
  return ready;
}

const saveCandidates = () => chrome.storage.session.set({ [K_CANDIDATES]: candidates.toJSON(), [K_TITLES]: titles });
const saveJobs = () => chrome.storage.local.set({ [K_JOBS]: queue.toJSON() });

async function ensureAlarm() {
  const existing = await chrome.alarms.get(TICK_ALARM);
  if (!existing) await chrome.alarms.create(TICK_ALARM, { periodInMinutes: 0.5 });
}

// ---------------------------------------------------------------- Genre 1: detection
const inFlight = new Set();

async function inspectCandidate(candidate) {
  if (inFlight.has(candidate.id) || candidate.mediaType === 'mp4') return;
  inFlight.add(candidate.id);
  try {
    // Anonymous fetch: cookies / Authorization are never replayed by the prototype.
    const res = await fetch(candidate.url, { credentials: 'omit', redirect: 'error', signal: AbortSignal.timeout(8000) });
    if (!res.ok) {
      candidates.setStatus(candidate.id, res.status === 401 || res.status === 403 ? 'auth-required' : 'http-error', { lastStatus: res.status });
      return;
    }
    const text = await res.text();
    if (candidate.mediaType === 'hls') {
      const r = inspectHls(text, candidate.url);
      candidates.setStatus(candidate.id, r.protected ? 'blocked-encrypted' : 'inspected', {
        variants: r.variants.map(({ bandwidth, resolution, codecs }) => ({ bandwidth, resolution, codecs })),
        segments: r.segments,
        durationSec: r.durationSec,
        endList: r.endList,
      });
    } else if (candidate.mediaType === 'dash') {
      const r = inspectDash(text);
      candidates.setStatus(candidate.id, r.protected ? 'blocked-drm' : 'inspected', { dynamic: r.dynamic });
    }
  } catch (e) {
    candidates.setStatus(candidate.id, 'inspect-error', { lastError: String(e && e.message || e).slice(0, 80) });
  } finally {
    inFlight.delete(candidate.id);
    await saveCandidates();
  }
}

chrome.webRequest.onHeadersReceived.addListener((d) => {
  void (async () => {
    await load();
    if (!settings.detectionEnabled) return;
    if (![200, 206].includes(d.statusCode) || !isRplayMediaRequest(d)) return;
    const ct = (d.responseHeaders || []).find((h) => String(h.name).toLowerCase() === 'content-type');
    const mediaType = classifyMediaUrl(d.url, ct && ct.value);
    if (!mediaType || (d.statusCode === 206 && mediaType !== 'mp4')) return;
    const { added, candidate } = candidates.upsert({ tabId: d.tabId, url: d.url, mediaType });
    await saveCandidates();
    if (added) {
      await chrome.action.setBadgeText({ tabId: d.tabId, text: String(candidates.list(d.tabId).length) });
      void inspectCandidate(candidate);
    }
  })();
}, { urls: ['https://*.rplay.live/*', 'https://rplay.live/*', 'https://*.rplay-cdn.com/*'] }, ['responseHeaders']);

chrome.tabs.onRemoved.addListener((tabId) => {
  void load().then(() => { candidates.clearTab(tabId); delete titles[tabId]; return saveCandidates(); });
});
chrome.tabs.onUpdated.addListener((tabId, info) => {
  if (!info.url) return;
  void load().then(() => { candidates.clearTab(tabId); return saveCandidates(); });
});

// ---------------------------------------------------------------- Genre 1: download queue (explicit only)
async function pump() {
  await load();
  for (const job of queue.runnable()) {
    const c = candidates.get(job.candidateId);
    if (!c) { queue.start(job.id); queue.fail(job.id, { errorCode: 'CANDIDATE_EXPIRED' }); continue; }
    try {
      const downloadId = await chrome.downloads.download({ url: c.url, filename: job.filename, conflictAction: 'uniquify', saveAs: false });
      queue.start(job.id, downloadId);
    } catch (e) {
      queue.start(job.id);
      queue.fail(job.id, { errorCode: 'NETWORK_FAILED', message: String(e && e.message || e).slice(0, 80) });
    }
  }
  await saveJobs();
}

chrome.downloads.onChanged.addListener((delta) => {
  void (async () => {
    await load();
    const job = queue.list().find((j) => j.browserDownloadId === delta.id && j.phase === 'running');
    if (!job || !delta.state) return;
    if (delta.state.current === 'complete') queue.complete(job.id);
    if (delta.state.current === 'interrupted') queue.fail(job.id, { errorCode: delta.error?.current || 'NETWORK_FAILED' });
    await saveJobs();
  })();
});

chrome.alarms.onAlarm.addListener((a) => { if (a.name === TICK_ALARM) void pump(); });

async function recoverAfterRestart() {
  await load();
  const running = queue.list().filter((j) => j.phase === 'running').map((j) => j.browserDownloadId).filter(Number.isInteger);
  const known = [];
  for (const id of running) {
    const [item] = await chrome.downloads.search({ id });
    if (item && item.state === 'in_progress') known.push(id);
    else if (item && item.state === 'complete') { const j = queue.list().find((x) => x.browserDownloadId === id); if (j) queue.complete(j.id); }
  }
  queue.recover(known);
  await saveJobs();
  await ensureAlarm();
}
chrome.runtime.onStartup.addListener(() => void recoverAfterRestart());
chrome.runtime.onInstalled.addListener(() => void recoverAfterRestart());

// ---------------------------------------------------------------- Genre 2 + 3: tab control
async function listTabs(site) {
  const tabs = normalizeTabs(await chrome.tabs.query({ url: [...TAB_QUERY_PATTERNS] }), { site });
  const results = await runOnTabs(tabs.filter((t) => !t.discarded).map((t) => t.tabId), 'status');
  return mergeStatus(tabs, results);
}

async function runOnTabs(tabIds, command) {
  return Promise.all(tabIds.map(async (tabId) => {
    try {
      const [r] = await chrome.scripting.executeScript({ target: { tabId }, func: mediaCommand, args: [command] });
      const value = r && r.result;
      return { tabId, media: value ? value.media : null, error: value && value.error };
    } catch (e) {
      return { tabId, media: null, error: String(e && e.message || e).slice(0, 80) };
    }
  }));
}

async function handle(msg) {
  await load();
  switch (msg.type) {
    case MSG.TABS_LIST:
      return { ok: true, tabs: await listTabs(msg.site) };
    case MSG.MEDIA_COMMAND: {
      const tabs = normalizeTabs(await chrome.tabs.query({ url: [...TAB_QUERY_PATTERNS] }), { site: msg.site });
      const allowed = new Set(tabs.filter((t) => !t.discarded).map((t) => t.tabId));
      const targets = (msg.tabIds || [...allowed]).filter((id) => allowed.has(id));
      return { ok: true, results: await runOnTabs(targets, msg.command) };
    }
    case MSG.TAB_MUTE: {
      const tabs = normalizeTabs(await chrome.tabs.query({ url: [...TAB_QUERY_PATTERNS] }));
      const allowed = new Set(tabs.map((t) => t.tabId));
      await Promise.all(msg.tabIds.filter((id) => allowed.has(id)).map((id) => chrome.tabs.update(id, { muted: msg.muted })));
      return { ok: true };
    }
    case MSG.CANDIDATES_LIST:
      return { ok: true, candidates: candidates.list(), settings };
    case MSG.JOBS_LIST:
      return { ok: true, jobs: queue.list() };
    case MSG.SETTINGS_GET:
      return { ok: true, settings };
    case MSG.SETTINGS_SET:
      settings = { ...settings, ...msg.settings };
      if (!settings.termsAcknowledged) settings.downloadsEnabled = false;
      await chrome.storage.local.set({ [K_SETTINGS]: settings });
      return { ok: true, settings };
    case MSG.DOWNLOAD_REQUEST: {
      if (!settings.downloadsEnabled || !settings.termsAcknowledged) return { ok: false, error: 'DOWNLOADS_DISABLED' };
      const c = candidates.get(msg.candidateId);
      if (!c) return { ok: false, error: 'CANDIDATE_EXPIRED' };
      if (c.status.startsWith('blocked')) return { ok: false, error: 'BLOCKED_PROTECTED_MEDIA' };
      const { added, job } = queue.enqueue({
        id: `j${Date.now().toString(36)}`,
        candidateId: c.id,
        mediaType: c.mediaType,
        filename: safeFilename(titles[c.tabId], c.mediaType === 'mp4' ? 'mp4' : ''),
      });
      await saveJobs();
      await ensureAlarm();
      if (added) void pump();
      return { ok: true, job };
    }
    case MSG.PAGE_INFO:
      return { ok: true };
    default:
      return { ok: false, error: 'UNKNOWN_TYPE' };
  }
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  const who = senderInfo(sender, chrome.runtime.id);
  const v = validateMessage(msg, who);
  if (!v.ok) { sendResponse(v); return false; }
  if (msg.type === MSG.PAGE_INFO) {
    void load().then(() => { titles[sender.tab.id] = msg.title; return saveCandidates(); });
    sendResponse({ ok: true });
    return false;
  }
  handle(msg).then(sendResponse, (e) => sendResponse({ ok: false, error: String(e && e.message || e).slice(0, 80) }));
  return true;
});
