/* aws.twin.sgit.ai — the interface.
   One AWS-shaped interface, several backends behind it. Consuming code is written
   against `AwsTwin.client(backend, scope)` and never against a backend, which is the
   whole claim of the site: the same calls that run against the vault today run against
   the live account once a session is in front of it.

   The shape follows the AWS SDK for JavaScript v3: a client is bound to one account and
   one region (a session), every operation takes one params object with PascalCase keys
   and returns a Promise of one result object. Where AWS has no operation for something
   the twin must do (seed a cost, import a snapshot), it lives under `twin.*`, never
   under an AWS service name, so the boundary between "AWS-shaped" and "twin-only" stays
   visible in the call log.

   Runs in the browser and in Node (admin/build/test.js). No dependencies. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.AwsTwin = factory();
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function TwinError(code, message, meta) {
    var e = new Error(message);
    e.name = 'TwinError';
    e.code = code;
    e.meta = meta || {};
    return e;
  }

  /* The operations the interface exposes, with the param keys each accepts. The
     manifest is the contract: a backend is complete when it answers every row, and
     the UI and the tests are generated from it rather than typed twice. */
  var MANIFEST = {
    sts: {
      getCallerIdentity: []
    },
    s3: {
      listBuckets: [],
      createBucket: ['Bucket', 'Region'],
      deleteBucket: ['Bucket'],
      headBucket: ['Bucket'],
      listObjectsV2: ['Bucket', 'Prefix'],
      putObject: ['Bucket', 'Key', 'Body', 'ContentType'],
      getObject: ['Bucket', 'Key'],
      deleteObject: ['Bucket', 'Key']
    },
    lambda: {
      listFunctions: [],
      getFunction: ['FunctionName'],
      createFunction: ['FunctionName', 'Runtime', 'Role', 'Handler', 'MemorySize', 'Timeout', 'Environment', 'PackageType', 'ImageUri', 'Tags'],
      updateFunctionConfiguration: ['FunctionName', 'MemorySize', 'Timeout', 'Environment'],
      deleteFunction: ['FunctionName'],
      invoke: ['FunctionName', 'Payload']
    },
    ec2: {
      describeInstances: ['Filters'],
      runInstances: ['ImageId', 'InstanceType', 'SecurityGroupIds', 'IamInstanceProfile', 'Name', 'Tags'],
      startInstances: ['InstanceIds'],
      stopInstances: ['InstanceIds'],
      terminateInstances: ['InstanceIds'],
      describeSecurityGroups: [],
      createSecurityGroup: ['GroupName', 'Description'],
      authorizeSecurityGroupIngress: ['GroupId', 'IpProtocol', 'FromPort', 'ToPort', 'CidrIp']
    },
    iam: {
      listRoles: [],
      getRole: ['RoleName'],
      createRole: ['RoleName', 'AssumeRolePolicyDocument', 'Description', 'Tags'],
      deleteRole: ['RoleName'],
      listPolicies: [],
      createPolicy: ['PolicyName', 'PolicyDocument', 'Description'],
      attachRolePolicy: ['RoleName', 'PolicyArn'],
      detachRolePolicy: ['RoleName', 'PolicyArn'],
      listAttachedRolePolicies: ['RoleName']
    },
    logs: {
      describeLogGroups: ['logGroupNamePrefix'],
      createLogGroup: ['logGroupName'],
      deleteLogGroup: ['logGroupName'],
      putLogEvents: ['logGroupName', 'logEvents'],
      filterLogEvents: ['logGroupName', 'filterPattern', 'limit']
    },
    ce: {
      getCostAndUsage: ['TimePeriod', 'Granularity', 'GroupBy']
    },
    cloudformation: {
      listStacks: [],
      describeStacks: ['StackName'],
      createStack: ['StackName', 'TemplateName', 'Parameters'],
      deleteStack: ['StackName']
    },
    twin: {
      recordCost: ['Service', 'Amount', 'Date', 'Region'],
      snapshot: [],
      state: []
    }
  };

  /* Services that are global per account rather than per region. The client still
     carries a region for them; the backend ignores it where AWS would. */
  var GLOBAL = { iam: true, sts: true, ce: true, s3: true, twin: true };

  var callSeq = 0;

  /* Build a client: `client.s3.listBuckets({})` → backend.call(...). Every call is
     recorded through `onCall`, so a UI can show the traffic as it would go to AWS. */
  function client(backend, scope, onCall, opts) {
    if (!backend || typeof backend.call !== 'function') throw TwinError('NoBackend', 'a backend with call(service, op, params, scope) is required');
    scope = scope || {};
    opts = opts || {};
    if (!scope.accountId) throw TwinError('NoScope', 'a client is bound to one account: scope.accountId is required');
    if (!scope.region) throw TwinError('NoScope', 'a client is bound to one region: scope.region is required');
    var c = { scope: scope, backend: backend, manifest: MANIFEST, sync: !!opts.sync };
    Object.keys(MANIFEST).forEach(function (service) {
      c[service] = {};
      Object.keys(MANIFEST[service]).forEach(function (op) {
        c[service][op] = function (params) {
          params = params || {};
          var allowed = MANIFEST[service][op];
          var unknown = Object.keys(params).filter(function (k) { return allowed.indexOf(k) < 0; });
          var started = Date.now();
          var rec = { seq: ++callSeq, at: new Date(started).toISOString(), service: service, op: op, command: commandName(service, op), params: params, scope: scope, backend: backend.kind };
          var done = function (res) { rec.result = res; rec.ms = Date.now() - started; if (onCall) onCall(rec); return res; };
          var failed = function (err) { rec.error = { code: err.code || err.name, message: err.message, meta: err.meta }; rec.ms = Date.now() - started; if (onCall) onCall(rec); throw err; };
          /* sync mode: templates and seeds run inside a backend call and need the
             result now; the backends are synchronous underneath, so this is honest. */
          if (opts.sync) {
            try {
              if (unknown.length) throw TwinError('UnknownParam', service + '.' + op + ' does not accept ' + unknown.join(', '));
              return done(backend.call(service, op, params, scope));
            } catch (e) { return failed(e); }
          }
          var p;
          if (unknown.length) p = Promise.reject(TwinError('UnknownParam', service + '.' + op + ' does not accept ' + unknown.join(', ')));
          else { try { p = Promise.resolve(backend.call(service, op, params, scope)); } catch (e) { p = Promise.reject(e); } }
          return p.then(done, failed);
        };
      });
    });
    return c;
  }

  /* The SDK v3 command this call would be, for the live backend and the call log. */
  function commandName(service, op) {
    return op.charAt(0).toUpperCase() + op.slice(1) + 'Command';
  }

  /* An empty account state document. One per account, inside the vault. */
  function emptyAccount(accountId, name) {
    return {
      accountId: accountId,
      name: name || accountId,
      s3: { buckets: [], objects: {} },
      lambda: { functions: [] },
      ec2: { instances: [], securityGroups: [] },
      iam: { roles: [], policies: [], attachments: [] },
      logs: { groups: [], events: {} },
      ce: { records: [] },
      cloudformation: { stacks: [] },
      twin: { invocations: [] }
    };
  }

  function emptyState() {
    return { version: 1, accounts: {} };
  }

  /* --- identifiers, AWS-shaped enough to be recognisable, random enough to differ --- */
  var rnd = function (n) {
    var s = '';
    while (s.length < n) s += Math.random().toString(16).slice(2);
    return s.slice(0, n);
  };
  var ids = {
    instance: function () { return 'i-0' + rnd(16); },
    sg: function () { return 'sg-0' + rnd(16); },
    requestId: function () { return rnd(8) + '-' + rnd(4) + '-' + rnd(4) + '-' + rnd(4) + '-' + rnd(12); },
    stackId: function (accountId, region, name) { return 'arn:aws:cloudformation:' + region + ':' + accountId + ':stack/' + name + '/' + rnd(8) + '-' + rnd(4); },
    roleId: function () { return 'AROA' + rnd(17).toUpperCase(); },
    policyId: function () { return 'ANPA' + rnd(17).toUpperCase(); },
    etag: function () { return '"' + rnd(32) + '"'; }
  };
  var now = function () { return new Date().toISOString(); };

  function find(list, key, value) {
    for (var i = 0; i < list.length; i++) if (list[i][key] === value) return list[i];
    return null;
  }
  function remove(list, key, value) {
    for (var i = 0; i < list.length; i++) if (list[i][key] === value) return list.splice(i, 1)[0];
    return null;
  }
  function clone(x) { return JSON.parse(JSON.stringify(x)); }

  /* --- the operations, implemented over the state document ---
     Every op is (acct, scope, params) → result, mutating `acct` in place where AWS
     would. The backend owns persistence; the ops own semantics, so the vault and
     memory backends share one implementation and the equivalence test holds. */
  var OPS = {
    sts: {
      getCallerIdentity: function (acct, scope) {
        return { Account: acct.accountId, Arn: 'arn:aws:sts::' + acct.accountId + ':assumed-role/' + (scope.role || 'twin') + '/' + (scope.user || 'session'), UserId: ids.roleId() + ':' + (scope.user || 'session') };
      }
    },
    s3: {
      listBuckets: function (acct) {
        return { Buckets: acct.s3.buckets.map(function (b) { return { Name: b.Name, CreationDate: b.CreationDate, BucketRegion: b.Region }; }), Owner: { ID: acct.accountId } };
      },
      createBucket: function (acct, scope, p) {
        if (!p.Bucket) throw TwinError('InvalidBucketName', 'Bucket is required');
        if (!/^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$/.test(p.Bucket)) throw TwinError('InvalidBucketName', 'The specified bucket is not valid: ' + p.Bucket);
        if (find(acct.s3.buckets, 'Name', p.Bucket)) throw TwinError('BucketAlreadyOwnedByYou', 'Your previous request to create the named bucket succeeded and you already own it.');
        acct.s3.buckets.push({ Name: p.Bucket, Region: p.Region || scope.region, CreationDate: now() });
        acct.s3.objects[p.Bucket] = [];
        return { Location: '/' + p.Bucket };
      },
      deleteBucket: function (acct, scope, p) {
        var b = find(acct.s3.buckets, 'Name', p.Bucket);
        if (!b) throw TwinError('NoSuchBucket', 'The specified bucket does not exist');
        if ((acct.s3.objects[p.Bucket] || []).length) throw TwinError('BucketNotEmpty', 'The bucket you tried to delete is not empty');
        remove(acct.s3.buckets, 'Name', p.Bucket);
        delete acct.s3.objects[p.Bucket];
        return {};
      },
      headBucket: function (acct, scope, p) {
        var b = find(acct.s3.buckets, 'Name', p.Bucket);
        if (!b) throw TwinError('NotFound', 'Not Found');
        return { BucketRegion: b.Region };
      },
      listObjectsV2: function (acct, scope, p) {
        if (!find(acct.s3.buckets, 'Name', p.Bucket)) throw TwinError('NoSuchBucket', 'The specified bucket does not exist');
        var objs = (acct.s3.objects[p.Bucket] || []).filter(function (o) { return !p.Prefix || o.Key.indexOf(p.Prefix) === 0; });
        return { Name: p.Bucket, Prefix: p.Prefix || '', KeyCount: objs.length, Contents: objs.map(function (o) { return { Key: o.Key, Size: o.Size, LastModified: o.LastModified, ETag: o.ETag }; }) };
      },
      putObject: function (acct, scope, p) {
        if (!find(acct.s3.buckets, 'Name', p.Bucket)) throw TwinError('NoSuchBucket', 'The specified bucket does not exist');
        if (!p.Key) throw TwinError('InvalidArgument', 'Key is required');
        var body = p.Body === undefined ? '' : String(p.Body);
        var list = acct.s3.objects[p.Bucket] = acct.s3.objects[p.Bucket] || [];
        remove(list, 'Key', p.Key);
        var o = { Key: p.Key, Size: body.length, LastModified: now(), ETag: ids.etag(), ContentType: p.ContentType || 'application/octet-stream', Body: body };
        list.push(o);
        return { ETag: o.ETag };
      },
      getObject: function (acct, scope, p) {
        if (!find(acct.s3.buckets, 'Name', p.Bucket)) throw TwinError('NoSuchBucket', 'The specified bucket does not exist');
        var o = find(acct.s3.objects[p.Bucket] || [], 'Key', p.Key);
        if (!o) throw TwinError('NoSuchKey', 'The specified key does not exist.');
        return { Body: o.Body, ContentLength: o.Size, ContentType: o.ContentType, ETag: o.ETag, LastModified: o.LastModified };
      },
      deleteObject: function (acct, scope, p) {
        if (!find(acct.s3.buckets, 'Name', p.Bucket)) throw TwinError('NoSuchBucket', 'The specified bucket does not exist');
        remove(acct.s3.objects[p.Bucket] || [], 'Key', p.Key);
        return {};
      }
    },
    lambda: {
      listFunctions: function (acct, scope) {
        return { Functions: acct.lambda.functions.filter(function (f) { return f.Region === scope.region; }).map(publicFn) };
      },
      getFunction: function (acct, scope, p) {
        var f = fnIn(acct, scope, p.FunctionName);
        return { Configuration: publicFn(f), Tags: f.Tags || {} };
      },
      createFunction: function (acct, scope, p) {
        if (!p.FunctionName) throw TwinError('InvalidParameterValueException', 'FunctionName is required');
        if (!p.Role) throw TwinError('InvalidParameterValueException', 'The role defined for the function cannot be assumed by Lambda.');
        var role = acct.iam.roles.filter(function (r) { return r.Arn === p.Role; })[0];
        if (!role) throw TwinError('InvalidParameterValueException', 'The role defined for the function cannot be assumed by Lambda: ' + p.Role);
        if (acct.lambda.functions.some(function (f) { return f.FunctionName === p.FunctionName && f.Region === scope.region; })) throw TwinError('ResourceConflictException', 'Function already exist: ' + p.FunctionName);
        var f = {
          FunctionName: p.FunctionName, Region: scope.region,
          FunctionArn: 'arn:aws:lambda:' + scope.region + ':' + acct.accountId + ':function:' + p.FunctionName,
          Runtime: p.PackageType === 'Image' ? undefined : (p.Runtime || 'python3.12'),
          PackageType: p.PackageType || 'Zip', ImageUri: p.ImageUri,
          Role: p.Role, Handler: p.Handler || 'handler.run',
          MemorySize: p.MemorySize || 128, Timeout: p.Timeout || 3,
          Environment: p.Environment || { Variables: {} }, Tags: p.Tags || {},
          State: 'Active', Version: '$LATEST', LastModified: now(), CodeSize: 0
        };
        acct.lambda.functions.push(f);
        var lg = '/aws/lambda/' + p.FunctionName;
        if (!acct.logs.groups.some(function (g) { return g.logGroupName === lg && g.Region === scope.region; })) {
          acct.logs.groups.push({ logGroupName: lg, Region: scope.region, creationTime: Date.now(), storedBytes: 0, arn: 'arn:aws:logs:' + scope.region + ':' + acct.accountId + ':log-group:' + lg });
        }
        return publicFn(f);
      },
      updateFunctionConfiguration: function (acct, scope, p) {
        var f = fnIn(acct, scope, p.FunctionName);
        if (p.MemorySize) f.MemorySize = p.MemorySize;
        if (p.Timeout) f.Timeout = p.Timeout;
        if (p.Environment) f.Environment = p.Environment;
        f.LastModified = now();
        return publicFn(f);
      },
      deleteFunction: function (acct, scope, p) {
        var f = fnIn(acct, scope, p.FunctionName);
        acct.lambda.functions.splice(acct.lambda.functions.indexOf(f), 1);
        return {};
      },
      invoke: function (acct, scope, p) {
        var f = fnIn(acct, scope, p.FunctionName);
        var reqId = ids.requestId();
        var started = Date.now();
        var payload = p.Payload === undefined ? {} : p.Payload;
        var lg = '/aws/lambda/' + f.FunctionName;
        var ms = 1 + Math.floor(Math.random() * 40);
        var line = function (m) { return { timestamp: started, message: m, ingestionTime: started }; };
        appendEvents(acct, scope, lg, [
          line('START RequestId: ' + reqId + ' Version: $LATEST'),
          line('[twin] ' + f.Handler + ' received ' + JSON.stringify(payload)),
          line('END RequestId: ' + reqId),
          line('REPORT RequestId: ' + reqId + '\tDuration: ' + ms + '.00 ms\tBilled Duration: ' + ms + ' ms\tMemory Size: ' + f.MemorySize + ' MB\tMax Memory Used: ' + Math.min(f.MemorySize, 40 + ms) + ' MB')
        ]);
        acct.twin.invocations.push({ FunctionName: f.FunctionName, Region: scope.region, RequestId: reqId, At: now(), DurationMs: ms });
        return { StatusCode: 200, ExecutedVersion: '$LATEST', Payload: { twin: true, echo: payload, requestId: reqId } };
      }
    },
    ec2: {
      describeInstances: function (acct, scope, p) {
        var list = acct.ec2.instances.filter(function (i) { return i.Region === scope.region; });
        (p.Filters || []).forEach(function (f) {
          if (f.Name === 'instance-state-name') list = list.filter(function (i) { return f.Values.indexOf(i.State.Name) >= 0; });
          if (f.Name === 'tag:Name') list = list.filter(function (i) { return f.Values.indexOf(tagOf(i, 'Name')) >= 0; });
        });
        return { Reservations: [{ Instances: list.map(clone) }] };
      },
      runInstances: function (acct, scope, p) {
        if (!p.ImageId) throw TwinError('MissingParameter', 'The request must contain the parameter ImageId');
        (p.SecurityGroupIds || []).forEach(function (id) { if (!acct.ec2.securityGroups.some(function (g) { return g.GroupId === id && g.Region === scope.region; })) throw TwinError('InvalidGroup.NotFound', "The security group '" + id + "' does not exist in " + scope.region); });
        if (p.IamInstanceProfile && !find(acct.iam.roles, 'RoleName', p.IamInstanceProfile)) throw TwinError('InvalidParameterValue', 'Invalid IAM Instance Profile name: ' + p.IamInstanceProfile);
        var tags = p.Tags ? clone(p.Tags) : [];
        if (p.Name && !tagOf({ Tags: tags }, 'Name')) tags.push({ Key: 'Name', Value: p.Name });
        var i = {
          InstanceId: ids.instance(), Region: scope.region, ImageId: p.ImageId, InstanceType: p.InstanceType || 't3.micro',
          State: { Code: 16, Name: 'running' }, LaunchTime: now(),
          SecurityGroups: (p.SecurityGroupIds || []).map(function (id) { var g = find(acct.ec2.securityGroups, 'GroupId', id); return { GroupId: id, GroupName: g.GroupName }; }),
          IamInstanceProfile: p.IamInstanceProfile ? { Arn: 'arn:aws:iam::' + acct.accountId + ':instance-profile/' + p.IamInstanceProfile, Name: p.IamInstanceProfile } : undefined,
          Tags: tags, Placement: { AvailabilityZone: scope.region + 'a' }
        };
        acct.ec2.instances.push(i);
        return { Instances: [clone(i)], ReservationId: 'r-0' + rnd(16) };
      },
      startInstances: function (acct, scope, p) { return transition(acct, scope, p.InstanceIds, 'running', 16, 'StartingInstances'); },
      stopInstances: function (acct, scope, p) { return transition(acct, scope, p.InstanceIds, 'stopped', 80, 'StoppingInstances'); },
      terminateInstances: function (acct, scope, p) { return transition(acct, scope, p.InstanceIds, 'terminated', 48, 'TerminatingInstances'); },
      describeSecurityGroups: function (acct, scope) {
        return { SecurityGroups: acct.ec2.securityGroups.filter(function (g) { return g.Region === scope.region; }).map(clone) };
      },
      createSecurityGroup: function (acct, scope, p) {
        if (!p.GroupName) throw TwinError('MissingParameter', 'The request must contain the parameter GroupName');
        if (acct.ec2.securityGroups.some(function (g) { return g.GroupName === p.GroupName && g.Region === scope.region; })) throw TwinError('InvalidGroup.Duplicate', "The security group '" + p.GroupName + "' already exists");
        var g = { GroupId: ids.sg(), GroupName: p.GroupName, Description: p.Description || '', Region: scope.region, IpPermissions: [], OwnerId: acct.accountId };
        acct.ec2.securityGroups.push(g);
        return { GroupId: g.GroupId };
      },
      authorizeSecurityGroupIngress: function (acct, scope, p) {
        var g = find(acct.ec2.securityGroups, 'GroupId', p.GroupId);
        if (!g || g.Region !== scope.region) throw TwinError('InvalidGroup.NotFound', "The security group '" + p.GroupId + "' does not exist");
        g.IpPermissions.push({ IpProtocol: p.IpProtocol || 'tcp', FromPort: p.FromPort, ToPort: p.ToPort, IpRanges: [{ CidrIp: p.CidrIp || '0.0.0.0/0' }] });
        return { Return: true };
      }
    },
    iam: {
      listRoles: function (acct) { return { Roles: acct.iam.roles.map(publicRole) }; },
      getRole: function (acct, scope, p) {
        var r = find(acct.iam.roles, 'RoleName', p.RoleName);
        if (!r) throw TwinError('NoSuchEntity', 'The role with name ' + p.RoleName + ' cannot be found.');
        return { Role: publicRole(r) };
      },
      createRole: function (acct, scope, p) {
        if (!p.RoleName) throw TwinError('ValidationError', 'RoleName is required');
        if (find(acct.iam.roles, 'RoleName', p.RoleName)) throw TwinError('EntityAlreadyExists', 'Role with name ' + p.RoleName + ' already exists.');
        var r = { RoleName: p.RoleName, RoleId: ids.roleId(), Arn: 'arn:aws:iam::' + acct.accountId + ':role/' + p.RoleName, Path: '/', CreateDate: now(), Description: p.Description || '', AssumeRolePolicyDocument: p.AssumeRolePolicyDocument || { Version: '2012-10-17', Statement: [] }, Tags: p.Tags || [] };
        acct.iam.roles.push(r);
        return { Role: publicRole(r) };
      },
      deleteRole: function (acct, scope, p) {
        var r = find(acct.iam.roles, 'RoleName', p.RoleName);
        if (!r) throw TwinError('NoSuchEntity', 'The role with name ' + p.RoleName + ' cannot be found.');
        if (acct.iam.attachments.some(function (a) { return a.RoleName === p.RoleName; })) throw TwinError('DeleteConflict', 'Cannot delete entity, must detach all policies first.');
        if (acct.lambda.functions.some(function (f) { return f.Role === r.Arn; })) throw TwinError('DeleteConflict', 'Cannot delete entity, it is in use by a Lambda function.');
        remove(acct.iam.roles, 'RoleName', p.RoleName);
        return {};
      },
      listPolicies: function (acct) { return { Policies: acct.iam.policies.map(publicPolicy) }; },
      createPolicy: function (acct, scope, p) {
        if (!p.PolicyName) throw TwinError('ValidationError', 'PolicyName is required');
        if (find(acct.iam.policies, 'PolicyName', p.PolicyName)) throw TwinError('EntityAlreadyExists', 'A policy called ' + p.PolicyName + ' already exists.');
        var pol = { PolicyName: p.PolicyName, PolicyId: ids.policyId(), Arn: 'arn:aws:iam::' + acct.accountId + ':policy/' + p.PolicyName, Path: '/', CreateDate: now(), Description: p.Description || '', PolicyDocument: p.PolicyDocument || { Version: '2012-10-17', Statement: [] }, AttachmentCount: 0 };
        acct.iam.policies.push(pol);
        return { Policy: publicPolicy(pol) };
      },
      attachRolePolicy: function (acct, scope, p) {
        var r = find(acct.iam.roles, 'RoleName', p.RoleName);
        if (!r) throw TwinError('NoSuchEntity', 'The role with name ' + p.RoleName + ' cannot be found.');
        var pol = find(acct.iam.policies, 'Arn', p.PolicyArn);
        if (!pol && !/^arn:aws:iam::aws:policy\//.test(p.PolicyArn || '')) throw TwinError('NoSuchEntity', 'Policy ' + p.PolicyArn + ' does not exist or is not attachable.');
        if (!acct.iam.attachments.some(function (a) { return a.RoleName === p.RoleName && a.PolicyArn === p.PolicyArn; })) {
          acct.iam.attachments.push({ RoleName: p.RoleName, PolicyArn: p.PolicyArn });
          if (pol) pol.AttachmentCount++;
        }
        return {};
      },
      detachRolePolicy: function (acct, scope, p) {
        var before = acct.iam.attachments.length;
        acct.iam.attachments = acct.iam.attachments.filter(function (a) { return !(a.RoleName === p.RoleName && a.PolicyArn === p.PolicyArn); });
        if (before === acct.iam.attachments.length) throw TwinError('NoSuchEntity', 'Policy ' + p.PolicyArn + ' was not found attached to role ' + p.RoleName);
        var pol = find(acct.iam.policies, 'Arn', p.PolicyArn);
        if (pol) pol.AttachmentCount--;
        return {};
      },
      listAttachedRolePolicies: function (acct, scope, p) {
        if (!find(acct.iam.roles, 'RoleName', p.RoleName)) throw TwinError('NoSuchEntity', 'The role with name ' + p.RoleName + ' cannot be found.');
        return { AttachedPolicies: acct.iam.attachments.filter(function (a) { return a.RoleName === p.RoleName; }).map(function (a) { return { PolicyArn: a.PolicyArn, PolicyName: a.PolicyArn.split('/').pop() }; }) };
      }
    },
    logs: {
      describeLogGroups: function (acct, scope, p) {
        return { logGroups: acct.logs.groups.filter(function (g) { return g.Region === scope.region && (!p.logGroupNamePrefix || g.logGroupName.indexOf(p.logGroupNamePrefix) === 0); }).map(clone) };
      },
      createLogGroup: function (acct, scope, p) {
        if (!p.logGroupName) throw TwinError('InvalidParameterException', 'logGroupName is required');
        if (acct.logs.groups.some(function (g) { return g.logGroupName === p.logGroupName && g.Region === scope.region; })) throw TwinError('ResourceAlreadyExistsException', 'The specified log group already exists');
        acct.logs.groups.push({ logGroupName: p.logGroupName, Region: scope.region, creationTime: Date.now(), storedBytes: 0, arn: 'arn:aws:logs:' + scope.region + ':' + acct.accountId + ':log-group:' + p.logGroupName });
        return {};
      },
      deleteLogGroup: function (acct, scope, p) {
        var g = groupIn(acct, scope, p.logGroupName);
        acct.logs.groups.splice(acct.logs.groups.indexOf(g), 1);
        delete acct.logs.events[scope.region + '|' + p.logGroupName];
        return {};
      },
      putLogEvents: function (acct, scope, p) {
        groupIn(acct, scope, p.logGroupName);
        appendEvents(acct, scope, p.logGroupName, (p.logEvents || []).map(function (e) { return { timestamp: e.timestamp || Date.now(), message: String(e.message), ingestionTime: Date.now() }; }));
        return { nextSequenceToken: rnd(24) };
      },
      filterLogEvents: function (acct, scope, p) {
        groupIn(acct, scope, p.logGroupName);
        var ev = (acct.logs.events[scope.region + '|' + p.logGroupName] || []).filter(function (e) { return !p.filterPattern || e.message.indexOf(p.filterPattern) >= 0; });
        if (p.limit) ev = ev.slice(-p.limit);
        return { events: ev.map(clone) };
      }
    },
    ce: {
      getCostAndUsage: function (acct, scope, p) {
        var tp = p.TimePeriod || {};
        var rows = acct.ce.records.filter(function (r) { return (!tp.Start || r.Date >= tp.Start) && (!tp.End || r.Date < tp.End); });
        var gran = p.Granularity || 'MONTHLY';
        var groupKey = (p.GroupBy && p.GroupBy[0] && p.GroupBy[0].Key) || 'SERVICE';
        var buckets = {};
        rows.forEach(function (r) {
          var period = gran === 'DAILY' ? r.Date : r.Date.slice(0, 7) + '-01';
          var key = groupKey === 'REGION' ? (r.Region || 'global') : r.Service;
          var b = buckets[period] = buckets[period] || {};
          b[key] = (b[key] || 0) + r.Amount;
        });
        return {
          GroupDefinitions: [{ Type: 'DIMENSION', Key: groupKey }],
          ResultsByTime: Object.keys(buckets).sort().map(function (period) {
            return { TimePeriod: { Start: period }, Groups: Object.keys(buckets[period]).sort().map(function (k) { return { Keys: [k], Metrics: { UnblendedCost: { Amount: buckets[period][k].toFixed(2), Unit: 'USD' } } }; }) };
          })
        };
      }
    },
    cloudformation: {
      listStacks: function (acct, scope) {
        return { StackSummaries: acct.cloudformation.stacks.filter(function (s) { return s.Region === scope.region; }).map(function (s) { return { StackName: s.StackName, StackId: s.StackId, StackStatus: s.StackStatus, CreationTime: s.CreationTime, TemplateDescription: s.TemplateName }; }) };
      },
      describeStacks: function (acct, scope, p) {
        var list = acct.cloudformation.stacks.filter(function (s) { return s.Region === scope.region && (!p.StackName || s.StackName === p.StackName); });
        if (p.StackName && !list.length) throw TwinError('ValidationError', 'Stack with id ' + p.StackName + ' does not exist');
        return { Stacks: list.map(clone) };
      },
      createStack: function (acct, scope, p, backend) {
        if (!p.StackName) throw TwinError('ValidationError', 'StackName is required');
        var tpl = backend.templates && backend.templates[p.TemplateName];
        if (!tpl) throw TwinError('ValidationError', 'Template not found: ' + p.TemplateName + ' (known: ' + Object.keys(backend.templates || {}).join(', ') + ')');
        if (acct.cloudformation.stacks.some(function (s) { return s.StackName === p.StackName && s.Region === scope.region; })) throw TwinError('AlreadyExistsException', 'Stack [' + p.StackName + '] already exists');
        var params = {};
        (p.Parameters || []).forEach(function (kv) { params[kv.ParameterKey] = kv.ParameterValue; });
        /* The template runs against the interface itself, so a deployment is nothing
           but a sequence of ordinary calls, recorded like any other. */
        var inner = client(backend, scope, null, { sync: true });
        var created = tpl.apply(inner, acct, params, p.StackName);
        var stack = { StackName: p.StackName, StackId: ids.stackId(acct.accountId, scope.region, p.StackName), Region: scope.region, TemplateName: p.TemplateName, Parameters: p.Parameters || [], StackStatus: 'CREATE_COMPLETE', CreationTime: now(), Outputs: created.outputs || [], Resources: created.resources || [] };
        acct.cloudformation.stacks.push(stack);
        return { StackId: stack.StackId };
      },
      deleteStack: function (acct, scope, p, backend) {
        var s = acct.cloudformation.stacks.filter(function (x) { return x.StackName === p.StackName && x.Region === scope.region; })[0];
        if (!s) throw TwinError('ValidationError', 'Stack with id ' + p.StackName + ' does not exist');
        var tpl = backend.templates && backend.templates[s.TemplateName];
        if (tpl && tpl.remove) tpl.remove(client(backend, scope, null, { sync: true }), acct, s);
        acct.cloudformation.stacks.splice(acct.cloudformation.stacks.indexOf(s), 1);
        return {};
      }
    },
    twin: {
      recordCost: function (acct, scope, p) {
        if (!p.Service || typeof p.Amount !== 'number') throw TwinError('ValidationError', 'Service and a numeric Amount are required');
        acct.ce.records.push({ Service: p.Service, Amount: p.Amount, Date: p.Date || now().slice(0, 10), Region: p.Region || scope.region });
        return {};
      },
      snapshot: function (acct) { return clone(acct); },
      state: function (acct) { return clone(acct); }
    }
  };

  /* --- helpers the ops share --- */
  function publicFn(f) { var c = clone(f); delete c.Region; return c; }
  function publicRole(r) { var c = clone(r); return c; }
  function publicPolicy(p) { var c = clone(p); return c; }
  function fnIn(acct, scope, name) {
    var f = acct.lambda.functions.filter(function (x) { return x.FunctionName === name && x.Region === scope.region; })[0];
    if (!f) throw TwinError('ResourceNotFoundException', 'Function not found: arn:aws:lambda:' + scope.region + ':' + acct.accountId + ':function:' + name);
    return f;
  }
  function groupIn(acct, scope, name) {
    var g = acct.logs.groups.filter(function (x) { return x.logGroupName === name && x.Region === scope.region; })[0];
    if (!g) throw TwinError('ResourceNotFoundException', 'The specified log group does not exist.');
    return g;
  }
  function appendEvents(acct, scope, group, events) {
    var k = scope.region + '|' + group;
    var list = acct.logs.events[k] = acct.logs.events[k] || [];
    events.forEach(function (e) { list.push(e); });
    var g = acct.logs.groups.filter(function (x) { return x.logGroupName === group && x.Region === scope.region; })[0];
    if (g) g.storedBytes += events.reduce(function (n, e) { return n + e.message.length; }, 0);
  }
  function tagOf(x, key) {
    var t = (x.Tags || []).filter(function (t) { return t.Key === key; })[0];
    return t ? t.Value : undefined;
  }
  function transition(acct, scope, idsList, name, code, field) {
    var out = {};
    out[field] = (idsList || []).map(function (id) {
      var i = find(acct.ec2.instances, 'InstanceId', id);
      if (!i || i.Region !== scope.region) throw TwinError('InvalidInstanceID.NotFound', "The instance ID '" + id + "' does not exist");
      var prev = i.State;
      i.State = { Code: code, Name: name };
      return { InstanceId: id, PreviousState: prev, CurrentState: i.State };
    });
    return out;
  }

  /* --- StateBackend: the ops over a state document; subclasses decide persistence --- */
  function StateBackend(kind) {
    this.kind = kind || 'state';
    this.state = emptyState();
    this.templates = {};
  }
  StateBackend.prototype.ensureAccount = function (accountId, name) {
    if (!this.state.accounts[accountId]) this.state.accounts[accountId] = emptyAccount(accountId, name);
    else if (name) this.state.accounts[accountId].name = name;
    this.save();
    return this.state.accounts[accountId];
  };
  StateBackend.prototype.accounts = function () {
    var s = this.state.accounts;
    return Object.keys(s).map(function (k) { return { accountId: k, name: s[k].name }; });
  };
  StateBackend.prototype.call = function (service, op, params, scope) {
    var svc = OPS[service];
    if (!svc || !svc[op]) throw TwinError('UnsupportedOperation', service + '.' + op + ' is not implemented by the ' + this.kind + ' backend');
    var acct = this.state.accounts[scope.accountId];
    if (!acct) throw TwinError('UnrecognizedClientException', 'The security token included in the request is invalid (no such account in this vault: ' + scope.accountId + ')');
    var result = svc[op](acct, scope, params, this);
    this.save();
    return clone(result === undefined ? {} : result);
  };
  StateBackend.prototype.importState = function (state) {
    if (!state || state.version !== 1 || typeof state.accounts !== 'object') throw TwinError('BadState', 'not a version-1 twin state document');
    this.state = clone(state);
    this.save();
  };
  StateBackend.prototype.exportState = function () { return clone(this.state); };
  StateBackend.prototype.registerTemplate = function (name, tpl) { this.templates[name] = tpl; };
  StateBackend.prototype.save = function () {};

  /* The memory backend: the same ops, nothing persisted. A test double and the
     third backend in the S3 container's list (real S3, vault, memory). */
  function MemoryBackend() { StateBackend.call(this, 'memory'); }
  MemoryBackend.prototype = Object.create(StateBackend.prototype);
  MemoryBackend.prototype.constructor = MemoryBackend;

  /* The live backend: the same interface, answered by AWS through the SDK for
     JavaScript v3 once a session is in front of it. In this PoC the slot is real and
     the wire is not: every call reports the exact command it would send and refuses,
     so the consuming code can be run against it and the gap measured. */
  function LiveBackend(sessionStore) {
    this.kind = 'live';
    this.sessionStore = sessionStore || null;
    this.templates = {};
  }
  LiveBackend.prototype.session = function () { return this.sessionStore ? this.sessionStore.get() : null; };
  LiveBackend.prototype.call = function (service, op, params, scope) {
    var s = this.session();
    var cmd = commandName(service, op);
    if (!MANIFEST[service] || !MANIFEST[service][op]) throw TwinError('UnsupportedOperation', service + '.' + op + ' is not in the interface');
    if (service === 'twin') throw TwinError('TwinOnly', 'twin.' + op + ' has no AWS counterpart; it is answered by the vault, never by the live backend');
    if (!s) throw TwinError('NoSession', 'no session in the vault: paste one from the AWS access portal first (would send ' + cmd + ')', { command: cmd });
    if (s.expiresAt && Date.parse(s.expiresAt) < Date.now()) throw TwinError('ExpiredToken', 'the session in the vault expired at ' + s.expiresAt + '; sign in to the access portal again (would send ' + cmd + ')', { command: cmd });
    throw TwinError('NotWired', 'live backend not wired in this PoC: would send ' + cmd + ' to ' + service + '.' + scope.region + '.amazonaws.com for account ' + scope.accountId + ' with the session that expires at ' + (s.expiresAt || 'unknown'), { command: cmd, service: service, region: scope.region, params: params });
  };
  LiveBackend.prototype.accounts = function () {
    var s = this.session();
    return s && s.accountId ? [{ accountId: s.accountId, name: s.accountName || s.accountId }] : [];
  };

  /* Snapshot diff: what changed between two account states, resource by resource. */
  function resourcesOf(acct) {
    var out = {};
    var put = function (kind, id, body) { out[kind + ' ' + id] = body; };
    acct.s3.buckets.forEach(function (b) { put('s3:bucket', b.Name, { Region: b.Region, objects: (acct.s3.objects[b.Name] || []).length }); });
    Object.keys(acct.s3.objects).forEach(function (bk) { acct.s3.objects[bk].forEach(function (o) { put('s3:object', bk + '/' + o.Key, { Size: o.Size, ETag: o.ETag }); }); });
    acct.lambda.functions.forEach(function (f) { put('lambda:function', f.Region + '/' + f.FunctionName, { Runtime: f.Runtime, PackageType: f.PackageType, ImageUri: f.ImageUri, Role: f.Role, MemorySize: f.MemorySize, Timeout: f.Timeout, Environment: f.Environment }); });
    acct.ec2.instances.forEach(function (i) { put('ec2:instance', i.Region + '/' + i.InstanceId, { InstanceType: i.InstanceType, State: i.State.Name, SecurityGroups: i.SecurityGroups.map(function (g) { return g.GroupId; }), Name: tagOf(i, 'Name') }); });
    acct.ec2.securityGroups.forEach(function (g) { put('ec2:security-group', g.Region + '/' + g.GroupId, { GroupName: g.GroupName, rules: g.IpPermissions.length }); });
    acct.iam.roles.forEach(function (r) { put('iam:role', r.RoleName, { attached: acct.iam.attachments.filter(function (a) { return a.RoleName === r.RoleName; }).map(function (a) { return a.PolicyArn; }).sort() }); });
    acct.iam.policies.forEach(function (p) { put('iam:policy', p.PolicyName, { PolicyDocument: p.PolicyDocument }); });
    acct.logs.groups.forEach(function (g) { put('logs:group', g.Region + '/' + g.logGroupName, { storedBytes: g.storedBytes }); });
    acct.cloudformation.stacks.forEach(function (s) { put('cloudformation:stack', s.Region + '/' + s.StackName, { TemplateName: s.TemplateName, StackStatus: s.StackStatus, Parameters: s.Parameters }); });
    var cost = acct.ce.records.reduce(function (n, r) { return n + r.Amount; }, 0);
    if (acct.ce.records.length) put('ce:total', 'all', { Amount: Math.round(cost * 100) / 100, records: acct.ce.records.length });
    return out;
  }
  function diffAccounts(a, b) {
    var ra = resourcesOf(a), rb = resourcesOf(b), out = { added: [], removed: [], changed: [], unchanged: 0 };
    Object.keys(rb).forEach(function (k) {
      if (!(k in ra)) out.added.push({ key: k, after: rb[k] });
      else if (JSON.stringify(ra[k]) !== JSON.stringify(rb[k])) out.changed.push({ key: k, before: ra[k], after: rb[k] });
      else out.unchanged++;
    });
    Object.keys(ra).forEach(function (k) { if (!(k in rb)) out.removed.push({ key: k, before: ra[k] }); });
    return out;
  }
  function diffStates(a, b) {
    var out = {};
    var ids = {};
    Object.keys(a.accounts).concat(Object.keys(b.accounts)).forEach(function (k) { ids[k] = true; });
    Object.keys(ids).sort().forEach(function (id) {
      out[id] = diffAccounts(a.accounts[id] || emptyAccount(id), b.accounts[id] || emptyAccount(id));
    });
    return out;
  }

  /* The account graph: resources as nodes, relationships as edges. */
  function graphOf(acct) {
    var nodes = [], edges = [], seen = {};
    var node = function (id, kind, label, region) { if (seen[id]) return id; seen[id] = true; nodes.push({ id: id, kind: kind, label: label, region: region }); return id; };
    var edge = function (from, to, rel) { edges.push({ from: from, to: to, rel: rel }); };
    acct.iam.policies.forEach(function (p) { node(p.Arn, 'policy', p.PolicyName); });
    acct.iam.roles.forEach(function (r) { node(r.Arn, 'role', r.RoleName); });
    acct.iam.attachments.forEach(function (a) {
      var r = find(acct.iam.roles, 'RoleName', a.RoleName);
      if (!r) return;
      node(a.PolicyArn, 'policy', a.PolicyArn.split('/').pop());
      edge(r.Arn, a.PolicyArn, 'attached_policy');
    });
    acct.s3.buckets.forEach(function (b) { node('arn:aws:s3:::' + b.Name, 'bucket', b.Name, b.Region); });
    acct.logs.groups.forEach(function (g) { node(g.arn, 'log-group', g.logGroupName, g.Region); });
    acct.lambda.functions.forEach(function (f) {
      node(f.FunctionArn, 'function', f.FunctionName, f.Region);
      edge(f.FunctionArn, f.Role, 'assumes_role');
      var lg = acct.logs.groups.filter(function (g) { return g.logGroupName === '/aws/lambda/' + f.FunctionName && g.Region === f.Region; })[0];
      if (lg) edge(f.FunctionArn, lg.arn, 'writes_logs');
      var vars = (f.Environment && f.Environment.Variables) || {};
      Object.keys(vars).forEach(function (k) {
        var b = find(acct.s3.buckets, 'Name', vars[k]);
        if (b) edge(f.FunctionArn, 'arn:aws:s3:::' + b.Name, 'uses_bucket');
      });
    });
    acct.ec2.securityGroups.forEach(function (g) { node(g.GroupId, 'security-group', g.GroupName, g.Region); });
    acct.ec2.instances.forEach(function (i) {
      if (i.State.Name === 'terminated') return;
      node(i.InstanceId, 'instance', tagOf(i, 'Name') || i.InstanceId, i.Region);
      i.SecurityGroups.forEach(function (g) { edge(i.InstanceId, g.GroupId, 'in_security_group'); });
      if (i.IamInstanceProfile) { var r = find(acct.iam.roles, 'RoleName', i.IamInstanceProfile.Name); if (r) edge(i.InstanceId, r.Arn, 'instance_profile'); }
    });
    acct.cloudformation.stacks.forEach(function (s) {
      node(s.StackId, 'stack', s.StackName, s.Region);
      (s.Resources || []).forEach(function (r) { if (seen[r]) edge(s.StackId, r, 'created'); });
    });
    return { nodes: nodes, edges: edges };
  }
  function graphToMermaid(g) {
    var lines = ['flowchart LR'];
    var safe = function (id) { return 'n' + Math.abs(hash32(id)).toString(36); };
    g.nodes.forEach(function (n) { lines.push('  ' + safe(n.id) + '["' + n.kind + ': ' + n.label.replace(/"/g, "'") + '"]'); });
    g.edges.forEach(function (e) { lines.push('  ' + safe(e.from) + ' -->|' + e.rel + '| ' + safe(e.to)); });
    return lines.join('\n');
  }

  /* A small content hash for commit ids. Not cryptographic: the vault's own commits
     carry the real hashes once this state is pushed through sgit. */
  function hash32(s) {
    var h = 0x811c9dc5;
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193); }
    return h | 0;
  }
  function contentId(obj) {
    var s = JSON.stringify(obj);
    var a = (hash32(s) >>> 0).toString(16), b = (hash32(s + '|' + s.length) >>> 0).toString(16);
    return ('00000000' + a).slice(-8) + ('00000000' + b).slice(-8);
  }

  return {
    MANIFEST: MANIFEST,
    GLOBAL: GLOBAL,
    OPS: OPS,
    TwinError: TwinError,
    client: client,
    commandName: commandName,
    emptyAccount: emptyAccount,
    emptyState: emptyState,
    StateBackend: StateBackend,
    MemoryBackend: MemoryBackend,
    LiveBackend: LiveBackend,
    resourcesOf: resourcesOf,
    diffAccounts: diffAccounts,
    diffStates: diffStates,
    graphOf: graphOf,
    graphToMermaid: graphToMermaid,
    contentId: contentId,
    clone: clone
  };
}));
