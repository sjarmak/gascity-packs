# gascity-packs

The pack ecosystem for [Gas City](https://github.com/gastownhall/gascity). Each top-level
directory is a _pack_: a configuration-only bundle of agents, commands, services, formulas,
skills, hooks, and template fragments that a city opts into by path-importing its `pack.toml`.
Packs compose through `[imports.<name>]` so a generic city becomes opinionated (Slack adapter,
GitHub/Discord intake, PR pipeline, jeffrey skills, rlm, tmux theme, flywheel) without forking
gascity. This repo's whole reason to exist is keeping that catalog growing while the
configuration-purity invariants below hold.

Issue tracker: bd (beads) — run `bd prime` for the workflow. Upstream is `gastownhall/gascity-packs`;
`origin` is the `sjarmak` fork.

## Don't

- **Don't put reasoning/policy logic in pack code (ZFC violation).** Pack scripts and binaries are
  plumbing — IO, schema validation, mechanical transforms. Semantic decisions (classification,
  quality judgments, planning) belong in formulas/prompts handed to a model, not in Python/Go.
- **Don't hardcode roles.** No pack may assume a specific agent role name (e.g. `polecat`, `mayor`).
  Formulas reference targets the consuming city supplies; `pr-review` explicitly ships no agent and
  documents that the consuming pack must provide the polecat.
- **Don't pull a private gascity SDK API into a pack's surface.** Packs are config-pure and must not
  depend on internals that aren't part of gascity's stable contract. If a pack needs a new capability,
  the fix usually belongs upstream in gascity, not smuggled into the pack.
- **Don't create cross-pack coupling.** Every pack must stay installable on its own. A change to one
  pack that breaks a sibling's standalone import is a regression, not a refactor.
- **Don't let a pack-surface change land without updating its README in the same PR.** Each pack's
  README is its contract; stale docs are a review blocker.
- **Don't tangle sibling packs in one change.** Scope a PR to one pack (plus shared docs). Tests ship
  in the same commit as the code they cover.

## Do

- Keep packs configuration-pure: a pack is `pack.toml` plus the assets it declares. Build artifacts
  (compiled Go binaries) live in the pack tree but are git-ignored and rebuilt per CONTRIBUTING.
- For packs with code, run their real gates before pushing: `python3 -m pytest tests/` for Python
  helpers; in `slack-pack` also `go test -race ./...` in both `adapter/` and `cli/`, plus `go vet ./...`.
- Author new packs to match an existing sibling's shape (see Layout). Provide a `doctor/` set of
  `check-*.sh` preflights for any external dependency the pack assumes (bd, gc, python, jq, openssl, docker).
- When deciding whether a feature belongs in a pack vs. gascity itself, treat the SDK boundary as a
  first-class design call — surface it rather than guessing.

## Pack anatomy

A `pack.toml` (schema 2) declares some combination of:

- `[[service]]` blocks (`proxy_process`) gc supervises — discord/github intake, slack adapter.
- `commands/<cmd>.sh` + `commands/<cmd>/{command.toml,help.md}` backing `gc <pack> <verb>`.
- `formulas/mol-*.formula.toml` — multi-step molecule workflows (pr-review, pr-pipeline, discord).
- `skills/<name>/SKILL.md` under an `overlay/.claude/` tree (jeffrey, flywheel subpacks).
- `template-fragments/*.template.md`, `[global]` session hooks (tmux-theme), `doctor/check-*.sh`.

A directory **with** `pack.toml` is itself an importable pack. A directory **without** one (e.g.
`flywheel/`, `jeffrey/`) groups related subpacks and ships an `all/` rollup that imports the group
as a unit.

## Layout

- `slack-pack/` — Slack provider: Go adapter (webhook receiver/publisher) + Go operator CLI + Python helpers.
- `discord/`, `discord-intake/` — Discord intake services + `gc discord` verbs + fix-issue formula.
- `github-intake/` — GitHub webhook intake service + admin service.
- `pr-review/` — maintainer-side incoming-PR review/merge formulas (`mol-adopt-pr`); no agent shipped.
- `pr-pipeline/` — author-side PR discipline formulas (`mol-pr-start|blast-radius|review|ship|triage`).
- `rlm/` — `gc rlm` ask/install/status CLI with a Docker runtime and Python scripts.
- `tmux-theme/` — `[global]` session-live hooks that theme tmux per agent/session.
- `jeffrey/` — skill-overlay subpacks (code-review, de-slopify, idea-wizard, planning, ui-polish, …) + `all/`.
- `flywheel/` — skill-overlay subpacks (cass search, cm recall/reflect, mcp-agent-mail, ubs scan-bugs) + `all/`.
- `.gc/project-brief.md` — the maintainer's intent, escalation triggers, and definition of "going well".
