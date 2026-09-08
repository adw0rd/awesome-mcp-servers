# Agent instructions

## Commit messages and session privacy (all projects)

- Never add `Co-Authored-By:` or `Claude-Session:` fields to commit messages, merge/squash messages, pull request descriptions, or other published metadata, regardless of capitalization or the person/tool named.
- Never publish assistant session IDs, session URLs, conversation links, or generated-by attribution. This applies to Claude, Codex, other agents, delegated tasks, skills, and automated GitHub workflows.
- Inspect the final message before every commit, amend, merge, or push; remove forbidden fields and session links, including anything inserted automatically by tools or GitHub.
- Keep Claude attribution disabled: `attribution.commit = ""`, `attribution.pr = ""`, and `attribution.sessionUrl = false`. Do not re-enable it in project settings.

## Upstream synchronization

- Sanitize upstream commit messages with `.github/scripts/strip-commit-metadata.py` before merging. Keep the pinned filter version and all history-preservation flags in `sync-upstream.yml`; they preserve a common ancestry with this cleaned fork.
- Preserve this fork's agent instructions, Claude settings, sanitizer, and workflows during upstream merges.
