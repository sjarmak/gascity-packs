# Architecture diagram (LikeC4)

Architecture-as-code model of `gascity-packs`, rendered with
[LikeC4](https://likec4.dev). The model is the source of truth across
[`spec.c4`](spec.c4) (element kinds, tags, deployment node kinds),
[`model.c4`](model.c4) (the pack catalog), and [`views.c4`](views.c4)
(structure, walkthrough, and risk views), with the deployment model in
[`deployment.c4`](deployment.c4). The narrative companions are the repo-root
[`README.md`](../README.md), [`AGENTS.md`](../AGENTS.md) (the pack invariants),
and the maintainer's [`.gc/project-brief.md`](../.gc/project-brief.md).

`gascity-packs` is an opt-in **pack catalog** for the
[Gas City](https://github.com/gastownhall/gascity) orchestrator: configuration
bundles (chat/VCS adapters, PR-discipline formulas, skill overlays, a
long-context sidecar, session theming) that a city path-imports to become
opinionated without forking gascity. The heavyweight is **`slack-pack`** — two
Go binaries (a long-running webhook adapter gc supervises as a `proxy_process`,
and a one-shot operator CLI) plus Python helpers — modelled here at component
granularity. The smaller packs are modelled as containers, since each is a
configuration bundle rather than a code module.

Every element `link`s to its real source (`slack-pack/…`, `discord/…`,
`registry.toml`, …) so any box in the explorer is one click from the code.

## Delivery state is tagged, not guessed

Every element carries a tag so **planned and scaffold work renders distinctly
from what already ships** (legend in `spec.c4`):

| Tag | Meaning | Render |
|---|---|---|
| `#built` | code path exists, is exercised, and ships in a release | solid |
| `#evolving` | built, but the surface/contract is still moving (feature-by-feature port) | solid (amber) |
| `#planned` | designed; CLI side written, but the runtime path is still a stub | **dashed, dimmed** |
| `#research` | speculative future track | **dashed, indigo** |

The evidence is in the tree, not invented: `slack-pack` is `#evolving` because
its own README states it is "not yet at parity with the discord pack" and is a
feature-by-feature port. The `@@launcher` dispatch is `#planned`/`#risk`
because `double_handle_prefix.go` emits a "placeholder ephemeral" and the
README's *Not yet implemented* section lists the adapter-side `@@<handle>`
session spawn as the one remaining stub (deferred to the gc-cby epic). The
OAuth flow is `#evolving`/`#risk` (single-tenant by design, writes an
`install.env` the operator must still re-source). `discord-intake` is
`#planned`-styled as the superseded legacy of the `discord` pack. The shared
`extmsg-pack-lib` is `#research` — the README's "where the work that's still
missing comes from" note about extracting the provider-agnostic state machine.

## Views

**Structure** — the static map:

| View | Scope |
|---|---|
| `index` | system landscape — the catalog in context of gascity, Slack, Discord, GitHub, Funnel, the LLM backend |
| `packsSystem` | the `gascity-packs` system decomposed into its packs (built vs planned) |
| `slackPackContainer` | the Slack pack — adapter + CLI + Python helpers + service/doctor |
| `adapterContainer` | the `gc-slack-adapter` Go binary — HTTP/HMAC, dispatch, interactions, rig/room dispatch, registries, publish, OAuth, file store |
| `eventDispatchView` | the inbound event-dispatch fan-out (where the one `@@launcher` stub lives) |
| `cliContainer` | the `gc-slack-cli` operator binary — verbs + registry-state writers |
| `planned` | the `@@launcher` stub, OAuth, legacy discord-intake, and the research shared-lib, with built deps dimmed |
| `deployment` | where each piece runs — process & ingress boundaries (supervised adapter + UDS, one-shot CLI, Funnel, Slack, LLM) |

**Walkthrough flows** (dynamic / numbered-step views) — the narrative spine for
a design-review walkthrough:

| View | Flow |
|---|---|
| `inboundFlow` | a Slack message → bound session (Funnel → HMAC/dispatch → route → gc inbound) |
| `outboundFlow` | an agent reply → Slack with peer fanout (via gc `/extmsg/outbound` → supervised `/publish`) |
| `slashToWorkFlow` | a slash command in a rig channel → fix modal → `bd create` + `gc sling` |
| `setupFlow` | operator setup — CLI writes a registry JSON, SIGHUP reloads it live |

**Risk lens:**

| View | Scope |
|---|---|
| `risks` | the `#risk`-flagged elements with each open question stated in-box (`@@launcher` spawn still a stub; OAuth single-tenant + manual `install.env` re-source) |

### Running the walkthrough

For a design review, present in this order: `index` → `packsSystem` (orient on
the catalog) → `slackPackContainer` → `adapterContainer` (the heavyweight) →
the four walkthrough flows in sequence (what actually happens) → `deployment`
(where it runs) → `risks` (what to probe) → `planned` (what's next). In
`npx likec4 start`, the dynamic views animate step-by-step and each view's
notes panel carries the gotchas (the fail-closed publish guard, the
all-or-nothing SIGHUP reload, the Funnel-out-of-band foot-gun).

## Viewing & regenerating

```bash
# Interactive, hot-reloading explorer (recommended)
npx likec4 start architecture

# Re-export the static PNGs in exports/ (needs a one-time browser download:
#   npx playwright install chromium-headless-shell)
npx likec4 export png architecture -o architecture/exports

# Validate the model (strict — the source of truth for correctness)
npx likec4 validate architecture
```

### Viewing the interactive explorer over SSH (headless remote)

`likec4 start` serves a Vite dev server on `localhost:5173`. From a headless
remote, forward that port to your laptop and open it locally — three options,
easiest first:

1. **VS Code / Cursor Remote-SSH** — run `npx likec4 start architecture` in the
   integrated terminal; the editor auto-forwards 5173 and offers "Open in
   Browser". Nothing else to configure.
2. **SSH local port-forward** — on your laptop:
   ```bash
   ssh -N -L 5173:localhost:5173 user@remote   # leave running
   ```
   then on the remote `npx likec4 start architecture` and open
   <http://localhost:5173> locally. (Already in an SSH session? Add the tunnel
   without reconnecting: press `~C` then type `-L 5173:localhost:5173`.)
3. **Bind + reach directly** — `npx likec4 start architecture --listen 0.0.0.0`
   and browse to `http://<remote-ip>:5173` (only if that port is reachable /
   firewall-open; the tunnel in option 2 is safer).

No browser at all? Export the PNGs with `npx likec4 export png` (needs no
display) — `scp` them down, or view inline if your terminal supports images.
