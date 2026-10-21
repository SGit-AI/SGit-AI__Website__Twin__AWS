#!/usr/bin/env node
/* aws.twin.sgit.ai — the interface tests, run with `node admin/build/test.js`.

   The same script runs against the memory backend and the vault backend (over a
   localStorage shim) and must produce the same answers, because that is the claim:
   consuming code is written against the interface, the backend is swappable. The live
   backend is tested for what it does in this PoC, which is to refuse with the command
   it would have sent. The vault's commits, diffs and the account graph are tested on
   top. No test framework: a failing assertion exits non-zero. */
'use strict';
var path = require('path');
var AwsTwin = require(path.join(__dirname, '../../assets/twin/interface.js'));
var Vault = require(path.join(__dirname, '../../assets/twin/vault.js'));
var Templates = require(path.join(__dirname, '../../assets/twin/templates.js'));

var passed = 0, failed = 0, current = '';
function ok(cond, msg) { if (cond) { passed++; } else { failed++; console.error('  FAIL [' + current + '] ' + msg); } }
function eq(a, b, msg) { ok(JSON.stringify(a) === JSON.stringify(b), msg + ' (got ' + JSON.stringify(a) + ', wanted ' + JSON.stringify(b) + ')'); }
function throwsCode(fn, code, msg) { try { fn(); ok(false, msg + ': did not throw'); } catch (e) { eq(e.code, code, msg); } }
function test(name, fn) { current = name; try { fn(); } catch (e) { failed++; console.error('  FAIL [' + name + '] threw ' + (e.stack || e)); } }

function memStorage() {
  var m = {};
  return { getItem: function (k) { return k in m ? m[k] : null; }, setItem: function (k, v) { m[k] = String(v); }, removeItem: function (k) { delete m[k]; }, _m: m };
}

/* --- 1. manifest coverage: every op in the manifest is implemented by the state ops --- */
test('manifest coverage', function () {
  Object.keys(AwsTwin.MANIFEST).forEach(function (svc) {
    Object.keys(AwsTwin.MANIFEST[svc]).forEach(function (op) {
      ok(AwsTwin.OPS[svc] && typeof AwsTwin.OPS[svc][op] === 'function', svc + '.' + op + ' is in the manifest but not implemented');
    });
  });
  Object.keys(AwsTwin.OPS).forEach(function (svc) {
    Object.keys(AwsTwin.OPS[svc]).forEach(function (op) {
      ok(AwsTwin.MANIFEST[svc] && AwsTwin.MANIFEST[svc][op], svc + '.' + op + ' is implemented but not in the manifest');
    });
  });
});

