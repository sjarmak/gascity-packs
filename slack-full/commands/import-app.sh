#!/bin/sh
set -eu

. "$(dirname "$0")/_lib.sh"

sf_require_pack_context import-app
sf_require_cli import-app

exec "$GC_PACK_DIR/cli/gc-slack-cli" import-app "$@"
