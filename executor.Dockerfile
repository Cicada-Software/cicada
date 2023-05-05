# Dockerfile for building the CI file executor image. This is basically an
# isolated instance where the CI files get ran, using information passed in
# via environment variables.
#
# Env vars:
#
# CLONE_URL: the git URL which will be used to clone the repo. It includes
#   the username/token info needed to clone the repo.
#
# CICADA_TRIGGER: The JSON data about the event which is triggering this CI
#   workflow.
#
# There is lots of room for improvements here, namely:
# * Don't use env vars to pass payload info (once payloads get too big)

FROM python:3.10.11-alpine3.17

RUN apk update \
	&& apk upgrade \
	&& apk add git git-lfs alpine-sdk neofetch \
	&& git lfs install \
	&& pip install typing_extensions

COPY . .

ENV CLONE_URL= \
	CICADA_TRIGGER=

COPY cicada/api/docker-init.sh /etc/

ENTRYPOINT [ "/etc/docker-init.sh" ]