/* --- 2. the same script, two backends, same answers --- */
function normalise(x) {
  /* strip what is random or clock-driven by design, so two runs compare equal */
  return JSON.parse(JSON.stringify(x, function (k, v) {
    if (typeof v === 'number' && /^(creationTime|ingestionTime|timestamp|storedBytes|ms)$/.test(k)) return '<n>';
    if (typeof v !== 'string') return v;
    if (/^(i-0|sg-0|r-0)[0-9a-f]{16}$/.test(v)) return '<id>';
    if (/^(AROA|ANPA)[0-9A-F]{17}/.test(v)) return '<id>';
    if (/^"[0-9a-f]{32}"$/.test(v)) return '<etag>';
    if (/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d/.test(v)) return '<time>';
    if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(v)) return '<request-id>';
    if (/arn:aws:cloudformation:.*\/[0-9a-f]{8}-[0-9a-f]{4}$/.test(v)) return v.replace(/\/[0-9a-f]{8}-[0-9a-f]{4}$/, '/<id>');
    if (/lambda-url\.[a-z0-9-]+\.on\.aws/.test(v)) return '<function-url>';
    if (/REPORT RequestId/.test(v)) return '<report>';
    if (/RequestId: /.test(v)) return v.replace(/RequestId: [0-9a-f-]+/, 'RequestId: <request-id>');
    return v;
  }));
}
function script(backend) {
  Templates.register(backend);
  var out = [];
  var rec = function (label, fn) { try { out.push([label, normalise(fn())]); } catch (e) { out.push([label, 'ERR ' + e.code]); } };
  backend.ensureAccount('123456789012', 'test');
  var c = AwsTwin.client(backend, { accountId: '123456789012', region: 'eu-west-2' }, null, { sync: true });
  var us = AwsTwin.client(backend, { accountId: '123456789012', region: 'us-east-1' }, null, { sync: true });
  rec('identity', function () { return c.sts.getCallerIdentity({}); });
  rec('buckets empty', function () { return c.s3.listBuckets({}); });
  rec('create bucket', function () { return c.s3.createBucket({ Bucket: 'twin-test-bucket' }); });
  rec('create bucket again', function () { return c.s3.createBucket({ Bucket: 'twin-test-bucket' }); });
  rec('bad bucket name', function () { return c.s3.createBucket({ Bucket: 'Bad_Name' }); });
  rec('put', function () { return c.s3.putObject({ Bucket: 'twin-test-bucket', Key: 'a/b.txt', Body: 'hello', ContentType: 'text/plain' }); });
  rec('put 2', function () { return c.s3.putObject({ Bucket: 'twin-test-bucket', Key: 'c.txt', Body: 'world' }); });
  rec('list prefix', function () { return c.s3.listObjectsV2({ Bucket: 'twin-test-bucket', Prefix: 'a/' }); });
  rec('get', function () { return c.s3.getObject({ Bucket: 'twin-test-bucket', Key: 'a/b.txt' }); });
  rec('get missing', function () { return c.s3.getObject({ Bucket: 'twin-test-bucket', Key: 'nope' }); });
  rec('delete non-empty bucket', function () { return c.s3.deleteBucket({ Bucket: 'twin-test-bucket' }); });
  rec('unknown param', function () { return c.s3.getObject({ Bucket: 'twin-test-bucket', Key: 'a/b.txt', Nope: 1 }); });
  rec('role', function () { return c.iam.createRole({ RoleName: 'fn-role' }); });
  rec('policy', function () { return c.iam.createPolicy({ PolicyName: 'fn-policy', PolicyDocument: { Version: '2012-10-17', Statement: [] } }); });
  rec('attach', function () { return c.iam.attachRolePolicy({ RoleName: 'fn-role', PolicyArn: 'arn:aws:iam::123456789012:policy/fn-policy' }); });
  rec('attach missing policy', function () { return c.iam.attachRolePolicy({ RoleName: 'fn-role', PolicyArn: 'arn:aws:iam::123456789012:policy/none' }); });
  rec('attach aws managed', function () { return c.iam.attachRolePolicy({ RoleName: 'fn-role', PolicyArn: 'arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess' }); });
  rec('attached', function () { return c.iam.listAttachedRolePolicies({ RoleName: 'fn-role' }); });
  rec('delete attached role', function () { return c.iam.deleteRole({ RoleName: 'fn-role' }); });
  rec('fn no role', function () { return c.lambda.createFunction({ FunctionName: 'f1', Role: 'arn:aws:iam::123456789012:role/none' }); });
  rec('fn', function () { return c.lambda.createFunction({ FunctionName: 'f1', Role: 'arn:aws:iam::123456789012:role/fn-role', Environment: { Variables: { BUCKET: 'twin-test-bucket' } } }); });
  rec('fn in other region', function () { return us.lambda.listFunctions({}); });
  rec('fn here', function () { return c.lambda.listFunctions({}); });
  rec('invoke', function () { return c.lambda.invoke({ FunctionName: 'f1', Payload: { x: 1 } }); });
  rec('invoke logs', function () { var r = c.logs.filterLogEvents({ logGroupName: '/aws/lambda/f1' }); return { n: r.events.length, first: r.events[0].message }; });
  rec('log groups', function () { return c.logs.describeLogGroups({}); });
  rec('sg', function () { return c.ec2.createSecurityGroup({ GroupName: 'web', Description: 'web' }); });
  var sgId = backend.state.accounts['123456789012'].ec2.securityGroups[0].GroupId;
  rec('ingress', function () { return c.ec2.authorizeSecurityGroupIngress({ GroupId: sgId, FromPort: 443, ToPort: 443 }); });
  rec('run', function () { return c.ec2.runInstances({ ImageId: 'ami-1', SecurityGroupIds: [sgId], IamInstanceProfile: 'fn-role', Name: 'box' }); });
  rec('run bad sg', function () { return c.ec2.runInstances({ ImageId: 'ami-1', SecurityGroupIds: ['sg-0deadbeefdeadbeef'] }); });
  var iid = backend.state.accounts['123456789012'].ec2.instances[0].InstanceId;
  rec('stop', function () { return c.ec2.stopInstances({ InstanceIds: [iid] }); });
  rec('describe stopped', function () { return c.ec2.describeInstances({ Filters: [{ Name: 'instance-state-name', Values: ['stopped'] }] }); });
  rec('describe other region', function () { return us.ec2.describeInstances({}); });
  rec('stop in other region', function () { return us.ec2.stopInstances({ InstanceIds: [iid] }); });
  rec('cost', function () { c.twin.recordCost({ Service: 'AWS Lambda', Amount: 1.5, Date: '2026-09-03' }); c.twin.recordCost({ Service: 'AWS Lambda', Amount: 2.25, Date: '2026-09-20' }); us.twin.recordCost({ Service: 'Amazon S3', Amount: 4, Date: '2026-10-01' }); return c.ce.getCostAndUsage({ TimePeriod: { Start: '2026-09-01', End: '2026-11-01' }, Granularity: 'MONTHLY' }); });
  rec('cost by region', function () { return c.ce.getCostAndUsage({ Granularity: 'MONTHLY', GroupBy: [{ Type: 'DIMENSION', Key: 'REGION' }] }); });
  rec('stack', function () { return c.cloudformation.createStack({ StackName: 'api', TemplateName: 'sg-send-lambda-url', Parameters: [{ ParameterKey: 'ImageTag', ParameterValue: 'v1' }] }); });
  rec('stack twice', function () { return c.cloudformation.createStack({ StackName: 'api', TemplateName: 'sg-send-lambda-url' }); });
  rec('stack bad template', function () { return c.cloudformation.createStack({ StackName: 'x', TemplateName: 'none' }); });
  rec('stacks', function () { return c.cloudformation.listStacks({}); });
  rec('stack described', function () { var s = c.cloudformation.describeStacks({ StackName: 'api' }).Stacks[0]; return { outputs: s.Outputs.map(function (o) { return o.OutputKey; }), resources: s.Resources.length, status: s.StackStatus }; });
  rec('fns after stack', function () { return c.lambda.listFunctions({}).Functions.map(function (f) { return f.FunctionName; }); });
  rec('fargate stack', function () { return us.cloudformation.createStack({ StackName: 'api-fg', TemplateName: 'sg-send-fargate' }); });
  rec('fargate gap recorded', function () { return us.cloudformation.describeStacks({ StackName: 'api-fg' }).Stacks[0].Outputs.filter(function (o) { return o.OutputKey === 'EcsService'; })[0].OutputValue; });
  rec('delete stack', function () { c.cloudformation.deleteStack({ StackName: 'api' }); return c.lambda.listFunctions({}).Functions.map(function (f) { return f.FunctionName; }); });
  rec('state summary', function () { return Vault.summarise(backend.state); });
  return out;
}
var memOut, vaultOut;
test('memory backend runs the script', function () { memOut = script(new AwsTwin.MemoryBackend()); ok(memOut.length > 40, 'script produced results'); });
test('vault backend runs the script', function () { vaultOut = script(new Vault.VaultBackend(memStorage())); ok(vaultOut.length > 40, 'script produced results'); });
test('the two backends agree', function () {
  for (var i = 0; i < memOut.length; i++) {
    eq(vaultOut[i], memOut[i], 'step "' + memOut[i][0] + '" differs between vault and memory');
  }
});
test('expected answers', function () {
  var o = {}; memOut.forEach(function (r) { o[r[0]] = r[1]; });
  eq(o['create bucket again'], 'ERR BucketAlreadyOwnedByYou', 'duplicate bucket');
  eq(o['bad bucket name'], 'ERR InvalidBucketName', 'bad bucket name');
  eq(o['list prefix'].KeyCount, 1, 'prefix listing');
  eq(o['get'].Body, 'hello', 'get body');
  eq(o['get missing'], 'ERR NoSuchKey', 'missing key');
  eq(o['delete non-empty bucket'], 'ERR BucketNotEmpty', 'non-empty bucket');
  eq(o['unknown param'], 'ERR UnknownParam', 'unknown param refused');
  eq(o['attach missing policy'], 'ERR NoSuchEntity', 'missing policy');
  eq(o['attached'].AttachedPolicies.length, 2, 'two attachments');
  eq(o['delete attached role'], 'ERR DeleteConflict', 'role in use');
  eq(o['fn no role'], 'ERR InvalidParameterValueException', 'function needs a role that exists');
  eq(o['fn in other region'].Functions.length, 0, 'regions are separate');
  eq(o['fn here'].Functions.length, 1, 'function listed in its region');
  eq(o['invoke'].StatusCode, 200, 'invoke ok');
  eq(o['invoke logs'].n, 4, 'invoke wrote four log lines');
  eq(o['log groups'].logGroups.length, 1, 'log group auto-created');
  eq(o['run bad sg'], 'ERR InvalidGroup.NotFound', 'bad sg refused');
  eq(o['describe stopped'].Reservations[0].Instances.length, 1, 'stopped filter');
  eq(o['describe other region'].Reservations[0].Instances.length, 0, 'instance not in other region');
  eq(o['stop in other region'], 'ERR InvalidInstanceID.NotFound', 'cannot stop from other region');
  eq(o['cost'].ResultsByTime.length, 2, 'two months');
  eq(o['cost'].ResultsByTime[0].Groups[0].Metrics.UnblendedCost.Amount, '3.75', 'september lambda summed');
  eq(o['cost by region'].ResultsByTime[1].Groups.map(function (g) { return g.Keys[0]; }), ['us-east-1'], 'grouped by region');
  eq(o['stack twice'], 'ERR AlreadyExistsException', 'duplicate stack');
  eq(o['stack bad template'], 'ERR ValidationError', 'unknown template');
  eq(o['stack described'].outputs, ['FunctionUrl', 'FunctionArn', 'StoreBucket', 'Version'], 'stack outputs');
  eq(o['stack described'].resources, 5, 'stack resources');
  eq(o['fns after stack'], ['f1', 'api-api'], 'stack created a function');
  ok(/tracked gap/.test(o['fargate gap recorded']), 'fargate records the ECS gap');
  eq(o['delete stack'], ['f1'], 'stack deletion removed its function');
  eq(o['state summary'].functions, 1, 'summary counts functions');
});

