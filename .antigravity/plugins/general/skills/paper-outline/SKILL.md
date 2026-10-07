---
name: paper-outline
description: Use when the user wants to outline an academic research paper, or to restructure or revise an existing outline. An interview-driven scribe — elicits the story from the user as one-line beats (zero inference, zero filler) and writes a high-level, rearrangeable outline that later evolves into a paragraph plan and prose. Format-agnostic — figure-led (1-page ISSCC style) or text-led (journal style) spines.
---

# SKILL: Paper Outline (Interview-Driven Scribe)

## 🎯 Trigger
Activate when the user asks to outline, structure, or plan an **academic research paper** — typically given a title or thesis, rough notes, and a target venue — **or to restructure, reorder, or tighten an outline that already exists**. Restructuring is where beats drift into sentences, so the rules below apply there in full.

## 🛑 Core Constraints (non-negotiable)
- **The user decides or provides.** Every beat traces to something the user said in this conversation. No inferring, no assumptions, no interpolation from training data, no filler.
- **Options only when asked.** When the user asks for options (a spine, a section, a reworded beat), propose 2–3, mark each `(proposed)`, build them only from what the user has said or from a checked source, and say where you disagree. The user picks; nothing proposed enters the outline until they do. Locks are provisional: the user may reopen any decision, and a later decision supersedes an earlier one.
- **Sources check claims; they never generate beats.** A claim the user makes may be checked against the code, the data, or the literature, and must be when the outline will assert it as fact. Return a verdict (holds / overstated / wrong, with the evidence), never new beats. Prefer a subagent for code checks, so implementation detail does not pile up in context and leak into beats. A citation stays a tag the user attaches.
- **Beats, not sentences.** One line, one move in the argument, in the user's own words — `per-die trim is test cost – want accurate untrimmed`, never `Because every sensor needs a per-die trim, and trimming is test cost, the goal is a sensor that is accurate untrimmed.` Sentences come two stages later (see *What this feeds*). In practice:
  - about 12 words at most; a longer beat is two beats or a sentence;
  - no actors — `trim range can be declared`, never `the designer declares` / `an agent can`;
  - no editorial modifiers (`honestly`, `stated plainly`, `notably`);
  - no clause another beat already implies — after `front-end shared across sensors`, drop `no per-sensor calibration involved`.
