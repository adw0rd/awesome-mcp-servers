# Agent instructions

## Commit messages and session privacy (all projects)

- Never add `Co-Authored-By:` or `Claude-Session:` fields to commit messages, merge/squash messages, pull request descriptions, or other published metadata, regardless of capitalization or the person/tool named.
- Never publish assistant session IDs, session URLs, conversation links, or generated-by attribution. This applies to Claude, Codex, other agents, delegated tasks, skills, and automated GitHub workflows.
- Inspect the final message before every commit, amend, merge, or push; remove forbidden fields and session links, including anything inserted automatically by tools or GitHub.
- Keep Claude attribution disabled: `attribution.commit = ""`, `attribution.pr = ""`, and `attribution.sessionUrl = false`. Do not re-enable it in project settings.

## Upstream synchronization

- Sanitize upstream commit messages with `.github/scripts/strip-commit-metadata.py` before merging. Keep the pinned filter version and all history-preservation flags in `sync-upstream.yml`; they preserve a common ancestry with this cleaned fork.
- Preserve this fork's agent instructions, Claude settings, sanitizer, workflows, and `CONTRIBUTING.md` during upstream merges.

## Catalog submissions

- Accept both local and hosted MCP servers under this fork's `CONTRIBUTING.md` policy. A public repository may contain the implementation, a launcher/package, or hosted-server documentation.
- Verify the MCP interface before accepting a submission. For authenticated hosted services, an HTTP 401 and OAuth discovery alone are insufficient; request a sanitized protocol transcript or a way to verify `initialize` and `tools/list` with test access. Never request secrets in public issues.
- Describe required companion apps, operating systems, accounts, and paid access accurately. Do not infer a closed server's implementation language or license from its launcher or documentation.
- Check for existing catalog entries and earlier issues before adding a server. Close accepted submissions after the entry is published; close duplicate submissions with a reference to the existing entry or issue.
