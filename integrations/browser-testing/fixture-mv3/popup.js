// Isolated UI behavior only; no site or privilege access.
document.querySelector('#activate').addEventListener('click', () => {
  document.querySelector('#result').textContent = 'Activated';
});
