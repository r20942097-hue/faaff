/** Measure incremental *synthetic request outcomes* over pinned EasyPrivacy fragments.
 * This is NOT the full EasyPrivacy subscription or any user's enabled stock lists.
 * Do not infer real-world tracking efficacy from this report.
 */
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const S = path.join(ROOT, 'integrations/browser-filters/source/s');
const HERE = path.join(ROOT, 'tools/privacy-control');
const args = process.argv.slice(2);
function option(name) { const at = args.indexOf(name); return at < 0 ? undefined : args[at + 1]; }
const stockDir = option('--stock-dir'), enginePath = option('--engine-dir');
const ghosteryFile = option('--ghostery-entry'), output = option('--report');
assert.ok(stockDir && enginePath && ghosteryFile && output, 'missing explicit stock/engine/report inputs');
const stockRoot = path.resolve(stockDir), engineRoot = path.resolve(enginePath);
const lock = JSON.parse(fs.readFileSync(path.join(HERE, 'verification/stock-source-lock.json')));
const validated = JSON.parse(fs.readFileSync(path.join(stockRoot, 'verified-sources.json')));
assert.equal(lock.schema, 'upc-stock-source-lock/v1');
assert.equal(validated.schema, 'upc-verified-stock-sources/v1');
assert.equal(validated.upstream_commit, lock.upstream_commit);
assert.equal(validated.scope, lock.scope);
assert.equal(validated.publication, 'NO_GO');
assert.equal(validated.real_enabled_stock_lists, 'NOT_VERIFIED');
assert.equal(validated.files.length, lock.files.length);
const gitHash = data => crypto.createHash('sha1').update(
  Buffer.concat([Buffer.from('blob ' + data.length + '\0'), data])).digest('hex');
const sha256 = data => crypto.createHash('sha256').update(data).digest('hex');
const stockParts = [];
for (let i = 0; i < lock.files.length; i++) {
  const record = lock.files[i];
  assert.ok(/^easyprivacy\/[a-z0-9_]+\.txt$/.test(record.path));
  const contents = fs.readFileSync(path.join(stockRoot, record.path));
  assert.equal(contents.length, record.size);
  assert.equal(gitHash(contents), record.git_blob_sha);
  assert.equal(validated.files[i].path, record.path);
  assert.equal(validated.files[i].sha256, sha256(contents));
  stockParts.push(contents.toString('utf8'));
}
const sourceIndex = JSON.parse(fs.readFileSync(path.join(ROOT, 'ai/imports/s.json')));
const sourceEntry = sourceIndex.files.find(x => x.path === 'v2/tracking.txt');
assert.ok(sourceEntry && sourceIndex.source_repository === 'r20942097-hue/s');
const candidateRaw = fs.readFileSync(path.join(S, 'v2/tracking.txt'));
assert.equal(gitHash(candidateRaw), sourceEntry.git_blob_sha);
const rules = candidateRaw.toString('utf8').split(/\r?\n/).map(x => x.trim())
  .filter(x => x && !x.startsWith('!') && !x.startsWith('['));
assert.equal(rules.length, 38);
const hosts = rules.map(rule => {
  const m = /^\|\|([a-z0-9.-]+)\^\$third-party$/i.exec(rule);
  assert.ok(m, 'candidate includes unsupported syntax: ' + rule);
  return m[1].toLowerCase();
});
assert.equal(new Set(hosts).size, 38);

const engineLock = JSON.parse(fs.readFileSync(path.join(S, 'verification/engine-lock.json')));
const engineManifest = JSON.parse(fs.readFileSync(path.join(engineRoot, 'manifest.json')));
assert.equal(engineManifest.ublock_commit, engineLock.ublock.commit);
for (const [relative, hash] of Object.entries(engineManifest.files)) {
  assert.ok(!path.isAbsolute(relative) && !relative.split('/').includes('..'));
  assert.equal(sha256(fs.readFileSync(path.join(engineRoot, relative))), hash);
}
const ghostEntry = path.resolve(ghosteryFile);
const pkgRoot = path.resolve(path.dirname(ghostEntry), '../..');
assert.equal(ghostEntry, path.join(pkgRoot, 'dist/esm/index.js'));
const pkg = JSON.parse(fs.readFileSync(path.join(pkgRoot, 'package.json')));
assert.equal(pkg.name, engineLock.secondary_engine.package);
assert.equal(pkg.version, engineLock.secondary_engine.version);
const installedLock = fs.readFileSync(path.join(pkgRoot, '../../..', 'package-lock.json'));
const sourceLock = fs.readFileSync(path.join(S, 'verification/ghostery/package-lock.json'));
assert.equal(sha256(installedLock), sha256(sourceLock));
const { pslInit, StaticNetFilteringEngine } =
  await import(pathToFileURL(path.join(engineRoot, 'node/index.js')));
const ghostery = await import(pathToFileURL(ghostEntry));
pslInit(fs.readFileSync(path.join(engineRoot, 'public_suffix_list.dat'), 'utf8'));

