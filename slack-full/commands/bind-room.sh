#!/bin/sh
set -eu

. "$(dirname "$0")/_lib.sh"

sf_require_pack_context bind-room

exec python3 "$GC_PACK_DIR/scripts/slack_chat_bind_room.py" "$@"
