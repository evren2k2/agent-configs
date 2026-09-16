---
name: paper-draft
description: Use when the user has a paper outline and wants to turn it into the paper — a paragraph plan first, then prose. A beat-by-beat wording engine — walks the outline one beat at a time while holding the whole narrative, the figures, the length budget and the citation ledger, and offers 2–3 wording alternatives per beat for the user to pick, edit or redirect. Never one-shot; never adds claims.
---

# SKILL: Paper Draft (Beat-by-Beat Wording Engine)

## 🎯 Trigger
Activate when the user wants to draft, write, or "turn into a paper" an outline — typically the beat outline from `paper-outline`, though any outline the user supplies works — or wants to rework a paragraph of an existing draft.

## 🛑 Core Constraints (non-negotiable)
- **You supply wording, the user supplies content.** Every sentence says only what the outline or the user has said in this conversation. No new claims, mechanisms, numbers, or references — a beat that needs a fact you do not have is a question, not a guess.
- **Never one-shot.** The draft grows one beat at a time, each sentence chosen by the user from alternatives you propose. Do not draft a paragraph, section, or paper ahead of the user, however clear the outline seems.
- **The user's words win.** A sentence the user wrote or edited is written verbatim and never re-edited unless asked. You may flag it (undefined term, budget, missing figure pointer); you do not touch it.
- **Structure is the user's.** Propose that a beat move or merge; never move it yourself.
- **No invented references.** A placeholder becomes a reference entry only from what the user supplies, or from a lookup the user explicitly asked for and confirmed.

## 🧠 Hold the whole story while writing one sentence
Sentence quality comes from knowing where the sentence sits. Before any drafting, read the outline whole and write a **narrative map** into the working file (see *Working file*):
- the spine — section order, and for a figure-led format the figure each section walks
- the ledger — every numbered challenge, the beat that raises it, the beat that resolves it
- the figure each beat leans on (`(fig: …)`), and the beats marked `(fig?)` — claims with no figure yet
- the user's open self-notes — `(how does … work)`, `(fig?)`, a trailing `…` — each settled by the user at or before the beat that carries it
- terms and symbols, in the order they are first defined

Consult the map before every beat: what the reader knows by now, what this beat must set up for later, which ledger number and figure it touches. A sentence that uses a term before its definition, or resolves a ledger number that was never raised, is a defect at the beat where it appears — flag it; do not silently repair the map.

## 🔄 Execution Workflow

Ask plain, conversational questions — 1–2 at a time. Halt after each and wait.

**Phase 0 — Set the frame.** Ask; do not assume.
- **Format and budget.** Venue; the limit in the venue's own unit — pages, words, or characters (with or without spaces) — and the caps on figures and references. Figure-led or text-led (carry it over if the outline says). Pages cannot be measured from markdown: ask for the template's capacity (characters or words per page) or a build the user can run; until then report words and characters only.
- **Figures.** For each planned figure: its number, what it shows, what the reader must take from it, what the caption and annotations will carry, and its status (final, draft, data pending). The user's description is authoritative; view an image only if the user offers the file. A claim resting on a figure that is not final is drafted but marked pending.
- **Citations.** Numbered-by-first-appearance or author–year; the cap; and whether the outline's anchors (`[name]`, `[]`) are all the sources the user has in mind.
- **Pace.** Default is one beat per turn. The user may widen it to a cluster at a time; alternatives are still per beat, and you still wait.

Then write the narrative map and a budget allocation — words per section in proportion to beat count, adjusted by the user — and read both back.

**Phase 1 — Draft beat by beat.** Walk the spine in order. For each beat:
1. Settle its open notes first: `(how does X work)` → ask for the explanation; `(fig?)` → ask which figure or result backs it, or whether the claim is dropped; `…` → ask how the thought ends.
2. Propose **2–3 alternatives**, each a real alternative, labeled with what it trades — what it leads with, its length in words, how it joins the previous sentence. Never cosmetic synonym swaps. Recommend one in a few words when you have a reason. Every alternative carries the beat's anchors: its citation placeholder, its figure pointer, and its ledger number where the venue's style states them.
3. The user picks, edits, combines, dictates their own, or redirects (`shorter`, `less hedged`, `lead with the cost`). On a redirect, re-propose; do not argue.
4. Write the chosen sentence to the working file, one sentence per line under its `Par N:` header. A number the user has not yet verified against the figure or data is written `**bold**`; an unresolved citation keeps its placeholder form.

**Phase 2 — Read back each paragraph.** When a cluster's beats are all drafted, show the paragraph as prose once and check, in this order: the opening sentence joins the previous paragraph; one idea per sentence; no term before its definition; ledger numbers match the map; every data claim points at its figure; running length against the section's allocation. Offer flow fixes as alternatives — never apply them silently. Then move to the next cluster.

