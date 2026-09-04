"""Regression tests for the instruction stack — Claude Code AND agy (antigravity).

These guard three fixes that live in prose and config rather than in code, and so
have no other safety net:

  1. Global instructions must not be double-injected. A file at <repo>/.claude/CLAUDE.md
     is read by Claude Code as PROJECT memory while its installed copy at
     ~/.claude/CLAUDE.md is read as USER memory — the same ~1.6k tokens twice on
     every request whenever the CWD is this repo. The managed source is therefore
     named instructions.md.
  2. The vault read policy is three tiers (read relevant notes yourself; line-range
     reads for large notes; delegate breadth only, with verbatim quotes back). The
     retired blanket rule said never to read vault notes directly and to accept a
     ~25-line subagent summary, and it contradicted itself two paragraphs later.
  3. Claude and agy must not drift. The agy mirrors are copies; nothing but a test
     notices when one side is updated and the other is not.
  4. A tool that exists is not a tool an agent can find. Every mention of
     vault_checkpoint used the bare short name while the callable id is prefixed
     with the server, so in a host that defers MCP schemas the lookup returned
     nothing and the agent fell back to a Read of working-context.md.

Run from repo root:
    py -3 -m unittest tests.test_instruction_stack -v
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

CLAUDE_INSTRUCTIONS = REPO / ".claude/instructions.md"
CLAUDE_RULES = REPO / ".claude/rules/obsidian-notes.md"
CLAUDE_CHECKPOINT = REPO / ".claude/skills/checkpoint/SKILL.md"
CLAUDE_SETTINGS = REPO / ".claude/settings.json"

AGY = REPO / ".antigravity/plugins/obsidian"
AGY_RULES = AGY / "skills/obsidian-vault-rules/SKILL.md"
AGY_CHECKPOINT = AGY / "skills/checkpoint/SKILL.md"
AGY_MCP = AGY / "mcp_config.json"

SESSION_START = REPO / "hooks/session-start.sh"

# The id an agent must actually call. The short name `vault_checkpoint` is prose;
# a host that defers MCP schemas lists only this string.
QUALIFIED_ID = "mcp__vault-mcp__vault_checkpoint"

# Phrasings the three-tier policy replaced. Any reappearance is a regression:
# each one tells the agent to hand a fidelity read to a summarizer.
RETIRED = [
    "never ingest full notes directly",
    "Do NOT read full vault notes directly",
    "don't pull full notes into main context",
    "~25-line summary",
    "Spawn Explore subagent",
    "returns ~25-line summary only",
]


def instruction_files() -> list[Path]:
    """Every markdown file that ends up in an agent's context."""
    out = [CLAUDE_INSTRUCTIONS, CLAUDE_RULES]
    out += sorted((REPO / ".claude/rules").glob("*.md"))
    out += sorted((REPO / ".claude/skills").rglob("*.md"))
    out += sorted((REPO / ".antigravity/plugins").rglob("*.md"))
    return sorted(set(p for p in out if p.is_file()))


class DoubleInjectionTests(unittest.TestCase):
    """Fix 1 — the managed source must sit outside the auto-injected filename."""

    def test_repo_has_no_dot_claude_claude_md(self):
        stray = REPO / ".claude/CLAUDE.md"
        self.assertFalse(
            stray.exists(),
            "<repo>/.claude/CLAUDE.md is injected as project memory on top of its "
            "installed copy at ~/.claude/CLAUDE.md — the managed source belongs at "
            ".claude/instructions.md",
        )

    def test_managed_source_exists(self):
        self.assertTrue(CLAUDE_INSTRUCTIONS.is_file())
        self.assertIn("Identity & Notes Vault", CLAUDE_INSTRUCTIONS.read_text(encoding="utf-8"))

    def test_agentcfg_installs_instructions_md_as_claude_md(self):
        src = (REPO / "bin/agentcfg").read_text(encoding="utf-8")
        line = next(l for l in src.splitlines() if l.startswith("MD_FILES"))
        self.assertIn('".claude/instructions.md"', line)
        self.assertIn('".claude/CLAUDE.md"', line)      # destination is unchanged
        self.assertLess(line.index("instructions.md"), line.index('HOME / ".claude/CLAUDE.md"'),
                        "source must be instructions.md, destination ~/.claude/CLAUDE.md")

    def test_project_claude_md_stays_small(self):
        """<repo>/CLAUDE.md is legitimately project memory; keep it a pointer, not a
        second copy of the global instructions."""
        text = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertLess(len(text), 2000, "project CLAUDE.md is growing into a duplicate")

    def test_stale_note_hook_still_watches_the_renamed_source(self):
        hook = (REPO / "hooks/detect-stale-notes.sh").read_text(encoding="utf-8")
        self.assertIn(".claude/instructions.md", hook)


