<!-- the markdown twin of https://aws.twin.sgit.ai/sessions/index.html, generated from the same source by admin/build/pages.py; site v0.4.2; content CC BY 4.0 -->

[aws.twin.sgit.ai](../index.md) / sessions

# AWS sessions: a temporary key, pasted, checked, and gone in an hour

The live side of the twin needs one thing from AWS: a session for one account and one role that expires on its own. IAM Identity Center gives exactly that, from one to twelve hours, one by default. This page is the setup, a paste box that checks the session against the real account from this browser, and what was measured on 21 October 2026 about better ways to get one.

## 1. Paste a session

From the AWS access portal: pick the account, then the role, then **Access keys**, and copy any of the options it shows (the macOS and Linux lines, the Windows lines, PowerShell, or the credentials-file block). The page reads the three values out of whatever you paste.

No session in this tab.

```

```

**Where it goes.** Into this tab's `sessionStorage` under `aws.twin/session`, with the expiry you set, and nowhere else. Closing the tab removes it. The page never shows the secret or the token back. **Check it against AWS** loads Python and sends one request, STS `GetCallerIdentity`, signed in this browser and sent from it, which needs no permission and which STS answers a browser. The request goes through the twin with its STS route set to live, so it is recorded like every other call. Nothing else leaves the page. A vault, rather than the tab, is where the session should live next; it is the same slot with a longer reach, and it is not built yet.

## 2. Set up IAM Identity Center for this

Once per organisation, by someone with administrator access to the management account. The console steps, then the same in the CLI.

1. **Enable IAM Identity Center** in the region you want it in (it lives in one region). Use the organisation instance, so permission sets can be assigned across accounts.
2. **Choose the identity source.** The built-in Identity Center directory is enough to start; an external IdP (Google Workspace, Entra ID, Okta) can replace it later without changing anything below.
3. **Create your user** and require MFA for sign-in (Settings, Authentication).
4. **Create two permission sets**, narrow on purpose, with a session duration of **1 hour**:

  - `TwinReader`: the AWS managed `ViewOnlyAccess`, or the inline policy below, which is what the twin's inventory, logs and cost views need and nothing more.
  - `TwinDeployer`: CloudFormation, Lambda and the `sg-send-*` buckets, plus `iam:PassRole` on the deployment roles only. Assign it only to the accounts you deploy into.

5. **Assign** your user (or a group) to each account with the permission sets it needs.
6. **Note the access portal URL** (Settings, the AWS access portal URL, of the form `https://d-xxxxxxxxxx.awsapps.com/start`). That is where sessions come from.

### The TwinReader inline policy

```
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "Inventory",
      "Effect": "Allow",
      "Action": [ "s3:ListAllMyBuckets", "s3:GetBucketLocation", "s3:ListBucket", "s3:GetBucketVersioning",
                  "s3:GetBucketPolicy", "lambda:List*", "lambda:GetFunction", "ec2:Describe*",
                  "iam:List*", "iam:Get*", "logs:Describe*", "logs:FilterLogEvents",
                  "cloudformation:List*", "cloudformation:Describe*", "ce:GetCostAndUsage",
                  "sts:GetCallerIdentity" ],
      "Resource": "*" }
  ]
}
```

### The same, from the CLI

```
# the instance and the identity store (once)
INSTANCE=$(aws sso-admin list-instances --query 'Instances[0].InstanceArn' --output text)

# a one-hour permission set with the policy above
curl -sO https://aws.twin.sgit.ai/iam/policies/twin-reader.json
PS=$(aws sso-admin create-permission-set --instance-arn $INSTANCE --name TwinReader \
       --session-duration PT1H --query 'PermissionSet.PermissionSetArn' --output text)
aws sso-admin put-inline-policy-to-permission-set --instance-arn $INSTANCE \
       --permission-set-arn $PS --inline-policy file://twin-reader.json

# assign a user to one account with it
aws sso-admin create-account-assignment --instance-arn $INSTANCE --permission-set-arn $PS \
       --target-type AWS_ACCOUNT --target-id 123456789012 \
       --principal-type USER --principal-id $USER_ID      # the user id: see the IAM page
```