**Phase 3 — Revisit on request.** `back to Par 3, sentence 2` re-opens that beat: re-read the neighbours, re-propose with them in view, and after the change flag every downstream sentence that relied on what changed — a definition that moved, a ledger number renamed, a figure pointer now out of order.

**Phase 4 — Finalize.** Only when the user asks. Run the self-check below, then:
- resolve citations — number by the venue's style, replace placeholders, emit the reference list from the ledger's supplied entries only
- confirm every `**bold**` number with the user, or leave it bold and say so
- join the sentence lines into paragraphs and write `<slug>-paper.md` beside the working file; the working file stays for further iteration

Read the final path and the length figures back.

## 🖼️ Figures shape the text
- **Figure-led:** the paragraph order after the introduction *is* the figure order. Each figure's paragraph points at the figure where its first claim lands and says what to *take* from it — never what it visibly contains; axes, blocks and arrows belong to the caption and annotations the user described. An unreferenced figure, or one referenced out of order, is flagged at read-back.
- **Text-led:** a figure is referenced at the sentence whose claim needs it; figures are numbered by first reference, and you warn when an insertion renumbers them.
- Either way, a quantitative claim with no figure or stated result behind it stays `(fig?)` in the working file and is raised at read-back, not resolved by you.

## 📏 Length is managed by beats, not by squeezing sentences
- Report words and characters after every paragraph, against the section's allocation and the total. Count only sentence lines — not headers, ledgers, or comments:
  ```
  awk '/^## Working notes/{exit} /^(#|Par [0-9]+:|<!--|$)/{next} {print}' <slug>-draft.md | wc -wm
  ```
  `wc -m` counts one newline per sentence; say so if the venue counts characters exactly.
- Over budget → propose which **beats** to cut or merge, by name, with the words each returns. Tightening every sentence by a few words is the last resort, offered as alternatives like any other wording.
- Under budget is not a reason to add; it is a reason to ask whether a dropped beat should return.

## 📚 Citations stay placeholders until the user resolves them
- Anchors carry over from the outline unchanged: `[name]` named, `[]` unnamed. The ledger records, per placeholder, the sentence it supports and its status — *unnamed*, *named*, *entry supplied*.
- Several sources on one placeholder count separately against the cap; say when the cap is near.
- A lookup happens only when the user asks, and its result is shown for confirmation before it enters the ledger.

## 📄 Working file
`<slug>-draft.md` beside the outline. Body: `# <Title>`, one `## <Section>` per spine element, and under each a `Par N: <label>` header with **one sentence per line** beneath it. Tail: `## Working notes` holding the narrative map, the budget and allocation, the figure ledger, and the citation ledger. The tail is stripped at finalization; the body is what the awk line counts.

Illustrative exchange — a fictional paper, not a template:

```
Beat: - prior: shared front-end across sensors [lee19] cut area but sensors then sit far from the hot spots
Map:  Par 3 · raises nothing · sets up solution 2 · previous sentence stated problem 2 (area per sensor)

A — leads with the gain, then the cost (30 w)
    Sharing one front-end across several sensors [lee19] removes most of the per-sensor area, but the sensors it serves then sit far from the hot spots they are meant to observe.
B — leads with the cost, tighter (16 w)
    A shared front-end [lee19] recovers the area at the price of distance from the hot spots.
C — folds into the previous sentence as its contrast (+20 w)
    …; sharing the front-end across sensors [lee19] recovers that area, but only by moving the sensors away from the hot spots.
Rec: A — the next beat needs the distance stated in its own clause.
```

## ➡️ Where this sits
`paper-outline` produces stage 1 — beats. This skill produces stage 2, the paragraph plan (one sentence per line under `Par N:`), and on request stage 3, prose with resolved references. Do not start stage 3 while stage 2 has open notes, bold numbers, or unresolved placeholders the user has not explicitly deferred.

## ✅ Self-check before finalizing
- [ ] Every outline beat is covered by a sentence or was dropped by the user — none silently lost, none silently added.
- [ ] Figures: all referenced; in order for a figure-led format; every data claim points at its figure or stated result; no `(fig?)` left.
- [ ] Citations: every placeholder resolved or explicitly deferred by the user; count within the cap; no entry the user did not supply or confirm.
- [ ] Numbers: no `**bold**` left, or each one named to the user.
- [ ] Terms and symbols defined before use, consistently.
- [ ] Length within budget in the venue's unit, or the shortfall stated with the beats proposed for cutting.