class RetiredPhrasingTests(unittest.TestCase):
    """Fix 2 — the blanket delegate-everything rule must not come back anywhere."""

    def test_no_instruction_file_carries_retired_phrasing(self):
        offenders = []
        for path in instruction_files():
            text = path.read_text(encoding="utf-8")
            for phrase in RETIRED:
                if phrase.lower() in text.lower():
                    offenders.append(f"{path.relative_to(REPO)}: {phrase!r}")
        self.assertEqual(offenders, [], "retired read-policy phrasing reappeared:\n" +
                         "\n".join(offenders))

    def test_rules_do_not_contradict_themselves_on_direct_reads(self):
        """The old file said 'Do NOT read full vault notes directly' in one section
        and 'Read them directly' in another. Assert only the permissive form."""
        for path in (CLAUDE_RULES, AGY_RULES):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"(?i)do\s+not\s+read\s+full\s+vault\s+notes",
                                f"{path.relative_to(REPO)} still forbids direct reads")


class ThreeTierPolicyTests(unittest.TestCase):
    """Fix 2 — both stacks must state all three tiers and the no-paraphrase rule."""

    def _rules(self):
        return {"claude": CLAUDE_RULES, "agy": AGY_RULES}

    def test_all_three_tiers_present_in_both_stacks(self):
        for stack, path in self._rules().items():
            text = path.read_text(encoding="utf-8")
            for tier in ("Tier 1", "Tier 2", "Tier 3"):
                self.assertIn(tier, text, f"{stack} rules missing {tier}")

    def test_tier_3_requires_verbatim_quotes_not_a_summary(self):
        for stack, path in self._rules().items():
            text = path.read_text(encoding="utf-8")
            self.assertIn("verbatim quotes", text, f"{stack} rules do not demand verbatim quotes")
            self.assertIn("does not compress", text, f"{stack} rules do not say the subagent routes")

    def test_no_paraphrase_rule_present_in_both_stacks(self):
        for stack, path in self._rules().items():
            text = path.read_text(encoding="utf-8")
            self.assertRegex(text, r"(?i)never paraphrase a number",
                             f"{stack} rules missing the no-paraphrase rule")

    def test_semantic_search_is_named_as_the_large_note_path(self):
        for stack, path in self._rules().items():
            text = path.read_text(encoding="utf-8")
            self.assertIn("read just that range", text,
                          f"{stack} rules do not route large notes through line ranges")

    def test_session_start_workflow_tells_the_agent_to_read_itself(self):
        text = CLAUDE_INSTRUCTIONS.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?i)read the notes that actually bear on the task")
        self.assertIn("vault_semantic_search", text)


