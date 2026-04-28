---
name: project-archaeology
description: Systematically reverse-engineer an existing codebase and produce trustworthy Obsidian vault documentation with evidence-tagged claims
disable-model-invocation: false
---

# Project Archaeology

Reverse-engineer a codebase that has never had Obsidian interaction. Produce vault notes that let a future agent work on the project immediately. Runs once per project — must be trustworthy.

**Invocation:** `/project-archaeology [optional/path/to/project]`
- If path omitted, use CWD
- Validate target has source files, build files, or git history

## Core Principles

1. **Depth over breadth.** A shallow inventory of components is worthless. The goal is to understand HOW things work, WHY decisions were made, and how information flows between layers. If you can't explain how a tool's output became an RTL parameter, you haven't gone deep enough.
2. **Trace causal chains.** Every design choice has a cause. Find the chain: requirement/spec → design decision → implementation → verification. If you can't trace a parameter back to its origin, keep digging.
3. **Capture operational knowledge.** "This project uses Timeloop" is useless. "Timeloop was run with config X, producing output Y, which showed PE=8 with K=2xC=4 mapping achieves 100% utilization, so `accelerator_top.sv` parameter NUM_PES was set to 8" is useful. Document the HOW — what commands, what inputs, what outputs, what decisions resulted.
4. **Ground truth first.** Identify the project's ground truth document (spec, requirements, paper). Everything else traces back to it. The ground truth is the organizing spine of the archaeology.
5. **Evidence-tagged claims.** Every factual statement gets a tag:
   - `[verified]` — ran it, saw the output
   - `[inferred]` — read the source, confident but didn't execute
   - `[unverified]` — mentioned in docs/comments, couldn't confirm
   - `[contradicted]` — execution produced different results than docs claim
6. **Connections are the primary output.** The most valuable thing archaeology produces is NOT descriptions of individual components — it's the explanation of how components interact, how data flows between stages, how one tool's output becomes another tool's input. If your notes don't have dense, specific cross-references, you've failed.
7. **Scratch files as external memory.** Write intermediate findings to disk after each phase. Read from disk at the start of each phase. Never rely on conversation memory for cross-phase state.
8. **Content integrity.** Only include information verified from source code, execution output, git history, or existing documentation. Do not interpolate from training data.

## Scratch Workspace

Create at `/tmp/archaeology-<project-name>-<timestamp>/`.

**Setup:**
- If the project is a git repo: `git clone --local <project-path> <scratch-path>`
- If not a git repo: `cp -r <project-path> <scratch-path>`
- All builds, tests, and command execution happen in scratch — NEVER in the original
- Scratch also holds intermediate findings (`phase1-*.md`, `phase2-*.md`, `phase3-*.md`)

**Cleanup:**
- On success (all vault notes pass quality gate): delete scratch workspace
- On failure (any phase errors out, agent interrupted, notes fail quality gate): preserve scratch and print its location so the user can inspect or resume

## Phase 1: Surface Scan

**Goal:** Map the project's major themes, identify the ground truth, and understand the high-level flow. NOT to document components — just to know what exists and where to dig.

**Steps:**

1. Create scratch workspace
2. **Find the ground truth.** What drives this project? A competition spec? A paper? A requirements doc? A class assignment? Read it thoroughly — this is the organizing spine. Every design decision traces back to it.
3. File tree inventory — categorize files by type (source, build/scripts, config, docs, tests, data/results, helpers)
4. Read all README, CLAUDE.md, and doc files — the project's self-description
5. Parse build system — Makefile targets, CMakeLists, setup.py, tcl scripts. For each target: what does it do, what does it depend on, what does it produce?
6. Git history summary (if available) — major development phases, most-changed files, recent activity
7. Identify project type and stage pipeline:
   - **Hardware:** behavioral sim → synthesis → APR → timing/verification
   - **HLS:** C/C++ source → HLS directives → synthesis → implementation
   - **Software:** source → build → test → deploy
   - **Mixed:** identify which parts are which
8. Map broad themes — discover the functional areas organically from what you find. Don't force a predefined taxonomy. The agent figures out what the real themes are.
9. **Map theme interactions at a high level** — which themes feed into which. What are the inputs and outputs of each? How does data flow between them? This is a rough sketch — Phase 2 will trace these in detail.
10. Check vault for existing notes: `grep -r "project: <name>" ~/obsidian_notes/ --include="*.md"` to avoid duplication

**Output:** Write `scratch/phase1-project-map.md` containing:
- Ground truth document identified and summarized (key requirements, constraints, scoring criteria)
- Project type and stage pipeline
- Broad themes with brief descriptions
- Rough theme interaction map (what feeds what)
- Build targets, runnable commands, and tool workflows discovered
- Areas flagged for deep dives (ranked by complexity/importance)
- Existing vault coverage (what's already documented, what's missing)

Everything in Phase 1 is tagged `[inferred]`.

## Phase 2: Deep Dives

