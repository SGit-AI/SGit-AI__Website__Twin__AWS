/* aws.twin.sgit.ai — the deployment templates, and the demo estate.

   A template here is a function over the interface: it makes ordinary calls against
   the client it is given, so a deployment rehearsed against the vault is the same
   sequence of calls as one run live. Two templates stand in for the SG/Send server
   components the article names as the first job: Lambda as a container image with a
   function URL, and ECS Fargate. The twin's state document does not yet hold ECS, so
   the Fargate template records that gap on its stack rather than pretending.

   The demo estate seeds two illustrative accounts so the twin has something to show
   before any live data arrives. The account ids are not real. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./interface.js'));
  else root.AwsTwinTemplates = factory(root.AwsTwin);
}(typeof self !== 'undefined' ? self : this, function (AwsTwin) {
  'use strict';

  var VERSION = 'v0.1.0';

  function has(list, key, value) { return list.some(function (x) { return x[key] === value; }); }
  function rnd(n) { var s = ''; while (s.length < n) s += Math.random().toString(36).slice(2); return s.slice(0, n); }

  /* Shared pieces: the role, the per-account-per-region bucket, the policy. */
  function ensureRole(c, acct, roleName, service) {
    if (!has(acct.iam.roles, 'RoleName', roleName)) {
      c.iam.createRole({ RoleName: roleName, Description: 'SG/Send server component role (' + service + ')', AssumeRolePolicyDocument: { Version: '2012-10-17', Statement: [{ Effect: 'Allow', Principal: { Service: service + '.amazonaws.com' }, Action: 'sts:AssumeRole' }] } });
    }
    return 'arn:aws:iam::' + acct.accountId + ':role/' + roleName;
  }
  function ensureBucket(c, acct, region) {
    var name = 'sg-send-' + acct.accountId + '-' + region;
    if (!has(acct.s3.buckets, 'Name', name)) c.s3.createBucket({ Bucket: name, Region: region });
    return name;
  }
  function ensureBucketPolicy(c, acct, roleName, bucket) {
    var policyName = 'sg-send-vault-store-' + bucket;
    var arn = 'arn:aws:iam::' + acct.accountId + ':policy/' + policyName;
    if (!has(acct.iam.policies, 'PolicyName', policyName)) {
      c.iam.createPolicy({ PolicyName: policyName, Description: 'Read and write the vault store bucket ' + bucket, PolicyDocument: { Version: '2012-10-17', Statement: [{ Effect: 'Allow', Action: ['s3:GetObject', 's3:PutObject', 's3:DeleteObject', 's3:ListBucket'], Resource: ['arn:aws:s3:::' + bucket, 'arn:aws:s3:::' + bucket + '/*'] }] } });
    }
    if (!acct.iam.attachments.some(function (a) { return a.RoleName === roleName && a.PolicyArn === arn; })) c.iam.attachRolePolicy({ RoleName: roleName, PolicyArn: arn });
    return arn;
  }

  var TEMPLATES = {
    'sg-send-lambda-url': {
      description: 'SG/Send API as a Lambda container image with a function URL, S3 storage mode, one bucket per account and region.',
      parameters: [
        { key: 'ImageTag', label: 'Container image tag', default: 'v0.9.0' },
        { key: 'MemorySize', label: 'Memory (MB)', default: '1024' }
      ],
      apply: function (c, acct, params, stackName) {
        var region = c.scope.region;
        var roleName = 'sg-send-lambda-role';
        var roleArn = ensureRole(c, acct, roleName, 'lambda');
        var bucket = ensureBucket(c, acct, region);
        var policyArn = ensureBucketPolicy(c, acct, roleName, bucket);
        var fnName = stackName + '-api';
        c.lambda.createFunction({
          FunctionName: fnName, PackageType: 'Image', Role: roleArn,
          ImageUri: acct.accountId + '.dkr.ecr.' + region + '.amazonaws.com/sg-send-api:' + (params.ImageTag || 'v0.9.0'),
          MemorySize: parseInt(params.MemorySize || '1024', 10), Timeout: 30,
          Environment: { Variables: { SG_SEND_STORAGE: 's3', SG_SEND_BUCKET: bucket, SG_SEND_VERSION: params.ImageTag || 'v0.9.0' } },
          Tags: { 'sg-send:stack': stackName, 'sg-send:template': 'sg-send-lambda-url' }
        });
        var fnArn = 'arn:aws:lambda:' + region + ':' + acct.accountId + ':function:' + fnName;
        var lgArn = 'arn:aws:logs:' + region + ':' + acct.accountId + ':log-group:/aws/lambda/' + fnName;
        return {
          outputs: [
            { OutputKey: 'FunctionUrl', OutputValue: 'https://' + rnd(32) + '.lambda-url.' + region + '.on.aws/' },
            { OutputKey: 'FunctionArn', OutputValue: fnArn },
            { OutputKey: 'StoreBucket', OutputValue: bucket },
            { OutputKey: 'Version', OutputValue: params.ImageTag || 'v0.9.0' }
          ],
          resources: [fnArn, roleArn, policyArn, 'arn:aws:s3:::' + bucket, lgArn]
        };
      },
      remove: function (c, acct, stack) {
        var fnName = stack.StackName + '-api';
        if (acct.lambda.functions.some(function (f) { return f.FunctionName === fnName && f.Region === stack.Region; })) c.lambda.deleteFunction({ FunctionName: fnName });
      }
    },
    'sg-send-fargate': {
      description: 'SG/Send API on ECS Fargate behind a security group, S3 storage mode. ECS is not in the interface yet: the stack records that gap.',
      parameters: [
        { key: 'ImageTag', label: 'Container image tag', default: 'v0.9.0' },
        { key: 'DesiredCount', label: 'Tasks', default: '2' }
      ],
      apply: function (c, acct, params, stackName) {
        var region = c.scope.region;
        var roleName = 'sg-send-task-role';
        var roleArn = ensureRole(c, acct, roleName, 'ecs-tasks');
        var bucket = ensureBucket(c, acct, region);
        var policyArn = ensureBucketPolicy(c, acct, roleName, bucket);
        var sgName = stackName + '-service';
        var sgId;
        var existing = acct.ec2.securityGroups.filter(function (g) { return g.GroupName === sgName && g.Region === region; })[0];
        if (existing) sgId = existing.GroupId;
        else {
          c.ec2.createSecurityGroup({ GroupName: sgName, Description: 'SG/Send Fargate service, HTTPS in' });
          sgId = acct.ec2.securityGroups.filter(function (g) { return g.GroupName === sgName && g.Region === region; })[0].GroupId;
          c.ec2.authorizeSecurityGroupIngress({ GroupId: sgId, IpProtocol: 'tcp', FromPort: 443, ToPort: 443, CidrIp: '0.0.0.0/0' });
        }
        var lg = '/ecs/' + stackName;
        if (!acct.logs.groups.some(function (g) { return g.logGroupName === lg && g.Region === region; })) c.logs.createLogGroup({ logGroupName: lg });
        return {
          outputs: [
            { OutputKey: 'ServiceSecurityGroup', OutputValue: sgId },
            { OutputKey: 'StoreBucket', OutputValue: bucket },
            { OutputKey: 'DesiredCount', OutputValue: params.DesiredCount || '2' },
            { OutputKey: 'Version', OutputValue: params.ImageTag || 'v0.9.0' },
            { OutputKey: 'EcsService', OutputValue: 'not in the interface: tracked gap (ecs.* is not in the manifest yet)' }
          ],
          resources: [roleArn, policyArn, 'arn:aws:s3:::' + bucket, sgId, 'arn:aws:logs:' + region + ':' + acct.accountId + ':log-group:' + lg]
        };
      },
      remove: function (c, acct, stack) {
        var lg = '/ecs/' + stack.StackName;
        if (acct.logs.groups.some(function (g) { return g.logGroupName === lg && g.Region === stack.Region; })) c.logs.deleteLogGroup({ logGroupName: lg });
      }
    }
  };

  function register(backend) {
    Object.keys(TEMPLATES).forEach(function (k) { backend.registerTemplate(k, TEMPLATES[k]); });
    return backend;
  }

  /* --- the demo estate --- */
  var DEMO_ACCOUNTS = [
    { accountId: '111111111111', name: 'sg-send-dev (illustrative)' },
    { accountId: '222222222222', name: 'sg-send-prod (illustrative)' }
  ];

  function seedDemo(backend, onCall) {
    register(backend);
    var calls = 0;
    var count = function (rec) { calls++; if (onCall) onCall(rec); };
    var monthsBack = function (n) { var d = new Date(); d.setUTCDate(1); d.setUTCMonth(d.getUTCMonth() - n); return d.toISOString().slice(0, 10); };

    DEMO_ACCOUNTS.forEach(function (a, ai) {
      var acct = backend.ensureAccount(a.accountId, a.name);
      var eu = AwsTwin.client(backend, { accountId: a.accountId, region: 'eu-west-2', role: 'AdministratorAccess' }, count, { sync: true });
      var us = AwsTwin.client(backend, { accountId: a.accountId, region: 'us-east-1', role: 'AdministratorAccess' }, count, { sync: true });

      /* IAM, global */
      eu.iam.createPolicy({ PolicyName: 'read-only-inventory', Description: 'Describe and list across the account', PolicyDocument: { Version: '2012-10-17', Statement: [{ Effect: 'Allow', Action: ['s3:List*', 'lambda:List*', 'lambda:Get*', 'ec2:Describe*', 'iam:List*', 'iam:Get*', 'logs:Describe*', 'logs:Filter*', 'ce:GetCostAndUsage'], Resource: '*' }] } });
      eu.iam.createRole({ RoleName: 'twin-reader', Description: 'The narrow reading role the twin should be given', AssumeRolePolicyDocument: { Version: '2012-10-17', Statement: [{ Effect: 'Allow', Principal: { AWS: 'arn:aws:iam::' + a.accountId + ':root' }, Action: 'sts:AssumeRole' }] } });
      eu.iam.attachRolePolicy({ RoleName: 'twin-reader', PolicyArn: 'arn:aws:iam::' + a.accountId + ':policy/read-only-inventory' });
      eu.iam.createRole({ RoleName: 'ec2-ssm-node', Description: 'SG/Compute node role: SSM only', AssumeRolePolicyDocument: { Version: '2012-10-17', Statement: [{ Effect: 'Allow', Principal: { Service: 'ec2.amazonaws.com' }, Action: 'sts:AssumeRole' }] } });
      eu.iam.attachRolePolicy({ RoleName: 'ec2-ssm-node', PolicyArn: 'arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore' });

      /* S3 */
      eu.s3.createBucket({ Bucket: 'sg-compute-artefacts-' + a.accountId, Region: 'eu-west-2' });
      eu.s3.putObject({ Bucket: 'sg-compute-artefacts-' + a.accountId, Key: 'runs/2026-10-20/screenshot-001.png', Body: 'png-bytes-stand-in', ContentType: 'image/png' });
      eu.s3.putObject({ Bucket: 'sg-compute-artefacts-' + a.accountId, Key: 'runs/2026-10-20/sequence.json', Body: JSON.stringify({ status: 'COMPLETED', steps: 7 }), ContentType: 'application/json' });
      us.s3.createBucket({ Bucket: 'sg-compute-amis-' + a.accountId + '-us-east-1', Region: 'us-east-1' });

      /* EC2 */
      eu.ec2.createSecurityGroup({ GroupName: 'sg-compute-node', Description: 'SG/Compute ephemeral node: HTTPS in, SSM out' });
      var sg = acct.ec2.securityGroups.filter(function (g) { return g.GroupName === 'sg-compute-node' && g.Region === 'eu-west-2'; })[0].GroupId;
      eu.ec2.authorizeSecurityGroupIngress({ GroupId: sg, IpProtocol: 'tcp', FromPort: 443, ToPort: 443, CidrIp: '0.0.0.0/0' });
      eu.ec2.runInstances({ ImageId: 'ami-0sgcompute0browser', InstanceType: 't3.large', SecurityGroupIds: [sg], IamInstanceProfile: 'ec2-ssm-node', Name: 'sg-compute-browser-headed', Tags: [{ Key: 'sg-compute:spec', Value: 'browser-headed' }, { Key: 'sg-compute:max-hours', Value: '1' }] });
      if (ai === 0) {
        eu.ec2.runInstances({ ImageId: 'ami-0sgcompute0vault', InstanceType: 't3.medium', SecurityGroupIds: [sg], IamInstanceProfile: 'ec2-ssm-node', Name: 'sg-compute-vault-s3', Tags: [{ Key: 'sg-compute:spec', Value: 'vault-s3' }] });
        var stopped = acct.ec2.instances.filter(function (i) { return i.Region === 'eu-west-2'; })[1].InstanceId;
        eu.ec2.stopInstances({ InstanceIds: [stopped] });
      }

      /* Logs */
      eu.logs.createLogGroup({ logGroupName: '/sg-compute/nodes' });
      eu.logs.putLogEvents({ logGroupName: '/sg-compute/nodes', logEvents: [
        { timestamp: Date.now() - 3600000, message: 'node i-browser-headed booted in 16.2s, SSM ready' },
        { timestamp: Date.now() - 3500000, message: 'health: ok (phase 2)' },
        { timestamp: Date.now() - 60000, message: 'self-destruct armed: max_hours=1 (halt means terminate)' }
      ] });

      /* The first job: the SG/Send API deployed to two regions per account */
      eu.cloudformation.createStack({ StackName: 'sg-send-api', TemplateName: 'sg-send-lambda-url', Parameters: [{ ParameterKey: 'ImageTag', ParameterValue: ai === 0 ? 'v0.9.1' : 'v0.9.0' }] });
      us.cloudformation.createStack({ StackName: 'sg-send-api', TemplateName: 'sg-send-lambda-url', Parameters: [{ ParameterKey: 'ImageTag', ParameterValue: 'v0.9.0' }] });
      eu.lambda.invoke({ FunctionName: 'sg-send-api-api', Payload: { path: '/health', method: 'GET' } });

      /* Costs: three months, a few services, both regions. Illustrative numbers. */
      var scale = ai === 0 ? 1 : 3.2;
      [2, 1, 0].forEach(function (m) {
        var d = monthsBack(m);
        eu.twin.recordCost({ Service: 'Amazon Elastic Compute Cloud - Compute', Amount: Math.round((41.7 + m * 6.3) * scale * 100) / 100, Date: d, Region: 'eu-west-2' });
        eu.twin.recordCost({ Service: 'AWS Lambda', Amount: Math.round((3.2 + m * 0.4) * scale * 100) / 100, Date: d, Region: 'eu-west-2' });
        us.twin.recordCost({ Service: 'AWS Lambda', Amount: Math.round((1.1 + m * 0.2) * scale * 100) / 100, Date: d, Region: 'us-east-1' });
        eu.twin.recordCost({ Service: 'Amazon Simple Storage Service', Amount: Math.round((2.9 + m * 0.7) * scale * 100) / 100, Date: d, Region: 'eu-west-2' });
        eu.twin.recordCost({ Service: 'AmazonCloudWatch', Amount: Math.round((0.8 + m * 0.1) * scale * 100) / 100, Date: d, Region: 'eu-west-2' });
      });
    });
    return { calls: calls, accounts: DEMO_ACCOUNTS.map(function (a) { return a.accountId; }) };
  }

  return { VERSION: VERSION, TEMPLATES: TEMPLATES, DEMO_ACCOUNTS: DEMO_ACCOUNTS, register: register, seedDemo: seedDemo };
}));
