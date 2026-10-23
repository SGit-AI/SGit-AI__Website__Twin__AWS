/* The console's overview: a count per service, from the twin or the account, and where to go next. */
import { boot, api, act, esc, crumb, state, go } from './core.js';

const card = (href, n, k, s) => `<a class="cx-card" href="${href}"><div class="n">${typeof n === 'object' ? '<span class="cx-dim" title="' + esc(n.error) + '">-</span>' : esc(n)}</div><div class="k">${esc(k)}</div><div class="s">${s}</div></a>`;
const errNote = (n) => typeof n === 'object' ? `the role may not read this: ${esc(n.error)}` : '';

boot({
  page: 'overview', home: 'home',
  views: {
    async home() {
      const o = await api('overview');
      const live = state.mode === 'live';
      return crumb(['Console']) + `<h1>${live ? 'Account ' + esc(state.live.account) : 'The twin'}</h1>
        <div class="cx-cards">
          ${card('s3.html', o.buckets, 'S3 buckets', errNote(o.buckets) || (live ? 'every region, listed through Cloud Control' : 'kept in this browser'))}
          ${card('lambda.html', o.functions, 'Lambda functions', errNote(o.functions) || 'in ' + esc(state.region))}
          ${card('resources.html#/type/' + encodeURIComponent('AWS::Events::Rule'), o.rules, 'EventBridge rules', errNote(o.rules) || 'in ' + esc(state.region))}
          ${card('resources.html#/type/' + encodeURIComponent('AWS::IAM::Role'), o.roles, 'IAM roles', errNote(o.roles) || 'global')}
        </div>
        <div class="s3-panel"><div class="s3-panel-h"><h2>${live ? 'Live' : 'Twin'} mode</h2>${live ? '' : '<button class="s3-btn" data-act="seed">Create examples in the twin</button>'}</div>
          <div class="s3-panel-sub">${live
            ? `Every call goes to the account with the session pasted on <a href="../sessions/index.html">the sessions page</a>, signed in this page and sent from this browser. ${state.live.allow_writes ? 'Writes are allowed.' : 'Read-only: anything that would change the account is refused before it is sent.'} Switch with <b>Twin</b>, top left.`
            : `Every call is answered by the Python twin in this page, from its store in this browser's IndexedDB, which every console page shares. Nothing is sent to AWS. <b>Live</b>, top left, sends the same calls to an account with a session from <a href="../sessions/index.html">the sessions page</a>.`}
            Open <b>Requests</b>, top right, to see every call and every request it sent.</div></div>
        <div class="s3-panel"><div class="s3-panel-h"><h2>The pages</h2></div><div class="s3-grid">
          <div><div class="k"><a href="s3.html">S3</a></div><div class="v">Buckets, objects, upload, properties. Live, buckets are listed through Cloud Control; a bucket's objects need a CORS rule on it.</div></div>
          <div><div class="k"><a href="lambda.html">Lambda</a></div><div class="v">Functions per region, a scan of every region, each function's configuration, code, permissions, triggers, logs, and a test invoke.</div></div>
          <div><div class="k"><a href="resources.html">All resources</a></div><div class="v">Any resource type, listed and read through the Cloud Control API, which answers a browser.</div></div>
          <div><div class="k"><a href="calls.html">Calls</a></div><div class="v">Which AWS calls work from a browser, the CLI and code, measured; and any operation sent by hand.</div></div>
          <div><div class="k"><a href="twin.html">Twin data</a></div><div class="v">What the twin holds in this browser, file by file.</div></div>
          <div><div class="k"><a href="plan.html">The plan</a></div><div class="v">What the console is for, what is next, and the vault.</div></div></div></div>`;
    }
  },
  actions: {
    seed: () => act(async () => {
      await api('lambda_seed', { region: state.region });
      try { await api('create_bucket', { name: 'example-twin-bucket', region: state.region }); } catch (e) { /* already there */ }
    }, 'Created example functions, a role, a schedule and a bucket in the twin')
  }
});
