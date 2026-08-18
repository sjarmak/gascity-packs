#!/bin/sh
set -eu

. "$(dirname "$0")/_lib.sh"

sf_require_pack_context map-rig
sf_require_cli map-rig

exec "$GC_PACK_DIR/cli/gc-slack-cli" map-rig "$@"
