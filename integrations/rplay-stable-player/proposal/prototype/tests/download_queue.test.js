import test from 'node:test';
import assert from 'node:assert/strict';
import { createQueue, canTransition } from '../lib/download_queue.js';
import { backoffMs, isRetryable } from '../lib/retry.js';

test('transitions', () => {
  assert.equal(canTransition('queued', 'running'), true);
  assert.equal(canTransition('completed', 'running'), false);
});

test('dedupe active jobs per candidate', () => {
  const q = createQueue();
  assert.equal(q.enqueue({ id: 'j1', candidateId: 'c1', mediaType: 'mp4', filename: 'f' }).added, true);
  assert.equal(q.enqueue({ id: 'j2', candidateId: 'c1', mediaType: 'mp4', filename: 'f' }).added, false);
});

test('segmented media is blocked in prototype', () => {
  const q = createQueue();
  assert.equal(q.enqueue({ id: 'j1', candidateId: 'c1', mediaType: 'hls', filename: 'f' }).job.phase, 'blocked');
});

test('retry with backoff then fail after maxAttempts', () => {
  let t = 0;
  const q = createQueue({ now: () => t, maxAttempts: 2, random: () => 0.5 });
  q.enqueue({ id: 'j', candidateId: 'c', mediaType: 'mp4', filename: 'f' });
  q.start('j', 10);
  assert.equal(q.fail('j', { status: 503 }).phase, 'waiting_retry');
  assert.equal(q.runnable().length, 0);
  t = 10_000;
  assert.equal(q.runnable().length, 1);
  q.start('j', 11);
  assert.equal(q.fail('j', { status: 503 }).phase, 'failed');
});

test('non-retryable failure is terminal', () => {
  const q = createQueue();
  q.enqueue({ id: 'j', candidateId: 'c', mediaType: 'mp4', filename: 'f' });
  q.start('j', 1);
  assert.equal(q.fail('j', { status: 403 }).phase, 'failed');
});

test('recover running jobs after worker restart', () => {
  const q = createQueue({ now: () => 1 });
  q.enqueue({ id: 'a', candidateId: 'c1', mediaType: 'mp4', filename: 'f' });
  q.enqueue({ id: 'b', candidateId: 'c2', mediaType: 'mp4', filename: 'f' });
  q.start('a', 1);
  q.start('b', 2);
  const q2 = createQueue({ now: () => 2 });
  q2.load(JSON.parse(JSON.stringify(q.toJSON())));
  q2.recover([2]);
  assert.equal(q2.find('a').phase, 'waiting_retry');
  assert.equal(q2.find('b').phase, 'running');
});

test('concurrency limit', () => {
  const q = createQueue({ maxConcurrent: 1 });
  q.enqueue({ id: 'a', candidateId: 'c1', mediaType: 'mp4', filename: 'f' });
  q.enqueue({ id: 'b', candidateId: 'c2', mediaType: 'mp4', filename: 'f' });
  assert.equal(q.runnable().length, 1);
  q.start('a', 1);
  assert.equal(q.runnable().length, 0);
});

test('retry policy', () => {
  assert.equal(isRetryable({ status: 429 }), true);
  assert.equal(isRetryable({ status: 404 }), false);
  assert.equal(isRetryable({ errorCode: 'NETWORK_FAILED' }), true);
  assert.equal(backoffMs(10, { random: () => 0.999, capMs: 60000 }) < 60000, true);
  assert.equal(backoffMs(0, { random: () => 0.5, baseMs: 1000 }), 500);
});