/* --- 3. vault commits, checkout and diff --- */
test('vault commits and diffs', function () {
  var store = memStorage();
  var v = new Vault.VaultBackend(store);
  Templates.register(v);
  v.ensureAccount('123456789012', 'a');
  var c = AwsTwin.client(v, { accountId: '123456789012', region: 'eu-west-2' }, null, { sync: true });
  c.s3.createBucket({ Bucket: 'bucket-1' });
  var c1 = v.commit('monday');
  ok(/^[0-9a-f]{16}$/.test(c1.id), 'commit id shape');
  eq(v.head(), c1.id, 'head moves');
  eq(v.isDirty(), false, 'clean after commit');
  c.s3.putObject({ Bucket: 'bucket-1', Key: 'k', Body: 'v' });
  c.s3.createBucket({ Bucket: 'bucket-2' });
  c.iam.createRole({ RoleName: 'r' });
  eq(v.isDirty(), true, 'dirty after changes');
  var c2 = v.commit('friday');
  var d = v.diff(c1.id, c2.id)['123456789012'];
  eq(d.added.map(function (x) { return x.key; }).sort(), ['iam:role r', 's3:bucket bucket-2', 's3:object bucket-1/k'], 'added resources');
  eq(d.changed.map(function (x) { return x.key; }), ['s3:bucket bucket-1'], 'bucket object count changed');
  eq(d.removed.length, 0, 'nothing removed');
  v.checkout(c1.id);
  eq(c.s3.listBuckets({}).Buckets.length, 1, 'checkout restored monday');
  var v2 = new Vault.VaultBackend(store);
  eq(v2.log().length, 2, 'reloaded from storage with both commits');
  eq(v2.log()[0].message, 'friday', 'log is newest first');
  var doc = v2.exportDoc();
  var v3 = new Vault.VaultBackend(memStorage());
  v3.importDoc(doc);
  eq(v3.head(), c1.id, 'import keeps head');
  throwsCode(function () { v3.importDoc({ nope: 1 }); }, 'BadVault', 'bad import refused');
  v3.reset();
  eq(v3.log().length, 0, 'reset clears commits');
  throwsCode(function () { c.s3.listBuckets({}); c.sts.getCallerIdentity({}); AwsTwin.client(v, { accountId: '999999999999', region: 'eu-west-2' }, null, { sync: true }).s3.listBuckets({}); }, 'UnrecognizedClientException', 'unknown account refused');
});

