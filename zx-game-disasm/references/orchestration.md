# Orchestration — running the disassembly as a multi-role workflow

A full disassembly to the quality bar is far more work than one context window holds well. A single agent doing all of it degrades two ways: its context fills and it starts re-deriving and re-breaking solved work, and under pressure to look finished it trades correctness for completion — inventing a color, matching a sprite by shape, guessing a purpose from a routine's callers.

This file is how the **Manager** runs the work as a set of roles so neither happens. The method (how to derive and document) lives in `comment-style.md`, `ctl-authoring.md`, `behavior-spec.md`, and the shared `../shared/disasm-analysis.md`. This file is the *organization* around it.

## The roles

Each role is a caller-side contract in `references/roles/`. The Manager is the main loop; the rest are spawned subagents with small, disposable contexts.

| Role | Spawn as | Owns | Brief |
| --- | --- | --- | --- |
| **Manager** | the main loop | plan, ledger, task queue, checkpoints | `roles/manager.md` |
| **Researcher** | read-only subagent | non-authoritative external priors | `roles/researcher.md` |
| **Worker** | subagent with edit access | one scoped target, derived + self-validated | `roles/worker.md` |
| **Challenger** | read-only subagent | the commit gate; per-claim verdicts | `roles/challenger.md` |

Code-quality is split: a mechanical linter (`scripts/lint_comments.py`, run in `make`) plus the Challenger's semantic judgment.

To spawn a role, direct the agent to read its brief and add the scoped task. The briefs are self-contained, so a spawned agent needs nothing else but the target and the project paths.

## The progressive-disclosure protocol

This is the core rule that keeps every checkpoint clean. The unit of progress is a **claim set** for one scoped target. The Worker derives it and self-validates; the Challenger partitions it; only the verified part lands.

```
Worker → claim set for target T (each claim + its evidence line)
   │
Challenger partitions each claim:
   confirmed         code-traced + self-validated       → commit
   provisional, and  the annotation already shows the   → commit as written
     hedged honestly  uncertainty ("~5 s at 50 Hz")       (it is honest, not a guess)
   provisional, but  stated as fact                     → downgrade to "labeled,
     stated as fact                                        undocumented" + dig-task
   unknown           genuinely undetermined             → leave bytes/skeleton
                                                          + dig-task (address + question)
   │
Checkpoint commit = confirmed claims + honestly-hedged provisional ones
   + .ctl marks every uncertainty visibly to the reader
   + a guess stated as fact never lands; it is downgraded or queued
   + new dig-tasks recorded by the Manager
```

The consequence: the disassembly is **never sloppy**. Everything committed is verified or explicitly flagged unverified; everything unknown is a queued task, not a silent guess and not a reason to stall. "Commit what you know, file a task for the rest" is the whole discipline, made mechanical.

The Manager owns the dig-task queue, kept wherever the user tracks work — a Worker or Challenger hands back its unknowns and the Manager records them (see "The dig-task queue" in `roles/manager.md`). It is also the Manager's steering surface at a checkpoint.

## The Manager loop

```
Manager loop
   pick ONE small target → Worker derives → Challenger gates → apply the verified result
   ▲                                                                                   │
   │   unknown → dig-task                                                              │
   └───────────────────────────────────────────────────────────────────────────────────┘
```

**What keeps it honest.** The check on a confident wrong answer is the **Challenger** — it verifies every claim before a commit, and the **dig-task** queue absorbs every unknown. A guess never lands and an unknown never stalls the loop; it is queued and the loop moves on.

## The phases

Logical order, not a strict schedule — phases 3 and 4 interleave, and verification is established early and kept green throughout.

| Phase | Roles | Output | Milestone |
| --- | --- | --- | --- |
| **0 Acquire & baseline** | Manager + Worker | snapshot; ORG/PC/SP; whole image as one `b` block; green byte-identical round-trip | baseline green |
| **1 Research priors** | Researcher (optional, parallel) | research notes, non-authoritative | priors summarized |
| **2 Breadth map** | Worker fan-out (grow code from entry) → Challenger | whole program split code/data; every routine *named* (label + tentative one-liner) from a quick read — **naming, not full derivation**; every entry point labeled | map + ledger; **pick highest-impact depth target** |
| **3 Deep-document** | Worker→Challenger, per routine | chosen routines derived **once** and brought to the bar; the routine description synthesized from its line-level comments; catalogs grown in place | subsystem committed |
| **4 Catalog & media** | Worker fan-out → Challenger verifies each entry | sprite/tile/item catalogs; code-derived groupings; render-verified | catalog complete |
| **5 Behavior spec** | Worker + Challenger | MDP synthesis (state / actions / dynamics / reward) | spec answers the control questions |
| **6 Publish** | Worker | HTML site | optional |

