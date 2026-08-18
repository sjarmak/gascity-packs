#!/bin/sh
set -eu

. "$(dirname "$0")/_lib.sh"

sf_require_pack_context enable-room-launch
sf_require_cli enable-room-launch

exec "$GC_PACK_DIR/cli/gc-slack-cli" enable-room-launch "$@"
