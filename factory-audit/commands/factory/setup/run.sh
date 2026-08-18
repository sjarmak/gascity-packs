#!/usr/bin/env bash
# gc <binding> factory setup — put the pinned reliability kit in the city.
#
# The only command in this pack that writes outside the report directory or
# reaches the network. Everything else fails with an instruction if the kit is
# missing, so a scheduled order can never pull code onto the machine on its own.
#
# Environment (set by gc): GC_CITY_PATH, GC_PACK_DIR, GC_PACK_NAME

set -euo pipefail

if [ -z "${GC_PACK_DIR:-}" ]; then
  echo "gc factory setup: missing Gas City pack context" >&2
  exit 1
fi

# shellcheck disable=SC1091
. "$GC_PACK_DIR/assets/scripts/kit.sh"

force=0
for arg in "$@"; do
  case "$arg" in
    --force) force=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "gc factory setup: unknown argument $arg" >&2; exit 64 ;;
  esac
done

if [ -n "${FACTORY_KIT_HOME:-}" ]; then
  cat >&2 <<MSG
gc factory setup: FACTORY_KIT_HOME is set to $FACTORY_KIT_HOME

Setup manages the city's own checkout at $(kit_default_dir). While the override
is set, that is not the checkout the other commands will use, so installing one
would be misleading. Unset FACTORY_KIT_HOME and re-run, or keep using your own.
MSG
  exit 2
fi

dest=$(kit_default_dir)

if [ -e "$dest" ] && [ "$force" -eq 0 ]; then
  at=$(git -C "$dest" rev-parse HEAD 2>/dev/null || printf 'not a git checkout')
  if [ "$at" = "$KIT_COMMIT" ]; then
    printf 'kit already at the pinned commit %s\n' "${KIT_COMMIT:0:12}"
    exit 0
  fi
  cat >&2 <<MSG
gc factory setup: $dest exists and is at $at

The pack pins $KIT_COMMIT. Re-run with --force to fetch and check out the pin.
MSG
  exit 3
fi

if [ ! -d "$dest/.git" ]; then
  mkdir -p "$(dirname "$dest")"
  git clone --quiet "$KIT_REPO" "$dest"
fi

git -C "$dest" fetch --quiet origin
# Fail here rather than land on some other commit: a kit that is not the pinned
# one produces findings the pack's own README cannot account for.
if ! git -C "$dest" cat-file -e "$KIT_COMMIT^{commit}" 2>/dev/null; then
  cat >&2 <<MSG
gc factory setup: $KIT_REPO has no commit $KIT_COMMIT

The pack's pin names a commit the remote does not carry. Either the pin is
ahead of what was published, or the remote is not the one the pin was written
against. Nothing was checked out.
MSG
  exit 4
fi
git -C "$dest" checkout --quiet --detach "$KIT_COMMIT"

printf 'kit %s installed at %s\n' "${KIT_COMMIT:0:12}" "$dest"
printf 'next: gc %s factory derive\n' "${GC_PACK_NAME:-factory-audit}"
