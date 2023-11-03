# Running Cicada on GitHub Codespaces

Thank you for taking the time to look into Cicada! You're almost ready to get started, but first
you'll need to run the setup script in the terminal below:

```
$ ./cicada/setup.sh
```

Once the dependencies are installed and the server has booted, a new browser tab will automatically
open for you. This should take about 10-15 seconds.

> If a tab doesn't open click on the "Ports" tab next to the "Terminal" tab,
> then click the URL under "Local Address".

There should be a big green button. This button will create a custom GitHub App that integrates with
your self-hosted instance of Cicada. Click it, accept the permissions, and you'll be redirected back
to Cicada.

If all goes to plan, you should get a success message telling you to wait while the server finishes rebooting.

Now the hard part is over! The last few steps are configuring the server and connecting to GitHub.

## Allow GitHub Webhooks

Now that you have successfully setup the server, you need to make your self-hosted instance publicly
available so that GitHub can send it webhooks events.

On the "Ports" tab, right click on the first line (the Cicada/NGINX server), then set "Port Visibility" to "Public".

## Logging In

In Cicada, click the login button, and click "Login with GitHub" button. You will be asked to authenticate with
the GitHub integration we just created. Accept the permissions, and you will be taken to the Cicada dashboard.

## Add Repositories

On the dashboard in the "connect" widget, click "GitHub" to connect your GitHub repositories to Cicada.
GitHub will then ask if you want to connect all of your repositories to Cicada, or only a select few.
This is up to you, and you can change this at any time. Note Cicada will only be able to work on repositories
it has access to.

Cicada is now ready to accept events from GitHub! Read the [getting started](./docs/ci-lang/getting-started.md)
docs for instructions on how to start writing workflow files.
