#!/usr/bin/env python3
"""Protect fork-only catalog entries and remove union-merge duplicates during upstream sync."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit


ENTRY = re.compile(r"^\s*[-*]\s+\[[^\]]+\]\((https?://[^)]+)\)", re.MULTILINE)
REPOSITORY = re.compile(r"[a-z0-9_.-]+/[a-z0-9_.-]+\Z")
HEADING = re.compile(r"^#{2,3} ")


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


def entry_key(line):
    match = ENTRY.match(line)
    if not match:
        return None
    url = re.sub(r"^https?://(www\.)?", "", match.group(1).strip().lower()).rstrip("/")
    return url.removesuffix(".git")


def headed(lines):
    heading = None
    for line in lines:
        if HEADING.match(line):
            heading = line
        yield heading, line


def merge_duplicate_headings(lines, upstream):
    blocks = [[None, []]]
    for line in lines:
        if HEADING.match(line):
            blocks.append([line, []])
        else:
            blocks[-1][1].append(line)
    order = [line for line in upstream if HEADING.match(line)]
    merged = 0
    for heading in {block[0] for block in blocks if block[0]}:
        copies = [i for i, block in enumerate(blocks) if block[0] == heading]
        if len(copies) < 2:
            continue
        expected = order[order.index(heading) - 1] if heading in order and order.index(heading) else None
        def previous(i):
            return next((blocks[j][0] for j in range(i - 1, -1, -1) if blocks[j][0] != heading), None)
        keep = next((i for i in copies if previous(i) == expected), copies[0])
        body = blocks[keep][1]
        tail = len(body)
        while tail and not body[tail - 1].strip():
            tail -= 1
        moved = [line for i in copies if i != keep for line in blocks[i][1]
                 if line.strip() and line not in body]
        body[tail:tail] = moved
        blocks = [block for i, block in enumerate(blocks) if i == keep or i not in copies]
        merged += len(copies) - 1
    result = blocks[0][1]
    for heading, body in blocks[1:]:
        result += [heading, *body]
    return result, merged


def dedupe(args):
    base = git("merge-base", args.fork_ref, args.upstream_ref).strip()
    upstream = git("show", f"{args.upstream_ref}:README.md").split("\n")
    fork = git("show", f"{args.fork_ref}:README.md").split("\n")
    common = set(git("show", f"{base}:README.md").split("\n"))
    original = args.readme.read_text()
    lines, merged = merge_duplicate_headings(original.split("\n"), upstream)
    # A line the fork wrote itself is curation; anything else defers to upstream.
    fork_written = {line for line in fork if entry_key(line)} - common - set(upstream)
    upstream_entries = [(heading, line, entry_key(line)) for heading, line in headed(upstream) if entry_key(line)]
    counts = Counter(key for _, _, key in upstream_entries)
    placed = Counter((heading, line) for heading, line, _ in upstream_entries)
    texts = {line for _, line, _ in upstream_entries}
    homes = defaultdict(set)
    for heading, _, key in upstream_entries:
        homes[key].add(heading)
    copies = defaultdict(list)
    for index, (heading, line) in enumerate(headed(lines)):
        key = entry_key(line)
        if key:
            copies[key].append((index, heading, line))

    drop = set()
    for key, found in copies.items():
        if len(found) < 2:
            continue
        limit, kept = max(counts[key], 1), set()
        tiers = (lambda heading, line: line in fork_written,
                 lambda heading, line: placed[(heading, line)] > 0,
                 lambda heading, line: line in texts,
                 lambda heading, line: heading in homes[key],
                 lambda heading, line: True)
        for matches in tiers:
            for index, heading, line in found:
                if len(kept) < limit and index not in kept and matches(heading, line):
                    kept.add(index)
                    placed[(heading, line)] -= 1
        drop.update(index for index, _, _ in found if index not in kept)
    result = "\n".join(line for index, line in enumerate(lines) if index not in drop)
    if result != original:
        args.readme.write_text(result)
    print(f"Removed {len(drop)} duplicate README entries and merged {merged} duplicate headings")


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
    command = commands.add_parser("dedupe")
    command.add_argument("--fork-ref", default="HEAD")
    command.add_argument("--upstream-ref", default="upstream/main")
    command.add_argument("--readme", type=Path, default=Path("README.md"))
    command.set_defaults(run=dedupe)
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