const scenarios = [];
for (const host of hosts) {
  scenarios.push(
    {host, kind:'third-party-script', origin:'https://example.org/',
     url:'https://' + host + '/probe.js', type:'script'},
    {host, kind:'third-party-image', origin:'https://example.org/',
     url:'https://' + host + '/probe.png', type:'image'},
    {host, kind:'third-party-xhr', origin:'https://example.org/',
     url:'https://' + host + '/probe', type:'xmlhttprequest'},
    {host, kind:'subdomain-script', origin:'https://example.org/',
     url:'https://sub.' + host + '/probe.js', type:'script'},
    {host, kind:'first-party-script', origin:'https://' + host + '/',
     url:'https://' + host + '/probe.js', type:'script'},
    {host, kind:'boundary-control', origin:'https://example.org/',
     url:'https://' + host + '.invalid.test/probe.js', type:'script'},
    {host, kind:'url-text-control', origin:'https://example.org/',
     url:'https://example.org/resource/path/' + host, type:'script'},
  );
}
const stockRaw = stockParts.join('\n');
const combinedRaw = stockRaw + '\n' + candidateRaw.toString('utf8');
const primary = await StaticNetFilteringEngine.create({noPSL:true});
async function matches(raw) {
  await primary.useLists([{name:'pinned-upstream-fragments',raw}]);
  const secondary = ghostery.FiltersEngine.parse(raw);
  return scenarios.map(item => {
    const request = {originURL:item.origin, sourceUrl:item.origin,
                     url:item.url, type:item.type};
    return {
      ubo:primary.matchRequest(request) === 1,
      ghostery:secondary.match(ghostery.Request.fromRawDetails(request)).match,
    };
  });
}
const before = await matches(stockRaw);
const after = await matches(combinedRaw);
const findings = [];
const counts = {
  source_components: lock.files.length,
  candidates: hosts.length, cases: scenarios.length,
  engine_observations: scenarios.length * 2 * 2,
  selected_source_baseline_blocked: {ubo:0,ghostery:0},
  additional_synthetic_blocks: {ubo:0,ghostery:0},
  baseline_regressions: {ubo:0,ghostery:0},
  engine_disagreements: {baseline:0,combined:0},
};
for (let i=0; i<scenarios.length; i++) {
  const testcase = scenarios[i], old=before[i], updated=after[i];
  for (const engine of ['ubo','ghostery']) {
    if (old[engine]) counts.selected_source_baseline_blocked[engine]++;
    if (!old[engine] && updated[engine]) counts.additional_synthetic_blocks[engine]++;
    if (old[engine] && !updated[engine]) counts.baseline_regressions[engine]++;
  }
  if (old.ubo !== old.ghostery) counts.engine_disagreements.baseline++;
  if (updated.ubo !== updated.ghostery) counts.engine_disagreements.combined++;
  if (['first-party-script','boundary-control','url-text-control'].includes(testcase.kind)) {
    for (const engine of ['ubo','ghostery']) {
      assert.equal(updated[engine], old[engine],
        'candidate changed required non-matching control: ' + engine + ' / ' +
        testcase.host + ' / ' + testcase.kind);
    }
  }
  findings.push({host:testcase.host,scenario:testcase.kind,
    stock_fragment_matches:old,candidate_plus_stock_matches:updated,
    actual_browser_stock_profile:'NOT_VERIFIED',
    real_site_incremental_efficacy:'NOT_ESTABLISHED'});
}
const perHost = hosts.map(host => {
  const subset = findings.filter(x => x.host === host);
  const incremental = Object.fromEntries(['ubo','ghostery'].map(engine => [
    engine, subset.filter(row => !row.stock_fragment_matches[engine] &&
                                row.candidate_plus_stock_matches[engine])
                  .map(row => row.scenario)
  ]));
  const covered = Object.fromEntries(['ubo','ghostery'].map(engine => [
    engine, subset.filter(row => row.stock_fragment_matches[engine])
                  .map(row => row.scenario)
  ]));
  return {host, selected_fragment_coverage:covered,
          additional_synthetic_cases:incremental,
          active_browser_stock_coverage:'NOT_VERIFIED',
          incremental_real_world_privacy:'NOT_ESTABLISHED',
          proposed_auto_adoption:false};
});
assert.equal(counts.cases, 266);
assert.equal(counts.engine_observations, 1064);
assert.equal(perHost.length, 38);
const report = {
 schema:'upc-stock-fragment-comparison/v1',
 result:'PASS',
 source:{repository:'easylist/easylist',commit:lock.upstream_commit,
         scope:lock.scope,files:validated.files},
 candidate_source:{repository:'r20942097-hue/s',commit:sourceIndex.source_commit,
                   path:'v2/tracking.txt',git_blob_sha:sourceEntry.git_blob_sha},
 engines:{ublock_origin_commit:engineLock.ublock.commit,
          ghostery_version:engineLock.secondary_engine.version},
 counts, findings, per_host:perHost, synthetic_only:true,
 selected_upstream_fragments_not_full_list:true,
 actual_browser_enabled_lists:'NOT_VERIFIED',
 production_browser_site_e2e:'NOT_RUN',
 adopted_rules:0,publication:'NO_GO',
};
fs.writeFileSync(path.resolve(output), JSON.stringify(report, null, 2) + '\n');
console.log('UPC STOCK FRAGMENT COMPARISON PASS:',JSON.stringify(counts),
            '; selected upstream files only, not a live browser profile');