**Goal:** Trace every causal chain. Understand not just WHAT exists but HOW it was created, WHY it was designed this way, and how it CONNECTS to everything else.

### What "deep" means

Surface level (BAD): "The accelerator uses 8 PEs and achieves 134x speedup."
Deep level (GOOD): "Timeloop DSE was run with configs in `model/analysis/timeloop/` exploring 4/8/16 PEs x 8/16/30KB buffers. The 8-PE config with K=2xC=4 spatial mapping achieved 100% PE utilization for the FC layer (vs 50% with naive K=4), which justified the area cost. This mapping is hardcoded in `accelerator_top.sv` as NUM_PES=8 and in `fc_compute.sv` as the K=2, C=4 loop structure. The SRAM bank sizes (8KB + 22KB) were derived from the Timeloop buffer analysis showing 30KB total is sufficient for all activations + weights."

Surface level (BAD): "Golden data is extracted from the TFLite model."
Deep level (GOOD): "The golden data pipeline works as follows: (1) `extract_weights_real.py` loads the .tflite model, extracts per-layer weights and biases, writes them as .hex files that the bootloader loads via SPI flash. (2) `extract_intermediate_tflite.py` runs actual inference through the TFLite interpreter, captures the output of each layer, saves as .npy. These become the ground truth for RTL verification. (3) `compute_golden_intermediates.py` reimplements the same math in pure NumPy as a cross-check — if TFLite and NumPy disagree, something is wrong. (4) `gen_conv_test_vectors.py` takes the intermediate outputs and packages them into .hex format that the testbenches can load via `$readmemh`. The naming convention: `_golden` = TFLite-extracted, `_manual` = NumPy-reimplemented."

### Steps

1. Read `scratch/phase1-project-map.md` to recover state
2. **For each theme, in order of importance, trace these dimensions:**

   **a. Workflow reconstruction:** How do you actually USE this part of the project? What exact commands do you run? What are the inputs? What are the outputs? What tools are required? What environment setup? Document the complete workflow so a future agent can reproduce it.

   **b. Causal chain tracing:** For every significant design parameter, trace it back to its origin. Where did this number come from? What tool output, analysis, or requirement drove this choice? Follow the chain: ground truth requirement → analysis/exploration → decision → implementation → verification.

   **c. Cross-theme data flow:** How does this theme's output become another theme's input? Be specific — not "the model feeds the testbench" but "extract_weights_real.py produces conv_weights.hex which tb_depthwise_conv2d.sv loads via $readmemh at line 47, and the same weights are loaded by bootloader.S into Bank 1 starting at address 0x3000_4000."

   **d. Design decisions and alternatives:** Why this approach and not another? Check git history for deleted alternatives, comments mentioning tradeoffs, TODO/FIXME/HACK markers. If a decision isn't justified anywhere, note it as "decision rationale not found — [unverified]."

   **e. Non-obvious operational details:** Magic constants and where they come from. Implicit ordering dependencies (must run X before Y). Tool version requirements. Environment variables. Things that would silently break if changed.

3. Write findings to `scratch/phase2-<theme-name>.md` as EACH theme completes — do not wait until all themes are done. This survives compaction.
4. After all themes: write `scratch/phase2-connections.md` — a DENSE cross-theme dependency map. For every connection, explain:
   - What data/artifact flows between themes
   - In what format (file type, data structure, protocol)
   - What would break if this connection were severed

Everything in Phase 2 is tagged `[inferred]`.

**Compaction safety:** If context compacts mid-phase, read your own scratch files to recover. The phase1 map tells you which themes exist. Check which `phase2-<theme>.md` files already exist to know where you left off.

### Depth check

Before moving to Phase 3, review your Phase 2 scratch files and ask:
- Can a future agent reproduce every workflow from these notes alone?
- Is every significant design parameter traced back to its origin?
- Are cross-theme connections specific (file names, line numbers, data formats) or vague ("see also")?
- Would a future agent understand WHY, not just WHAT?

If the answer to any of these is no, go back and dig deeper on those themes.

## Phase 3: Verification

**Goal:** Run what can be run. Tag every claim with its evidence level. Verify workflows end-to-end, not just individual commands.

**Steps:**

1. Read `scratch/phase1-project-map.md` for build targets
2. Read all `scratch/phase2-*.md` for claims to verify
3. **Verify workflows, not just commands.** Don't just run `make compile` — trace the full pipeline:
   - Does the build produce the expected output files?
   - Do the output files match what Phase 2 claims they contain?
   - Does the downstream consumer (testbench, synthesis script, etc.) actually use these outputs?
4. For each build target / runnable command:
   - Run it in the scratch workspace (set a timeout — if it hangs, log and move on)
   - Capture stdout, stderr, return code
   - Compare against Phase 2 claims
   - Save output to `scratch/phase3-run-<target>.log`
5. For claims that can't be verified by running:
   - Check if tests exist that cover the claim — run them if so
   - If no way to execute, leave as `[inferred]`
