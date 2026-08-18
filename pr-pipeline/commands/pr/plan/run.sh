#!/bin/sh
# gc <binding> pr plan — sling a coding agent the mol-pr-start formula.
#
# Usage:
#   gc <binding> pr plan <issue-number> [--rig <name>] [--agent <name>]
#
# Environment (set by gc):
#   GC_CITY_PATH   absolute city root
#   GC_PACK_DIR    absolute pack directory
#   GC_PACK_NAME   pack name ("pr-pipeline")
#   GC_CITY_NAME   city workspace name
#   GC_RIG         current rig (when running inside a rig session)

set -eu

. "$(dirname "$0")/../../_lib.sh"

if [ -z "${GC_PACK_DIR:-}" ]; then
    pr_die plan "missing Gas City pack context" 1
fi

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ] || [ -z "${1:-}" ]; then
    pr_help plan
    [ -z "${1:-}" ] && exit 2 || exit 0
fi

ISSUE="$1"
shift

case "$ISSUE" in
    ''|*[!0-9]*)
        pr_die plan "<issue> must be a positive integer (got: $ISSUE)" 2
        ;;
esac

RIG=""
AGENT="polecat"

while [ $# -gt 0 ]; do
    case "$1" in
        --rig)        RIG="$2"; shift 2 ;;
        --rig=*)      RIG="${1#--rig=}"; shift ;;
        --agent)      AGENT="$2"; shift 2 ;;
        --agent=*)    AGENT="${1#--agent=}"; shift ;;
        *)
            pr_die plan "unknown argument: $1" 2
            ;;
    esac
done

if [ -z "$RIG" ]; then
    RIG="${GC_RIG:-}"
fi

if [ -z "$RIG" ]; then
    echo "pr-pipeline pr plan: rig is required." >&2
    cat >&2 <<'EOF'

Pass --rig <name> or run inside a rig session where GC_RIG is set.

The planner formula needs to run inside a rig's git worktree to read the
issue and produce the structured plan. Pick the rig whose repository
contains the issue's code.

EOF
    pr_hint plan
    exit 2
fi

if ! command -v gc >/dev/null 2>&1; then
    pr_die plan "gc binary not in PATH" 1
fi

exec gc sling "$RIG/$AGENT" mol-pr-start --formula --var "issue=$ISSUE"
