# Cicada

A FOSS, cross-platform version of GitHub Actions and Gitlab CI.

![Workflow File Example](/docs/img/ci-file-example.png)

The above workflow runs on both GitHub and Gitlab with no modifications.
To read more about the capabilities of Cicada, read the [docs](/docs/ci-lang/README.md).

## Installing

Cicada is currently in closed-beta. You can [join the waitlist](https://cicada.sh) on our homepage.

In the meantime you will have to self-host. The docs for self-hosting are minimal at the moment,
but in short:

You will need to [make a GitHub App](/docs/making-a-github-app.md) that will communicate with the Cicada server.

Then, you will need to create a Gitlab Webhook. The docs for doing so are not there, but you can use the
[official docs](https://docs.gitlab.com/ee/user/project/integrations/webhooks.html#configure-a-webhook-in-gitlab)
as a starting point. You'll need to remember to:

* When setting the "URL" field, it must be in the form: `https://DOMAIN/gitlab_webhook`
* Copy the "Secret Token" to the `GITLAB_WEBHOOK_SECRET` field in the `.env` file.
* Under the "Trigger" field, check:
  * Push events (All branches)
  * Tag push events
  * Issue events

In addition, you will need to [create a PAT (personal access token)](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html#create-a-personal-access-token)
for this app, and store it in `GITLAB_ACCESS_TOKEN`.

Then, build the workflow executor:

```
$ sudo docker build -f executor.Dockerfile -t cicada .
```

Lastly, install the dependencies, run the migrations, and start the server:

```
$ python3 -m virtualenv .venv
$ source .venv/bin/activate
$ pip install -r requirements.txt

$ python3 -m cicada.api.infra.migrate
$ python3 -m cicada.api
```

## Support

If you would like to support the development of Cicada, feel free to support
me on [GitHub Sponsors](https://github.com/sponsors/dosisod).
