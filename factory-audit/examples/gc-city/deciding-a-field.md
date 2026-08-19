# Deciding a field

`derive` writes `unknown` into every field that is a decision, because a scan
cannot read one. This is what each of those decisions asks, where the answer
lives in a tree, and what each answer costs. Our own five effects are the
worked cases, including the two whose answer is bad.

The contract next to this file has the reasoning inline against each one, with
the command that would refute it. Read that for the argument; read this for the
shape of the question.

## `effect_identity`: what makes two attempts the same effect?

**The question.** A retry re-sends work. What does the destination look at to
tell "this is the thing I already have" from "this is a new thing"?

**Where the answer lives.** The call site. Read the arguments actually passed
to the outbound call, not the wrapper's signature: an identity that exists as a
parameter and is never filled at the call sites is not an identity. Ours was
exactly that for one effect, accepted and discarded at every site.

**What makes an answer bad.** An identity derived from the attempt rather than
from the work. Every retry mints a new one, so nothing can ever match, and the
field reads decided while deduplication is impossible. The checker warns on
this (`IDENT-002`) rather than failing, because the value is a real decision,
just a self-defeating one. The other trap is an identity built from something
mutable: a branch name, a ref, `latest`. It matches until someone moves it.

**Ours.** The merge effect uses `pr_head_sha`, the commit that was tested, so a
retry that finds the branch moved is correctly a different effect. The push
effect uses a triple that includes the intended commit oid, which is what the
readback compares, so the identity survives a force-update. The pull-request
effect prefers a marker written into the body, because that is durable across a
branch rename, and falls back to a triple that is only as stable as the naming
rule above it. That fallback is stated rather than hidden.

## `retry_contract`: what does the destination do with a repeat?

**The question.** Not what you would like it to do. What it does.

**Where the answer lives.** The destination's own documentation and behaviour,
not your code. Send the same thing twice in a scratch environment and look.

**The four answers.**

| Value | What it asserts |
| --- | --- |
| `deduplicate` | the destination refuses or collapses the second copy |
| `converge` | repeats are harmless because the operation sets a state rather than appending |
| `reconcile` | you read the destination back and act on what is actually there |
| `at_least_once` | repeats land, and both copies stay |

**What makes an answer bad.** Writing `deduplicate` because the destination
ought to. That is the one edit that turns this whole exercise into decoration:
a green line over a mechanism that does not exist. If repeats land, say
`at_least_once` and then say what a duplicate does to you; the checker requires
that second half (`EFFECT-005`) precisely so the bad answer cannot be recorded
as a shrug.

**Ours.** Two `reconcile`, one `deduplicate`, two `at_least_once`. The two
honest bad ones are the messaging effects, and their `duplicate_disposition`
fields say what a repeat costs: a second Slack message that nothing supersedes,
and a second instruction to an agent that has been observed re-running work it
had already finished.

## `unknown_state_policy`: what happens when you cannot tell?

**The question.** The call timed out, or the connection dropped after the
request went out. You do not know whether it landed. What does the factory do?

**Where the answer lives.** Your error handling, and be honest about the
default. A bare `except` that logs and continues is `assume_failure` if it
retries and `assume_success` if it moves on. Not deciding is deciding.

**The three sound answers** are `block_and_escalate`, `reconcile_then_block`
and `manual_review`. All three stop and surface. The two unsound ones are
writable on purpose, because a factory that guesses does not stop guessing when
a schema refuses the word, and `unknown` would then be indistinguishable from a
builder who never looked:

- `assume_success` loses the effect. If it did not land, nothing goes back to
  check and the work is silently dropped.
- `assume_failure` duplicates it. If it did land, the retry sends a second one.

Which cost you can carry depends on the destination, and that is the whole
decision. A duplicate Slack message is noise; a duplicate merge is not.

**Ours.** Three `block_and_escalate` on the code-host effects. The Slack effect
is `assume_failure` and the agent-nudge effect is `assume_success`, and both are
failures in our own score that we have not cleared.

## `instructed_call_sites`: how many routes are prose?

**The question.** Not a decision, a count, and the only field here a scan can
check. How many of the places that trigger this effect are sentences telling an
agent to run a command, rather than lines of code?

**Where the answer lives.** `reconcile` prints them. `review` cannot, because
it is handed a contract and never an installation.

**Why it matters.** An instructed route has no arguments until runtime, so no
static check can confirm it carries the identity. The count withdraws the
identity claim for those routes rather than ignoring them.

**Ours.** 34, 32, 18, 7 and 2. Five failures out of nine, and the largest
single reason our own score is not zero.

## Our five answers, as a table

Every value here is read out of `factory.yaml` beside this file, and a test
holds the two together.

| Effect | `retry_contract` | `unknown_state_policy` |
| --- | --- | --- |
| `git_push` | `reconcile` | `block_and_escalate` |
| `open_pull_request` | `reconcile` | `block_and_escalate` |
| `merge_pull_request` | `deduplicate` | `block_and_escalate` |
| `slack_publish` | `at_least_once` | `assume_failure` |
| `agent_mail_nudge` | `at_least_once` | `assume_success` |

Two of the ten cells are answers we are not happy with. They are in the file
because the alternative is a contract that describes a factory we do not have.
