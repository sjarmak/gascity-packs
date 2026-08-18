# gc factory reconcile

Check the contract against the installation it describes.

## Usage

```bash
gc <binding> factory reconcile [--contract <path>] [--probes <path>]
```

Runs the probe pack against the real tree and compares what it finds to what
the contract claims.

| Verdict | Meaning |
| --- | --- |
| `DRIFT` | the contract claims an identity the call sites do not carry |
| `UNDECLARED` | the installation performs an effect the contract omits |
| `unverified` | the contract says nothing; the call sites do carry an identity |
| `confirmed` | contract and call sites agree |
| `open` | neither the contract nor the code settles it |

Exits nonzero on `DRIFT` or `UNDECLARED`. Both mean the document is wrong about
what the machine does, and a safety document that is wrong is worse than none.

## Why `open` is a verdict and not a failure

Some effects have no identity to look for because nobody has decided what one
would be. Reporting that as a failed search would be a false reading — the
search never had a target. It is a question for a person, counted separately,
and it stays on the list until someone answers it.

## Reading a DRIFT you disagree with

Reconcile is not always right about your code. It binds identities to
*scripted* call sites — a line a static check can read. An effect performed by
an agent following a sentence in a formula has no argv until runtime, and no
matcher can bind it. Those are reported as instructed sites and left out of the
identity verdict rather than counted as missing, because a missed call site
confirms an identity that does not hold, and that is the direction that lies.
