"""
Setup a new self-hosted Cicada server. This is a custom FastAPI app because
you need a live server to handle the OAuth flow to create the GitHub app. Once
the GitHub app is setup the server will need to be restarted so that the actual
app will be used instead.
"""

import json
import os
from pathlib import Path
from secrets import token_urlsafe

import requests
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI()


if codespace_name := os.getenv("CODESPACE_NAME", ""):
    # Running in GitHub Codespaces, auto-build domain name

    preview_domain = os.getenv("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "")
    port = 80

    CICADA_DOMAIN = f"{codespace_name}-{port}.{preview_domain}"
    CICADA_USER = os.getenv("GITHUB_USER")

else:
    CICADA_DOMAIN = os.getenv("CICADA_DOMAIN", "")
    CICADA_USER = os.getenv("CICADA_USER", "")

assert (
    CICADA_DOMAIN and CICADA_USER
), "CICADA_DOMAIN and CICADA_USER must be set"


def get_github_app_manifest() -> str:
    url = f"https://{CICADA_DOMAIN}"
    user = CICADA_USER

    payload = {
        "name": "Cicada Manifest Test",
        "url": url,
        "hook_attributes": {"url": f"{url}/api/github_webhook"},
        "redirect_url": url,
        "callback_urls": [f"{url}/api/github_sso"],
        "setup_url": f"{url}/setup_url",
        "description": f"Cicada integration for @{user}",
        "public": False,
        "default_events": [
            "meta",
            "check_suite",
            "check_run",
            "issues",
            "push",
            "star",
            "watch",
        ],
        "default_permissions": {
            "checks": "write",
            "statuses": "write",
            "contents": "read",
            "issues": "read",
            "metadata": "read",
            "workflows": "write",
        },
        "request_oauth_on_install": True,
        "setup_on_update": False,
    }

    return json.dumps(payload, separators=(",", ":"))


@app.get("/")
async def create_deploy_button() -> HTMLResponse:
    manifest = get_github_app_manifest()

    return HTMLResponse(
        f"""
<!DOCTYPE html>
<html>

<head>
<title>Self-hosted Cicada Setup</title>
</head>

<body>
<form action="https://github.com/settings/apps/new" method="post">
  <h1>Create GitHub App</h1>
  <input type="text" name="manifest" id="manifest">
  <input type="submit" value="Create">
</form>

<script>
if (new URLSearchParams(window.location.search).get("success")) {{
    document.querySelector("h1").innerText = "Setup is complete! Restart server for changes to take effect.";
    document.querySelector("input[type=submit]").style.display = "none";
}} else {{
    document.getElementById("manifest").value = JSON.stringify({manifest});
}}
</script>

<style>
html, body {{
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  background: #171717;
  font-family: monospace;
}}

h1 {{
  color: #5b5b5b;
}}

form {{
  text-align: center;
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
}}

#manifest {{
  display: none;
}}

input[type=submit] {{
  padding: 0.75em 1em;
  background: #0f0;
  color: #0d0d0d;
  font-size: 1.25em;
  border: 0;
  border-radius: 0.15em;
  cursor: pointer;
}}
</style>

</body>

</html>
"""
    )


@app.get("/api/github_sso")
async def redirect_url(code: str) -> RedirectResponse:
    resp = requests.post(  # noqa: ASYNC100
        f"https://api.github.com/app-manifests/{code}/conversions", timeout=10
    )

    id, pem, webhook_secret, client_id, client_secret = resp.json()

    key_filename = f"cicada-key-{id}.pem"
    Path(key_filename).write_text(pem)

    admin_pw = token_urlsafe(32)
    jwt_secret = token_urlsafe(32)

    env_file = f"""\
# Common
DB_URL=./db.db3
CICADA_DOMAIN={CICADA_DOMAIN}
CICADA_HOST=0.0.0.0
CICADA_PORT=8000
CICADA_ADMIN_PW="{admin_pw}"
JWT_TOKEN_SECRET="{jwt_secret}"
JWT_TOKEN_EXPIRE_SECONDS=3600
REPO_WHITE_LIST=".*"
ENABLED_PROVIDERS=github
CICADA_EXECUTOR=remote-podman

# Github specific
GITHUB_WEBHOOK_SECRET="{webhook_secret}"
GITHUB_APP_ID={id}
GITHUB_APP_CLIENT_ID="{client_id}"
GITHUB_APP_CLIENT_SECRET="{client_secret}"
GITHUB_APP_PRIVATE_KEY_FILE={key_filename}
"""

    Path(".env").write_text(env_file)

    return RedirectResponse("/?success=1", status_code=302)


@app.post("/api/github_webhook")
async def github_webhook() -> None:
    pass