Then sign in to the portal, pick the account and `TwinReader`, choose **Access keys**, and paste above.

**Narrower than that**, for S3 alone (list bucket names only, read one bucket, read one folder, read and write one bucket), with groups, a daily user, testing a policy before assigning it, and moving the administrator role out of daily reach: [least privilege for the twin](../iam/index.md).

## 3. Is there a better way than pasting? Measured

Pasting is the first method because it works today and the site never holds anything but one short session. The better ways all need AWS to answer a browser, so on 21 October 2026 each endpoint was asked, with no credentials, whether it would: a CORS preflight from `https://aws.twin.sgit.ai`, and the response headers.

| Method | What it needs from the browser | Measured | State |
|---|---|---|---|
| **Paste from the access portal** | STS for the check | STS answers any origin; a signed GetCallerIdentity from Python in the browser reached AWS and came back | built |
| **SSO device code in the browser**, what `aws sso login` does: register a client, start a device authorisation, approve in the portal, get a token, then role credentials | sso-oidc, then the portal API | sso-oidc's token endpoint allows a preflight; RegisterClient refuses the preflight but answers a plain-text request with `Access-Control-Allow-Origin: *`. The portal's credentials and accounts API refuses outright: `Origin not allowed` | blocked at the last step |
| **Cognito identity pool**: sign in with a user pool or an external IdP, then `GetId` and `GetCredentialsForIdentity` return credentials for an IAM role chosen per user | cognito-identity | Preflight allowed for `content-type, x-amz-target, x-amz-user-agent` | designed, reachable |
| **STS AssumeRoleWithWebIdentity**: an OIDC token from an IdP the account trusts (Google, GitHub, a Cognito user pool) exchanged for role credentials, unsigned | STS | Preflight allowed for `content-type` | designed, reachable |
| **IAM Roles Anywhere**: an X.509 certificate from your own CA exchanged for role credentials | rolesanywhere, a signature with the certificate's key | Preflight allowed for `authorization, content-type, x-amz-date, x-amz-x509` | designed, reachable |

**What that means.** The device-code flow, the one that would replace the paste with a button and the portal's own approval page, cannot finish in a browser: the portal API that turns a token into role credentials does not answer one. It can finish with one helper call, made by a small process on the user's machine or an SG/Compute node, which is the helper the article kept in reserve. The three methods that do reach the browser are the ones that give the granularity the twin wants:

- **Cognito identity pools** map each signed-in user to a role by rules or by principal tags, so a permission set per person, per group or per task is configuration, not code. This is the natural second method.
- **AssumeRoleWithWebIdentity** is the same idea without Cognito, for an IdP the account already trusts. Short and direct; the role's trust policy carries the granularity.
- **Roles Anywhere** is the PKI path: a key made in the browser with WebCrypto, never exportable, a certificate from a CA you run, and a session from that. The endpoint answers a browser; signing the request with the X.509 scheme from WebCrypto is the part to build and test.

The plan, in order: paste (built), then a Cognito identity pool with one role per permission set and a role per group, then Roles Anywhere as the experiment. Each is a different way of filling the same slot; the twin, its live route and everything built on them do not change.

## 4. The rules for sessions here

- **Temporary only.** The slot refuses a key without a session token: a long-lived IAM user key is exactly what this design declines to hold.
- **One hour by default**, twelve at most, as the portal allows.
- **Narrow roles.** A reading role and a deploying role, never more than the job.
- **Never in a file, a commit or a page.** The site's validator fails the build on anything shaped like a key.
- **The code that holds it is versioned.** The version in the nav names the copy of this page you trusted, and [the release history](../admin/versions.md) says what changed in each.

[← The console](../console/index.md)[The Python twin →](../python/index.md)

---

*[This page as HTML](https://aws.twin.sgit.ai/sessions/index.html) · [The site for agents](https://aws.twin.sgit.ai/llms.txt) · CC BY 4.0*
