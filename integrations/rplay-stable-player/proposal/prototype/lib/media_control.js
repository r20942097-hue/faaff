// The function below is injected with chrome.scripting.executeScript({func: mediaCommand, args:[cmd]}).
// It MUST be self-contained (no closures / imports) because it is serialized into the page.
// It only touches <video>/<audio> elements that are already present; it does not read cookies,
// storage, network data or player internals.
export function mediaCommand(command, doc) {
  const d = doc || document;
  const allowed = ['status', 'play', 'pause', 'mute', 'unmute', 'toggleMute'];
  if (!allowed.includes(command)) return { ok: false, error: 'UNKNOWN_COMMAND', media: [] };
  const els = Array.from(d.querySelectorAll('video, audio')).slice(0, 16);
  const errors = [];
  for (const el of els) {
    try {
      if (command === 'play') {
        const p = el.play();
        if (p && typeof p.catch === 'function') p.catch((e) => errors.push(String((e && e.name) || e)));
      } else if (command === 'pause') {
        el.pause();
      } else if (command === 'mute') {
        el.muted = true;
      } else if (command === 'unmute') {
        el.muted = false;
      } else if (command === 'toggleMute') {
        el.muted = !el.muted;
      }
    } catch (e) {
      errors.push(String((e && e.name) || e));
    }
  }
  const media = els.map((el) => ({
    tag: String(el.tagName || '').toLowerCase(),
    paused: Boolean(el.paused),
    muted: Boolean(el.muted),
    volume: typeof el.volume === 'number' ? Math.round(el.volume * 100) / 100 : null,
    currentTime: typeof el.currentTime === 'number' ? Math.floor(el.currentTime) : null,
    duration: Number.isFinite(el.duration) ? Math.floor(el.duration) : null,
    live: el.duration === Infinity,
  }));
  return { ok: errors.length === 0, error: errors[0] || null, media };
}

export const MEDIA_COMMANDS = Object.freeze(['status', 'play', 'pause', 'mute', 'unmute', 'toggleMute']);
