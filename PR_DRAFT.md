## Summary

Imports the Slack pack as a top-level pack in `gastownhall/gascity-packs`,
matching the shape of the existing `discord` and `pr-review` packs.
The pack ships its operator CLI verbs as a second in-pack Go binary
(`cli/gc-slack-cli`), invoked by the `commands/<cmd>.sh` wrappers, so
operator command-line ergonomics (`gc slack <cmd>`) stay byte-identical
to the pre-extraction in-tree experience.

## Context

This pack lived in-tree at `gastownhall/gascity@examples/slack-pack/`
during its scaffold phase. Epic `gc-coe10`
([gascity#polecat-relocation-slack-cli @ abe34fae](https://github.com/gastownhall/gascity/tree/polecat-relocation-slack-cli))
prepped the extraction by:

1. Standing up a separate `examples/slack-pack/cli/` Go module
   (`github.com/sjarmak/gc-slack-cli`) with all six operator verbs
   ported from `cmd/gc/cmd_slack_*.go`.
2. Adding `examples/slack-pack/commands/<cmd>.sh` wrappers that
   `exec` the cli at `$GC_PACK_DIR/cli/gc-slack-cli`.
3. Cutover-deleting the cmd/gc-side Slack code (`cmd/gc/cmd_slack_*.go`
   + `cmd/gc/slack_*.go`).

This PR carries that work over into `gascity-packs/slack-pack/`. A
follow-up PR in `gastownhall/gascity` will delete `examples/slack-pack/`
from the gascity tree and update consuming `city.toml` files to import
this pack via:

```toml
[imports.slack]
source = "<path-to-gascity-packs>/slack-pack"
```

## What's in this PR

Three commits on `feat/import-slack-pack`:

- `84a321b` **import(slack-pack): plant slack-pack from gastownhall/gascity@abe34fae** (`gc-ejp.1`)

  Pristine copy of `examples/slack-pack/` from the gascity epic branch,
  via `git archive | tar --transform`. 153 files; no edits in this
  commit.

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

## Out of scope

These follow-ups land separately:

- Removing `examples/slack-pack/` from `gastownhall/gascity` (a
  follow-up PR in that repo)
- Updating consuming `city.toml` files to import this pack via
  `[imports.slack] source = "<path>/gascity-packs/slack-pack"`
- Tagging a `slack-pack@v0.1.0` release (this is the working baseline;
  consumers can pin to the merge commit until then)
