#!/bin/sh
set -eu

. "$(dirname "$0")/_lib.sh"

sf_require_pack_context register-agent-app

exec python3 "$GC_PACK_DIR/scripts/slack_register_agent_app.py" "$@"
