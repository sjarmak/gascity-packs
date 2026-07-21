# Architecture diagram (LikeC4)

Architecture-as-code model of the author's own **gascity packs** — the Slack
intake family and the PR-discipline family — rendered with
[LikeC4](https://likec4.dev). This is a focused, authored-packs-only view: it
covers the five packs Stephanie Jarmak wrote (`slack-pack`, `slack-channel`,
`slack-mini`, `pr-pipeline`, `pr-review`) and nothing else in the catalog.

All of it layers on **gascity**, the multi-agent orchestrator: the Slack
adapters are `proxy_process` services gc supervises and bridges to sessions over
its extmsg bridge; the PR-discipline packs are gc formulas (and one skill
overlay) slung onto a rig on demand.

The model is the source of truth across [`spec.c4`](spec.c4) (element kinds,
tags, deployment node kinds), [`model.c4`](model.c4) (the system),
[`views.c4`](views.c4) (structure, walkthrough, and risk views), with the
deployment model in [`deployment.c4`](deployment.c4).

Every element `link`s to its real source path, relative to `architecture/`
(e.g. `../slack-pack/adapter/main.go`) — so any box in the explorer is one click
from the code behind it.

## Delivery state is tagged, not guessed

Every element carries a tag so **stubbed / experimental work renders distinctly
from what ships** (legend in `spec.c4`):

| Tag | Meaning | Render |
|---|---|---|
| `#built` | code path exists, is exercised, and ships | solid |
| `#evolving` | built, but the surface/contract is still moving | solid |
| `#planned` | designed; runtime path is still a stub | **dashed, dimmed** |
| `#research` | speculative track | **dashed, indigo** |

Planned / stubbed items in the model: slack-pack's room launcher (`@@<handle>`,
returns "not yet available") and `sync-commands` (slash-command registration is
manual today); slack-channel's interaction handler (signature-verify + ack
only); and pr-review's two vapor formulas (`mol-pr-from-issue`,
`mol-pr-iterate`).

## The five packs

| Container | Family | What it is |
|---|---|---|
| `slack-pack` | Slack | The rich provider — webhook adapter, HMAC verify, OAuth, event/interaction dispatch, rig + room launch, thread→session routing, Go CLI, extmsg scripts |
| `slack-channel` | Slack | Tier-2 channel bridge — bind a channel/DM to one-or-many sessions, per-session identities, `@handle` addressing; stdlib-only Go, three on-disk registries |
| `slack-mini` | Slack | Tier-1 minimal bridge — `@`-mention → mayor, one outbound verb; single-file, stateless |
| `pr-pipeline` | PR discipline | Author-side: issue → plan → blast-radius → self-review → pre-push ship gate, plus triage; gc formulas + commands |
| `pr-review` | PR discipline | Maintainer-side: adopt → multi-model review (`/review-pr`) → resolve a merge path; gc formulas + a skill overlay |

The three Slack packs are **tiered alternatives** — pick exactly one per city;
the upgrade path preserves the same bot token + signing secret.

## Views

**Structure** — the static map:

| View | Scope |
|---|---|
| `index` | system landscape — the five packs in context of gascity, Slack, GitHub, review models |
| `packsSystem` | the system decomposed into its five pack containers |
| `slackPackView` | slack-pack components (adapter, HMAC, OAuth, dispatch, routing, CLI, scripts) |
| `slackChannelView` | slack-channel components (signature, inbound/outbound, registries) |
| `slackMiniView` | slack-mini components (single-file adapter, minimal manifest) |
| `prPipelineView` | pr-pipeline components (commands + the five formulas + template) |
| `prReviewView` | pr-review components (mol-adopt-pr, /review-pr skill, merge/diagnose/revert, vapor formulas) |
| `planned` | the stubbed + vapor work, with built dependencies dimmed |
| `deployment` | where each pack runs — three supervised adapters + on-demand formula sessions |

**Walkthrough flows** (dynamic / numbered-step views) — the narrative spine:

| View | Flow |
|---|---|
| `slackInbound` | a Slack message arrives → HMAC verify → thread→session resolve → extmsg → session |
| `slackRigDispatch` | a rig slash-command → modal context → bead spawn → gc sling |
| `prShipFlow` | author-side: issue → plan → blast-radius → ship gate (stops at a readiness report) |
| `prAdoptFlow` | maintainer-side: incoming PR → /review-pr fan-out → human-gate → merge path |

**Risk lens:**

| View | Scope |
|---|---|
| `risks` | the `#risk`-flagged elements with each open question stated in-box (dispatch-drop silent loss, the two pr-review vapor formulas) |

### Running the walkthrough

For a review, present in this order: `index` → `packsSystem` (orient on
structure) → the per-pack component views → the four walkthrough flows (what
actually happens) → `deployment` (where it runs) → `risks` (what to probe) →
`planned` (what's still a stub). In `npx likec4 start`, the dynamic views animate
step-by-step.

## Viewing & regenerating

```bash
# Interactive, hot-reloading explorer (recommended)
npx likec4 start architecture

# Validate the model (strict — the source of truth for correctness)
npx likec4 validate architecture
```
