# factory-audit changelog

This pack does not carry the checker; it pins one (`kit.pin`). So the entries
that matter to a city running it are the pin moves, and each one says what
changed in the kit and what a city sees differently because of it.

## Unreleased

### Kit pin moved to `ca66097` (from `37c873d`, 12 commits)

`docs(readme): the front page sent people to the hand-written contract`

The reason to move it: two of those commits fix things a city sees on its
*first* run, and neither could be found on the installation the kit was written
against.

- **`gc factory derive` printed a fix list for an identity nobody declared.**
  A scaffolded probe pack has no identity name yet, so the derived report said
  "there is nothing to look for" and then printed a `no unknown: <path>` line
  for every call site it had just found, one line per site, contradicting the
  summary directly above it. Measured on a 4,863-file installation: 116 output
  lines before, 62 after, the 54 removed being exactly those lines. The sites
  are still reported as sites. Only the claim that they are failing is
  withdrawn. (`9e51b48`)
- **The set-aside gate named a language the classifier never emits.** It
  listed `markdown`; the classifier emits `md`. A branch that can never be
  taken reads as covered, so mentions of an effect inside prose were never set
  aside from the fix list. No reading moved on the installation the kit was
  written against, because that one has no such sites. (`e1a0cad`)
- **The README's only "use it on your own factory" path was the shape the
  quickstart warns against**, sending a new user to hand-write a contract
  instead of deriving one from their installation. It now leads with
  `probes-init` then `infer` then `review`. (`ca66097`)

The rest change how much a large city has to read:

- The scan skips paths the installation's own VCS declares to be output, and
  the probe scaffold does the same, so a tree with vendored or generated
  directories no longer reports call sites inside them. (`9796b50`, `04eeaea`)
- The fix list sets aside quoted mentions, splits shell commands on separators
  outside quotes, and stops reading a bare assignment as a call. Fewer entries,
  and the ones left are call sites. (`08a6493`, `bad4d32`, `2694405`)
- `gc factory reconcile` compares the code lane, so a `confirmed` verdict is
  reachable at all, and a fenced call site now improves the score rather than
  reading as unfenced. (`f2643a6`, `9e1441e`)

Two documentation commits in the kit (`1391590`, `f575ff7`) do not change any
reading.

**This pin names a commit that is not yet published**, so `gc factory setup`
will refuse it with "the pack's pin names a commit the remote does not carry"
and check out nothing. That refusal is the designed behaviour for an unfetchable
pin, not a pack defect, and it clears when the kit commits are pushed.

## 0.1.0

First version. `gc factory setup` / `derive` / `audit` / `reconcile`, a daily
read-only drift order, and a probe template.
