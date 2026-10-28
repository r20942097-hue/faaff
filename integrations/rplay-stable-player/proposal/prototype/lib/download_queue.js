// Pure download job state machine. Persistable; the service worker stores it in chrome.storage.local
// and a chrome.alarms tick re-drives it after the worker is restarted.
import { shouldRetry, backoffMs } from './retry.js';

export const PHASES = Object.freeze(['queued', 'running', 'waiting_retry', 'completed', 'failed', 'canceled', 'blocked']);
const TERMINAL = new Set(['completed', 'failed', 'canceled', 'blocked']);
const TRANSITIONS = {
  queued: ['running', 'canceled', 'blocked'],
  running: ['completed', 'waiting_retry', 'failed', 'canceled'],
  waiting_retry: ['running', 'canceled', 'failed'],
};

export function canTransition(from, to) {
  return (TRANSITIONS[from] || []).includes(to);
}

export function createQueue({ now = () => Date.now(), maxAttempts = 4, maxConcurrent = 1, random = Math.random } = {}) {
  let jobs = [];

  function find(id) { return jobs.find((j) => j.id === id) || null; }

  function move(job, to, patch = {}) {
    if (!canTransition(job.phase, to)) throw new Error(`BAD_TRANSITION_${job.phase}_${to}`);
    Object.assign(job, patch, { phase: to, updatedAt: now() });
    return job;
  }

  /** Dedup key: same candidate never queued twice while not terminal. */
  function enqueue({ id, candidateId, mediaType, filename }) {
    const dup = jobs.find((j) => j.candidateId === candidateId && !TERMINAL.has(j.phase));
    if (dup) return { added: false, job: dup };
    const job = { id, candidateId, mediaType, filename, phase: 'queued', attempts: 0, nextAt: 0, createdAt: now(), updatedAt: now(), error: null };
    jobs.push(job);
    if (mediaType !== 'mp4') move(job, 'blocked', { error: 'SEGMENTED_ACQUISITION_NOT_IN_PROTOTYPE' });
    return { added: true, job };
  }

  /** Jobs that may be started now. */
  function runnable() {
    const running = jobs.filter((j) => j.phase === 'running').length;
    const free = Math.max(0, maxConcurrent - running);
    return jobs.filter((j) => j.phase === 'queued' || (j.phase === 'waiting_retry' && j.nextAt <= now())).slice(0, free);
  }

  function start(id, browserDownloadId) {
    const job = find(id);
    job.attempts += 1;
    return move(job, 'running', { browserDownloadId: browserDownloadId ?? null, error: null });
  }

  function complete(id) { return move(find(id), 'completed'); }

  function fail(id, failure) {
    const job = find(id);
    if (shouldRetry(job.attempts - 1, maxAttempts, failure)) {
      return move(job, 'waiting_retry', { error: failure, nextAt: now() + backoffMs(job.attempts, { random }) });
    }
    return move(job, 'failed', { error: failure });
  }

  function cancel(id) { return move(find(id), 'canceled'); }

  /** After a worker restart, a "running" job whose browser download is unknown is re-queued for retry. */
  function recover(knownDownloadIds) {
    const known = new Set(knownDownloadIds);
    for (const j of jobs) {
      if (j.phase === 'running' && !known.has(j.browserDownloadId)) {
        move(j, 'waiting_retry', { error: { errorCode: 'WORKER_RESTARTED' }, nextAt: now() });
      }
    }
  }

  return {
    enqueue, runnable, start, complete, fail, cancel, recover, find,
    list: () => jobs.map((j) => ({ ...j })),
    toJSON: () => ({ jobs }),
    load(data) { jobs = Array.isArray(data?.jobs) ? data.jobs.filter((j) => PHASES.includes(j.phase)) : []; },
  };
}
