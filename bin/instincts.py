#!/usr/bin/env python3
"""instincts — the disposition staging queue, and its promotion path into rules/.

WHAT A DISPOSITION IS, AND WHAT IT IS NOT
    A *disposition* is how the agent should work: "never state a runtime estimate you
    have not measured". Its trigger is *any turn*, not a searchable situation, so it
    only does anything if it is always in context.

    A *knowledge* item is what is true about a system: "PyMTL3 cosim reports 0
    mismatches when an InPort is undriven". Its trigger is a specific situation, it is
    retrieved on demand, and it belongs in a vault project note — which is indexed and
    actually gets read.

    The old instincts.yaml conflated the two. Because the capture prompt asked "did any
    reusable pattern emerge?" at end-of-turn, when session specifics are at peak
    salience, it returned knowledge every single time: 30 of 30 entries, none of which
    ever recurred, in a file nothing ever read. Dispositions come from a different
    source — the moments the user corrected us — and so need a different question.

WHY A SCRIPT AND NOT A PROSE RULE
    The old file had a `confidence` field that was supposed to rise on validation and
    fall on contradiction. Across 43 commits it never moved once: 40 were pure appends.
    An invariant an agent is merely *asked* to maintain does not hold. So the two that
    matter are enforced here instead:

      * the CAP. Dispositions are always-on, so the budget is finite. Adding to a full
        queue fails and names what you must evict.
      * PROMOTION IS EARNED. A disposition leaves the queue only after it has been
        re-triggered in a LATER session (`seen`), which is the evidence that its
        trigger actually recurs — the property the old entries provably lacked.
        Re-proposing an already-queued rule counts as that re-trigger, which is what
        closes the loop: the hook asks every session to propose what it was corrected
        on, so a second session reaching the same rule promotes it without anyone
        having to remember a separate command. A date guard keeps "again" meaning a
        later session rather than a second mention in this one.

    Capture stays autonomous and cheap. Activation does not: `promote` prints the block
    and changes nothing until `--apply`, because a rule that shapes every future session
    is a direction-class write under the vault policy and belongs to the user.

SCOPE — PROJECT BY DEFAULT
    Projects differ in scope and method, so a rule learned on one is not presumed to
    hold on another. Every disposition carries `scope: project` (the default) or
    `scope: global`, and promotion routes on it:
      * project -> the vault's projects/<p>/decisions/working-mode.md, which the
        SessionStart hook prints whenever that project is the CWD. This is the same
        content as the "working mode" rulings that used to live only in a checkpoint
        ledger — and were lost when one checkpoint failed to carry the ledger forward.
      * global  -> the vault's agent/learned-dispositions.md, which the SessionStart
        hook prints in every session of every project.
    Both live in the vault, not the repo: dispositions are the user's, and the repo is
    the mechanism. A repo rules file also needed `agentcfg update --apply` to be linked
    into ~/.claude/rules, and for a week it was not, so global rules loaded only when
    the CWD was agent-configs. A hook print has no install step to forget, and one
    print serves both stacks because agy runs the same session-start.sh.
    The signal that a rule is global is the same re-trigger evidence promotion already
    asks for: the identical rule proposed from a SECOND project. `propose` records the
    extra project and says so; `promote --scope global` makes the call, with approval.

USAGE
    instincts.py propose --disposition TEXT --origin TEXT --project P [--scope project|global]
    instincts.py list [--all]
    instincts.py pending                    # hook-friendly: READY / near-cap lines, else silent
    instincts.py seen --match TEXT [--origin TEXT]   # re-triggered; earns promotion
    instincts.py promote --match TEXT [--apply] [--scope project|global]
    instincts.py expire                     # drop stale never-re-triggered proposals
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

import yaml

BIN_DIR = Path(__file__).resolve().parent
if str(BIN_DIR) not in sys.path:
    sys.path.append(str(BIN_DIR))

from vault import vault_root, _atomic_write_text  # root resolution + durable writes

CAP = 15                    # always-on budget; see module docstring
PROMOTE_AT = 2              # distinct sessions a disposition must re-trigger in
EXPIRE_DAYS = 90            # a proposal that never re-triggers is not a disposition

FIELDS = ("disposition", "origin", "date", "project", "scope", "seen", "last_seen")
SCOPES = ("project", "global")


def global_path() -> Path:
    """Where a GLOBAL disposition lands; session-start.sh prints it in every session."""
    return vault_root() / "agent" / "learned-dispositions.md"


def working_mode_path(project: str) -> Path:
    """Where a PROJECT-scoped disposition lands: the project's direction set."""
    return vault_root() / "projects" / project / "decisions" / "working-mode.md"


