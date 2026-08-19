"""The commit this pack pins has to exist somewhere a stranger can fetch it.

`test_factory_audit_scripts.py` covers what the setup script does with a kit it
already has. It builds that kit with `install_stub_kit`, which is a local `git
init` in a temp directory, so nothing in that file ever contacts `KIT_REPO`. The
pin is read there as a string and compared to another string. That is a real
test of the wrapper and it is blind to the one property the pin exists to carry:
that `gc fa setup` can obtain the commit on a machine that is not this one.

Measured 2026-08-19: the pinned commit was absent from the public remote for
days while this pack's whole suite passed. Every install by anyone other than us
failed on the first command with `upload-pack: not our ref`, and no test said so.

Both rails are exercised. The check below fails when the pin is unfetchable; the
control immediately after it fails if the probe has stopped being able to fail
at all -- a network stack that resolves everything, a git that reports success
on a missing ref, a stubbed subprocess. Without the control, "green" and "the
probe is inert" are the same reading, which is the failure mode this file was
written to close rather than to reproduce.

Skipping is confined to one cause: the remote is not reachable at all. A remote
that answers and does not have the commit is a FAILURE, never a skip, because
that is precisely the broken state.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest


PACK = Path(__file__).resolve().parents[1]

# Long enough that a slow network does not read as a broken pin, short enough
# that a hung probe fails the run rather than the suite's overall timeout.
NET_TIMEOUT = 90

# A syntactically valid commit id that cannot exist. Used only by the control.
ABSENT_COMMIT = "0123456789abcdef0123456789abcdef01234567"


def read_pin() -> tuple[str, str]:
    repo = commit = ""
    for line in PACK.joinpath("kit.pin").read_text().splitlines():
        line = line.strip()
        if line.startswith("KIT_REPO="):
            repo = line.split("=", 1)[1].strip().strip("'\"")
        elif line.startswith("KIT_COMMIT="):
            commit = line.split("=", 1)[1].strip().strip("'\"")
    assert repo, "kit.pin declares no KIT_REPO"
    assert commit, "kit.pin declares no KIT_COMMIT"
    return repo, commit


def fetchable(repo: str, commit: str, tmp_path: Path) -> subprocess.CompletedProcess:
    """Ask the remote for one commit, the way `gc fa setup` does."""
    work = tmp_path / "probe"
    work.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=work, check=True)
    return subprocess.run(
        ["git", "fetch", "-q", "--depth", "1", repo, commit],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=NET_TIMEOUT,
    )


def require_reachable_remote(repo: str) -> None:
    """Skip only when the host cannot be reached.

    `ls-remote` succeeding is the discriminator: it proves the remote answered,
    so a subsequent fetch failure is about the commit and not about the network.
    """
    try:
        probe = subprocess.run(
            ["git", "ls-remote", "--heads", repo],
            capture_output=True,
            text=True,
            timeout=NET_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        pytest.skip(f"remote {repo} did not answer within {NET_TIMEOUT}s")
    if probe.returncode != 0:
        pytest.skip(f"remote {repo} unreachable: {probe.stderr.strip()[:200]}")


def test_the_pinned_kit_commit_can_be_fetched_by_someone_who_is_not_us(
    tmp_path: Path,
) -> None:
    repo, commit = read_pin()
    require_reachable_remote(repo)
    result = fetchable(repo, commit, tmp_path)
    assert result.returncode == 0, (
        f"kit.pin names {commit[:12]}, which {repo} will not serve.\n"
        f"`gc fa setup` fails for every installer until that commit is pushed.\n"
        f"git said: {result.stderr.strip()[:400]}"
    )


def test_the_fetch_probe_still_fails_on_a_commit_that_cannot_exist(
    tmp_path: Path,
) -> None:
    """The control for the test above.

    If this passes, the probe above cannot distinguish a served commit from an
    absent one, and its green says nothing about the pin.
    """
    repo, _ = read_pin()
    require_reachable_remote(repo)
    result = fetchable(repo, ABSENT_COMMIT, tmp_path)
    assert result.returncode != 0, (
        "the fetch probe reported success for a commit that cannot exist, so a "
        "green result from the pin check above is not evidence of anything"
    )
