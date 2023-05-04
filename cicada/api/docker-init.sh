#!/bin/sh

set -e

old_cwd="$(pwd)"
tempdir="$(mktemp -d)"

cd "$tempdir"

git clone -q "$CLONE_URL"

# Hack to cd into the repo we just cloned. If this doesn't work, we can just use
# the `basename` command instead.
cd *

# TODO: dont suppress error output here. When we get support for collapsable groups we should just
# stuff all of this output there, but for now, it clogs up the normal output, and should be ignored.
CICADA_TRIGGER="$CICADA_TRIGGER" python3 "$old_cwd/cicada/scripts/checkout_commit.py" > /dev/null 2>&1

# TODO: Rename this "eval.main" to something more important sounding
# TODO: see if there is a less hacky way of running python from a different directory
PYTHONPATH="$old_cwd" CICADA_TRIGGER="$CICADA_TRIGGER" python3 -c "
import sys
from pathlib import Path

sys.path.insert(0, '$old_cwd')

from cicada.eval.main import main

main([])
"
