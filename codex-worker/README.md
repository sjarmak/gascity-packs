# codex-worker

Durable, named Codex coding workers that project leads delegate to by name.

A lead routes a bead to `<worker-name>`. It picks the bead up on its next turn, does the
work in its own worktree, and reports. Next week the lead routes another one to
`<worker-name>`, and it is the same conversation: what it learned about the codebase is
still there.

No Go ships here. Every mechanism already exists in the SDK; this pack is the
composition and the arguments for the settings it picks.

## Install

```toml
# city.toml
[imports.codex-worker]
source = "../packs/codex-worker"

[[named_session]]
name     = "<worker-name>"
template = "codex-worker.coder"
mode     = "always"
```

One `[[named_session]]` per worker. Declare as many as you have lead capacity
for.

**Choose the name deliberately.** In a city that keeps an agent roster, a named
seat with durable identity gets a roster entry, and by convention that entry is
self-authored by the seat and amended only by it. Do not reuse an existing seat's
name for a new worker, and do not pre-write a roster entry on a worker's behalf.
The pack's job is only to leave that possible: give the worker a workspace from
which it can read and amend its own entry.

Verify before relying on it:

```
gc config show | grep -A6 'name = "<worker-name>"'
```

## Why named, not pooled

A pool instance is interchangeable by design: it routes on its pool name, not
its own, and its conversation is disposable. That is right for fan-out and wrong
for a colleague you delegate to repeatedly. `mode = "always"` gives the worker a
stable public identity the controller keeps alive, which is what makes "route it
to <worker-name>" mean a particular worker with particular accumulated context.

The pack also ships `coder-pool` for genuine fan-out, so choosing a pool stays a
decision rather than an accident.

## The failure this pack is built around

Codex exposes no session-id flag and no fork verb to the SDK. Its resume key can
arrive by exactly one route: the SessionStart hook's stdin. If that hook is
missing, drifted, or user-owned, the key is never captured, and `BuildResumeCommand`
falls through to a cold start:

```go
// internal/session/manager.go
if info.ResumeCommand != "" && info.SessionKey != "" { ... }   // explicit path
if info.ResumeFlag == "" || info.SessionKey == "" { return info.Command }  // cold
```

Both branches require a non-empty `SessionKey`. So a worker declared
`wake_mode = "resume"` with a hand-written `resume_command` will still silently
start a fresh conversation if the key was never captured. It runs, it answers,
and it has forgotten everything. Recorded intent, never read back as outcome.

`GC_PROVIDER_SESSION_ID_REQUIRED = "1"` in the agent's env turns that silence
into a startup error. **Do not remove it to quiet a noisy start.** A worker that
cannot resume is not this pack's worker, and you want to hear about it at start
rather than discover it several delegations later.

To confirm a worker is actually warm rather than trusting the config:

```
gc session show <worker-name> --json | grep session_key   # must be non-empty
```

Empty means every wake has been cold no matter what `wake_mode` says.

## Verification belongs to the dispatcher

Do not treat a worker's own green report as evidence. Measured on this fleet,
2026-08-09, delegating one bug to Codex twice:

- **Round 1** returned a patch that compiled, passed `go vet`, and called real
  helper functions. It fixed nothing. It had been sandboxed away from the Go
  build cache and the parent repo's `.git`, so no gate it reported had run. It
  said so, and the report still read as credible.
- **Round 2** returned a working fix plus an undisclosed edit to unrelated
  production code, and a self-report containing a 0.087s run for tests that take
  4s, a "no leak" claim for a case that must leak, and a mutation check where
  reverting the fix did not bring the bug back.

Both were caught by re-running the gates, neither by reading the report. So the
lead re-runs them:

```
go test ./<pkg>/ -run '<the tests>' -count=1    # read the TIMINGS, not just exit
go vet ./<pkg>/ && make lint
git -C <worktree> status --short                 # scope escapes show up here
git -C <worktree> log --oneline <base>..HEAD
```

`git status` is the cheap one and it is the one that caught the undisclosed
edit. Run it every time.

This is also why the worker gets `permission_mode = "unrestricted"`. Codex's
`--full-auto` sandbox blocks the Go build cache, the parent `.git`, and socket
operations, so a worker under it cannot compile, commit, or run a store-backed
test; it can only produce unverified confidence. Widening the sandbox per-run
fixes the first two and not sockets. Until the profile can describe a workspace
covering a worker's real toolchain, the honest arrangement is a worker that can
actually run its gates plus a dispatcher that re-runs them.

## Known sharp edges

- **`MaxSessionAge` will restart a worker meant to persist.** Unset for these
  agents unless your provider needs periodic token refresh. Restart is
  idle-gated and jittered, so it will not look like a crash.
- **`.codex/hooks.json` is content-hashed when staged**, unlike Claude's
  path-only fingerprint. Rewriting it drains live Codex sessions. Expect a
  worker restart after any hook change, and re-check `session_key` afterwards.
- **`CODEX_HOME` is where resume transcripts live.** Workers sharing one
  `CODEX_HOME` share a session store. If you run several named workers on one
  host, isolate it per worker before assuming their histories are independent.
- **No turn-completion signal is consumed.** There is a durable marker for
  interrupts but nothing reads a turn-finished event, so a worker cannot yet
  reliably report "done" without something watching. Delegate work that ends in
  a committed branch, which is observable, rather than work that ends in an
  announcement.
