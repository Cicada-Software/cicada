FROM alpine:3.18

LABEL org.opencontainers.image.source=https://github.com/cicada-software/cicada

RUN apk add --no-cache \
		bash \
		build-base \
		git \
		git-lfs \
		jq \
		sqlite \
		sudo \
	&& git lfs install \
	# Most CI systems expect bash to be the default shell, so use bash
	&& sed "s/\/bin\/ash/\/bin\/bash/" /etc/passwd

ENTRYPOINT [ "/bin/bash" ]
