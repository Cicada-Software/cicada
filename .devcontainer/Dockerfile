FROM python:3.11-alpine3.18

RUN apk add --no-cache git git-lfs fuse-overlayfs podman iptables build-base nginx \
	&& git-lfs install

COPY .devcontainer/nginx.conf /etc/nginx/nginx.conf
