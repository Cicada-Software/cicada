FROM python:3.11.3-alpine3.18 AS build

WORKDIR /app

COPY . .

RUN pip install wheel \
	&& python3 setup.py bdist_wheel \
	&& python3 cicada/runner/setup.py bdist_wheel


FROM python:3.11.3-alpine3.18

WORKDIR /app

COPY --from=build \
	/app/dist/cicada-0.0.0-py3-none-any.whl \
	/app/cicada/dist/cicada_runner-0.0.0-py3-none-any.whl \
	/tmp/

RUN pip install /tmp/cicada*.whl \
	&& apk add --no-cache git

ENV RUNNER_ID= \
	RUNNER_SECRET= \
	CICADA_DOMAIN= \
	LOG_LEVEL=

CMD ["python3", "-m", "cicada-runner"]
