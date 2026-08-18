"""Resolve an installed ``gc`` binary to exact source and test Git blobs.

The order file attests which source and test paths belong to its command. This
module verifies the installed bytes, receipt, repository, commit, and named
blobs; it does not infer that semantic command-to-path mapping.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import tomllib
import typing


FULL_SHA = re.compile(r"[0-9a-f]{40}")


class ProvenanceSubject(typing.NamedTuple):
    source_path: pathlib.Path
    test_path: pathlib.Path
    display: str
    attestation: str
    source_text: str
    test_text: str


class OrderAttestation(typing.NamedTuple):
    source: str
    test: str
    argv: list[str]


def _safe_repo_relative(value: object, field: str) -> tuple[str | None, str | None]:
    if not isinstance(value, str) or not value:
        return None, f"{field} is missing"
    path = pathlib.PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or str(path) != value:
        return None, f"{field} is not a canonical repository-relative path"
    return value, None


def _git_environment() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    })
    return env


def _git_blob(
    repo: pathlib.Path,
    head: str,
    relative: str,
    label: str,
) -> tuple[str | None, str | None]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "show", f"{head}:{relative}"],
            capture_output=True,
            timeout=15,
            env=_git_environment(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"cannot read exact {label} blob ({exc})"
    if result.returncode != 0:
        return None, f"cannot read exact {label} blob"
    try:
        return result.stdout.decode("utf-8"), None
    except UnicodeError as exc:
        return None, f"cannot decode exact {label} blob ({exc})"


def _verify_source_repository(
    source_root: pathlib.Path,
    expected_remote: str,
    head: str,
) -> str | None:
    checks = (
        (["rev-parse", "--show-toplevel"], str(source_root.resolve())),
        (["remote", "get-url", "origin"], expected_remote),
    )
    for arguments, expected in checks:
        try:
            result = subprocess.run(
                ["git", "-C", str(source_root), *arguments],
                capture_output=True,
                text=True,
                timeout=15,
                env=_git_environment(),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return f"cannot verify canonical source repository ({exc})"
        if result.returncode != 0 or result.stdout.strip() != expected:
            return "canonical source repository identity does not match"
    try:
        result = subprocess.run(
            ["git", "-C", str(source_root), "cat-file", "-e", f"{head}^{{commit}}"],
            capture_output=True,
            timeout=15,
            env=_git_environment(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"cannot verify installed source commit ({exc})"
    return None if result.returncode == 0 else "installed source commit is unavailable"


def _tokenize_command(command: str) -> list[str] | None:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return None


def _strip_assignments(words: list[str]) -> list[str]:
    for index, word in enumerate(words):
        if "=" not in word or word.startswith(("/", "./", "../")):
            return words[index:]
        name, _value = word.split("=", 1)
        if not name.replace("_", "a").isalnum() or name[:1].isdigit():
            return words[index:]
    return []


def _resolve_target(word: str) -> pathlib.Path | None:
    if "/" in word:
        candidate = pathlib.Path(word).expanduser()
        if not candidate.is_absolute():
            return None
        return candidate.resolve() if candidate.exists() else None
    found = shutil.which(word)
    return pathlib.Path(found).resolve() if found else None


def _binding_arguments(command: str, target: pathlib.Path) -> tuple[list[str] | None, str | None]:
    words = _tokenize_command(command)
    if not words or any(word in {";", "&&", "||", "|", "&", "\n"} for word in words):
        return None, "instrument command is not one simple invocation"
    words = _strip_assignments(words)
    if words and pathlib.Path(words[0]).name == "env":
        words = _strip_assignments(words[1:])
    if words and words[0] == "exec":
        words = _strip_assignments(words[1:])
    if not words or _resolve_target(words[0]) != target:
        return None, "instrument executable does not match the resolved target"
    return words[1:], None


def _installed_gc_identity(
    target: pathlib.Path,
    source_root: pathlib.Path,
    receipt_path: pathlib.Path,
) -> tuple[str | None, str | None]:
    try:
        receipt = receipt_path.read_text().strip()
    except OSError as exc:
        return None, f"cannot read install receipt ({exc})"
    if FULL_SHA.fullmatch(receipt) is None:
        return None, "install receipt is not one full commit SHA"
    try:
        target_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        built_hash = hashlib.sha256((source_root / "bin" / "gc").read_bytes()).hexdigest()
    except OSError as exc:
        return None, f"cannot hash installed gc identity ({exc})"
    if target_hash != built_hash:
        return None, "installed gc binary bytes differ from the canonical built copy"
    try:
        result = subprocess.run(
            [str(target), "version", "--json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        value = json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return None, f"cannot read installed gc version ({exc})"
    commit = value.get("commit") if isinstance(value, dict) else None
    if not isinstance(commit, str) or len(commit) < 7 or not receipt.startswith(commit):
        return None, "installed gc version does not match receipt"
    return receipt, None


def _load_gc_order_attestation(
    order_path: pathlib.Path,
    target: pathlib.Path,
) -> tuple[OrderAttestation | None, str | None]:
    try:
        table = tomllib.loads(order_path.read_text())["order"]
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        return None, f"cannot read order provenance ({exc})"
    if table.get("instrument_repository") != "gascity" or target.name != "gc":
        return None, "external installed executable"
    source, error = _safe_repo_relative(table.get("instrument_source"), "instrument_source")
    if error:
        return None, error
    test, error = _safe_repo_relative(table.get("instrument_test"), "instrument_test")
    if error:
        return None, f"{error}; C3 presence could not be checked"
    argv = table.get("instrument_argv")
    if not isinstance(argv, list) or not argv or any(
        not isinstance(value, str) or not value for value in argv
    ):
        return None, "instrument_argv must be a nonempty string array"
    return OrderAttestation(source=source, test=test, argv=argv), None


def resolve_installed_gc_subject(
    *,
    order_path: pathlib.Path,
    command: str,
    target: pathlib.Path,
    source_root: pathlib.Path,
    receipt_path: pathlib.Path,
    expected_remote: str,
) -> tuple[ProvenanceSubject | None, str | None]:
    attestation, error = _load_gc_order_attestation(order_path, target)
    if error:
        return None, error
    actual_argv, error = _binding_arguments(command, target)
    if error:
        return None, error
    if actual_argv[:len(attestation.argv)] != attestation.argv:
        return None, "instrument_argv does not match the order command"
    head, error = _installed_gc_identity(target, source_root, receipt_path)
    if error:
        return None, error
    error = _verify_source_repository(source_root, expected_remote, head)
    if error:
        return None, error
    source_text, error = _git_blob(source_root, head, attestation.source, "source")
    if error:
        return None, error
    test_text, error = _git_blob(source_root, head, attestation.test, "test")
    if error:
        return None, f"{error}; C3 presence could not be checked"
    order_label = pathlib.PurePosixPath(order_path.parent.name, order_path.name)
    return ProvenanceSubject(
        source_path=source_root / attestation.source,
        test_path=source_root / attestation.test,
        display=f"gascity@{head}:{attestation.source}",
        attestation=(
            f"source/test mapping attested by {order_label}; "
            "not derived from command"
        ),
        source_text=source_text,
        test_text=test_text,
    ), None
