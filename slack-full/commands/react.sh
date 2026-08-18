#!/bin/sh
set -eu

. "$(dirname "$0")/_lib.sh"

sf_require_pack_context react

exec python3 "$GC_PACK_DIR/scripts/slack_chat_react.py" "$@"