def bump(entry: dict, origin: str = "") -> bool:
    """Count a re-trigger. True if it counted, False if already counted today.

    The date guard is what keeps `seen` meaning "recurred in a LATER session" rather
    than "was mentioned twice in one". It under-counts (two sessions on one day count
    once), which is the safe direction for a gate that installs always-on behaviour.
    """
    today = datetime.date.today().isoformat()
    if entry.get("last_seen") == today:
        return False
    entry["seen"] = entry.get("seen", 0) + 1
    entry["last_seen"] = today
    if origin:
        entry.setdefault("recurrences", []).append(f"{today}: {origin}")
    return True


def queue_path() -> Path:
    return vault_root() / "agent" / "instincts.yaml"


def load() -> list[dict]:
    p = queue_path()
    if not p.exists():
        return []
    return yaml.safe_load(p.read_text(encoding="utf-8")) or []


HEADER = """\
# Disposition staging queue — HOW the agent should work, not what is true about a system.
#
# Knowledge ("the X test validates Y", "this edge case comes from A/B interaction") goes
# to a vault project note instead; it is retrieved on demand and does not belong here.
#
# Entries are proposals, scoped `project` (default) or `global`. Promotion -- only after
# re-triggering in a later session, and only with the user's approval -- routes on scope:
# project -> projects/<p>/decisions/working-mode.md (printed at session start for that
# project); global -> agent/learned-dispositions.md (printed in every session, every project).
# Managed by bin/instincts.py; the cap is enforced, not requested.
"""


def save(items: list[dict]) -> None:
    body = yaml.safe_dump(items, sort_keys=False, allow_unicode=True, width=88,
                          default_flow_style=False) if items else ""
    _atomic_write_text(queue_path(), HEADER + body)


def find(items: list[dict], needle: str) -> int:
    """Index of the single entry matching `needle`, or exit with a useful message."""
    n = needle.lower()
    hits = [i for i, x in enumerate(items)
            if n in str(x.get("disposition", "")).lower()
            or n in str(x.get("origin", "")).lower()]
    if not hits:
        sys.exit(f"instincts: nothing matches {needle!r}")
    if len(hits) > 1:
        listing = "\n".join(f"  - {items[i]['disposition'][:80]}" for i in hits)
        sys.exit(f"instincts: {needle!r} matches {len(hits)} entries:\n{listing}")
    return hits[0]


# ------------------------------------------------------------------ commands
def cmd_propose(args) -> int:
    items = load()

    text = args.disposition.strip()
    scope = getattr(args, "scope", None) or "project"
    if scope not in SCOPES:
        sys.exit(f"instincts: --scope must be one of {SCOPES}")
    if scope == "project" and not args.project:
        sys.exit("instincts: a project-scoped disposition needs --project <p> "
                 "(or say --scope global if it truly holds everywhere)")
    for x in items:
        if x["disposition"].strip().lower() != text.lower():
            continue
        # The same rule arriving from a DIFFERENT project is the evidence that it is
        # not project working-mode but a global disposition. Record it; the promotion
        # (and the scope call) stays with the user.
        if args.project and args.project != x.get("project"):
            also = x.setdefault("also_seen_in", [])
            if args.project not in also:
                also.append(args.project)
            print(f"re-triggered in a second project ({x.get('project')} -> {args.project}); "
                  f"candidate for `promote --scope global`")
        # A duplicate is not noise — it is the evidence promotion asks for. The hook
        # tells every session to propose what it was corrected on; a LATER session
        # independently arriving at the same rule is exactly "this recurs". Treating
        # it as a no-op (the original behaviour) left `seen` pinned at 1 forever, so
        # nothing could ever promote and the queue quietly expired instead.
        if bump(x, args.origin.strip()):
            save(items)
            print(f"already queued — counted as a re-trigger (seen={x['seen']}): "
                  f"{x['disposition'][:60]}")
            if x["seen"] >= PROMOTE_AT:
                print("READY to promote — `instincts.py promote --match ... --apply` "
                      "(needs the user's approval)")
        else:
            print(f"already queued, already counted today (seen={x.get('seen', 1)}): "
                  f"{x['disposition'][:60]}")
        return 0

    if len(items) >= args.cap:
        weakest = sorted(items, key=lambda x: (x.get("seen", 0), x.get("date", "")))[:3]
        listing = "\n".join(
            f"  seen={x.get('seen', 0)} {x.get('date', '?')}  {x['disposition'][:66]}"
            for x in weakest)
        sys.exit(
            f"instincts: queue is full ({len(items)}/{args.cap}). A disposition is "
            f"always-on, so the budget is finite.\nEvict one first "
            f"(`instincts.py expire`, or promote a ready one). Weakest candidates:\n"
            f"{listing}")

    today = datetime.date.today().isoformat()
    items.append({
        "disposition": text,
        "origin": args.origin.strip(),
        "date": today,
        "project": args.project or "global",
        "scope": scope,
        "seen": 1,
        "last_seen": today,
    })
    save(items)
    print(f"queued ({len(items)}/{args.cap}, scope={scope}): {text[:70]}")
    print(f"promotes after re-triggering in {PROMOTE_AT - 1} more session(s)")
    return 0


