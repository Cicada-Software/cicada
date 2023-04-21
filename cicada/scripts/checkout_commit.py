import json
import os
import subprocess

payload = json.loads(os.getenv("CICADA_TRIGGER", "{}"))

# TODO: dont assume all refs follow "refs/XYZ/branch-name"
# This might "work" now, but will fail if ref happens to be "refs/HEAD"
try:
    ref = "/".join(payload.get("ref").split("/")[2:])
except AttributeError:
    ref = "HEAD"
sha = payload.get("sha")

if ref and sha:
    subprocess.run(["git", "checkout", ref])  # noqa: S603, S607
    subprocess.run(["git", "reset", "--hard", sha])  # noqa: S603, S607
