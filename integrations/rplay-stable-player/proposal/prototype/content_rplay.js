// RPLAY content script (classic script). Sends the page title only; no DOM scraping of
// user data, no network interception, no token access.
(() => {
  const send = () => {
    const title = String(document.title || '').replace(/\s*[|\-–]\s*RPLAY.*$/i, '').trim().slice(0, 300);
    chrome.runtime.sendMessage({ v: 1, type: 'rplay.pageInfo', title }).catch(() => {});
  };
  send();
  let last = location.href;
  new MutationObserver(() => { if (location.href !== last) { last = location.href; send(); } })
    .observe(document.querySelector('title') || document.documentElement, { childList: true, subtree: true });
})();