Because breadth only *names*, no derivation is duplicated: a routine is derived in full exactly once, in the depth pass, where its line-level comments and its routine description are authored together. A breadth Worker that fully derives a routine and returns only a summary is doing depth work and throwing most of it away — the Manager spawns breadth Workers to name and depth Workers to derive, and does not conflate the two.

## How the Manager spawns

### Lanes — parallelize across artifacts first

The deliverable is **several files**, not one: the `.ctl` (code annotations), `graphics.ref` (the sprite/tile/item catalog), `sound.ref` (audio), and the `spec/*.md` files. Each is a **lane**. Workers in *different* lanes edit *different files*, so they **cannot collide** — they run fully in parallel, always. The `.ctl`-contention rules below apply *only within the code lane*; they say nothing about the others.

This is the first and biggest axis of parallelism, and the easy one to miss: a coupled `.ctl` task (a shared variable block, an interdependent core) is run serially **in the code lane** — but that must **never** stall the catalog, audio, or spec lanes, whose work is in entirely separate files. At any moment the Manager should have work moving in *every* lane that still has open work:

- **code** (`.ctl`) — disjoint range-fragments in parallel, or one serial Worker for a coupled region;
- **catalog** (`graphics.ref`) — name and render each sprite/tile/item;
- **audio** (`sound.ref`) — an `[Audio:]` section + `#AUDIO` per effect;
- **spec** (`spec/*.md`) — a subsystem account per file.

The catalog/audio/spec lanes don't even touch the byte-identical build (they edit `.ref`/`.md`, not the `.ctl`), so their commits carry no round-trip risk — there is *no* reason to hold them behind code work. If the only available code target is a coupled serial one, that is exactly when the other lanes should be busiest.

The rest of this section is about parallelism *within the code lane*.

### Parallel — the throughput path

Spawn a batch of Workers at once, each owning a **small disjoint slice — one routine, or a couple of small related ones, never a subsystem** (non-overlapping address ranges, returning in ~minutes so the batch lands fast). Each returns a **range-fragment**: the `.ctl` directives for its own routines' ranges *only*. The Manager merges each with **`scripts/splice_ctl.py`**, which replaces each owned `c`-block in the canonical `.ctl` by address — a deterministic, order-preserving splice, not a hand-merge. Then it builds green, one fragment at a time. Because the `.ctl` is address-ordered and the fragments are address-disjoint, this is reliable, and the splice tool **refuses** a fragment that strays outside its routine ranges — catching a mis-scoped Worker before it can corrupt the file.

Three rules make the merge clean. Without them, Workers contend on the variable block and the Manager falls back to hand-merging and re-deriving:

1. **A depth Worker stays inside its routine ranges.** It documents its routines and references shared variables by their existing label (or `#R<addr>` if not yet labeled). It does **not** add labels to the shared low-RAM variable block or define global constants. `splice_ctl.py` enforces this.
2. **Shared regions are their own single-owner task.** Labeling the variable block and defining global constants is *cross-cutting* — it cannot be split per routine, so it is one dedicated task (one Worker), sequenced before or after the routine fan-out, never contended by parallel Workers.
3. **The Manager never hand-merges or self-derives.** It runs the splice tool and the build; it does not edit annotations or re-derive logic. A fragment that breaks the build at a boundary is **re-delegated** to a Worker to fix. Falling back to solo work is the exact failure this structure exists to prevent.

**Run it as a pipeline, not a batch barrier.** Do not spawn a batch, block until *all* of it returns, then process the pile — that idles the Workers while the Manager integrates and idles the Manager while they derive (the "stop the world" that eats the wall-clock). Instead the Manager spawns Workers in the background and keeps a steady *pool* in flight; as each one finishes it is gated by a Challenger and its fragment integrated, while the rest of the pool is still deriving, and a fresh Worker refills the freed slot. Integration overlaps derivation; nothing stops the world. Every commit is gated by a Challenger — `make` proves byte-identity, not that a claim is true, so the Manager must never substitute its own build check for the adversarial gate. See the loop and "The Challenger gate" in `roles/manager.md`.

### Serial — for a coupled *region*, not the whole file

