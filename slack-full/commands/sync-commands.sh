#!/bin/sh
set -eu

. "$(dirname "$0")/_lib.sh"

sf_require_pack_context sync-commands
sf_require_cli sync-commands

exec "$GC_PACK_DIR/cli/gc-slack-cli" sync-commands "$@"
