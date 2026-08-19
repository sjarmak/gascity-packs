# A worked contract for a Gas City, with its failures left in

`factory.yaml` here is the real contract for the city this pack was written
against, copied out of that city with absolute paths replaced by placeholders
and nothing else changed. It is 1,171 lines and it fails.

## Why a failing example

`derive` reads your installation and writes a contract in which every
`effect_identity`, `retry_contract` and `unknown_state_policy` says `unknown`.
That is honest: those three are decisions about how your factory should behave
when an outbound action's outcome is not known, and no static scan can read a
decision. It is also where most people stop, because a file of `unknown` gives
no picture of what a decided field looks like.

This one has the answers, with the reasoning next to each, and it still has
nine failures. Both halves matter. A contract you can copy is worth less than
a contract you can argue with.

**Do not copy the decided values into your own contract.** Declaring
`deduplicate` for an effect whose code does not deduplicate produces a green
line over a broken mechanism, which is the failure the checker exists to
catch. Every decided field here is a claim about that city's code, checkable
by the command written beside it. Read them, run the equivalent against yours,
then write your own answer.

## The score, and what each failure is

Run `factory_check review examples/gc-city/factory.yaml` and you get
`9 FAIL, 5 WARN`.

### Failures

| Rule | Where | Why it is still open |
| --- | --- | --- |
| `IDENT-001` | `work` | No per-attempt identifier exists anywhere on that city's work path. A retry cannot tell its own attempt apart from the one before it. The field stays `unknown` because the city does not have the thing, and declaring a name for it would be the lie described above. |
| `AUTH-001` | `work.ownership` | Same shape: no ownership generation, so a stale holder that wakes after a reclaim is fenced by nothing. The neighbouring `lease_expiry` names a real column, which is worth noticing, because the rule passes on a field name while that mechanism sits mostly unused. |
| `EFFECT-003` ×2 | `effects[3]`, `effects[4]` | Two effects declare a policy for an unknown outcome that the rule refuses: one assumes failure, which can send a second copy; the other assumes success, which can drop the work silently. Both are deliberate and both are wrong in the rule's terms, which is the correct reading. |
| `EFFECT-006` ×5 | every effect's `instructed_call_sites` | Every one of the five effects is triggered somewhere by a sentence in an agent's prompt rather than a line of code, so no static check can bind an identity to those routes. Five effects, five failures. |

`EFFECT-006` is the one to expect if your factory is agent-driven, and it is
the one worth understanding before you try to clear it. A count of instructed
call sites is not a defect list. It includes instructions that exist to
*forbid* the command, so writing a ban into a prompt raises the number: a
factory with no written policy scores better than one with a policy. Clearing
it by deleting the count switches the rule off. `reconcile` prints the lines,
sorted, so you can see which yours are.

### Warnings

`RECON-002` (no running-session fact, so a retry cannot attach to work already
in flight and relaunches blind), `FLEET-001`, `FLEET-002` and `FLEET-003` (no
recovery ceiling, no reserved interactive capacity, no fairness levels), and
`OBS-001` (a declared observability promise with nothing emitting it).

Warnings do not gate. They are the shape of the next argument, not a queue.

## A field that passes, over a mechanism that does not run

`work.ownership.lease_expiry` names `lease_expires_at` and the checker accepts
it. The comments beside it record what the store actually holds: nine leases
ever taken, eight of them expired days ago, against 1,557 issues. AUTH-001 is
red here for the other half of the same rule, the claim generation, which has
nothing to do with the lease. Clear the generation and this rule goes green over
a lease almost nothing takes.

That is the limit of a checker that reads a description, and the pack README
states it under "A decided field is not a live mechanism". It is also why this
example ships with its measurements in the comments. The numbers are the part
the rule cannot see.

## How to read a decided field

Each one carries what it asserts about the code and how to check it. From the
merge effect:

```yaml
    effect_identity: pr_head_sha
    retry_contract: deduplicate
    unknown_state_policy: block_and_escalate
```

The first says the merge is identified by the commit that was tested, so a
retry that finds the branch moved is a different effect and not a repeat. The
second says the destination refuses a second merge of the same head. The third
says an ambiguous outcome stops the chain rather than guessing. Change any one
of them and you are describing a different factory, not a tidier file.