class CheckpointWiringTests(unittest.TestCase):
    """Fix 3 — one parser, a one-call write, and a read tool both stacks can see."""

    def test_agy_and_claude_checkpoint_skills_are_identical(self):
        self.assertEqual(
            CLAUDE_CHECKPOINT.read_text(encoding="utf-8"),
            AGY_CHECKPOINT.read_text(encoding="utf-8"),
            "the agy checkpoint skill has drifted from the Claude one",
        )

    def test_checkpoint_skills_teach_the_one_call_write(self):
        for path in (CLAUDE_CHECKPOINT, AGY_CHECKPOINT):
            text = path.read_text(encoding="utf-8")
            self.assertIn("checkpoint.py write", text)
            self.assertIn("vault_checkpoint", text)
            self.assertNotRegex(
                text, r"(?i)read the file back.*split on",
                f"{path.relative_to(REPO)} still prescribes the read-append-reread-rewrite dance",
            )

    def test_vault_checkpoint_is_exposed_by_the_mcp_server(self):
        src = (REPO / "bin/vault-mcp.py").read_text(encoding="utf-8")
        self.assertIn('"name": "vault_checkpoint"', src)
        self.assertIn('if name == "vault_checkpoint"', src)
        self.assertIn("def tool_checkpoint", src)

    def test_vault_checkpoint_answers_before_the_index_loads(self):
        """It reads one known file; paying for an index build would be waste."""
        src = (REPO / "bin/vault-mcp.py").read_text(encoding="utf-8")
        dispatch = src.index('if name == "vault_checkpoint"')
        ensure = src.index("idx = self.ensure_index()")
        self.assertLess(dispatch, ensure)

    def test_vault_checkpoint_is_preapproved_for_claude(self):
        allow = json.loads(CLAUDE_SETTINGS.read_text(encoding="utf-8"))["permissions"]["allow"]
        self.assertIn("mcp__vault-mcp__vault_checkpoint", allow)
        self.assertTrue(any("checkpoint.py" in rule for rule in allow),
                        "the checkpoint script is not pre-approved for Bash")

    def test_agy_reaches_the_same_mcp_server(self):
        """agy gets vault_checkpoint for free, but only while it registers vault-mcp."""
        cfg = json.loads(AGY_MCP.read_text(encoding="utf-8"))
        self.assertIn("vault-mcp", cfg["mcpServers"])

    def test_both_stacks_advertise_the_tool_in_their_rules(self):
        for path in (CLAUDE_RULES, AGY_RULES):
            text = path.read_text(encoding="utf-8")
            self.assertIn("vault_checkpoint", text,
                          f"{path.relative_to(REPO)} does not mention vault_checkpoint")
            self.assertIn("Six native MCP tools", text,
                          f"{path.relative_to(REPO)} still says five tools")


class CheckpointDiscoveryTests(unittest.TestCase):
    """The reported failure: the server exposed vault_checkpoint, the permission
    allowed it, both stacks named it — and an agent still could not call it,
    because every mention used the bare short name while the callable id is
    prefixed with the server (`mcp__vault-mcp__`). A host that defers MCP schemas
    advertises only the prefixed form, so looking up the short name finds nothing
    and the agent degrades to a Read of working-context.md — exactly what the
    skill forbids without naming an alternative.

    CheckpointWiringTests asserts the tool EXISTS. These assert an agent can FIND
    it, and has somewhere to go when it cannot."""

    STACKS = {"claude": CLAUDE_CHECKPOINT, "agy": AGY_CHECKPOINT}
    RULES = {"claude": CLAUDE_RULES, "agy": AGY_RULES}

    def test_checkpoint_skills_give_the_qualified_tool_id(self):
        for stack, path in self.STACKS.items():
            self.assertIn(QUALIFIED_ID, path.read_text(encoding="utf-8"),
                          f"{stack} checkpoint skill names only the short "
                          f"`vault_checkpoint`, which resolves to nothing in a "
                          f"host that defers MCP schemas")

    def test_rules_explain_that_short_names_are_shorthand(self):
        """The rules table lists six short names. Without this note an agent reads
        that table as a list of callable ids."""
        for stack, path in self.RULES.items():
            text = path.read_text(encoding="utf-8")
            self.assertIn("mcp__vault-mcp__", text,
                          f"{stack} rules never show the prefixed form")
            self.assertRegex(text, r"(?i)unfetched, not missing",
                             f"{stack} rules do not tell the agent an unresolved "
                             f"short name means the schema is unfetched")

    def test_both_stacks_name_the_bash_fallback(self):
        """`Read` and a subagent are both forbidden for this read. Something has to
        be permitted when the tool is unavailable, or the agent picks a forbidden
        path anyway."""
        for group in (self.STACKS, self.RULES):
            for stack, path in group.items():
                text = path.read_text(encoding="utf-8")
                self.assertIn("checkpoint.py read", text,
                              f"{path.relative_to(REPO)} forbids Read/subagent for "
                              f"checkpoints without naming the Bash fallback")

    def test_the_documented_fallback_is_pre_approved(self):
        """A fallback that triggers a permission prompt is not a fallback."""
        allow = json.loads(CLAUDE_SETTINGS.read_text(encoding="utf-8"))["permissions"]["allow"]
        prefixes = [r[len("Bash("):-len(":*)")] for r in allow
                    if r.startswith("Bash(") and r.endswith(":*)")]
        cmd = "python3 ~/.agent-configs/bin/checkpoint.py read --project demo"
        self.assertTrue(any(cmd.startswith(p) for p in prefixes),
                        f"no allow-rule prefix in {prefixes} covers {cmd!r}")

    def test_session_start_advertises_the_prefixed_form(self):
        """First thing in context every session — the one place a name is certain
        to be seen before the agent needs it."""
        hook = SESSION_START.read_text(encoding="utf-8")
        self.assertIn("mcp__vault-mcp__", hook)
        self.assertIn("checkpoint.py read", hook,
                      "the hook offers no fallback next to the tool it advertises")

    def test_session_start_mentions_checkpoints_only_when_one_exists(self):
        """The hook runs on every session start; an unconditional extra line would
        be a permanent token cost for projects that have never checkpointed."""
        hook = SESSION_START.read_text(encoding="utf-8")
        self.assertRegex(
            hook,
            r'if \[ -f "\$VAULT/projects/\$MATCHED_PROJECT/working-context\.md" \]',
            "the checkpoint hint is not gated on the file existing")

    def test_no_stack_still_claims_the_tools_need_no_lookup(self):
        """'always active' next to a bare short name is the premise that failed."""
        for stack, path in self.RULES.items():
            text = path.read_text(encoding="utf-8")
            if "always active" in text:
                self.assertIn("mcp__vault-mcp__", text,
                              f"{stack} rules say the tools are 'always active' but "
                              f"never show the id that makes that true")


