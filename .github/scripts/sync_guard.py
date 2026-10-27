#!/usr/bin/env python3
"""Refuse upstream synchronization that loses fork-only catalog entries."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit


ENTRY = re.compile(r"^\s*[-*]\s+\[[^\]]+\]\((https?://[^)]+)\)", re.MULTILINE)
REPOSITORY = re.compile(r"[a-z0-9_.-]+/[a-z0-9_.-]+\Z")


def git(*args):
    return subprocess.check_output(["git", *args], text=True)


def repositories(text):
    result = set()
    for match in ENTRY.finditer(text):
        url = urlsplit(match.group(1))
        if url.hostname not in ("github.com", "www.github.com") or url.username:
            continue
        parts = unquote(url.path).strip("/").split("/")
        if len(parts) < 2:
            continue
        repository = (parts[0] + "/" + parts[1].removesuffix(".git")).lower()
        if REPOSITORY.fullmatch(repository):
            result.add(repository)
    return result


def capture(args):
    base = git("merge-base", args.fork_ref, args.upstream_ref).strip()
    fork = repositories(git("show", f"{args.fork_ref}:README.md"))
    upstream = repositories(git("show", f"{args.upstream_ref}:README.md"))
    common = repositories(git("show", f"{base}:README.md"))
    if not fork or not upstream or not common:
        raise ValueError("Cannot capture snapshot: fork, upstream and merge-base catalogs must be nonempty")
    snapshot = {
        "schema_version": 1,
        "fork_count": len(fork),
        "upstream_count": len(upstream),
        "base_count": len(common),
        "repositories": sorted(fork - common),
    }
    args.output.write_text(json.dumps(snapshot, indent=2) + "\n")
    print(f"Captured {len(snapshot['repositories'])} fork-only repositories")


def check_conflicts(_args):
    unmerged = git("diff", "--name-only", "--diff-filter=U", "-z").split("\0")
    if "README.md" in unmerged:
        raise ValueError("README.md has unresolved merge conflicts; refusing to take upstream's version")


def verify(args):
    snapshot = json.loads(args.snapshot.read_text())
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1:
        raise ValueError("Invalid catalog snapshot schema")
    for key in ("fork_count", "upstream_count", "base_count"):
        if type(snapshot.get(key)) is not int or snapshot[key] < 1:
            raise ValueError(f"Invalid catalog snapshot: {key}")
    expected = snapshot.get("repositories")
    if (not isinstance(expected, list) or
            any(not isinstance(repo, str) or not REPOSITORY.fullmatch(repo) for repo in expected) or
            len(set(expected)) != len(expected) or len(expected) > snapshot["fork_count"]):
        raise ValueError("Invalid catalog snapshot repositories")
    check_conflicts(args)
    attribute = git("check-attr", "-z", "merge", "--", "README.md").split("\0")
    if attribute != ["README.md", "merge", "union", ""]:
        raise ValueError("README.md must retain merge=union")
    actual = repositories(args.readme.read_text())
    if not actual:
        raise ValueError("Merged README.md has no catalog entries")
    missing = set(expected) - actual
    if missing:
        raise ValueError("Fork catalog entries disappeared: " + ", ".join(sorted(missing)))
    print(f"Verified {len(expected)} fork-only repositories and README.md merge=union")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("capture")
    command.add_argument("--fork-ref", default="HEAD")
    command.add_argument("--upstream-ref", default="upstream/main")
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(run=capture)
    command = commands.add_parser("check-conflicts")
    command.set_defaults(run=check_conflicts)
    command = commands.add_parser("verify")
    command.add_argument("--snapshot", type=Path, required=True)
    command.add_argument("--readme", type=Path, default=Path("README.md"))
    command.set_defaults(run=verify)
    args = parser.parse_args()
    try:
        args.run(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Sync guard failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
