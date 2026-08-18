#!/bin/sh
set -eu

. "$(dirname "$0")/_lib.sh"

sf_require_pack_context company-status

exec python3 "$GC_PACK_DIR/scripts/slack_company_admin.py" company-status "$@"
