# Self-Hosted Installation

This is an overview of how to install Cicada locally. This is only useful if you plan on self-hosting Cicada,
otherwise, see our cloud-hosted version at [cicada.sh](https://cicada.sh).

If you would like to demo Cicada before installing you can demo Cicada using
[GitHub Codespaces](https://codespaces.new/Cicada-Software/cicada?quickstart=1).

## Using Automatic Setup (Recommended)

### Setting Up

Cicada has a "wizard" that walks you through the GitHub App setup process, which is used to receive events
from GitHub and allow for login with GitHub support.

To get started, clone the repository:

```
$ git clone https://github.com/Cicada-Software/cicada
$ cd cicada
```

Setup a virtual environment and install packages:

```
$ python3 -m virtualenv .venv
$ source .venv/bin/activate
$ pip install -r requirements.txt
```

Run database migrations:

> Note: This will need to be re-ran after each update.

```
$ python3 -m cicada.api.infra.migrate
```

Then start the server:

```
$ export CICADA_DOMAIN=yourdomain.here
$ export CICADA_USER=optional-username-here
$ python3 -m cicada.api
```

The `CICADA_DOMAIN` and `CICADA_USER` environment variables are used to setup/configure the
GitHub App.

`CICADA_DOMAIN` must be a publicly accessible domain that you own,
since GitHub will need to redirect back to this domain. This means you cannot use `localhost`
as a domain. If you want to use `localhost` you will need to setup a reverse proxy
such as [ngrok](https://ngrok.com/). In addition, `CICADA_DOMAIN` must be a plain
domain name, that is, it should not start with `https://` or end with `/`.

`CICADA_USER` is an optional string (typically your GitHub username) which is used to
create a unique app id for your GitHub App. If you don't set this environment variable,
a random string will be used to make your app id unique.

### Creating GitHub App

Once you have started the webserver, navigate to the URL it tells you to (it should be
[](http://0.0.0.0:8000) or similar).

You should see a green button. Once you click it you will be redirected to GitHub,
where you will be asked to confirm the information and accept. Once you accept you will
be redirected back to the `CICADA_DOMAIN` URL you set earlier.
Assuming everything worked, a success message will tell you to restart the server.

That's it! You should see 2 new files: `.env`, which contains all the secrets, and `cicada-key-*.pem`,
which is the secret key used to authenticate your GitHub App with GitHub. Don't share
either of these files with anyone!

## Using Manual Setup (Not Recommended)

If the automatic setup does not work, or you would rather do it manually, you can manually
setup a GitHub App by reading [these docs](./making-a-github-app.md). You will need to clone
and setup the repository like you do using the automatic method, so follow those instructions
until you get to the "Start the server" section.
