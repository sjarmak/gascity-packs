#!/usr/bin/env bash
# gc <binding> factory derive — read this installation and write what it does.
#
# Two steps, both read-only against the city:
#
#   probes-init   scan the tree for outbound-effect call sites and scaffold a
#                 probe pack naming where each effect is performed
#   infer         run those probes and report, per effect, whether the call
#                 sites actually carry an identity a retry could dedupe on
#
# The output is a description of the installation, not a decision about it.
# `gc factory reconcile` is what compares it to a contract you wrote.
#
# Environment (set by gc): GC_CITY_PATH, GC_PACK_DIR, GC_PACK_NAME

set -euo pipefail

if [ -z "${GC_PACK_DIR:-}" ]; then
  echo "gc factory derive: missing Gas City pack context" >&2
  exit 1
fi

# shellcheck disable=SC1091
. "$GC_PACK_DIR/assets/scripts/kit.sh"

need_operand() {
  # Under `set -u` a bare $2 aborts with bash's own message and exit 1, so a
  # typo in a flag reads as an internal error rather than as bad input.
  if [ "$#" -lt 2 ]; then
    printf '%s: %s needs a value\n' "$0" "$1" >&2
    exit 64
  fi
}


city=${GC_CITY_PATH:-$PWD}
out="$city/.gc/factory-audit"
probes="$out/probes.yaml"
rewrite=0
template=""
extra=()

while [ $# -gt 0 ]; do
  case "$1" in
    --rewrite-probes) rewrite=1 ;;
    --template) need_operand "$@"; template=$2; shift ;;
    --exclude) need_operand "$@"; extra+=(--exclude "$2"); shift ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "gc factory derive: unknown argument $1" >&2; exit 64 ;;
  esac
  shift
done

kit_require

mkdir -p "$out"
kit_banner

# A probe pack is a starting point that gets HAND-EDITED: the scaffold finds
# candidate call sites and guesses the flag that would carry an identity, and
# only a person can say which guesses are right. So it is written once and then
# left alone. Overwriting it on every run would silently discard that work,
# which is the whole reason --rewrite-probes has to be asked for.
if [ -n "$template" ]; then
  source_file="$GC_PACK_DIR/templates/$template-probes.yaml"
  if [ ! -f "$source_file" ]; then
    printf 'gc factory derive: no template %s\n\n' "$template" >&2
    printf 'Available:\n' >&2
    for candidate in "$GC_PACK_DIR"/templates/*-probes.yaml; do
      [ -e "$candidate" ] || continue
      name=${candidate##*/}
      printf '  %s\n' "${name%-probes.yaml}" >&2
    done
    exit 64
  fi
fi

if [ ! -f "$probes" ] || [ "$rewrite" -eq 1 ]; then
  if [ -f "$probes" ]; then
    cp "$probes" "$probes.$(date -u +%Y%m%dT%H%M%SZ).bak"
    printf 'kept your previous probes.yaml alongside the new one (.bak)\n'
  fi
  if [ -n "$template" ]; then
    cp "$source_file" "$probes"
    printf 'probes: %s (from the %s template)\n' "$probes" "$template"
    printf 'Edit factory_name and check the include globs against your layout.\n'
  else
    kit_run probes-init "$city" --write "$probes" "${extra[@]+"${extra[@]}"}"
  fi
elif [ -n "$template" ]; then
  # Refusing rather than overwriting: --template on an existing probe pack is
  # most likely someone re-running the setup line from the README, and their
  # hand-edits are the expensive part of this file.
  printf 'gc factory derive: %s already exists; --template will not overwrite it\n' \
    "$probes" >&2
  printf 'Add --rewrite-probes to replace it (your version is kept as a .bak).\n' >&2
  exit 3
else
  printf 'probes: %s (kept; --rewrite-probes to re-scaffold)\n' "$probes"
fi

kit_run infer "$city" --probes "$probes" \
  --out "$out" --write "$out/factory.derived.yaml" | tee "$out/derived.txt"

cat <<MSG

wrote $out/factory.derived.yaml   what this installation actually does
      $out/evidence.json          the call sites behind every line of it
      $out/derived.txt            the same reading in prose

The derived contract is a description, not a target. Copy the lines you agree
with into your own factory.yaml, argue with the ones you do not, then run
  gc $(gc_binding) factory reconcile
to see where the two disagree.
MSG