class SkillMirrorTests(unittest.TestCase):
    """Fix 3, generalized — a skill installed for Claude and for agy is one skill.
    Nothing but a test notices when a change lands on one side only.

    VERBATIM_MIRRORS are the pairs that must stay byte-identical. HOST_ADAPTED are
    the pairs that legitimately differ, and only because agy names its host tools
    differently (`Bash` -> `run_shell_command`, `Read` -> `read_file`, `Grep` ->
    `grep`) or points at a skill where Claude points at a file path. Those are
    checked for equal shape instead, so a real edit to one side still shows up."""

    CLAUDE_SKILLS = REPO / ".claude/skills"
    PLUGINS = REPO / ".antigravity/plugins"

    VERBATIM_MIRRORS = {
        "architect-interview": "general",
        "compose-docs": "general",
        "paper-outline": "general",
        "isscc-figure": "general",
        "checkpoint": "obsidian",
        "project-archaeology": "obsidian",
    }
    HOST_ADAPTED = {
        "santa-method": "general",
        "obsidian-audit": "obsidian",
        "obsidian-notes": "obsidian",
    }
    # Claude-only: graphify ships with its own references/ tree and has no agy plugin.
    CLAUDE_ONLY = {"graphify"}

    def _pair(self, skill, plugin):
        return (self.CLAUDE_SKILLS / skill / "SKILL.md",
                self.PLUGINS / plugin / "skills" / skill / "SKILL.md")

    def test_every_claude_skill_is_accounted_for(self):
        """A new skill added to one stack only is the failure this catches."""
        known = set(self.VERBATIM_MIRRORS) | set(self.HOST_ADAPTED) | self.CLAUDE_ONLY
        on_disk = {d.name for d in self.CLAUDE_SKILLS.iterdir() if (d / "SKILL.md").is_file()}
        self.assertEqual(on_disk - known, set(),
                         "skill(s) exist for Claude but are not classified here — "
                         "mirror them into an agy plugin, or add to CLAUDE_ONLY")
        self.assertEqual(known - on_disk - self.CLAUDE_ONLY, set(),
                         "classified skill(s) no longer exist under .claude/skills")

    def test_verbatim_mirrors_are_byte_identical(self):
        for skill, plugin in self.VERBATIM_MIRRORS.items():
            claude, agy = self._pair(skill, plugin)
            with self.subTest(skill=skill):
                self.assertTrue(agy.is_file(), f"{skill} is not installed for agy ({agy})")
                self.assertEqual(claude.read_text(encoding="utf-8"),
                                 agy.read_text(encoding="utf-8"),
                                 f"the agy copy of {skill} has drifted from the Claude one")

    def test_host_adapted_mirrors_keep_the_same_shape(self):
        """These differ only in host tool names, so their headings must still match."""
        for skill, plugin in self.HOST_ADAPTED.items():
            claude, agy = self._pair(skill, plugin)
            with self.subTest(skill=skill):
                heads = [tuple(l for l in p.read_text(encoding="utf-8").splitlines()
                               if l.startswith("#")) for p in (claude, agy)]
                self.assertEqual(heads[0], heads[1],
                                 f"{skill} headings diverged — that is content drift, "
                                 f"not a host-tool rename")

    def test_every_skill_declares_name_and_description(self):
        """Both hosts route on the frontmatter description; without it a skill is
        installed but never surfaced — the same class of bug as an unfindable tool."""
        for path in sorted(self.CLAUDE_SKILLS.glob("*/SKILL.md")) + \
                sorted(self.PLUGINS.glob("*/skills/*/SKILL.md")):
            with self.subTest(skill=str(path.relative_to(REPO))):
                lines = path.read_text(encoding="utf-8").splitlines()
                self.assertEqual(lines[0], "---", "SKILL.md must open with frontmatter")
                end = lines.index("---", 1)
                fm = "\n".join(lines[1:end])
                self.assertRegex(fm, r"(?m)^name: \S+")
                self.assertRegex(fm, r"(?m)^description: \S+")

    def test_skill_dir_names_are_lowercase_hyphenated(self):
        for path in sorted(self.CLAUDE_SKILLS.glob("*/SKILL.md")) + \
                sorted(self.PLUGINS.glob("*/skills/*/SKILL.md")):
            name = path.parent.name
            with self.subTest(skill=name):
                self.assertRegex(name, r"^[a-z0-9]+(-[a-z0-9]+)*$")

    def test_skill_dir_matches_its_declared_name(self):
        """agentcfg symlinks by DIRECTORY name; the host routes on the frontmatter
        `name`. If they disagree the skill is invoked under a name that is not the
        one installed."""
        for path in sorted(self.CLAUDE_SKILLS.glob("*/SKILL.md")) + \
                sorted(self.PLUGINS.glob("*/skills/*/SKILL.md")):
            declared = re.search(r"(?m)^name:\s*(\S+)", path.read_text(encoding="utf-8"))
            with self.subTest(skill=path.parent.name):
                self.assertIsNotNone(declared)
                self.assertEqual(declared.group(1), path.parent.name)


