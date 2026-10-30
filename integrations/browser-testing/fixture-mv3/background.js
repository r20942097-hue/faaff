// Synthetic MV3 extension worker; no network, cookies, storage or host permissions.
chrome.runtime.onInstalled.addListener(() => {
  console.info('Isolated fixture loaded');
});

// Exercise a real popup-to-service-worker roundtrip rather than only verifying
// that the worker file is present on disk.
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === 'PING') {
    sendResponse({ ok: true, worker: 'alive' });
  }
});
