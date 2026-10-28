const send = (msg) => chrome.runtime.sendMessage({ v: 1, ...msg });
let site = '';
const $ = (s) => document.querySelector(s);

function el(tag, text, cls) { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; }

function mediaSummary(media) {
  if (!media) return '状態取得不可';
  if (!media.length) return 'メディア要素なし';
  const m = media[0];
  return `${m.paused ? '停止' : '再生中'} / ${m.muted ? 'ミュート' : '音あり'}${m.live ? ' / LIVE' : ''}${media.length > 1 ? ` (+${media.length - 1})` : ''}`;
}

async function renderTabs() {
  const r = await send({ type: 'tabs.list', ...(site ? { site } : {}) });
  const ul = $('#tabs'); ul.replaceChildren();
  if (!r || !r.ok) { ul.append(el('li', `取得失敗: ${r && r.error}`, 'err')); return; }
  if (!r.tabs.length) ul.append(el('li', '対象タブなし'));
  for (const t of r.tabs) {
    const li = el('li');
    li.append(el('span', t.site === 'rplay' ? 'RPLAY' : 'YouTube', 'site'), el('span', ` ${t.title} `), el('small', mediaSummary(t.media)));
    if (t.error) li.append(el('div', t.error, 'err'));
    for (const [cmd, label] of [['play', '▶'], ['pause', '⏸'], ['toggleMute', '🔇']]) {
      const b = el('button', label); b.onclick = async () => { await send({ type: 'media.command', command: cmd, tabIds: [t.tabId] }); renderTabs(); };
      li.append(b);
    }
    const tm = el('button', t.tabMuted ? 'タブ音解除' : 'タブ消音');
    tm.onclick = async () => { await send({ type: 'tab.mute', tabIds: [t.tabId], muted: !t.tabMuted }); renderTabs(); };
    const fo = el('button', '表示'); fo.onclick = () => chrome.tabs.update(t.tabId, { active: true });
    li.append(tm, fo);
    ul.append(li);
  }
}

async function renderCandidates() {
  const r = await send({ type: 'candidates.list' });
  const ul = $('#candidates'); ul.replaceChildren();
  if (!r || !r.ok) return;
  $('#terms').checked = Boolean(r.settings.termsAcknowledged);
  if (!r.candidates.length) ul.append(el('li', '候補なし'));
  for (const c of r.candidates) {
    const li = el('li');
    li.append(el('span', `${c.mediaType.toUpperCase()} `, 'site'), el('small', `${c.displayUrl} [${c.status}]`));
    if (c.variants && c.variants.length) li.append(el('div', c.variants.map((v) => v.resolution || `${Math.round(v.bandwidth / 1000)}kbps`).join(', ')));
    const b = el('button', '保存（明示）');
    b.disabled = !r.settings.downloadsEnabled || c.status.startsWith('blocked');
    b.onclick = async () => { const x = await send({ type: 'download.request', candidateId: c.id }); $('#status').textContent = x.ok ? `キュー: ${x.job.phase}` : `拒否: ${x.error}`; renderJobs(); };
    li.append(b);
    ul.append(li);
  }
}

async function renderJobs() {
  const r = await send({ type: 'jobs.list' });
  const ul = $('#jobs'); ul.replaceChildren();
  if (!r || !r.ok) return;
  for (const j of r.jobs.slice(-8).reverse()) ul.append(el('li', `${j.filename} — ${j.phase}${j.error ? ` (${j.error.errorCode || j.error})` : ''}`));
}

document.querySelectorAll('#filters button').forEach((b) => b.addEventListener('click', () => {
  site = b.dataset.site; document.querySelectorAll('#filters button').forEach((x) => x.classList.toggle('on', x === b)); renderTabs();
}));
document.querySelectorAll('#bulk button[data-cmd]').forEach((b) => b.addEventListener('click', async () => {
  const r = await send({ type: 'media.command', command: b.dataset.cmd, ...(site ? { site } : {}) });
  const failed = (r.results || []).filter((x) => x.error).length;
  $('#status').textContent = `${b.textContent}: ${(r.results || []).length} タブ, エラー ${failed}`;
  renderTabs();
}));
$('#refresh').onclick = () => { renderTabs(); renderCandidates(); renderJobs(); };
$('#terms').onchange = async (e) => {
  const on = e.target.checked;
  await send({ type: 'settings.set', settings: { termsAcknowledged: on, downloadsEnabled: on } });
  renderCandidates();
};
renderTabs(); renderCandidates(); renderJobs();
