#!/bin/sh
# gc <binding> pr review — sling a coding agent the mol-pr-review formula
# to self-review an outgoing PR against an 11-category scorecard.
#
# Usage:
#   gc <binding> pr review <pr-number-or-url> [--rig <name>] [--agent <name>]
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
    pr_die review "missing Gas City pack context" 1
fi

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ] || [ -z "${1:-}" ]; then
    pr_help review
    [ -z "${1:-}" ] && exit 2 || exit 0
fi

PR="$1"
shift

# Accept bare integer or full URL of the form https://github.com/<owner>/<repo>/pull/<integer>.
case "$PR" in
    https://github.com/*/pull/*)
        # Verify the segment after /pull/ is a positive integer (strip any
        # trailing /files, ?query, or #fragment).
        PR_NUM="${PR##*/pull/}"
        PR_NUM="${PR_NUM%%/*}"
        PR_NUM="${PR_NUM%%\?*}"
        PR_NUM="${PR_NUM%%#*}"
        case "$PR_NUM" in
            ''|*[!0-9]*)
                pr_die review "PR URL must end in /pull/<integer> (got: $PR)" 2
                ;;
        esac
        ;;
    *[!0-9]*)
        pr_die review "<pr> must be a positive integer or a GitHub PR URL (got: $PR)" 2
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
            pr_die review "unknown argument: $1" 2
            ;;
    esac
done

if [ -z "$RIG" ]; then
    RIG="${GC_RIG:-}"
fi

if [ -z "$RIG" ]; then
    pr_die review "--rig <name> required (or set GC_RIG)" 2
fi

if ! command -v gc >/dev/null 2>&1; then
    pr_die review "gc binary not in PATH" 1
fi

exec gc sling "$RIG/$AGENT" mol-pr-review --formula --var "pr=$PR"