6. **Verify causal chains where possible.** If Phase 2 says "Timeloop output determined NUM_PES=8", check: does the Timeloop config exist? Does the output file exist? Does it show PE=8 as optimal? Does `accelerator_top.sv` actually use NUM_PES=8?
7. Write `scratch/phase3-verification.md`:
   - Each verifiable claim from Phase 2 with its final evidence tag
   - Any `[contradicted]` findings with what actually happened
   - Commands that failed and why (missing tools, broken paths, etc.) — this is useful information
   - Workflow verification results (did the end-to-end pipeline work?)

**Safety:** All execution in scratch. Timeout long-running commands (5 minutes default). Document failures — they're valuable.

**EDA tool note:** For hardware projects requiring EDA tools (VCS, Vivado, Cadence), check if the environment supports them. If `source.me.first` or similar setup scripts exist, source them before running. If EDA tools aren't available, tag those claims as `[unverified — requires EDA tools]` rather than failing.

## Phase 4: Vault Note Production

**Goal:** Synthesize scratch files into vault-compliant Obsidian notes that are DENSELY INTERCONNECTED and capture deep operational knowledge.

**Steps:**

1. Read all scratch files
2. Determine note structure based on project complexity:
   - Small project (1-2 themes): 2-3 notes
   - Medium project (3-5 themes): 4-6 notes
   - Large project (6+ themes): 7-10 notes, never more than 10
3. Create `projects/<project-name>/` subfolder in vault
4. For each note:
   - Full YAML frontmatter: `date`, `tags`, `type: concept`, `status: active`, `project: <name>`
   - Lowercase-hyphenated filename
   - Evidence tags inline next to claims: `[verified]`, `[inferred]`, `[unverified]`
   - **Dense, specific wikilinks** — not "see [[other-note]]" but "the weights extracted here are loaded by the boot flow described in [[soc-architecture#Boot Flow]], and verified against the golden model pipeline in [[verification-infrastructure#Golden Data Pipeline]]"
   - **Operational sections** — every note that describes a workflow must include a "How to run" or "Workflow" section with actual commands
   - 200-400 lines target per note
5. Note structure (agent decides which are warranted — don't force notes that aren't needed):
   - **Project overview** — ground truth summary, themes, stage pipeline, how pieces connect. This is the entry point. It should trace the complete flow from requirements to implementation.
   - **Theme notes** — one per major theme that has enough substance. Each must cover: what it does, how to use it, why it's designed this way, what it connects to.
   - **Cross-cutting reference** — if reusable patterns, workflows, or operational knowledge emerges that spans themes
6. Append to `agent/session-log.md` with archaeology summary
7. Cleanup:
   - Verify all notes pass quality gate (frontmatter, wikilinks, filenames, correct folder)
   - If PASS: delete scratch workspace
   - If FAIL: preserve scratch, print location

### Note quality check

Before finalizing, verify each note against these criteria:
- **Reproducibility:** Could a future agent reproduce the workflows described? Are commands, inputs, outputs, and environment requirements explicit?
- **Causal depth:** Are design parameters traced to their origins? Or just stated as facts?
- **Connection density:** Do wikilinks explain the relationship, not just point to another note?
- **Operational value:** Does the note tell you HOW to do something, or just THAT something exists?

If a note fails any of these, revise it before writing to the vault.

**Notes must NOT contain:**
- Raw numerical results (those live in the source repo)
- Restated READMEs without added reasoning
- File-by-file inventories (notes are about themes and connections)
- Vague connections ("see also", "related to") without explaining the actual relationship
- Component descriptions without operational context (how to use, how to modify, what breaks if changed)

## Anti-Patterns

- **Do NOT** produce a component inventory. "The project has X, Y, Z" is not archaeology. Archaeology traces how X produces output consumed by Y, which was designed to satisfy requirement Z from the spec.
- **Do NOT** stop at surface level. If you find a parameter, trace it to its source. If you find a script, understand what it produces and who consumes the output. If you find a design decision, find out why.
- **Do NOT** write vague connections. "See [[other-note]]" is worthless. "The Timeloop DSE results in [[dse-analysis]] directly determined the PE array parameters used in [[accelerator-architecture#Hardware Architecture]]" is useful.
- **Do NOT** skip operational knowledge. Every workflow, build process, and tool usage must be documented with enough detail to reproduce.
- **Do NOT** read every file before understanding the project structure. Surface scan first, then targeted deep dives.
- **Do NOT** run commands in the original project directory. Everything executes in scratch.
- **Do NOT** hold all findings in conversation memory. Write to scratch files after each phase/theme.
- **Do NOT** create a note per source file. Notes are about themes, not files.
- **Do NOT** include unverified training-data knowledge as if it were project-specific fact.
- **Do NOT** force exactly N notes. Let project complexity determine the count.
- **Do NOT** skip Phase 3 verification even if it seems obvious. Trust but verify.
