#!/usr/bin/env bash
# gc <binding> scan — audit your orders for instruments that have no test.
#
# With no arguments this audits the city's whole enabled-order population,
# which is the standing reading. With paths, it audits exactly those files,
# which is what you want in a pre-commit or on a branch.
#
# Environment (set by gc): GC_CITY_PATH, GC_PACK_DIR, GC_PACK_NAME

set -euo pipefail

if [ -z "${GC_PACK_DIR:-}" ]; then
  echo "untested-orders scan: missing Gas City pack context" >&2
  exit 1
fi

checker="$GC_PACK_DIR/assets/scripts/untested-orders-check"
if [ ! -f "$checker" ]; then
  echo "untested-orders scan: checker missing at $checker" >&2
  exit 1
fi

export GC_CITY_PATH="${GC_CITY_PATH:-$PWD}"

if [ "$#" -eq 0 ]; then
  exec python3 "$checker" --enabled-local-orders
fi

exec python3 "$checker" "$@"
