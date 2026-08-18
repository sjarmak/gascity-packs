#!/bin/sh
# gc <binding> post-message — post plain text to a Slack channel/thread.
#
# Tier 1 has no operator CLI binary: this wrapper relays to the running
# slack-mini adapter through gc's /svc/slack-mini reverse proxy. The
# adapter holds SLACK_BOT_TOKEN and calls Slack chat.postMessage, so the
# token never has to be present in the command environment.
#
# Usage:
#   gc <binding> post-message --channel C0123 --text "build is green"
#   gc <binding> post-message --channel C0123 --thread-ts 1700000000.0001 \
#       --text "follow-up in thread"
set -eu

PACK_DIR=${GC_PACK_DIR:-$(cd "$(dirname "$0")/.." && pwd)}

# gc_binding prints the word a user types after `gc` to reach this pack, or
# the literal `<binding>` when that cannot be determined. See
# assets/scripts/gc_binding.py for why a placeholder beats a guess.
gc_binding() {
  if _gc_binding_name=$(python3 "$PACK_DIR/assets/scripts/gc_binding.py" 2>/dev/null) \
     && [ -n "$_gc_binding_name" ]; then
    printf '%s' "$_gc_binding_name"
  else
    printf '<binding>'
  fi
}

# hint — the "how to read the help" line. Every failure prints it, not the
# ones whose text happens to read like a usage error: which error path an
# author was looking at is not a property a user can see.
hint() {
  echo "Run: gc $(gc_binding) post-message --help" >&2
}

# die MESSAGE [EXIT] — say which command failed, then how to read its help.
# The message deliberately does not start with `gc `: it names the failing
# command rather than something to type, which is what makes any `gc ` this
# pack prints an instruction that has to carry the binding.
die() {
  echo "slack-mini post-message: $1" >&2
  hint
  exit "${2:-2}"
}

channel=""
text=""
thread_ts=""

require_value() {
  # $1 = flag name, $2 = arg count remaining (including the flag itself)
  if [ "$2" -lt 2 ]; then
    die "$1 requires a value" 2
  fi
}

while [ $# -gt 0 ]; do
  case "$1" in
    --channel)    require_value "$1" "$#"; channel="$2"; shift 2 ;;
    --text)       require_value "$1" "$#"; text="$2"; shift 2 ;;
    --thread-ts)  require_value "$1" "$#"; thread_ts="$2"; shift 2 ;;
    --channel=*)   channel="${1#*=}"; shift ;;
    --text=*)      text="${1#*=}"; shift ;;
    --thread-ts=*) thread_ts="${1#*=}"; shift ;;
    -h|--help)
      sed 's/<binding>/'"$(gc_binding)"'/g' "$(dirname "$0")/post-message/help.md"
      exit 0
      ;;
    *)
      die "unknown argument: $1" 2
      ;;
  esac
done

if [ -z "$channel" ]; then
  die "--channel is required" 2
fi
if [ -z "$text" ]; then
  die "--text is required" 2
fi

api_base="${GC_API_BASE_URL:-http://127.0.0.1:9443}"
api_base="${api_base%/}"
city="${GC_CITY_NAME:-}"
if [ -z "$city" ]; then
  die "GC_CITY_NAME is not set" 1
fi

# Resolve the adapter endpoint: gc proxies /svc/slack-mini/* to the
# adapter's UDS. SLACK_MINI_ADAPTER_URL overrides for local testing.
url="${SLACK_MINI_ADAPTER_URL:-${api_base}/v0/city/${city}/svc/slack-mini/post-message}"

# Build the request body with jq so channel/text/thread_ts are correctly
# JSON-escaped (text may contain quotes, newlines, etc.).
body=$(jq -n \
  --arg channel "$channel" \
  --arg text "$text" \
  --arg thread_ts "$thread_ts" \
  '{channel: $channel, text: $text} + (if $thread_ts == "" then {} else {thread_ts: $thread_ts} end)')

# Capture status and body separately so the adapter's JSON error payload
# ({"ok":false,"error":...}) reaches the operator instead of being swallowed
# by `curl -f`. -w writes the HTTP status on its own trailing line.
response=$(curl -sS -X POST "$url" \
  -H 'Content-Type: application/json' \
  -H 'X-GC-Request: gc-slack-mini' \
  -d "$body" \
  -w '\n%{http_code}') || {
  echo "slack-mini post-message: request to adapter failed" >&2
  echo "$response" >&2
  hint
  exit 1
}

http_code=$(printf '%s\n' "$response" | tail -n1)
payload=$(printf '%s\n' "$response" | sed '$d')

printf '%s\n' "$payload"
case "$http_code" in
  2*) exit 0 ;;
  *)
    die "adapter returned HTTP $http_code" 1
    ;;
esac
