import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
GUARD = ROOT / ".github/scripts/sync_guard.py"
WORKFLOW = ROOT / ".github/workflows/sync-upstream.yml"


def catalog(*repositories):
    return "## Server Implementations\n\n### Tools\n\n" + "".join(
        f"- [{repo}](https://github.com/{repo}) - Example server.\n"
        for repo in repositories
    )


def entry(path, text="Example server."):
    return f"- [{path}](https://github.com/{path}) - {text}\n"


def sections(*blocks):
    return "## Server Implementations\n" + "".join(
        f"\n### {name}\n\n" + "".join(entries) for name, entries in blocks)


def merge_script():
    lines = WORKFLOW.read_text().splitlines()
    start = lines.index("      - name: Merge upstream changes") + 2
    end = next(i for i in range(start, len(lines)) if lines[i].startswith("      - name:"))
    return "\n".join(line[10:] if line.startswith("          ") else line for line in lines[start:end])


class SyncGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.runner = self.root / "runner"
        self.runner.mkdir()
        self.env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_CONFIG_NOSYSTEM": "1", "RUNNER_TEMP": str(self.runner)}
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Sync test")
        self.git("config", "user.email", "sync-test@example.invalid")
        protected = ["AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md",
                     ".claude/settings.json", ".github/scripts/strip-commit-metadata.py"]
        for path in protected:
            self.write(path, "Fork-owned fixture.\n")
        self.write(".github/workflows/sync-upstream.yml", WORKFLOW.read_text())
        if GUARD.exists():
            self.write(".github/scripts/sync_guard.py", GUARD.read_text())
            shutil.copyfile(GUARD, self.runner / "sync_guard.py")
        self.write(".gitattributes", "README.md merge=union\n")
        self.write("README.md", catalog("shared/base"))
        self.commit("Initial catalog")

    def git(self, *args, check=True):
        return subprocess.run(["git", *args], cwd=self.repo, env=self.env,
                              capture_output=True, text=True, check=check)

    def write(self, path, content):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "-q", "-m", message)

    def guard(self, *args):
        return subprocess.run([sys.executable, str(GUARD), *map(str, args)],
                              cwd=self.repo, env=self.env, capture_output=True, text=True)

    def diverge(self, *, union=True, upstream_attributes=None):
        if not union:
            self.write(".gitattributes", "*.md text\n")
            self.commit("Configure merge behavior")
        base = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("checkout", "-q", "-b", "upstream-branch", base)
        self.write("README.md", catalog("shared/base", "upstream/new"))
        if upstream_attributes is not None:
            self.write(".gitattributes", upstream_attributes)
        self.commit("Upstream catalog change")
        self.git("update-ref", "refs/remotes/upstream/main", "HEAD")
        self.git("checkout", "-q", "main")
        self.write("README.md", catalog("shared/base", "fork/local"))
        self.commit("Fork catalog change")

    def capture(self):
        snapshot = self.runner / "fork-catalog.json"
        result = self.guard("capture", "--output", snapshot)
        self.assertEqual(result.returncode, 0, result.stderr)
        return snapshot

    def test_workflow_stops_instead_of_taking_upstream_readme(self):
        self.diverge(union=False)
        before = self.git("rev-parse", "HEAD").stdout
        result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", merge_script()],
                                cwd=self.repo, env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, "Conflicted README was silently replaced")
        self.assertIn("README.md has unresolved merge conflicts", result.stdout + result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout, before)

    def test_capture_records_only_fork_entries(self):
        self.diverge()
        snapshot = json.loads(self.capture().read_text())
        self.assertEqual(snapshot["repositories"], ["fork/local"])

    def test_verify_rejects_a_lost_fork_entry(self):
        self.diverge()
        snapshot = self.capture()
        self.write("README.md", catalog("shared/base", "upstream/new"))
        result = self.guard("verify", "--snapshot", snapshot)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fork/local", result.stderr)

    def test_verify_allows_upstream_removals(self):
        self.diverge()
        snapshot = self.capture()
        self.write("README.md", catalog("fork/local", "upstream/new"))
        result = self.guard("verify", "--snapshot", snapshot)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_upstream_deletions_are_not_mistaken_for_fork_additions(self):
        self.diverge()
        self.git("checkout", "-q", "upstream-branch")
        self.write("README.md", catalog("upstream/new"))
        self.commit("Remove shared upstream entry")
        self.git("update-ref", "refs/remotes/upstream/main", "HEAD")
        self.git("checkout", "-q", "main")
        snapshot = json.loads(self.capture().read_text())
        self.assertEqual(snapshot["repositories"], ["fork/local"])

    def test_fatal_merge_error_stops_the_workflow(self):
        before = self.git("rev-parse", "HEAD").stdout
        result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", merge_script()],
                                cwd=self.repo, env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout, before)

    def test_repository_identity_ignores_case_subpaths_and_git_suffix(self):
        self.diverge()
        snapshot = self.capture()
        self.write("README.md", "- [Local](https://www.github.com/FORK/LOCAL.git/tree/main) - Same repository.\n")
        result = self.guard("verify", "--snapshot", snapshot)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_union_merge_preserves_entries_and_fork_attributes(self):
        self.diverge(upstream_attributes="*.md text\n")
        snapshot = self.capture()
        result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", merge_script()],
                                cwd=self.repo, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("fork/local", (self.repo / "README.md").read_text())
        self.assertIn("upstream/new", (self.repo / "README.md").read_text())
        self.assertEqual((self.repo / ".gitattributes").read_text(), "README.md merge=union\n")
        self.assertEqual(self.guard("verify", "--snapshot", snapshot).returncode, 0)

    def test_verify_rejects_missing_union_rule(self):
        self.diverge()
        snapshot = self.capture()
        self.write(".gitattributes", "*.md text\n")
        result = self.guard("verify", "--snapshot", snapshot)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("merge=union", result.stderr)

    def test_invalid_snapshot_cannot_disable_checks(self):
        snapshot = self.runner / "invalid.json"
        snapshot.write_text(json.dumps({"schema_version": 1, "repositories": []}))
        result = self.guard("verify", "--snapshot", snapshot)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("snapshot", result.stderr.lower())

    def test_capture_rejects_empty_upstream_catalog(self):
        self.git("checkout", "-q", "-b", "empty-upstream")
        self.write("README.md", "No catalog here.\n")
        self.commit("Empty upstream catalog")
        self.git("update-ref", "refs/remotes/upstream/main", "HEAD")
        self.git("checkout", "-q", "main")
        result = self.guard("capture", "--output", self.runner / "snapshot.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("upstream", result.stderr.lower())


    def history(self, base, upstream, fork):
        def commit(content, message):
            self.write("README.md", content)
            self.git("add", ".")
            self.git("commit", "-q", "--allow-empty", "-m", message)
        commit(base, "Base catalog")
        self.git("checkout", "-q", "-b", "upstream-branch")
        commit(upstream, "Upstream catalog change")
        self.git("update-ref", "refs/remotes/upstream/main", "HEAD")
        self.git("checkout", "-q", "main")
        commit(fork, "Fork catalog change")

    def run_merge(self):
        result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", merge_script()],
                                cwd=self.repo, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return (self.repo / "README.md").read_text()

    def dedupe(self, readme):
        self.write("README.md", readme)
        result = self.guard("dedupe")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return (self.repo / "README.md").read_text()

    def test_union_merge_keeps_one_current_copy_of_an_updated_entry(self):
        old, new = entry("shared/base"), entry("shared/base", "Updated description.")
        self.history(sections(("Tools", [old])), sections(("Tools", [new])),
                     sections(("Tools", [old, entry("fork/local")])))
        snapshot = self.capture()
        readme = self.run_merge()
        self.assertEqual(readme.count("](https://github.com/shared/base)"), 1, readme)
        self.assertIn(new, readme)
        self.assertIn(entry("fork/local"), readme)
        self.assertEqual(self.guard("verify", "--snapshot", snapshot).returncode, 0)

    def test_union_merge_keeps_the_fork_correction_of_an_upstream_entry(self):
        fixed = entry("shared/base", "Fork correction with access disclosure.")
        self.history(sections(("Tools", [entry("shared/base")])),
                     sections(("Tools", [entry("shared/base", "Updated description.")])),
                     sections(("Tools", [fixed])))
        readme = self.run_merge()
        self.assertEqual(readme.count("](https://github.com/shared/base)"), 1, readme)
        self.assertIn(fixed, readme)

    def test_dedupe_keeps_an_entry_in_its_upstream_category(self):
        moved = entry("moved/entry")
        self.history(sections(("Alpha", [moved]), ("Beta", [])),
                     sections(("Alpha", []), ("Beta", [moved])),
                     sections(("Alpha", [moved, entry("fork/local")]), ("Beta", [])))
        readme = self.dedupe(sections(("Alpha", [moved, entry("fork/local")]), ("Beta", [moved])))
        self.assertEqual(readme, sections(("Alpha", [entry("fork/local")]), ("Beta", [moved])))

    def test_dedupe_preserves_entries_upstream_lists_twice(self):
        twice = entry("listed/twice")
        both = sections(("Alpha", [twice]), ("Beta", [twice]))
        self.history(both, both, sections(("Alpha", [twice, entry("fork/local")]), ("Beta", [twice])))
        readme = self.dedupe(sections(("Alpha", [twice, entry("fork/local"), twice]), ("Beta", [twice])))
        self.assertEqual(readme, sections(("Alpha", [twice, entry("fork/local")]), ("Beta", [twice])))

    def test_dedupe_merges_a_duplicated_category_heading(self):
        upstream = sections(("Alpha", [entry("a/one")]), ("Tools", [entry("t/one")]), ("Zeta", []))
        self.history(upstream, upstream, upstream)
        readme = self.dedupe(sections(("Alpha", [entry("a/one")]), ("Tools", [entry("t/one")]),
                                      ("Tools", [entry("fork/local")]), ("Zeta", [])))
        self.assertEqual(readme.count("### Tools"), 1, readme)
        self.assertEqual(readme, sections(("Alpha", [entry("a/one")]),
                                          ("Tools", [entry("t/one"), entry("fork/local")]), ("Zeta", [])))

    def test_dedupe_keeps_one_copy_of_a_repeated_fork_entry(self):
        upstream = sections(("Tools", [entry("shared/base")]))
        self.history(upstream, upstream, upstream)
        readme = self.dedupe(sections(("Tools", [entry("fork/local"), entry("shared/base"),
                                                 entry("fork/local")])))
        self.assertEqual(readme, sections(("Tools", [entry("fork/local"), entry("shared/base")])))

    def test_dedupe_leaves_a_clean_catalog_and_monorepo_subpaths_unchanged(self):
        servers = [entry("org/servers/tree/main/src/a"), entry("org/servers/tree/main/src/b")]
        clean = sections(("Tools", servers + [entry("fork/local")]))
        self.history(sections(("Tools", servers)), sections(("Tools", servers)), clean)
        self.assertEqual(self.dedupe(clean), clean)
        self.assertEqual(self.dedupe(clean), clean)

if __name__ == "__main__":
    unittest.main()
