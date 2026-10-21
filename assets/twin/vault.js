/* aws.twin.sgit.ai — the vault backend, and the session slot.

   The vault backend is the StateBackend persisted to a key/value store with commits.
   In this PoC the store is the browser's localStorage, standing in for the user's
   vault: the shape (a working state, a list of commits, a head) is the shape an sgit
   vault gives for free, so the export of this document is what gets pushed there.

   The session slot is the place the live backend reads its credentials from. It is
   deliberately a different store from the twin data (sessionStorage by default: the
   tab's lifetime, never written to disk by the browser the way localStorage is), it
   carries an expiry, and nothing on this site ever reads the secret back into a page.
   Runs in the browser and in Node with a storage shim (admin/build/test.js). */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./interface.js'));
  else root.AwsTwinVault = factory(root.AwsTwin);
}(typeof self !== 'undefined' ? self : this, function (AwsTwin) {
  'use strict';

  var clone = AwsTwin.clone;
  var now = function () { return new Date().toISOString(); };

  function VaultBackend(storage, key, name) {
    AwsTwin.StateBackend.call(this, 'vault');
    this.storage = storage;
    this.key = key || 'aws.twin/vault';
    this.doc = this.load() || VaultBackend.newDoc(name);
    this.state = this.doc.working;
  }
  VaultBackend.newDoc = function (name) {
    return { format: 'aws.twin/vault@1', name: name || 'aws-twin', created: now(), head: null, commits: [], working: AwsTwin.emptyState() };
  };
  VaultBackend.prototype = Object.create(AwsTwin.StateBackend.prototype);
  VaultBackend.prototype.constructor = VaultBackend;

  VaultBackend.prototype.load = function () {
    try {
      var raw = this.storage.getItem(this.key);
      if (!raw) return null;
      var doc = JSON.parse(raw);
      if (doc.format !== 'aws.twin/vault@1') return null;
      return doc;
    } catch (e) { return null; }
  };
  VaultBackend.prototype.save = function () {
    this.doc.working = this.state;
    this.doc.savedAt = now();
    try { this.storage.setItem(this.key, JSON.stringify(this.doc)); }
    catch (e) { throw AwsTwin.TwinError('VaultWriteFailed', 'the vault could not be written: ' + e.message); }
  };

  /* Commits: every snapshot is a commit. The full state is kept per commit, because
     the PoC's states are small and a diff between any two commits must be cheap. */
  VaultBackend.prototype.commit = function (message) {
    var c = { parent: this.doc.head, at: now(), message: message || 'snapshot', state: clone(this.state) };
    c.id = AwsTwin.contentId({ parent: c.parent, at: c.at, message: c.message, state: c.state });
    c.summary = summarise(c.state);
    this.doc.commits.push(c);
    this.doc.head = c.id;
    this.save();
    return { id: c.id, at: c.at, message: c.message, parent: c.parent, summary: c.summary };
  };
  VaultBackend.prototype.log = function () {
    return this.doc.commits.slice().reverse().map(function (c) { return { id: c.id, at: c.at, message: c.message, parent: c.parent, summary: c.summary }; });
  };
  VaultBackend.prototype.head = function () { return this.doc.head; };
  VaultBackend.prototype.commitById = function (id) {
    for (var i = 0; i < this.doc.commits.length; i++) if (this.doc.commits[i].id === id || this.doc.commits[i].id.indexOf(id) === 0) return this.doc.commits[i];
    return null;
  };
  VaultBackend.prototype.stateAt = function (ref) {
    if (!ref || ref === 'working') return clone(this.state);
    var c = this.commitById(ref);
    if (!c) throw AwsTwin.TwinError('NoSuchCommit', 'no commit ' + ref + ' in this vault');
    return clone(c.state);
  };
  VaultBackend.prototype.checkout = function (ref) {
    this.state = this.stateAt(ref);
    if (ref && ref !== 'working') this.doc.head = this.commitById(ref).id;
    this.save();
  };
  VaultBackend.prototype.diff = function (refA, refB) {
    return AwsTwin.diffStates(this.stateAt(refA), this.stateAt(refB || 'working'));
  };
  VaultBackend.prototype.isDirty = function () {
    if (!this.doc.head) return Object.keys(this.state.accounts).length > 0;
    var d = this.diff(this.doc.head, 'working');
    return Object.keys(d).some(function (k) { return d[k].added.length || d[k].removed.length || d[k].changed.length; });
  };
  VaultBackend.prototype.exportDoc = function () { return clone(this.doc); };
  VaultBackend.prototype.importDoc = function (doc) {
    if (!doc || doc.format !== 'aws.twin/vault@1' || !doc.working || !Array.isArray(doc.commits)) throw AwsTwin.TwinError('BadVault', 'not an aws.twin/vault@1 document');
    this.doc = clone(doc);
    this.state = this.doc.working;
    this.save();
  };
  VaultBackend.prototype.reset = function (name) {
    this.doc = VaultBackend.newDoc(name || this.doc.name);
    this.state = this.doc.working;
    this.save();
  };
  VaultBackend.prototype.sizeBytes = function () {
    try { return (this.storage.getItem(this.key) || '').length; } catch (e) { return 0; }
  };

  function summarise(state) {
    var s = { accounts: 0, buckets: 0, objects: 0, functions: 0, instances: 0, roles: 0, policies: 0, logGroups: 0, stacks: 0, cost: 0 };
    Object.keys(state.accounts).forEach(function (id) {
      var a = state.accounts[id];
      s.accounts++;
      s.buckets += a.s3.buckets.length;
      Object.keys(a.s3.objects).forEach(function (b) { s.objects += a.s3.objects[b].length; });
      s.functions += a.lambda.functions.length;
      s.instances += a.ec2.instances.filter(function (i) { return i.State.Name !== 'terminated'; }).length;
      s.roles += a.iam.roles.length;
      s.policies += a.iam.policies.length;
      s.logGroups += a.logs.groups.length;
      s.stacks += a.cloudformation.stacks.length;
      s.cost += a.ce.records.reduce(function (n, r) { return n + r.Amount; }, 0);
    });
    s.cost = Math.round(s.cost * 100) / 100;
    return s;
  }

  /* --- the session slot --- */
  function SessionStore(storage, key) {
    this.storage = storage;
    this.key = key || 'aws.twin/session';
  }
  SessionStore.prototype.get = function () {
    try { var raw = this.storage.getItem(this.key); return raw ? JSON.parse(raw) : null; } catch (e) { return null; }
  };
  SessionStore.prototype.set = function (session) {
    var s = SessionStore.validate(session);
    this.storage.setItem(this.key, JSON.stringify(s));
    return this.status();
  };
  SessionStore.prototype.clear = function () { try { this.storage.removeItem(this.key); } catch (e) { /* nothing to clear */ } };
  SessionStore.prototype.status = function () {
    var s = this.get();
    if (!s) return { present: false };
    var left = s.expiresAt ? Date.parse(s.expiresAt) - Date.now() : null;
    return {
      present: true, accountId: s.accountId, accountName: s.accountName, role: s.role, region: s.region,
      keyId: s.accessKeyId, expiresAt: s.expiresAt, secondsLeft: left === null ? null : Math.max(0, Math.floor(left / 1000)),
      expired: left !== null && left <= 0
    };
  };
  SessionStore.validate = function (s) {
    s = s || {};
    if (!s.accessKeyId || !s.secretAccessKey) throw AwsTwin.TwinError('BadSession', 'a session needs at least an access key id and a secret access key');
    if (!s.sessionToken) throw AwsTwin.TwinError('BadSession', 'no session token: the access portal issues temporary credentials, and a long-lived IAM user key is exactly what this design refuses to hold');
    if (!/^\d{12}$/.test(s.accountId || '')) throw AwsTwin.TwinError('BadSession', 'accountId must be the 12-digit account the session belongs to');
    var out = {
      accessKeyId: s.accessKeyId, secretAccessKey: s.secretAccessKey, sessionToken: s.sessionToken,
      accountId: s.accountId, accountName: s.accountName || '', role: s.role || '', region: s.region || 'eu-west-2',
      pastedAt: now(), expiresAt: s.expiresAt || new Date(Date.now() + 3600 * 1000).toISOString()
    };
    return out;
  };
  /* Parse what the access portal's "Access keys" dialog gives: the macOS/Linux
     export lines, the Windows set lines, the PowerShell lines, or the credentials
     file block. All four name the same three variables. */
  SessionStore.parsePaste = function (text) {
    var out = {};
    var grab = function (name, key) {
      var re = new RegExp(name + '\\s*[=:]\\s*"?([^"\\s]+)"?', 'i');
      var m = re.exec(text || '');
      if (m) out[key] = m[1];
    };
    grab('AWS_ACCESS_KEY_ID', 'accessKeyId');
    grab('aws_access_key_id', 'accessKeyId');
    grab('AWS_SECRET_ACCESS_KEY', 'secretAccessKey');
    grab('aws_secret_access_key', 'secretAccessKey');
    grab('AWS_SESSION_TOKEN', 'sessionToken');
    grab('aws_session_token', 'sessionToken');
    var profile = /\[(\d{12})_([^\]\s]+)\]/.exec(text || '');
    if (profile) { out.accountId = profile[1]; out.role = profile[2]; }
    return out;
  };

  return { VaultBackend: VaultBackend, SessionStore: SessionStore, summarise: summarise };
}));
