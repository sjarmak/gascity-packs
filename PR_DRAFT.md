## Summary

Imports the Slack pack as a top-level pack in `gastownhall/gascity-packs`,
matching the shape of the existing `discord` and `pr-review` packs.
The pack ships its operator CLI verbs as a second in-pack Go binary
(`cli/gc-slack-cli`), invoked by the `commands/<cmd>.sh` wrappers, so
the operator surface (`gc slack <cmd>`) lives entirely pack-side with
no `gastownhall/gascity` binary changes required.

## Context

The pack was developed in-tree on a working branch at
`gastownhall/gascity@polecat-relocation-slack-cli` (epic `gc-coe10`).
That work shaped it into a self-contained pack — separate Go modules
for the adapter and cli, bash wrappers, no imports back into the
gascity tree. This PR carries the result over to gascity-packs without
modification beyond pack-relative path adjustments.

There is **no companion PR in gastownhall/gascity** required for this
to ship. Upstream gascity main has no Slack code today, so consumers
just import this pack the same way they import `discord` or
`pr-review`. The operator surface (`gc slack <cmd>`) is provided by
the pack's wrappers + cli binary; the gascity binary itself stays
slack-agnostic.

## What's in this PR

Three commits on `feat/import-slack-pack`:

- `84a321b` **import(slack-pack): plant slack-pack from gastownhall/gascity@abe34fae** (`gc-ejp.1`)

  Pristine copy of `examples/slack-pack/` from the gascity working
  branch, via `git archive | tar --transform`. 153 files; no edits in
  this commit.

- `ed55e4c` **fix(slack-pack): trim pack.toml header to match neighbor-pack conventions** (`gc-ejp.2`)

  The `[pack]` / `[[service]]` blocks already matched discord. The
  comment header was stale ("Status: scaffold (this session). Mirrors
  the structure of the upstream..." plus stale Implemented / Not Yet
  Implemented checklists). Trimmed to a discord-style short header
  describing the pack's two binaries (adapter + cli).

- `97fd5a7` **docs(slack-pack): replace `examples/slack-pack/` path refs with pack-relative paths** (`gc-ejp.2`)

  Nine files had `examples/slack-pack/` mentions in comments and
  docstrings. None operational — `tests/test_manifest.py` already
  uses `pathlib.Path(__file__).resolve().parent.parent` for path
  resolution. Replaced descriptive strings with pack-relative paths
  (`manifest/app.json (pack-relative)`,
  `schema/<X>.schema.json (pack-relative)`,
  `adapter/ (pack-relative)`). Also updated two adapter docstrings
  to reference the cli equivalents instead of the deleted
  `cmd/gc/slack_*.go` paths.

Top-level pack contents (153 files):

```
slack-pack/
├── pack.toml
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── .gitignore
├── adapter/        Slack-side HTTP/UDS bridge (Go module: gc-slack-adapter)
├── cli/            Operator CLI verbs (Go module: gc-slack-cli)
├── commands/       gc slack <cmd> wrappers (.sh + command.toml + help.md)
├── docs/
├── manifest/       Slack app manifest (the OAuth contract)
├── schema/         JSON schemas for on-disk registries
├── scripts/        Python shim scripts (bind-dm, publish, react, status, ...)
├── template-fragments/
└── tests/          pytest coverage for the python scripts
```

## How reviewers can try it out

This PR is self-contained: anyone on upstream `gastownhall/gascity`
main can stand the pack up locally. Two paths depending on whether
you're wiring it into a real Slack workspace or just exercising the
cli verbs.

### Path A — smoke the cli + adapter without Slack

Build both in-pack binaries and exercise `gc-slack-cli --help`:

```bash
git clone -b feat/import-slack-pack \
    https://github.com/sjarmak/gascity-packs.git
cd gascity-packs/slack-pack

# Build the operator cli (used by commands/*.sh wrappers)
( cd cli && go build -o gc-slack-cli . )

# Build the slack adapter (proxy_process service)
( cd adapter && go build -o gc-slack-adapter . )

# Quick verify
./cli/gc-slack-cli --help                      # cobra help, lists 6 verbs
./adapter/gc-slack-adapter --help              # adapter usage
python3 -m pytest tests/                       # 57 tests, all PASS
( cd cli && go test -race ./... )              # 8 packages, all PASS
( cd adapter && go test ./... )                # adapter tests PASS
```