/* --- 4. the account graph --- */
test('account graph', function () {
  var m = new AwsTwin.MemoryBackend();
  var seeded = Templates.seedDemo(m);
  ok(seeded.calls > 50, 'demo seed made calls through the interface (' + seeded.calls + ')');
  var g = AwsTwin.graphOf(m.state.accounts['111111111111']);
  var kinds = {};
  g.nodes.forEach(function (n) { kinds[n.kind] = (kinds[n.kind] || 0) + 1; });
  ok(kinds.function === 2, 'two functions in the graph (' + kinds.function + ')');
  ok(kinds.instance === 2, 'two live instances');
  ok(kinds.stack === 2, 'two stacks');
  var rels = {};
  g.edges.forEach(function (e) { rels[e.rel] = (rels[e.rel] || 0) + 1; });
  ok(rels.assumes_role === 2, 'function → role edges');
  ok(rels.uses_bucket === 2, 'function → bucket edges from env vars');
  ok(rels.in_security_group === 2, 'instance → security group edges');
  ok(rels.instance_profile === 2, 'instance → role edges');
  ok(rels.attached_policy >= 4, 'role → policy edges');
  ok(rels.created >= 8, 'stack → resource edges');
  var mm = AwsTwin.graphToMermaid(g);
  ok(/^flowchart LR/.test(mm) && mm.split('\n').length === 1 + g.nodes.length + g.edges.length, 'mermaid has a line per node and edge');
});

