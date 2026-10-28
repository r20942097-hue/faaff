// Pure retry policy: exponential backoff with full jitter and a cap.
export const RETRYABLE_HTTP = new Set([408, 425, 429, 500, 502, 503, 504]);

export function isRetryable({ status, errorCode } = {}) {
  if (Number.isInteger(status)) return RETRYABLE_HTTP.has(status);
  return ['NETWORK_ERROR', 'TIMEOUT', 'NETWORK_FAILED', 'SERVER_FAILED'].includes(errorCode);
}

export function backoffMs(attempt, { baseMs = 1000, capMs = 60000, random = Math.random } = {}) {
  const n = Math.max(0, Math.floor(attempt));
  const ceiling = Math.min(capMs, baseMs * 2 ** n);
  return Math.floor(random() * ceiling);
}

export function shouldRetry(attempt, maxAttempts, failure) {
  return attempt + 1 < maxAttempts && isRetryable(failure);
}
