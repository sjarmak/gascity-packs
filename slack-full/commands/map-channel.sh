#!/bin/sh
set -eu

. "$(dirname "$0")/_lib.sh"

sf_require_pack_context map-channel
sf_require_cli map-channel

exec "$GC_PACK_DIR/cli/gc-slack-cli" map-channel "$@"