class SingleParserTests(unittest.TestCase):
    """Fix 3 — the ---CHECKPOINT--- format must have exactly one implementation."""

    HOOKS = ("hooks/update-timeline.sh", "hooks/pre-compact.sh", "hooks/session-start.sh")

    def test_hooks_delegate_to_checkpoint_py(self):
        for rel in self.HOOKS:
            text = (REPO / rel).read_text(encoding="utf-8")
            self.assertIn("checkpoint.py", text, f"{rel} does not call the shared parser")

    def test_no_hook_reimplements_the_split(self):
        for rel in self.HOOKS:
            text = (REPO / rel).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"re\.split\(.{0,10}---CHECKPOINT---",
                                f"{rel} re-implements the checkpoint split")
            self.assertNotRegex(text, r'grep\s+"\^## Checkpoint"',
                                f"{rel} re-implements the checkpoint header scan")

    def test_separator_matching_is_line_anchored(self):
        """Notes mention `---CHECKPOINT---` in prose; a substring split tears the
        hand-maintained preamble into entries that trimming then deletes."""
        src = (REPO / "bin/checkpoint.py").read_text(encoding="utf-8")
        self.assertRegex(src, r"SEP_RE\s*=\s*re\.compile\(r?\"\(\?m\)\^---CHECKPOINT---")
        self.assertIn("SEP_RE.split(text)", src)


if __name__ == "__main__":
    unittest.main()
