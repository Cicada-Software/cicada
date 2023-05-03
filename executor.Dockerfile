# Dockerfile for building the CI file executor image. This is basically an
# isolated instance where the CI files get ran, using information passed in
# via environment variables.
#
# Env vars:
#
# CLONE_URL: the git URL which will be used to clone the repo. It includes
#   the username/token info needed to pull the repo down.
#
# CICADA_TRIGGER: The JSON data about the event which is triggering this CI
#   workflow.
#
# There is lots of room for improvements here, namely:
# * Don't build sqlite from scratch, it should be done in our CI file instead
# * Don't use env vars to pass payload info (once payloads get too big)

FROM python:3.10.8-slim-bullseye

RUN apt update \
	&& apt upgrade -y \
	&& apt install build-essential curl -y \
	&& curl https://www.sqlite.org/2022/sqlite-autoconf-3400100.tar.gz > /tmp/sqlite.tar.gz \
	&& cd tmp \
	&& tar -zxvf sqlite.tar.gz \
	&& cd sqlite-autoconf-3400100 \
	&& ./configure \
	&& make \
	&& make install

RUN apt install git git-lfs neofetch -y
RUN pip install typing_extensions

WORKDIR /app

COPY . .

ENV CLONE_URL= \
	CICADA_TRIGGER=

COPY cicada/api/docker-init.sh .

ENTRYPOINT [ "/app/docker-init.sh" ]
