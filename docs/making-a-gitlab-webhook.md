# Setting up a Gitlab Webhook

This is an overview of how to setup your own [Gitlab webhook](https://docs.gitlab.com/ee/user/project/integrations/webhooks.html)
for Cicada.

These docs assume you have already cloned and configured Cicada. If you have not, read [this](./installing.md)
first.

## Setup

Next, follow along with the [official docs](https://docs.gitlab.com/ee/user/project/integrations/webhooks.html#configure-a-webhook-in-gitlab),
and, in addition to those steps, make sure that:

* The "URL" field must be in the form: `https://DOMAIN_HERE/gitlab_webhook`
* Copy whatever you put in the "Secret Token" field to the `GITLAB_WEBHOOK_SECRET` field in the `.env` file.
* Under the "Trigger" field, check:
  * Push events (All branches)
  * Tag push events
  * Issue events

In addition, you will need to [create a PAT (personal access token)](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html#create-a-personal-access-token)
for this app, and store it in `GITLAB_ACCESS_TOKEN` field in the `.env` file.

Once you are all done, the Gitlab section of your `.env` file should look something like this:

```shell
# Gitlab specific
GITLAB_WEBHOOK_SECRET=xxxxxxxxxxxxxxxx
GITLAB_ACCESS_TOKEN=glpat-xxxxxxxxxxxxxxxx
```
