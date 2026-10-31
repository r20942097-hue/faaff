/** UPC two-engine read-only synthetic request matrix (not real-site E2E). */
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const s = path.join(root, 'integrations/browser-filters/source/s');
const args = process.argv.slice(2);
function option(name) {
  const index = args.indexOf(name);
  return index < 0 ? undefined : args[index + 1];
}
const dir = option('--engine-dir');
const ghosteryFile = option('--ghostery-entry');
assert.ok(dir && ghosteryFile && option('--report'), 'engine-dir, ghostery-entry and report required');
const engineDir = path.resolve(dir);
const packageEntry = path.resolve(ghosteryFile);
const lock = JSON.parse(fs.readFileSync(path.join(s, 'verification/engine-lock.json'), 'utf8'));
const manifest = JSON.parse(fs.readFileSync(path.join(engineDir, 'manifest.json'), 'utf8'));
assert.equal(manifest.ublock_commit, lock.ublock.commit);
for (const [name, expected] of Object.entries(manifest.files)) {
  assert.ok(!path.isAbsolute(name) && !name.split('/').includes('..'), 'unsafe engine file');
  const actual = crypto.createHash('sha256').update(fs.readFileSync(path.join(engineDir, name))).digest('hex');
  assert.equal(actual, expected, 'engine file hash changed: ' + name);
}
const index = JSON.parse(fs.readFileSync(path.join(root, 'ai/imports/s.json'), 'utf8'));
assert.equal(index.source_repository, 'r20942097-hue/s');
const files = new Map(index.files.map(x => [x.path, x]));
function readPinned(name) {
  const bytes = fs.readFileSync(path.join(s, name));
  const header = Buffer.from('blob ' + bytes.length + '\0');
  const sha = crypto.createHash('sha1').update(header).update(bytes).digest('hex');
  assert.equal(sha, files.get(name)?.git_blob_sha, 'pinned source mismatch: ' + name);
  assert.equal(bytes.length, files.get(name).size);
  return bytes.toString('utf8');
}
const rootPackage = path.resolve(path.dirname(packageEntry), '../..');
assert.equal(packageEntry, path.join(rootPackage, 'dist/esm/index.js'));
const metadata = JSON.parse(fs.readFileSync(path.join(rootPackage, 'package.json'), 'utf8'));
assert.equal(metadata.name, lock.secondary_engine.package);
assert.equal(metadata.version, lock.secondary_engine.version);
const npmLock = fs.readFileSync(path.join(s, 'verification/ghostery/package-lock.json'));
const installedLock = fs.readFileSync(path.join(rootPackage, '../../..', 'package-lock.json'));
assert.equal(crypto.createHash('sha256').update(installedLock).digest('hex'),
             crypto.createHash('sha256').update(npmLock).digest('hex'));
assert.equal(JSON.parse(npmLock).packages['node_modules/' + metadata.name].integrity,
             lock.secondary_engine.integrity);

const { pslInit, StaticNetFilteringEngine } =
  await import(pathToFileURL(path.join(engineDir, 'node/index.js')));
const ghostery = await import(pathToFileURL(packageEntry));
pslInit(fs.readFileSync(path.join(engineDir, 'public_suffix_list.dat'), 'utf8'));

const sourceFiles = ['tracking.txt', 'v2/tracking.txt'];
const primary = await StaticNetFilteringEngine.create({ noPSL: true });
let checks = 0, rules = 0;
const profiles = [];
for (const name of sourceFiles) {
  const list = readPinned(name);
  const parsed = list.split(/\r?\n/).map(x => x.trim())
    .filter(x => x && !x.startsWith('!') && !x.startsWith('['));
  await primary.useLists([{ name, raw: list }]);
  const secondary = ghostery.FiltersEngine.parse(list);
  const observations = [];
  for (const line of parsed) {
    const match = /^\|\|([a-z0-9.-]+)\^\$third-party$/i.exec(line);
    assert.ok(match, 'unsupported rule requires explicit fixture review: ' + line);
    const host = match[1].toLowerCase();
    const cases = [
      ['third-party', 'https://unrelated.example/', 'https://' + host + '/probe.js', 'script', true],
      ['subdomain', 'https://unrelated.example/', 'https://sub.' + host + '/probe.js', 'script', true],
      ['first-party', 'https://' + host + '/', 'https://' + host + '/probe.js', 'script', false],
      ['hostname-boundary', 'https://unrelated.example/', 'https://' + host + '.invalid.test/probe.js', 'script', false],
      ['url-text', 'https://unrelated.example/', 'https://unrelated.example/path/' + host, 'script', false],
      ['image', 'https://unrelated.example/', 'https://' + host + '/probe.gif', 'image', true],
    ];
    for (const [scenario, originURL, url, type, expected] of cases) {
      const primaryMatch = primary.matchRequest({ originURL, url, type }) === 1;
      const secondaryMatch = secondary.match(ghostery.Request.fromRawDetails({
        sourceUrl: originURL, url, type,
      })).match;
      assert.equal(primaryMatch, expected, 'uBO mismatch ' + name + ' / ' + line + ' / ' + scenario);
      assert.equal(secondaryMatch, expected, 'Ghostery mismatch ' + name + ' / ' + line + ' / ' + scenario);
      checks += 2;
    }
    observations.push(host);
    rules++;
  }
  // A synthetic opt-out must override blocking in both actual engines.
  // This exception lives in memory only, never in a published filter.
  const host = observations[0];
  assert.ok(host, 'no first rule for exception control');
  const nl = String.fromCharCode(10);
  const withException = list + nl + '@@||' + host + '^$third-party' + nl;
  await primary.useLists([{ name, raw: withException }]);
  const secondaryWithException = ghostery.FiltersEngine.parse(withException);
  const probe = {
    originURL: 'https://unrelated.example/',
    sourceUrl: 'https://unrelated.example/',
    url: 'https://' + host + '/probe.js', type: 'script',
  };
  assert.equal(primary.matchRequest(probe), 2, 'uBO exception not honored');
  const outcome = secondaryWithException.match(ghostery.Request.fromRawDetails(probe));
  assert.equal(outcome.match, false, 'Ghostery exception not honored');
  assert.ok(outcome.exception, 'Ghostery exception not identified');
  checks += 2;
  profiles.push({ path: name, rules: observations.length,
                  scenarios_per_rule: 6, exception_controls: 2 });
}
assert.equal(rules, 47);
assert.equal(checks, 47 * 6 * 2 + 4);
const report = {
  schema: 'upc-engine-matrix/v1',
  result: 'PASS',
  source_commit: index.source_commit,
  engines: { ublock_origin_commit: lock.ublock.commit,
             ghostery_version: lock.secondary_engine.version },
  pinned_tracking_rules: rules,
  exception_controls: 4,
  requests_compared: checks,
  profiles,
  synthetic_only: true,
  actual_stock_lists_enabled: 'NOT_RUN',
  live_site_compatibility: 'NOT_RUN',
  publication: 'NO_GO',
};
fs.writeFileSync(option('--report'), JSON.stringify(report, null, 2) + '\n');
console.log('UPC TWO-ENGINE MATRIX PASS:', rules, 'rules,', checks,
            'synthetic engine comparisons, no stock list or real-site claim');
