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

USAGE
    instincts.py propose --disposition TEXT --origin TEXT [--project P]
    instincts.py list [--all]
    instincts.py seen --match TEXT [--origin TEXT]   # re-triggered; earns promotion
    instincts.py promote --match TEXT [--apply]
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

# A promotion has to land in BOTH stacks or it is not a disposition, it is a Claude
# disposition. agentcfg installs `rules/` for Claude only (AGENTS = ["claude"]), so agy
# takes the same content as a skill in the general plugin — the arrangement already used
# for behavioral-guidelines. Both files are written from one string by `promote`, because
# a mirror that depends on someone remembering to update it is a mirror that drifts.
RULES_FILE = BIN_DIR.parent / ".claude/rules/learned-dispositions.md"
AGY_SKILL = (BIN_DIR.parent /
             ".antigravity/plugins/general/skills/learned-dispositions/SKILL.md")

FIELDS = ("disposition", "origin", "date", "project", "seen", "last_seen")


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
# Entries are proposals. They are promoted into .claude/rules/learned-dispositions.md --
# which every session loads -- only after re-triggering in a later session, and only with
# the user's approval. Managed by bin/instincts.py; the cap is enforced, not requested.
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
    for x in items:
        if x["disposition"].strip().lower() != text.lower():
            continue
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
        "seen": 1,
        "last_seen": today,
    })
    save(items)
    print(f"queued ({len(items)}/{args.cap}): {text[:70]}")
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
        print(f"  [{ready}] seen={x.get('seen', 0)} {x.get('date', '?')} "
              f"({x.get('project', '?')})")
        print(f"          {x['disposition']}")
        if args.all:
            print(f"          origin: {x.get('origin', '')[:140]}")
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
              "(needs the user's approval; it edits a rules file loaded every session)")
    return 0


_BODY = """\
# Learned dispositions

How to work, learned from corrections in past sessions and promoted out of the
`agent/instincts.yaml` staging queue by `bin/instincts.py`. Each entry re-triggered in
at least {promote_at} separate sessions before landing here, and was approved by the user.

These are deliberately kept apart from the hand-authored guidance in
`behavioral-guidelines.md` so their provenance stays visible.
"""

RULES_HEADER = "---\ntitle: Learned dispositions\n---\n\n" + _BODY

# agy loads skills, not rules, so the same content ships with skill frontmatter.
AGY_HEADER = (
    "---\nname: learned-dispositions\n"
    "description: Dispositions learned from corrections in past sessions and promoted "
    "from the instincts queue — how to work, not what is true about a system. Load at "
    "the start of any task.\n---\n\n" + _BODY
)


def _append(path: Path, header: str, block: str) -> None:
    if path.exists():
        text = path.read_text(encoding="utf-8").rstrip("\n") + "\n"
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = header.format(promote_at=PROMOTE_AT)
    _atomic_write_text(path, text + "\n" + block)


def cmd_promote(args) -> int:
    items = load()
    i = find(items, args.match)
    x = items[i]

    if x.get("seen", 0) < PROMOTE_AT and not args.force:
        sys.exit(f"instincts: seen={x.get('seen', 0)}, needs {PROMOTE_AT}. A disposition "
                 f"earns always-on status by recurring, which is exactly what the "
                 f"retired instincts never did. Use --force to override.")

    block = (f"- **{x['disposition']}**\n"
             f"  <sub>seen {x.get('seen', 1)}x since {x.get('date', '?')} "
             f"({x.get('project', '?')}); {x.get('origin', '')}</sub>\n")

    if not args.apply:
        print(f"would append to BOTH stacks:\n  {RULES_FILE}\n  {AGY_SKILL}\n")
        print(block)
        print("nothing written. re-run with --apply once the user has approved — these "
              "files are loaded into every session.")
        return 0

    _append(RULES_FILE, RULES_HEADER, block)
    _append(AGY_SKILL, AGY_HEADER, block)

    del items[i]
    save(items)
    print(f"promoted -> {RULES_FILE}")
    print(f"         -> {AGY_SKILL}")
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
    p.add_argument("--project")
    p.add_argument("--cap", type=int, default=CAP)
    p.set_defaults(fn=cmd_propose)

    p = sub.add_parser("list", help="show the queue")
    p.add_argument("--all", action="store_true", help="include origins")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("seen", help="mark re-triggered in this session")
    p.add_argument("--match", required=True)
    p.add_argument("--origin", default="", help="what re-triggered it, verbatim")
    p.set_defaults(fn=cmd_seen)

    p = sub.add_parser("promote", help="move into the always-loaded rules file")
    p.add_argument("--match", required=True)
    p.add_argument("--apply", action="store_true", help="actually write (user approved)")
    p.add_argument("--force", action="store_true", help="promote below the seen bar")
    p.set_defaults(fn=cmd_promote)

    p = sub.add_parser("expire", help="drop stale proposals that never re-triggered")
    p.add_argument("--days", type=int, default=EXPIRE_DAYS)
    p.set_defaults(fn=cmd_expire)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