/* --- 5. the live backend refuses with the command it would send --- */
test('live backend', function () {
  var ss = new Vault.SessionStore(memStorage());
  var live = new AwsTwin.LiveBackend(ss);
  var c = AwsTwin.client(live, { accountId: '123456789012', region: 'eu-west-2' }, null, { sync: true });
  throwsCode(function () { c.s3.listBuckets({}); }, 'NoSession', 'no session');
  throwsCode(function () { ss.set({ accessKeyId: 'ASIA', secretAccessKey: 's' }); }, 'BadSession', 'no token refused');
  throwsCode(function () { ss.set({ accessKeyId: 'ASIA', secretAccessKey: 's', sessionToken: 't', accountId: '12' }); }, 'BadSession', 'bad account refused');
  var parsed = Vault.SessionStore.parsePaste('export AWS_ACCESS_KEY_ID="ASIAEXAMPLE"\nexport AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI"\nexport AWS_SESSION_TOKEN="IQoJb3JpZ2luX2Vj"');
  eq(parsed, { accessKeyId: 'ASIAEXAMPLE', secretAccessKey: 'wJalrXUtnFEMI', sessionToken: 'IQoJb3JpZ2luX2Vj' }, 'export lines parsed');
  var parsed2 = Vault.SessionStore.parsePaste('[123456789012_AdministratorAccess]\naws_access_key_id = ASIAEXAMPLE\naws_secret_access_key = wJalr\naws_session_token = IQoJ');
  eq(parsed2.accountId, '123456789012', 'credentials-file profile gives the account');
  eq(parsed2.role, 'AdministratorAccess', 'credentials-file profile gives the role');
  var parsed3 = Vault.SessionStore.parsePaste('$Env:AWS_ACCESS_KEY_ID="ASIAX"\n$Env:AWS_SECRET_ACCESS_KEY="s"\n$Env:AWS_SESSION_TOKEN="t"');
  eq(parsed3.accessKeyId, 'ASIAX', 'powershell lines parsed');
  var parsed4 = Vault.SessionStore.parsePaste('SET AWS_ACCESS_KEY_ID=ASIAY\nSET AWS_SECRET_ACCESS_KEY=s\nSET AWS_SESSION_TOKEN=t');
  eq(parsed4.accessKeyId, 'ASIAY', 'windows set lines parsed');
  ss.set({ accessKeyId: 'ASIA', secretAccessKey: 's', sessionToken: 't', accountId: '123456789012', expiresAt: new Date(Date.now() + 3600000).toISOString() });
  ok(ss.status().secondsLeft > 3500, 'expiry counted down');
  try { c.s3.listBuckets({}); ok(false, 'should refuse'); } catch (e) { eq(e.code, 'NotWired', 'not wired'); eq(e.meta.command, 'ListBucketsCommand', 'names the SDK command'); }
  throwsCode(function () { c.twin.recordCost({ Service: 'x', Amount: 1 }); }, 'TwinOnly', 'twin-only ops never reach the live backend');
  ss.set({ accessKeyId: 'ASIA', secretAccessKey: 's', sessionToken: 't', accountId: '123456789012', expiresAt: new Date(Date.now() - 1000).toISOString() });
  throwsCode(function () { c.s3.listBuckets({}); }, 'ExpiredToken', 'expired session refused');
  eq(ss.status().expired, true, 'status says expired');
  ss.clear();
  eq(ss.status().present, false, 'cleared');
});

/* --- 6. the async client surface, which the UI uses --- */
test('async client', function () {
  var m = new AwsTwin.MemoryBackend();
  m.ensureAccount('123456789012');
  var log = [];
  var c = AwsTwin.client(m, { accountId: '123456789012', region: 'eu-west-2' }, function (r) { log.push(r); });
  var p = c.s3.createBucket({ Bucket: 'async-b' });
  ok(typeof p.then === 'function', 'returns a promise');
  return p.then(function () { return c.s3.getObject({ Bucket: 'async-b', Key: 'none' }); }).then(function () { ok(false, 'should reject'); }, function (e) {
    eq(e.code, 'NoSuchKey', 'rejects with the AWS error code');
    eq(log.length, 2, 'both calls logged');
    eq(log[1].error.code, 'NoSuchKey', 'log carries the error');
    eq(log[0].command, 'CreateBucketCommand', 'log carries the SDK command name');
  });
});

/* tests are synchronous apart from the last one; wait for it before reporting */
setTimeout(function () {
  console.log('aws.twin interface tests: ' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
}, 50);
