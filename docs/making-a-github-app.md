# Making a GitHub App for Cicada

This is an overview of how to setup your own [GitHub App](https://docs.github.com/en/apps) for use with
Cicada. This is only useful if you plan on self-hosting Cicada: Otherwise, see our cloud-hosted version
at [cicada.sh](https://cicada.sh).

To get started, clone the [Cicada repository](https://github.com/Cicada-Software/cicada), and run the
following command:

```
$ cp .env.example .env
```

The `.env` file will contain all the important information about your application, including sensitive
information used for authenticating with GitHub, Gitlab (if setup with Gitlab), and so on. Do not share
this file with anyone!

By default, the `.env` file should start with something similar to the following:

```shell
# Common
DB_URL=./db.db3
CICADA_DOMAIN=localhost
CICADA_ADMIN_PW=change-this-to-something-different
JWT_TOKEN_SECRET=change-this-to-something-different
JWT_TOKEN_EXPIRE_SECONDS=300
REPO_WHITE_LIST=".*"
```

Some of these can be as-is, but others should be changed immediately:

* `CICADA_DOMAIN`: The domain where you will be running Cicada. If you are using `localhost` for
testing purposes, you will need to use a reverse-proxy like [ngrok](https://ngrok.com/) to make
`localhost` reachable by GitHub.

* `CICADA_ADMIN_PW`: This is the default password for the `admin` user in Cicada. It is only
generated once when first starting, and has no effect if set afterwards. Make sure to change
this!

* `JWT_TOKEN_SECRET`: This is used for issuing [JWT tokens](https://jwt.io/) to users. If this
is not changed, anyone will be able forge tokens and impersonate another user, including `admin`.

The rest of the fields can be left as-is. You might want to change them though:

* `DB_URL`: The location of the SQLite database used for storing all the data.

* `JWT_TOKEN_EXPIRE_SECONDS`: This sets how long a JWT token is valid for (defaults to 5 minutes).
Changing this will change how often users will have to re-login after closing a tab.

* `REPO_WHITE_LIST`: A comma-separated list of regular expressions that define which repositories
are allowed to run workflows. By default, anyone who uses your GitHub App will be able to run
workflows. Change this to something different if you only want specific people to run workflows.
For example: `bob/.*,alice/repo` will run any workflows that come from `bob`, but will only run
workflows for the `repo` repository owned by `alice`.

## Creating The App

Use the [official GitHub docs](https://docs.github.com/en/apps/creating-github-apps/creating-github-apps/creating-a-github-app)
as a starting point, but before you click "Create GitHub App", make sure to adjust the following:

### Basic Setup

In "Callback URL" add your URL in the following form: `https://DOMAIN/github_sso`

In "Webhook URL" add your URL in the following form: `https://DOMAIN/github_webhook`

In the webhook secret add a long, secure password. Be sure to save it in the `GITHUB_WEBHOOK_SECRET`
environment variable.

### Permissions

In the "Repository permissions" section, expand it and add the following permissions:

* Checks: Make this *Read and Write*. This allows for interacting with GitHub's checks API, which
is used to attach CI workflows to commits, pull requests, and so on.

* Commit Statuses: Make this *Read and Write*. This permission might not be needed in
the future, but should be enabled until further notice.

* Contents: Make this *Read-only*. This allows for Cicada to read the contents of your
repositories in order to find and execute CI files.

* Issues: Make this *Read-only*. This allows for Cicada to read issue data and respond to
issue-related events.

* Metadata: This is mandatory, and should already be set, but make sure it is *Read-only*.

* Workflows: Make this *Read and Write*. This permission might not be needed in
the future, but should be enabled until further notice.

### Webhook Events

Now that we have permissions set up, we need to tell GitHub which webhook events to send
to us. Select the following:

* Meta
* Check suite
* Check run
* Issues
* Push
* Star
* Watch

Note that new features added to Cicada may require more of these webhook events be selected.
Currently, the above list includes all of currently (or soon-to-be) supported/required
events.

## Post Setup

Now that we have the GitHub App all setup, we will need to generate/download some information
to finish setting up the app.

Open the `.env` file from before, and add update the following lines:

* `GITHUB_APP_ID`: Set this to the number after "App ID"
* `GITHUB_APP_CLIENT_ID`: Set this to the string after "Client ID"

Then, on the GitHub App settings page, click "Generate a new client secret". This will
show a hexidecimal string which will be used to authenticate your app. Copy this to the
`GITHUB_APP_CLIENT_SECRET` field in your `.env` file.

Click "Save Changes".

Next, you will need to generate a private key for your application. This in addition to
the client id/secret allows your GitHub App to authenticate with GitHub. Click "Generate
a private key", which should generate, add, and download a new key for you. Move this
file from your downloads folder to a safe location (for example, inside the cloned
repository), and update the `GITHUB_APP_PRIVATE_KEY_FILE` field to point to the path
of the private key file.

Assuming you've followed the steps correctly, you should have a `.env` file that looks
something like this:

```shell
# Github specific
GITHUB_WEBHOOK_SECRET="secret here"
GITHUB_APP_ID=12345
GITHUB_APP_CLIENT_ID=Iv1.xxxxxxxxxxxxxxxx
GITHUB_APP_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_APP_PRIVATE_KEY_FILE=path/to/key.pem
```
