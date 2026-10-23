/* The console's All resources page: any resource type, listed and read through the Cloud Control
   API, which answers a browser from any origin. The twin answers the types it holds (S3 buckets,
   Lambda functions, IAM roles, EventBridge rules, CloudFront distributions) and names the rest. */
import { boot, api, esc, enc, crumb, state, go, pretty } from './core.js';

const SERVICE_PAGE = { 'AWS::S3::Bucket': id => `s3.html#/b/${enc(id)}`, 'AWS::Lambda::Function': id => `lambda.html#/fn/${enc(state.region)}/${enc(id)}` };

boot({
  page: 'resources', home: 'types',
  views: {
    async types() {
      return crumb(['All resources']) + `<h1>All resources</h1>
        <div class="s3-panel"><div class="s3-panel-h"><h2>Resource types</h2></div>
          <div class="s3-panel-sub">Through the <b>Cloud Control API</b>: one way to list and read any resource type, and one a browser can reach (S3's own ListBuckets cannot). ${state.mode === 'live' ? 'Each list needs the role to have <code>cloudformation:ListResources</code> and the type\'s own read permissions.' : 'The twin answers the types it holds and says so, by name, for the rest.'}</div>
          <form class="s3-form s3-inline" data-submit="type"><label>Any type <small>for example AWS::DynamoDB::Table; Cloud Control lists the CloudFormation registry's types</small><input name="type" placeholder="AWS::Service::Resource" autocomplete="off"></label><div><button class="s3-btn primary" type="submit">List</button></div></form>
          <table class="s3-table"><tbody>${state.resourceTypes.map(t => `<tr><td><a href="#/type/${enc(t)}">${esc(t)}</a></td><td class="cx-dim">${/S3::Bucket|IAM::Role|CloudFront|Route53/.test(t) ? 'global' : 'in ' + esc(state.region)}</td></tr>`).join('')}</tbody></table></div>`;
    },
    async type(typeName) {
      const r = await api('resources', { type_name: typeName });
      const rows = r.resources.map(x => `<tr data-row="${esc(x.identifier)}"><td><a href="#/res/${enc(typeName)}/${enc(x.identifier)}">${esc(x.identifier)}</a></td><td><code class="cx-dim">${esc(JSON.stringify(x.properties).slice(0, 140))}</code></td></tr>`).join('');
      return crumb(['All resources', '#/types'], [typeName]) + `<h1>${esc(typeName)}</h1>
        <div class="s3-panel"><div class="s3-panel-h"><h2>Resources <span class="count">(${r.resources.length})</span></h2></div>
          <div class="s3-panel-sub">From <code>cloudcontrol.list_resources(TypeName=${esc(JSON.stringify(typeName))})</code> in ${esc(r.region)}. A list carries only the identifying properties; open one for the rest.</div>
          <div class="s3-search"><input placeholder="Find by identifier" data-filter="res"></div>
          ${r.resources.length ? `<table class="s3-table"><thead><tr><th>Identifier</th><th>Properties in the list</th></tr></thead><tbody>${rows}</tbody></table>` : `<div class="s3-empty"><b>None</b>No ${esc(typeName)} in ${esc(r.region)}.</div>`}</div>`;
    },
    async res(typeName, identifier) {
      const r = await api('resource', { type_name: typeName, identifier });
      const page = SERVICE_PAGE[typeName];
      return crumb(['All resources', '#/types'], [typeName, `#/type/${enc(typeName)}`], [identifier]) + `<h1>${esc(identifier)}</h1>
        <div class="s3-panel"><div class="s3-panel-h"><h2>Properties</h2>${page ? `<a class="s3-btn" href="${page(identifier)}">Open in its service page</a>` : ''}</div>
          <div class="s3-panel-sub">From <code>cloudcontrol.get_resource</code>, in the shape of the type's CloudFormation schema.</div>${pretty(r.properties)}</div>`;
    }
  },
  submits: { type: (f, data) => { const t = (data.get('type') || '').trim(); if (t) go('#/type/' + enc(t)); } }
});
