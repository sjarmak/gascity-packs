#!/bin/sh
set -eu

. "$(dirname "$0")/_lib.sh"

sf_require_pack_context post-message
sf_require_cli post-message

exec "$GC_PACK_DIR/cli/gc-slack-cli" post-message "$@"