- **Concept by default; implementation only where the section calls for it.** A beat says what the idea does or enables, not how it is built or used (counts, internals, tool names). Some papers have sections that are implementation by nature (a circuit paper's implementation section); there, and wherever the user asks, implementation beats belong. Never use implementation detail to elaborate a beat in a conceptual section. Take the cue from the user and the spine; if unsure for a section, ask.
- **Every beat earns its place.** If it adds nothing to the story, drop it.
- **Halt and ask.** Never run ahead and draft sections on your own. The outline grows only as the user feeds it.

## 🧠 The outline is a story told in movable beats
A research outline is an argument, not a table of contents. At this stage it is a set of **beats** — each a single line that can be cut, moved, or regrouped without breaking anything else. That property is the whole point of the format; every rule below protects it.
- **One beat per line, one level deep — sub-beats sparingly.** No multi-line bullets, no beat that only makes sense because of the one above it. The one exception: a numbered sub-list under a lead-in beat when the points must stay pinned to it (`prior: each attempt leaves one standing:` → `1. shared front-end …` `2. regulated front-end …`). Use it rarely — most clusters need none — and never deeper than one level.
- **Clusters.** Blank lines group beats into clusters ≈ one future paragraph. Clusters are unlabeled; labels come at the next stage.
- **The ledger.** Challenges are numbered once, in the order first raised — `problem 1 (process)`, `problem 3 (supply)` — and every later beat that answers one cites the number. Numbers are never reassigned when beats move; the ledger is what keeps a rearranged outline coherent.
- **Role labels, only where the role is not obvious.** A short lowercase prefix: `proposition`, `problem n`, `prior`, `solution n`, `this work`, `pivot` (a turn in the argument — `…but a throttling-only chip can live with that`). Plain beats need no label.
- **Self-notes in parentheses.** `(how does trim work)` = needs explaining later; `(process)` / `(supply)` = kind of challenge; `(fig: error vs temp)` = the figure or result the beat leans on; `(fig?)` = a claim the user has not yet tied to a figure or result. Where a figure carries the point on its own, the beat is just `we show X (fig: …)` — do not restate what the figure shows. A trailing `…` marks a thought the user left unfinished — keep it, do not finish it.
- **Citations as anchors.** `[lee19]` where the user attached one; bare `[]` where the user knows a cite is needed but did not name it.
- **Re-sketch in place.** The user will retell a cluster with more structure as the story firms up. Replace the earlier sketch with the new one; the outline holds only the current telling.

Excerpt in the target register — a fictional paper, mid-interview:

```
## Introduction

- on-die thermal monitoring is mandatory at today's power density
- BJT sensors are the accurate option (why BJT – brief)
- but each sensor needs a per-die trim, and trim time is test cost…
- want accuracy without trim…

- proposition: untrimmed sensors []
- problem 1 (process): die-to-die spread sets the untrimmed error floor
- problem 2 (area): cancelling it costs area per sensor – a die needs many
- solution 1: a throttling-only chip can live with the floor – so 2 is the one that matters
- pivot: solve area and you have a sensor you can sprinkle everywhere

- problem 3 (supply): droop under load shifts the reading (fig?)
- prior: each attempt leaves one standing:
  1. shared front-end [lee19] – area down, sensors far from hot spots
  2. supply-regulated front-end [park21] – beats 3, area back…
- solution 2/3: this work…
```

## 🔄 Execution Workflow

Ask plain, conversational questions — 1–2 at a time. Halt after each and wait for the answer. Do not batch the whole interview.

**Phase 0 — Frame the format.**
Ask for the venue and length, then the one question that shapes the spine. Do not assume ISSCC or any other format.
- **Budget.** Turn the venue's limit into a per-section word budget with space set aside for figures and tables. Check it against 2–3 published papers from that venue (count their words per section), not against the page limit alone, and show the user both. Re-check a section against its budget when it fills.
- **Detail level.** Ask how much implementation the paper carries and in which sections (see *Concept by default*).
- **Figure-led** (e.g. a 1-page ISSCC paper): the text narrates the figures, so the figures *are* the spine. Elicit the planned figure list, in order; it is locked as the spine in Phase 2.
- **Text-led** (e.g. a journal paper): the sections carry the story and figures support beats. The spine is a section list, elicited in Phase 2.

**Phase 1 — Tell the intro in beats.**
The intro pins everything downstream. Ask the user to tell the intro roughly, in the order it comes to them, then probe until these moves exist — each in the user's words:
- the problem — what is broken or unaddressed
- the proposition — the approach this paper builds on
- the challenges — numbered into the ledger as they surface
- prior attempts — who tried what, and which challenge each left standing
- this work — which ledger numbers it resolves

The intro is locked when **every ledger number has a resolution — by argument (`a throttling-only chip tolerates the floor`) or by this work**. Read the intro beats back; do not proceed until the user confirms.

**Phase 2 — Lock the spine.**
- Figure-led: read the Phase 0 figure list back as the spine — one section per figure in figure order, plus the intro, the close, and any section the user says stands without a figure. Let the user reorder or drop.
- Text-led: ask how the story should unfold after the intro and in what order. Do **not** propose the arc yourself unless the user asks for options (see *Options only when asked*). List the sections back, let the user reorder/rename.
Lock the spine before filling anything.

**Phase 3 — Fill the spine.**
Walk the locked spine in order.
- Figure-led: for each figure, ask *what must the reader take from this figure* — its beats are that answer, in narrative order.
- Text-led: for each section, ask what goes in it; a figure the user mentions attaches to its beat as `(fig: …)`.
- A claim the user attributes to a source gets its anchor inline; one the user has not backed gets `[]`.
- **Missing info:** if the story wants a beat the user has not supplied, keep probing until the user provides it *or* explicitly says to skip. On skip, **omit** the beat — no placeholder.

**Phase 4 — Write the file.**
Write one outline note: in the project's vault folder when the project has one, otherwise in the current working directory (filename: a lowercase-hyphenated slug of the title). Structure:
- `# <Title>` — the working title, if the user has one
- one `## <spine element>` per section (figure-led: `## Fig. N – <what it shows>`)
- under each, the beat clusters — `- ` on every beat, blank line between clusters
- a separate `## Decisions` block for rationale, caveats, check verdicts and open questions — never inside the beat list

On a restructure, move the superseded outline and any superseded decisions to an archive file next to it; the live note holds only the current telling.

Read the final file path back to the user.

## ➡️ What this feeds
The beats seed a three-stage evolution; this skill produces stage 1 only.
1. **Beats** (this skill) — one move per line, movable, no sentences.
2. **Paragraph plan** — each cluster becomes `Par N: <label>` with one complete sentence per line; numbers and cites still placeholders (`**0.8°C**` bold = unverified, `[lee19]` / `[]` = to resolve). Produced by `paper-draft`.
3. **Prose** — paragraphs, numbered references, verified numbers. Also `paper-draft`, on request.

Do not drift into stage 2 while producing stage 1: a beat that reads as a finished sentence is the story being written before it is decided.

## ✅ Self-check before writing the file
- [ ] Every beat traces to a user statement — nothing inferred or filled in; any `(proposed)` beat was accepted by the user.
- [ ] Re-read every beat: ≤ ~12 words, no actor, no editorial modifier, no clause implied by another beat; none reads as a finished sentence.
- [ ] One level deep, movable on its own; any sub-list is numbered, under a lead-in, and rare.
- [ ] No implementation detail elaborating a beat in a conceptual section.
- [ ] Rationale and caveats are in the decisions block, not the beats; each section is within its word budget.
- [ ] Ledger numbers assigned once, in order raised; every number resolved by argument or by this work.
- [ ] Spine matches the format the user named (figure list or section list), not a default template.
- [ ] Sources appear only as anchors the user attached; unnamed cites as `[]`; skipped beats omitted, not stubbed.
