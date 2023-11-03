#!/bin/sh

pip install -r requirements.txt

# Start server in background
python3 -m cicada.api &

# Wait for server to start before starting NGINX since Codespaces will auto
# open a page when port 80 is available and we want to make sure the API is
# ready before then
sleep 1

# Stop NGINX if it is already running, then start/restart
nginx -s stop &> /dev/null
nginx &

# Wait for .env file to be created
while :; do
	sleep 1;
	[ -e ".env" ] && break;
done

# Kill the server
pid="$(ps -a | grep cicada.api | head -n 1 | awk '{print $1}')"
kill -9 "$pid"

# Run migrations
python3 -m cicada.api.infra.migrate

echo
echo Congrats! Your self-hosted instance of Cicada is all setup!
echo
echo Refresh your other browser window, then login.
echo

# Reboot server
python3 -m cicada.api