def cmd_list(args) -> int:
    items = load()
    if not items:
        print("instincts: queue is empty")
        return 0
    print(f"{len(items)}/{CAP} queued\n")
    for x in sorted(items, key=lambda x: -x.get("seen", 0)):
        ready = "READY" if x.get("seen", 0) >= PROMOTE_AT else "     "
        where = "global" if x.get("scope") == "global" else f"project:{x.get('project', '?')}"
        extra = f" +{','.join(x['also_seen_in'])}" if x.get("also_seen_in") else ""
        print(f"  [{ready}] seen={x.get('seen', 0)} {x.get('date', '?')} ({where}{extra})")
        print(f"          {x['disposition']}")
        if args.all:
            print(f"          origin: {x.get('origin', '')[:140]}")
    return 0


def cmd_pending(args) -> int:
    """What the user needs to decide, or nothing.

    Promotion is the user's call, but the only place READY ever showed was the
    `propose` output in the turn it happened — if the agent did not ask right then,
    nothing reminded anyone. The SessionStart hook prints this so a pending decision
    is raised at the start of the next session rather than forgotten. Silent when
    there is nothing to say, so it costs no tokens on the normal path.
    """
    items = load()
    ready = [x for x in items if x.get("seen", 0) >= PROMOTE_AT]
    lines = []
    for x in ready:
        where = "global" if x.get("scope") == "global" else f"project:{x.get('project', '?')}"
        extra = f"; also seen in {','.join(x['also_seen_in'])} -> consider --scope global" \
            if x.get("also_seen_in") else ""
        lines.append(f"  READY (seen={x['seen']}, {where}{extra}): {x['disposition'][:90]}")
    if lines:
        print(f"DISPOSITIONS READY TO PROMOTE — ask the user before acting; promotion is their "
              f"call (`instincts.py promote --match <text> --apply`):")
        print("\n".join(lines))
    if len(items) >= CAP - 1:
        print(f"DISPOSITION QUEUE {len(items)}/{CAP}: the next `propose` "
              f"{'will be refused' if len(items) >= CAP else 'fills it'} — ask the user which "
              f"entries to promote or expire (`instincts.py list`).")
    return 0


def cmd_seen(args) -> int:
    items = load()
    i = find(items, args.match)
    x = items[i]
    if not bump(x, args.origin.strip() if getattr(args, "origin", "") else ""):
        print(f"already counted today (seen={x.get('seen', 1)}): {x['disposition'][:60]}")
        return 0
    save(items)
    print(f"seen={x['seen']}: {x['disposition'][:70]}")
    if x["seen"] >= PROMOTE_AT:
        print("READY to promote — `instincts.py promote --match ... --apply` "
              "(needs the user's approval; it edits a note printed into every session)")
    return 0


# A global promotion lands in the vault, so it is a note like working-mode below. The
# `seen` count in each entry is the evidence: an entry promoted with --force (the user's
# call, e.g. when the queue is full) shows seen 1x, and the header must not claim more.
GLOBAL_HEADER = """\
---
date: {today}
tags: [agent_util, disposition, direction]
type: decision
status: active
---

# Learned dispositions

How to work, in every project: corrections from past sessions, promoted out of the
`agent/instincts.yaml` queue by `bin/instincts.py` with the user's approval — after
re-triggering in a later session, or directly by the user. The SessionStart hook prints
these in every session; each project's `decisions/working-mode.md` (e.g.
[[agent-configs/decisions/working-mode]]) adds rulings for that project only. Never edit by hand; use `instincts.py promote --apply`.
"""


# A project-scoped promotion lands in the vault, so it is a note: frontmatter and a
# wikilink are required by the vault rules. `type: decision` because working mode is
# direction — the user's rulings on HOW this project is run — not implementation.
WORKING_MODE_HEADER = """\
---
date: {{today}}
tags: [{project}, working-mode, direction, disposition]
type: decision
status: active
project: {project}
---

# {project} — Working mode

How this project is run: the user's standing rulings on the agent's role, tooling
and process. Each entry was a correction made in a session, promoted out of the
`agent/instincts.yaml` queue by `bin/instincts.py` after recurring, and approved by
the user. The SessionStart hook prints these whenever this project is the CWD, so
they bind before the first action — independently of the [[{project}/working-context]]
checkpoint ledger, which carries the same rulings verbatim but can be lost.

Treat every line as binding unless the user has since said otherwise.
"""


