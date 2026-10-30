// A real MV3 message roundtrip, but no external sites or privileged APIs.
document.querySelector('#activate').addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'PING' }, (response) => {
    document.querySelector('#result').textContent =
      !chrome.runtime.lastError && response?.ok === true && response?.worker === 'alive'
        ? 'Activated'
        : 'Worker unavailable';
  });
});
