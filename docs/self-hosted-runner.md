# Setting Up Self-Hosted Runner

This is how to setup a self-hosted runner for use with [Cicada.sh](https://cicada.sh).

> Note: There is no UI to setup or manage self-hosted runners at the moment. In order to get
> your runner ID and runner secret, please reach out to [contact@cicada.sh](mailto:contact@cicada.sh)
> to get started.

## Install via Docker

To install using Docker run the following command:

```
docker run \
  --rm -it \
  -e RUNNER_ID="runner id here" \
  -e RUNNER_SECRET="secret here" \
  ghcr.io/cicada-software/cicada-self-hosted-runner:v1
```

You should see output similar to this:

```
[2023-08-08 13:24:02,265.265] [INFO] [site-packages/cicada-runner/__main__.py:54]: Attempting to read .env file
[2023-08-08 13:24:02,266.266] [INFO] [site-packages/cicada-runner/__main__.py:103]: Connecting to cicada.sh
[2023-08-08 13:24:03,094.94] [INFO] [site-packages/cicada-runner/__main__.py:171]: Connection successful
```

If you are having issues connecting try adding `-e LOG_LEVEL=debug` to Docker command to increase the verbosity.

If you are connecting a self-hosted runner to a self-hosted version of Cicada you will need to pass
`-e CICADA_DOMAIN="your.website.com"` to Docker as well.

## Install Manually

> Note: When installing Cicada on your local machine, workflows ran on your runner will have direct access to your
> machine. This is good if you need direct access to drivers or devices, but not great in terms of security.
> Only install manually if you have a specific need to do so!

Before you begin installing Cicada locally, make sure you have Python 3.11 installed. If you are using Ubuntu, read
[this](https://askubuntu.com/a/1438713) Stack Overflow post on how to install Python 3.11.

Once you have Python 3.11 installed, create a new directory, create a `.env` file, and add the following:

```
RUNNER_ID="runner id here"
RUNNER_SECRET="secret here"
```

Replace `runner id here` with your runner UUID. Same for `RUNNER_SECRET`.

Then, install the runner and start it:

```
$ pip install cicada-runner
$ python3 -m cicada-runner
```