### Path B — wire it into a gas-city for end-to-end Slack

Add the pack to your city's `city.toml` and provision the adapter env:

```bash
# In your city directory's city.toml, add (or update):
cat >> city.toml <<'EOF'

[imports.slack]
source = "/path/to/your/clone/of/gascity-packs/slack-pack"
EOF
```

Provision adapter secrets (the adapter needs Slack credentials and a
gc API base URL). Drop a file at
`~/.config/gc-slack-adapter/env` with at minimum:

```
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
SLACK_WORKSPACE_ID=T0...
GC_API_BASE_URL=http://127.0.0.1:8372    # supervisor mode; or 9443 for legacy
GC_CITY_NAME=<your-city-name>
LISTEN_PUBLIC=:8775                      # port the adapter binds for Slack events
```

Then make the supervisor source it:

```ini
# /home/<you>/.config/systemd/user/gascity-supervisor.service.d/slack-adapter-env.conf
[Service]
EnvironmentFile=-/home/<you>/.config/gc-slack-adapter/env
```

Restart supervisor; the slack `[[service]]` will spawn the adapter as
a `proxy_process` and the operator verbs (`gc slack post-message`,
`gc slack map-rig`, ...) become available immediately.

> Known footgun (separate from this PR): on every supervisor restart
> the adapter races the city-running flag and may exit before
> registering. Symptom is `register adapter: register failed: 404
> not_found: city not found or not running` in
> `<city>/.gc/services/slack/logs/service.log`. Fix until upstream
> retries: `curl -sS -X POST -H "X-GC-Request: 1" \
> "http://127.0.0.1:8372/v0/city/<city>/service/slack/restart"`.

### Verbs available

Six operator verbs ported from cmd/gc + ten existing Python wrappers
already in the pack:

```
# Go-port verbs (now via cli/gc-slack-cli)
gc slack post-message --channel <C> --kind milestone ...
gc slack import-app --manifest manifest/app.json
gc slack sync-commands --workspace-id <T>
gc slack map-channel <C> --session <name>
gc slack map-rig <rig> --workspace-id <T> --channel <C>
gc slack enable-room-launch <C>

# Python wrappers (unchanged)
gc slack identity / publish / publish-to-channel / react /
       reply-current / bind-dm / bind-room / handle-alias /
       upload / status / retry-peer-fanout
```

## Test plan

- [x] `cd slack-pack/cli && go build ./...` clean
- [x] `cd slack-pack/cli && go vet ./...` clean
- [x] `cd slack-pack/cli && go test -race ./...` (8 packages, all PASS)
- [x] `cd slack-pack/cli && go mod tidy` no-op (no diff)
- [x] `cd slack-pack/adapter && go build ./...` clean
- [x] `cd slack-pack/adapter && go vet ./...` clean
- [x] `cd slack-pack/adapter && go test ./...` PASS (full -race suite)
- [x] `python3 -m pytest slack-pack/tests/ -x` (57 tests across 7 files PASS)
- [x] `cd slack-pack/cli && go install .` succeeds; binary runs (`gc-slack-cli --help`)
- [x] All six `commands/<cmd>.sh` wrappers smoke-pass against
      `gc-slack-cli --help` (import-app, map-channel, map-rig,
      post-message, sync-commands, enable-room-launch)
- [x] No `gastownhall/gascity` Go imports anywhere in the pack
- [x] No remaining `examples/slack-pack/` path references
- [x] End-to-end smoke against a live Slack workspace: `@mayor: ping`
      from a Slack channel routes to the bound mayor session and a
      `gc slack publish-to-channel` reply lands threaded under the
      original message (verified 2026-05-06 in dogfood mode against
      a `ds-research` city wired to point `[imports.slack].source` at
      this branch's slack-pack tree).

## Out of scope

- Tagging a `slack-pack@v0.1.0` release (this is the working baseline;
  consumers can pin to the merge commit until then).
- Auto-retry of the adapter's registration POST on
  `404 city-not-running` (lives in `adapter/main.go` —
  separate adapter-side PR).
- Reaper sweep of stale `state=creating` session beads in gascity
  (separate gascity-side issue, unrelated to slack-pack).
