# gc <binding> audit

Run the rule catalog against the contract you maintain.

## Usage

```bash
gc <binding> audit [--contract <path>] [--strict] [--require-verified]
```

Defaults to `<city>/.gc/factory-audit/factory.yaml`. Writes `audit.txt` and
`findings.json` next to it, and exits nonzero when any rule FAILs. `--strict`
also exits nonzero on WARN.

## What it cannot tell you, and how it now says so

Audit reads only the contract. A contract asserting that every effect is
idempotent and every gate enforced scores perfectly whether or not any of that
is true, which is exactly how a reliability document becomes a liability.

`gc <binding> reconcile` is the half that checks the claims against the
code, and it leaves a receipt in `reconcile.receipt`. Audit reads that receipt
and prints one line above and below the score:

| verification | what it means |
| --- | --- |
| `NONE` | no reconcile has ever run against this contract |
| `STALE` | the contract or the probe pack changed after the last reconcile |
| `DRIFTED` | the last reconcile found the code contradicts this contract |
| `ERRORED` | the last reconcile did not complete |
| `VACUOUS` | the last reconcile found no drift and confirmed nothing |
| `CONFIRMED` | the last reconcile compared this exact contract and found no drift |

`DRIFTED` exits **4** even when every rule passes. A clean number over a
document the installation contradicts is the claim this pack exists to stop
anyone making, including you. `NONE`, `STALE`, `ERRORED` and `VACUOUS` keep the
findings' own exit code by default; `--require-verified` makes them exit 4 as
well, which is the setting for a CI job that should refuse an unchecked
contract.

`VACUOUS` is the quiet half of `DRIFTED` and it is the state a new contract
lands in. Reconcile exits 0 when nothing contradicts the contract, and a
contract that leaves every effect undecided has nothing to contradict, so it
exits 0 while confirming nothing. Reading only that exit status turns an
unchecked document into a verified one, which is this pack's own failure mode
wearing its own badge. The receipt records the counts, so audit can tell the
two zeroes apart: no drift found, and nothing checked.

The receipt is matched on the SHA-256 of the contract and of the probe pack, not
on their paths. Editing the contract after a clean reconcile moves it back to
`STALE`, which is the case the whole mechanism exists for.
