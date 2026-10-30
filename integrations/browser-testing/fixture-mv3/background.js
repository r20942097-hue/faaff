// Synthetic extension service worker; no network, cookies, storage or permissions.
chrome.runtime.onInstalled.addListener(() => {
  console.info('Isolated fixture loaded');
});
