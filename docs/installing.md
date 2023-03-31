# Installing

This is a basic overview of how to install Cicada locally. This is only useful if you plan on self-hosting Cicada,
otherwise, see our cloud-hosted version at [cicada.sh](https://cicada.sh).

To get started, clone the [Cicada repository](https://github.com/Cicada-Software/cicada) and make a copy of the
`.env.example` file:

```
$ git clone https://github.com/Cicada-Software/cicada
$ cd cicada
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
ENABLED_PROVIDERS=github,gitlab
```

Some of these can be as-is, but others should be changed immediately:

* `CICADA_DOMAIN`: The domain where you will be running Cicada. If you are using `localhost` for
testing purposes, you will need to use a reverse-proxy like [ngrok](https://ngrok.com/) to make
`localhost` reachable by GitHub/Gitlab.

* `CICADA_ADMIN_PW`: This is the default password for the `admin` user in Cicada. It is only
generated once when first starting, and has no effect if changed afterwards. Make sure to change
this!

* `JWT_TOKEN_SECRET`: This is used for issuing [JWT tokens](https://jwt.io/) to users. If this
is not changed, anyone will be able forge tokens and impersonate another user, including `admin`.

The rest of the fields can be left as-is, but here is what they mean/do:

* `DB_URL`: The location of the SQLite database used for storing all the data.

* `JWT_TOKEN_EXPIRE_SECONDS`: This sets how long a JWT token is valid for (defaults to 1 hour).
Changing this will change how often users will have to re-login after closing a tab.

* `REPO_WHITE_LIST`: A comma-separated list of regular expressions that define which repositories
are allowed to run workflows. By default, anyone who uses your GitHub App will be able to run
workflows. Change this to something different if you only want specific people to run workflows.
For example: `bob/.*,alice/repo` will run any workflows that come from `bob`, but will only run
workflows for the `repo` repository owned by `alice`.

* `ENABLED_PROVIDERS`: A comma-separated list of enabled providers. For example, if `github` is
specified in that list, Cicada will recieve webhooks from GitHub, as well as enable GitHub SSO.

## Next Steps

Currently Cicada only supports GitHub and Gitlab. You can use one or the other, or both:

* If you plan on using GitHub, you will need to [make a GitHub App](./making-a-github-app.md).

* If you plan on using Gitlab, you will need to [make a Gitlab Webhook](./making-a-gitlab-webhook.md).

Once you have setup GitHub and/or Gitlab support, you will need to update the `ENABLED_PROVIDERS` field
in the `.env` file to indicate which providers you've enabled:

```shell
# Must be a comma separated list

ENABLED_PROVIDERS=github,gitlab
```

## Starting the Server

Now you're almost ready to go! Just a few more steps:

Set up the virtualenv:

```
$ python3 -m virtualenv .venv
$ source .venv/bin/activate
```

Install dependencies:

```
$ pip install -r requirements.txt
```

Run migrations and build docker executor image (these will need to be re-ran every update):

```
$ python3 -m cicada.api.infra.migrate
$ docker build -f executor.Dockerfile -t cicada .
```

Then start the server!

```
$ python3 -m cicada.api
```