When a *specific region* is tightly coupled — a shared variable block, a couple of routines whose boundaries depend on each other — give **that region** one Worker that edits the real `.ctl` directly (no fragment, no splice). But this is a small serial island, **not** a serialization of the code lane: it runs *concurrently* with parallel range-fragment Workers on all the other disjoint routines, which are almost always the bulk of the program. A full game has one shared variable block and dozens of mutually-independent routines (HUD, high-score, front-end, sound, collision, each enemy handler) — the coupled island is one lane-internal Worker among many parallel ones, never a reason to stop fanning the rest out. Reach for fully-serial-everything only on a tiny program where almost everything interlocks.

## The reader pass

Every other check reads a *claim*: the Challenger verifies one annotation, the linter matches one pattern, `make coverage` counts. None of them reads the deliverable the way its audience does — start to finish, as a person. The reader pass is that read.

**It is a render, and only a render counts.** The pass is performed on pages *displayed by a browser* — pixels on a screen, at a real viewport width — and its evidence is a screenshot, looked at, of every page the pass reports on. On a site too large to shoot page by page, the floor is one of each of the six page types the styling checklist enumerates (`references/html-docs.md`, *"Prove it by looking at it"*: a code routine, a data block, a text block, a graphics-heavy page, a reference/catalog page, the index), plus every page the prose read gave a reason to doubt. Six screenshots of a 200-page site is a spot check, not the pass; if that is what you ran, report it as one. Reading the generated HTML, the `.ref` sources or the CSS is not a reader pass and cannot stand in for one: the whole second half of what this pass exists to catch is markup that reads correctly and *renders* wrong, and no amount of source reading reaches it. If no screenshot was taken, the pass did not happen. Render headless — the browser need not be visible, only the page:

```
# CHROME: the Chrome or Chromium binary; SITE: the built site's absolute path
mkdir -p build/review/screenshots
"$CHROME" --headless \
  --disable-gpu --hide-scrollbars --window-size=1280,1400 \
  --screenshot=build/review/screenshots/index.png "file://$SITE/index.html"
```

Then **look at the PNG**. Reading it back with an image-capable tool is the pass; producing the file is not.

What a linear read of the prose catches:

- typos and broken sentences;
- **link duplication** — `name (name)`, where a `#R` renders the label already written beside it;
- **fossil identifiers** — an old label or an auto-generated name still standing in the prose after the rename that replaced it;
- **metronome prose** — one template stamped per sibling, identical in rhythm all the way down a family of blocks and invisible while you read one block at a time;
- a table that transcribes the data block beside it instead of adding to it;
- **register and altitude** defects — investigation vocabulary on a reader-facing page, a header pitched at the wrong level, a fact with two homes, a data block left unindexed.

And what only the render catches — the class the source is blind to, because in the source nothing is wrong:

- a cell that is *styled* as though it were annotated when it is empty;
- a title that pushes the page sideways, or crowds the logo beside it;
- an image macro whose picture is not there, leaving the sentence that introduces it standing over a hole;
- a large image that flows as a word in a paragraph instead of sitting as a figure;
- a page whose paragraphs all ran together into one wall of text;
- a ref field left unset, rendering as an empty slot rather than as nothing.

Each of those is written up — symptom, cause, how to check, and whether a gate catches it — as **the rendered-page traps** in `references/html-docs.md`. Read that list before the pass; it is the checklist of what to look *for*.

Run it twice over a project's life:

- **at pickup**, over the built site, to inventory the qualitative gaps the gauge cannot see — that is the second instrument of the gap ledger in `roles/manager.md`;
- **before any milestone or "done" claim.** A project is not at the bar until someone has read it as a reader.

Findings are recorded as dig-tasks and worked through the normal loop, like any other unknown. The Challenger runs the same read at fragment scale for a prose-heavy target ("Read the rendered page" in `roles/challenger.md`); the Manager's pass is the whole-site one.

## Durable artifacts

| File | Owner | Purpose |
| --- | --- | --- |
| `.ctl` | Worker | the code annotations; round-trips to original bytes |
| `graphics.ref`, `sound.ref` | Worker | the sprite/tile/item catalog and the audio catalog |
| the plan | Manager | phase status + coverage ledger, kept wherever the user tracks work |
| dig-tasks | Manager | the dig-task queue, kept wherever the user tracks work |
| research notes | Researcher | non-authoritative priors |
| `spec/*` | Worker | behavior spec / MDP |
</content>
