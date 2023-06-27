# Running Cicada on GitHub Codespaces

Thank you for taking the time to look into Cicada! You're almost ready to get started, but first
you'll need to run the setup script:

`$ ./cicada/setup.sh`

A new browser tab will automatically open when the server is finished starting.

> If a tab doesn't open click on the "Ports" tab next to the "Terminal" tab,
> then click the URL under "Local Address".

There should be a big green button. This button will create a custom GitHub App that integrates with
your self-hosted instance of Cicada. Click it, accept the permissions, and you'll be redirected back
to Cicada.

Now restart the webserver and refresh the page, and your self-hosted Cicada instance will be up and running!

## Connecting to GitHub

> Before connecting to GitHub you will need to make sure the Cicada server is publicly accessible.
> On the "Ports" tab, right click on the first line (the Cicada/NGINX server) and under "Port Visibility"
> make sure "Public" is selected.

We just finished creating our new GitHub App, but it hasn't been connected to any repos yet!
To connect, sign in, and on the dashboard click the "GitHub" button on the "Connect" section.
This will redirect you to GitHub where you select which repositories you want to install Cicada on.

Now Cicada is ready to accept events from GitHub! Read the [getting started](./docs/ci-lang/getting-started.md)
docs for instructions on how to start writing workflow files.
