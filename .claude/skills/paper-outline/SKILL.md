---
name: paper-outline
description: Use when the user wants to outline an academic research paper. An interview-driven scribe — elicits the story from the user as one-line beats (zero inference, zero filler) and writes a high-level, rearrangeable outline that later evolves into a paragraph plan and prose. Format-agnostic — figure-led (1-page ISSCC style) or text-led (journal style) spines.
---

# SKILL: Paper Outline (Interview-Driven Scribe)

## 🎯 Trigger
Activate when the user asks to outline, structure, or plan an **academic research paper** — typically given a title or thesis, rough notes, and a target venue.

## 🛑 Core Constraints (non-negotiable)
- **You are a scribe, not an author.** Every beat in the outline must trace to something the user said in this conversation. No inferring, no assumptions, no interpolation from training data, no filler.
- **Sources are anchors, not content.** Never read or mine source files/PDFs for claims or numbers. The user states each claim; a source is only a citation tag the user attaches to it.
- **Beats, not sentences.** One line, one move in the argument, in the user's own words — `per-die trim is test cost – want accurate untrimmed`, never `Because every sensor needs a per-die trim, and trimming is test cost, the goal is a sensor that is accurate untrimmed.` Sentences come two stages later (see *What this feeds*).
- **Every beat earns its place.** If it adds nothing to the story, drop it.
- **Halt and ask.** Never run ahead and draft sections on your own. The outline grows only as the user feeds it.

## 🧠 The outline is a story told in movable beats
A research outline is an argument, not a table of contents. At this stage it is a set of **beats** — each a single line that can be cut, moved, or regrouped without breaking anything else. That property is the whole point of the format; every rule below protects it.
- **One beat per line, one level deep.** No nesting, no multi-line bullets, no beat that only makes sense because of the one above it.
- **Clusters.** Blank lines group beats into clusters ≈ one future paragraph. Clusters are unlabeled; labels come at the next stage.
- **The ledger.** Challenges are numbered once, in the order first raised — `problem 1/2 (process)`, `problem 3 (supply)` — and every later beat that answers one cites the number. Numbers are never reassigned when beats move; the ledger is what keeps a rearranged outline coherent.
- **Role labels, only where the role is not obvious.** A short lowercase prefix: `proposition`, `problem n`, `prior`, `solution n`, `this work`, `pivot` (a turn in the argument — `…but a throttling-only chip can live with that`). Plain beats need no label.
- **Self-notes in parentheses.** `(how does trim work)` = needs explaining later; `(process)` / `(supply)` = kind of challenge; `(fig: error vs temp)` = the figure or result the beat leans on; `(fig?)` = a claim the user has not yet tied to a figure or result. A trailing `…` marks a thought the user left unfinished — keep it, do not finish it.
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
- problem 1/2 (process): spread of the base–emitter voltage across dies sets the untrimmed error floor; the front-end that cancels it costs area per sensor, and a die needs many
- solution 1: a throttling-only chip can live with the floor – so 2 is the one that matters
- pivot: solve area and you have a sensor you can sprinkle everywhere

- problem 3 (supply): supply droop under load shifts the reading (fig?)
- prior: shared front-end across sensors [lee19] cut area but sensors then sit far from the hot spots
- prior: supply-regulated front-end [park21] beat 3 but the area came back…
- solution 2/3: this work…
```

## 🔄 Execution Workflow

Ask plain, conversational questions — 1–2 at a time. Halt after each and wait for the answer. Do not batch the whole interview.

**Phase 0 — Frame the format.**
Ask for the venue and length, then the one question that shapes the spine. Do not assume ISSCC or any other format.
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
- Text-led: ask how the story should unfold after the intro and in what order. Do **not** propose the arc yourself. List the sections back, let the user reorder/rename.
Lock the spine before filling anything.

**Phase 3 — Fill the spine.**
Walk the locked spine in order.
- Figure-led: for each figure, ask *what must the reader take from this figure* — its beats are that answer, in narrative order.
- Text-led: for each section, ask what goes in it; a figure the user mentions attaches to its beat as `(fig: …)`.
- A claim the user attributes to a source gets its anchor inline; one the user has not backed gets `[]`.
- **Missing info:** if the story wants a beat the user has not supplied, keep probing until the user provides it *or* explicitly says to skip. On skip, **omit** the beat — no placeholder.

**Phase 4 — Write the file.**
Write to a markdown file in the current working directory (filename: a lowercase-hyphenated slug of the title). Structure:
- `# <Title>` — the working title, if the user has one
- one `## <spine element>` per section (figure-led: `## Fig. N – <what it shows>`)
- under each, the beat clusters — `- ` on every beat, blank line between clusters

Read the final file path back to the user.

## ➡️ What this feeds
The beats seed a three-stage evolution; this skill produces stage 1 only.
1. **Beats** (this skill) — one move per line, movable, no sentences.
2. **Paragraph plan** — each cluster becomes `Par N: <label>` with one complete sentence per line; numbers and cites still placeholders (`**0.8°C**` bold = unverified, `[lee19]` / `[]` = to resolve). Produced by `paper-draft`.
3. **Prose** — paragraphs, numbered references, verified numbers. Also `paper-draft`, on request.

Do not drift into stage 2 while producing stage 1: a beat that reads as a finished sentence is the story being written before it is decided.

## ✅ Self-check before writing the file
- [ ] Every beat traces to a user statement — nothing inferred or filled in.
- [ ] Every beat is one line, one level deep, movable on its own; none reads as a finished sentence.
- [ ] Ledger numbers assigned once, in order raised; every number resolved by argument or by this work.
- [ ] Spine matches the format the user named (figure list or section list), not a default template.
- [ ] Sources appear only as anchors the user attached; unnamed cites as `[]`; skipped beats omitted, not stubbed.