def _append(path: Path, header: str, block: str) -> None:
    if path.exists():
        text = path.read_text(encoding="utf-8").rstrip("\n") + "\n"
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = header.replace("{today}", datetime.date.today().isoformat())
    _atomic_write_text(path, text + "\n" + block)


def cmd_promote(args) -> int:
    items = load()
    i = find(items, args.match)
    x = items[i]

    if x.get("seen", 0) < PROMOTE_AT and not args.force:
        sys.exit(f"instincts: seen={x.get('seen', 0)}, needs {PROMOTE_AT}. A disposition "
                 f"earns always-on status by recurring, which is exactly what the "
                 f"retired instincts never did. Use --force to override.")

    scope = getattr(args, "scope", None) or x.get("scope") or "project"
    if scope not in SCOPES:
        sys.exit(f"instincts: --scope must be one of {SCOPES}")
    project = x.get("project") or ""
    if scope == "project" and (not project or project == "global"):
        sys.exit("instincts: this entry has no project; promote it with --scope global "
                 "or fix its `project:` field first")

    block = (f"- **{x['disposition']}**\n"
             f"  <sub>seen {x.get('seen', 1)}x since {x.get('date', '?')} "
             f"({project or '?'}); {x.get('origin', '')}</sub>\n")

    if scope == "global":
        targets = [(global_path(), GLOBAL_HEADER)]
        where = "the global learned-dispositions note (printed in every session)"
    else:
        targets = [(working_mode_path(project), WORKING_MODE_HEADER.format(project=project))]
        where = f"the {project} working-mode note (printed at session start for that project)"

    if not args.apply:
        print(f"would append to {where}:")
        for path, _ in targets:
            print(f"  {path}")
        print()
        print(block)
        print("nothing written. re-run with --apply once the user has approved — these "
              "files are loaded into future sessions.")
        return 0

    for path, header in targets:
        _append(path, header, block)

    del items[i]
    save(items)
    for path, _ in targets:
        print(f"promoted -> {path}")
    print(f"queue now {len(items)}/{CAP}")
    return 0


def cmd_expire(args) -> int:
    items = load()
    cutoff = (datetime.date.today() - datetime.timedelta(days=args.days)).isoformat()
    keep, drop = [], []
    for x in items:
        stale = x.get("date", "9999") < cutoff and x.get("seen", 0) < PROMOTE_AT
        (drop if stale else keep).append(x)
    if not drop:
        print(f"instincts: nothing older than {args.days}d without a re-trigger")
        return 0
    save(keep)
    print(f"expired {len(drop)} never-re-triggered proposal(s); queue now {len(keep)}/{CAP}")
    for x in drop:
        print(f"  - {x.get('date', '?')} {x['disposition'][:70]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("propose", help="queue a disposition learned from a correction")
    p.add_argument("--disposition", required=True, help="the rule, imperative, one line")
    p.add_argument("--origin", required=True,
                   help="what produced it — quote the user's correction verbatim")
    p.add_argument("--project", help="where the correction happened (required for scope=project)")
    p.add_argument("--scope", choices=SCOPES, default="project",
                   help="project (default): binds only on that project; global: every session")
    p.add_argument("--cap", type=int, default=CAP)
    p.set_defaults(fn=cmd_propose)

    p = sub.add_parser("list", help="show the queue")
    p.add_argument("--all", action="store_true", help="include origins")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("pending", help="READY / near-cap lines for the session-start hook; silent otherwise")
    p.set_defaults(fn=cmd_pending)

    p = sub.add_parser("seen", help="mark re-triggered in this session")
    p.add_argument("--match", required=True)
    p.add_argument("--origin", default="", help="what re-triggered it, verbatim")
    p.set_defaults(fn=cmd_seen)

    p = sub.add_parser("promote", help="move into the always-printed vault note (global or project working mode)")
    p.add_argument("--match", required=True)
    p.add_argument("--apply", action="store_true", help="actually write (user approved)")
    p.add_argument("--force", action="store_true", help="promote below the seen bar")
    p.add_argument("--scope", choices=SCOPES, default=None,
                   help="override the queued scope at promotion time")
    p.set_defaults(fn=cmd_promote)

    p = sub.add_parser("expire", help="drop stale proposals that never re-triggered")
    p.add_argument("--days", type=int, default=EXPIRE_DAYS)
    p.set_defaults(fn=cmd_expire)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
