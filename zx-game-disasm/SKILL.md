---
name: zx-game-disasm
description: >-
  Build a documented, reassemblable Z80 disassembly of a ZX Spectrum game,
  end to end, from a game image (.tzx/.tap/.sna/.z80/.szx/.trd) using SkoolKit.
  Use this whenever the user wants to reverse engineer, disassemble, annotate,
  or document a ZX Spectrum game — "disassemble this game", "annotate the
  machine code", "produce commented Z80 source", "reverse engineer the loader
  and the game", "make a SkoolKit disassembly", "document how this game works
  at the code level", "build a reassemblable source that round-trips to the
  original bytes", or "spec out the game's mechanics so I can port it or train
  an agent to play it". Covers the whole pipeline: acquire a clean post-load
  snapshot (including packed/multi-stage loaders), map code vs data, author the
  SkoolKit control file with labels and constants, document each routine, build
  and verify a byte-identical round-trip, synthesize a subsystem behavior
  specification (with the agent-facing MDP: state addresses, actions, dynamics,
  reward), and optionally generate browsable HTML documentation.
metadata:
  # The gate generation. Every `make gate` verdict names it, and every
  # lint-baseline.txt records the one it was written under, so a stored GREEN or
  # RED says which gate produced it. Raise it in the same commit that changes
  # what the gate accepts or rejects — a new gating check, a check that gains a
  # finding kind, a rule that widens. See references/build-verify.md.
  gate: 8
---

# ZX Spectrum game disassembly

Turn a ZX Spectrum game image into a fully annotated Z80 source that anyone can read, reassemble to the *exact original bytes*, and use to reimplement the game in a higher-level language. The toolchain is [SkoolKit](https://skoolkit.ca) (disassembly, round-trip, HTML) plus [pasmo](https://pasmo.speccy.org/) (independent reassembly check).

The deliverable is a project: a `Makefile`, a primary `.ctl` control file (the hand-edited source of truth), generated `.skool`/`.asm` intermediates, a verified byte-identical snapshot, and — optionally — an HTML documentation site.

## What a complete disassembly delivers — five goals, all at once

A disassembly can be *correct* and still be mediocre. A top-quality one holds all five of these. The first is the hard foundation; the rest are the depth, content, and presentation that separate a polished artifact from a raw dump — breadth and a green build are the *start*, not "done".

1. **Reassemblable and correct — the foundation.** The source reassembles to a byte-identical copy of the original. That round-trip is the hard floor, checked by **`make`** — the single gate that drives every check (round-trip, linters, and the HTML build that validates the `.ref` catalogs). If the bytes drift, the documentation describes code that no longer matches. Full correctness — every reference relocatable, every block named (no `L####` auto-labels) — is reached progressively as the map is understood, and `make coverage` tracks it (you cannot name a block before you have disassembled it). **"Relocatable" is claimed only after the program has been moved and run** — the gauge counts operands, so it is blind to an address held as data, built from an 8-bit immediate, bound by an absolute `@equ`, or hiding in code annotated as bytes. The proof, its two non-obvious constraints, and how to bisect it when it fails are in `references/build-verify.md`. Relocatability is never inferred from a green build.
2. **Complete on game mechanics — enough to train *and* reimplement.** The capstone is a **behavior specification**: a subsystem-by-subsystem account in concrete numbers, serving two readers — a **human reimplementing the game** in another language (rendering, input, sound, logic, well enough to rewrite), and an **ML agent learning to play**, which needs the game as a Markov decision process: the **state** and *where in RAM* it lives, the **actions** and their effects, the **transition dynamics**, and the **reward** (scoring, the resource economy, win/lose). The real tests of completeness: can you re-describe each subsystem in plain language, and could someone port it from the spec alone? See `references/behavior-spec.md`.
3. **Resource catalogs — the game's content, rendered from its bytes.** The `.ctl` is the **source of truth** for every resource: each sprite frame, tile, animation, and sound rendered *at its own block* (never screenshots, never raw `DEFB`), structured data schematized and indexed element by element. The `.ref` pages are the **indexes** — browsable digests that collect what the blocks establish and link back. Full audio as playable `#AUDIO`, inline first. See `references/expressive-palette.md`.
4. **A reference manual over the listing.** Bugs, pokes, trivia, a glossary, navigable maps — the docs read as a manual, not a dump, written in a *reader's register*: curated, one home per fact, no investigation narration. See `references/html-docs.md` and `references/comment-style.md`. **How well it is written is measured**, not judged: description and sentence lengths, one term per thing, and the sentence rules a linter can decide. The numbers and what enforces them are in `references/prose-bar.md`. A project over that bar is not done, in the same sense a bare basic block is not done.
5. **Great visuals — what earns the reader.** The HTML themed to *this* game: a dark game palette, a title logo, an on-theme decorative flourish. A plain-default page gets the work ignored however good the content underneath. See `references/html-docs.md`.

Hold all five at once. The byte-identical round-trip is the one hard gate on every commit; everything else — full naming and relocatability, and goals 2–5's depth, catalog, manual, and presentation — is progressive, measured by the `make coverage` gauge and the Challenger against the bar.

## The five stages

Work in order, but the table is a logical order, not a strict schedule. In practice the first real moves are mapping data vs code and getting a warning-clean, byte-identical build — verification is established early and kept green from then on, not saved for the end. Stages 2–4 then interleave: you map a region, document its routines, rebuild, and move to the next. The bulk of the effort is stage 3, and it proceeds one routine at a time over many small steps, each leaving the build green.

| Stage | Goal | Reference |
| --- | --- | --- |
| 1. Acquire | Get a clean snapshot of the fully-loaded game in memory | `references/acquisition.md` |
| 2. Map | Separate code from data, find entry points, get a clean `.skool` | `references/ctl-authoring.md` |
| 3. Document | Annotate the `.ctl`, express it richly, synthesize the behavior spec | `references/comment-style.md`, `references/prose-bar.md`, `references/ctl-authoring.md`, `references/expressive-palette.md`, `references/behavior-spec.md` |
| 4. Verify | Build and prove a byte-identical round-trip; pass the linters | `references/build-verify.md` |
| 5. Publish | Generate the browsable HTML site (optional) | `references/html-docs.md` |

The working rules live in `references/agents.md`, which the skill maintains. A copy of them in a project goes stale when the skill changes.

## Running it: solo or orchestrated

For a small target — one routine, a single subsystem, "figure out how this loader works" — run the method yourself, in this one context. For a *whole game*, do not: a full disassembly is far more than one context window holds well. A single agent doing all of it degrades two ways at once — its context fills and it starts re-deriving and re-breaking solved work, and under pressure to look finished it trades correctness for completion (a color it chose, a sprite matched by shape, a purpose guessed from a routine's callers).

So a whole game is run as a **multi-role workflow**, and you are the **Manager**. This is a forcing instruction, not a suggestion: your job is *not* to do the documentation yourself. Your job is to run the loop — spawn a **Worker** to derive each target and a **Challenger** to gate it, apply the verified result, and continue with the next target. If your first move on a whole game is to survey the project solo, you are doing it wrong: spawn the loop.

Spawn Workers and Challengers as subagents, in the background, so the Manager keeps working while they derive and review.

What keeps the work honest:

- a **Challenger** gates every commit, refute-unless-evidence, so nothing fabricated or untraced lands. It is the quality check on every claim;
- the **progressive-disclosure protocol** — commit what is verified or honestly hedged, downgrade a guess that reads as fact, file a **dig-task** for what is unknown — so the disassembly is never left sloppy and an unknown is queued, never guessed.

**Two things you must do, or the whole role structure silently collapses:**

1. **Read your own contract first.** Before spawning anything, read `references/roles/manager.md` (your contract and the project-bootstrap / upgrade audit) and `references/orchestration.md` (phases, the pipeline, the protocol). Working from this summary alone is *not enough* — it omits the bootstrap and the spawn mechanics.
2. **Every spawn carries its role's brief — do not reconstruct it from memory.** Begin each Worker/Challenger spawn prompt by directing the agent to **read its contract** (`references/roles/worker.md` or `references/roles/challenger.md`), then add the scoped task. The briefs hold load-bearing rules — Workers *pre-validate every fragment with `make verify-frag` before reporting*, derive meaning from code, name a catalog entry after its glyph; Challengers refute unless the code shows otherwise. Hand-write a spawn prompt from your own understanding and these drop out silently (a Worker that never runs `verify-frag` hands you broken fragments to debug). Point every agent at its brief; the file is the source of truth and stays current as the skill evolves.

`references/roles/` holds the rest. These are not optional reading.

## The mental model

SkoolKit disassembles a *snapshot* — a frozen image of RAM with the game already loaded. The `.ctl` control file is your annotations *over* that snapshot: where code starts and stops, what each address means, what to name it. `sna2skool` applies the `.ctl` to the snapshot to produce a `.skool` (the disassembly with your comments woven in). `skool2asm` turns that into assembly; `skool2bin` plus a `cmp` against the original proves the round-trip.

So the `.ctl` is the only file you hand-edit. Everything else is generated. Never edit the `.skool` or `.asm` directly — your changes would be overwritten on the next build, and they would not feed back into the round-trip check.

## Working discipline — iterate in green checkpoints

A full disassembly is a long effort, far too long to run blind: work in the wrong direction compounds, and a single broken boundary can leave the project unbuildable for a long stretch. So the unit of progress is not "the finished disassembly" — it is **a small, green checkpoint**, and you produce a steady stream of them, each leaving a buildable project.

The rules that keep it steerable:

- **Every checkpoint passes `make` — the one gate.** At each checkpoint the project must `make` clean. **`make` is the gate**: it drives the round-trip `cmp`, the `.ctl` linters, *and* the HTML build — and `skool2html` is the only step that validates the `.ref` catalogs (their `#R` cross-references and image/audio macros). It is not slow, so there is no separate "verify"; run `make` and never hand back, commit, or call green without it — a dangling `#R` in `sound.ref` shows up only in `make`. A green `make` is one the user could build, boot, and inspect right now — and "builds" means the full `make`: the `.skool`, the human-readable `.asm`, *and* the HTML site are all produced. The `.asm` is the deliverable a reader opens — keep it current even when a task only asks about the control file.
- **A green round-trip is not proof the map is right.** Byte-identity proves the bytes are faithful; it says nothing about whether your code/data split and data-structure boundaries are correct, because mislabeled bytes still round-trip (see "What the round-trip does NOT prove" in `references/build-verify.md`). Validate boundaries from how the code *uses* the data, and where a boundary is genuinely undeterminable, document the uncertainty rather than committing to a silent guess.
- **Keep increments small.** One region mapped, one routine documented, one data table laid out — then rebuild and verify. If a change cannot be made without breaking the build, it is too big; split it. Small steps mean a wrong turn costs minutes, not hours.
- **Breadth before depth — and breadth means *naming*, not deriving.** The first pass maps code vs data and gives every routine a label (and at most a tentative one-line purpose) from a quick structural read — never a full derivation of its logic. Deriving a routine in depth and then discarding that understanding for a one-line summary is wasted twice over: a later pass has to derive it again, and the throwaway summary can drift from what that second derivation finds. So derive each routine **once**, in the depth pass, and author its line-level annotations and its routine description *together* there — the description synthesized from the lines so the two cannot disagree. A shallow naming pass still reveals the shape of the whole game, so the Manager picks the high-impact systems to deepen instead of discovering late that the effort went to the wrong place.
- **Before any milestone or "done" claim, run the reader pass.** A linear read of the site *as a browser renders it*, page by page, as a person (see `references/orchestration.md`) — headless screenshots you then look at; reading the generated markup does not count. It is the only check that catches typos, link duplication, fossil identifiers and template-stamped prose that per-claim verification never sees, and the only one that sees a page laid out wrong from markup that reads right.

The throughline: a steady stream of adversarially-verified, byte-identical green checkpoints is what makes a long effort *safe*. Each checkpoint is gated by the Challenger, so the work moves forward without trading correctness for completion. The Challenger is the quality gate.

## "Mature" is a measurement, not an impression

A disassembly where every routine has a label, a one-line description, and a green build *looks* finished — and calling it "mature", "mostly documented", or "nearly done" is a misjudgment. It is not finished: that is **breadth** (every routine *named*), and the depth — an explained *body* on every routine, the catalogs, the audio, the spec — is where most of the work lives and is usually barely begun. A green, fully-labeled `.ctl` whose routines all carry a `D` description is still far short of the bar, because those descriptions sit over bare bodies (the *skeletal* state).

So never characterize a project's state from an impression, and never from a count of `D` lines — a description on every routine is breadth, not depth. When you pick up an existing disassembly, **run `make coverage` first** and state where it stands in the gauge's terms (for example, "40% of routines explained, 60 skeletal, no audio"), never "mature". The gauge exists to replace the impression; if it says NOT at the bar, the project is not mature, however polished the labels look. The gauge also runs the prose linter, so a project written under older requirements reports its own gap to the current bar — those NOT-at-the-bar reasons are the upgrade backlog, not cosmetic polish (see the gap ledger in `references/roles/manager.md`).

**Core principle — upgrade an existing project to the current standard, first.** This skill evolves; a project built to an older version is held to the bar as it stands *now*. Before any documentation work, run this **mechanical upgrade audit** (quick, and it does not depend on understanding the code, so do it up front — a green build with a stale structure still needs it):

1. **Makefile.** Is it the thin stub that ends in `include $(SKILL)/tools/disassembly.mk`? If it is a fat Makefile with its own rules (`all:`, `verify:`, `pasmo …`), **replace it** with `assets/Makefile.template` (set the game's name and numbers). A working fat Makefile is *still wrong* — it won't pick up framework fixes, and nothing breaks to show it.
2. **Scripts.** Delete any vendored `scripts/` copy in the project — the framework self-locates the skill's `scripts/`.
3. **Addresses.** The `.ctl` must be hex (`sna2ctl.py --hex`; see `references/ctl-authoring.md`). A stray decimal address is a quick mechanical fix.

Do these *before* the gauge work. Then the progressive quality goals the gauge measures — label naming toward 100%, inline-rendered sprites, data-block schemas — advance through the loop. Inherit the game's work, not its stale conventions. (Full detail: the Manager's bootstrap in `references/roles/manager.md`.)

Record dig-tasks wherever the user tracks work; `references/roles/manager.md`, "The dig-task queue", says what each one carries.

## If the gauge says the prose is over the bar

`make coverage` prints a `PROSE BAR` line and, when the project is over it, names each figure in the verdict. It is not a polishing task to leave for the end.

Do it in this order. Each step is measurable, and each one moves a number the gauge reads.

1. **Set up the linter if it is not set up.** `references/build-verify.md` has the steps. Then `make lint-prose` for the sentence-level list.
2. **Fix the terminology first**, because every later edit re-types the terms. Build the registry in `glossary.ref`, then rename each variant everywhere it appears — prose, titles, labels, `@equ` names, `.ref` pages, spec. `references/prose-bar.md` has the admission test for deciding which name survives.
3. **Cut the descriptions to their contract.** The median is the figure to move, not the longest entry. A description says what the routine is for and the one consequence a caller needs; everything else goes to an `N` note at the instruction it describes, or to a `.ref` page. This is a move, not a delete — the facts keep their home, and it usually *lowers* the total word count while raising what a reader gets.
4. **Split the sentences that carry more than one idea.** Work from the `make lint-prose` list. A record layout or an enum written as running prose is a `#TABLE`; a chain of "so … so …" is three sentences; a sentence whose subject is an address gets a thing as its subject.
5. **Re-run `make coverage`.** The verdict is the progress report.

Do not baseline your way out of this. The baseline exists for findings a project has decided to carry, and prose length is not one of them: it is the thing the reader actually experiences.

## Stage 1 — Acquire a clean snapshot

SkoolKit needs the game *as it sits in memory after loading*, not the raw tape. For most tape games, `tap2sna.py` simulates the load and writes a `.z80` snapshot in one step. Snapshots (`.sna`/`.szx`/`.z80`) can be used directly. Disk images and packed/multi-stage loaders need more care — a compressed game must be captured *after* it decompresses itself, sometimes as two snapshots (one for the unpacker, one for the unpacked body).

The output of this stage is a snapshot plus three numbers the rest of the pipeline needs: the origin (`ORG`), the entry point (`PC`), and the stack pointer (`SP`). See `references/acquisition.md` for tape, disk, snapshot, and packed-loader recipes, and how to find `ORG`/`PC`/`SP`.

When `tap2sna` cannot load the game cleanly and you need to drive the loader live — turbo timing, decryption, relocation you must follow block by block — run it under FuseX with the **`zx-fuse-driver`** skill, and apply the general comprehension method in `../shared/disasm-analysis.md`. Capture a snapshot at the hand-off point once the game is in memory. (The `zx-tape-to-trdos` skill has tape-loader-specific trapping recipes if the loader is a turbo/protected one.)

## Stage 2 — Map code vs data

A bare disassembly treats every byte as code, which is wrong wherever the game stores graphics, tables, or text. The `.ctl` marks each region with a block type (`c` code, `b` bytes, `t` text, `w` words, `s` space, `g` game-status buffer). Getting these boundaries right is what makes the disassembly readable and what keeps `pasmo` from choking on data interpreted as opcodes.

Start the `.ctl` as one `b` block over the image and convert a region to `c` only as execution flow confirms it (see `references/agents.md`). `sna2ctl.py --hex` guesses code and data; read its output as a hint, never as the map. **Every `.ctl` address is hex** — see `references/ctl-authoring.md`. The `.skool` is your map: rebuild it after every change and watch for `overlapping instruction` warnings, which mean a block boundary falls mid-instruction.

**Derive the boundaries from execution, not from the eye.** A static guess plus hand correction misses the byte that reads as a sprite and is later jumped into. Play the game under **`zx-fuse-driver`**, record the session as an RZX, then replay it with FuseX's per-address profiler running (`profile_start` / `profile_finish`; see that skill's `references/driving.md`). The map it writes names every address an instruction started at.

**Start the recording from the post-load snapshot — the one this `.ctl` maps — and drop every hit below `$4000`.** The profiler proves an instruction began at an address *in the memory of that run*, and a run that includes the tape load is a different memory: the loader's code, its buffers and the bytes it has not written yet. Its RAM hits can land outside every `c` block of the post-load map, inside a sprite bitmap among them. Read that map as evidence and you promote a sprite to code, which is the failure this paragraph exists to prevent.

So filtered, a hit is direct evidence for `c`. A miss proves nothing, because only an instruction's first byte is charged and an untaken path is absent whether it is code or data. The check therefore promotes blocks to `c` and never demotes one to `b` — cover the game's modes in the recording, and treat a gap as unvisited until something else settles it.

## Stage 3 — Document

This is the work. Iterate on the `.ctl`: name routines and variables, define symbolic constants, write each routine's **contract** as its description (purpose, inputs, outputs, side effects — not the mechanism), explain its **algorithm and math at the line level** so it can be reimplemented without the Z80, and document data structures as you meet them. The altitude split — purpose/contract at the top, mechanism in the body — is in `references/comment-style.md`.

Documenting presupposes understanding. The method for *deriving* a routine's logic — static reading, Z80 idiom recognition, and dynamic confirmation when a static read is ambiguous — is the shared reference `../shared/disasm-analysis.md`. When reading the bytes is not enough (a computed jump, self-modifying code, a state-dependent value), run the game under the **`zx-fuse-driver`** skill and observe it. Derive first, then document what you derived.

A run supplies *you* with evidence; the code is what the documentation rests on. Every runtime finding must therefore land as a statement the code supports — the observation tells you where to look, and the routine that makes it true is what you write down. A fact you cannot get back out of the code does not ship, and the deliverable never cites an emulator (`references/comment-style.md`).

The comment philosophy is the thing to internalize, not a list of directives: **every comment must add what the code cannot show.** Never restate an instruction; describe the *why*, the formula, the game rule. Read `references/comment-style.md` before writing comments — it is the heart of the skill — and `references/ctl-authoring.md` for the control-file syntax that expresses it (labels, `@isub` constants, numeric bases, `#TABLE`, `R` annotations, cross-references).

Work breadth-first: give every routine a one-line purpose before deep-diving any single algorithm. Skip routines you genuinely do not understand rather than speculating — a wrong comment is worse than none. Build often; small verified steps beat large unverifiable ones.

Express it richly. SkoolKit is a documentation toolkit with a large vocabulary, and the richer the disassembly, the more it is worth to the end user. Prefer the *native* device over prose: render a sprite with `#UDG`/`#UDGARRAY` instead of describing it, play a sound with `#AUDIO`, lay out a bitfield as a `#TABLE`, compute a timing with `#TSTATES`, encode a literal as an `@isub` constant, carry a bugfix in `@bfix`, record a cheat as a `[Poke:...]` section. Whenever you are about to write a sentence, check whether a device expresses the fact directly — it usually does. `references/expressive-palette.md` is the full catalog, grouped by purpose; reach into it liberally — up to the top tier: the game's own levels and sprites rendered from the data, derived facts generated by scripts, a reference manual built over the listing.

Once routines are annotated, synthesize the **behavior specification**: a subsystem-by-subsystem account (player, input, enemies, collision, fuel, scoring, …) of how the game behaves, in concrete numbers, each claim traced to a `.ctl` label. This is the artifact a porter or an agent-trainer actually consumes. `references/behavior-spec.md` covers how to organize it, the concreteness standard, and the MDP checklist (state addresses, actions, dynamics, reward) that makes it usable for training an agent, not only for porting.

## Stage 4 — Verify

Run `make`. It regenerates the `.skool`, emits the assembly, reassembles it, and `cmp`s the result against bytes extracted from the original snapshot. A clean `cmp` is the proof the source is faithful. The build also runs twelve linters: four keep the `.ctl` consistent (address order, directive order within an address, no redundant lengths, label length), six hold it to its content contracts (every entry titled and every sub-block named; every data entry tiled; every published page inside the program image and standing for one thing; prose naming a labeled slot by its label; no instruction comment reciting a byte count the listing already carries; every record of an array annotated individually), and one holds the *built site* to its (every image macro named a file, and every named file is on the site — the HTML building is not the HTML containing anything). The content checks land red on a mature project, so it records what it starts with in `lint-baseline.txt` and the gate fails on anything new — and on a baseline entry the check no longer reports. `make coverage` reads that baseline too: a project holding recorded findings is not at the bar, whatever its own counts say. See `references/build-verify.md` for the Makefile, the round-trip mechanics, and the `@ofix`/`@isub` fix directives for the rare bytes that differ between original and ideal source.

A verdict is only as readable as the gate it names, because the skill and a disassembly move independently: the same commit passes under one gate and fails under the next. So `make gate` names both — `[SkoolKit 10.1, gate N/e70342a]` — and `lint-baseline.txt` records the gate it was written under, which makes a baseline older than the gate detectably stale rather than silently wrong. **Never report or store a bare GREEN or RED**; report the verdict line. When a red gate's baseline names a different gate, the finding is the gate moving and not the commit regressing — `references/build-verify.md` carries that rule and the rebuild loop across a gate change.

## Stage 5 — Publish (optional)

`skool2html.py` turns the `.skool` plus `.ref` files into a cross-linked HTML site: disassembly pages, graphics galleries (`#UDG`/`#FONT`), playable sound effects (`#AUDIO`), data tables, and a glossary. See `references/html-docs.md`.

## Tools

Verify each exists before use; name any that is missing.

- **SkoolKit** (`tap2sna.py`, `sna2skool.py`, `sna2ctl.py`, `skool2asm.py`, `skool2bin.py`, `bin2sna.py`, `skool2html.py`, `sna2img.py`) — the disassembly toolchain.
- **pasmo** — independent reassembly, to cross-check the round-trip.
- **Vale** (`brew install vale`, or https://vale.sh/docs/install) — the prose linter, carrying the Microsoft style and the ZXDisasm rules. `make lint-prose` needs it; `references/build-verify.md` has the one-time project setup.
- **Python 3** — runs the bundled `.ctl` linters and the byte-extraction helper in `scripts/`.

## Bundled resources

- `references/prose-bar.md` — how well the prose has to be written, in numbers: the terminology registry, the description budget, the sentence rules, and what `make lint-prose` and `make coverage` hold each to.
- `assets/vale.ini.template` and `assets/styles/ZXDisasm/` — the prose linter's config and this domain's own rules. `scripts/extract_prose.py` lifts the prose out of the `.skool` (Vale cannot read one) and `scripts/vale_report.py` puts the findings back on real source lines.
- `references/orchestration.md` and `references/roles/` — the multi-role workflow: the operating manual and the Manager / Worker / Challenger / Researcher contracts.
- `scripts/` — `.ctl` linters (`validate_ctl_address_order.py`, `validate_ctl_instruction_order.py`, `validate_ctl_lengths.py`, `validate_ctl_label_length.py` — caps label length at 24 chars so a long label can't open a wide gutter in the HTML listing), `validate_ctl_identity.py` (gating: every entry titled, every sub-directive described or labeled, so no published block is one a reader cannot identify), `validate_ctl_data_structure.py` (gating: holds every data entry to a tiling — sub-directives covering every byte exactly once — so code cannot hide as an undifferentiated byte span that relocates nothing), `validate_ctl_publication.py` (gating: the set of pages the `.ctl` publishes and what each one stands for — no entry outside the program image, no structure cut into a run of same-titled pages, no `t` entry holding something that is not text, no `b` or `u` entry over bytes the generated `.skool` shows the code storing to, and no title, description or label denying a writer the same `.skool` names), `validate_prose_names.py` (gating: prose must name a labeled slot family's member by its label, never "the second ship"), `validate_ctl_byte_counts.py` (gating: an instruction comment must not recite a byte count the listing already carries — a rate, "9 bytes per slot", is the exemption), `validate_ctl_array_elements.py` (gating: an array of records must name each record on its own line, so a reader can find record 12 — a render macro, a `w` entry, a one-byte stride and a page-sized region at a power-of-two width are exempt, each a span whose `.ctl` already says what the bytes are), `validate_rendered_images.py` (gating, over the built site: every image macro names an output file and every named file is there — the outcome, not the macro count that stands in for it), `ctl_baseline.py` (the known-failing baseline the gating content checks read, so they can be wired in on a mature project without being switched off), `lint_comments.py` (comment quality: the precise kinds gate against the baseline — the two span laws that hold a `{ }` comment group to one act by reading the control flow, the self-link, the operand echo, the investigation-and-emulator vocabulary and the typed `(unverified)` / `TODO:` markers, swept across the `.skool`, the `.ref` catalogs and `spec/*.md`; the judgment-call kinds, RET / restated / placeholder / STAMP, print and never fail), `coverage_report.py` (the "is it done?" gauge — the basic blocks carrying no comment and the comment units per block, plus audio/table/placeholder gaps, the standing `(unverified)` markers, the images the build actually wrote, and the findings the gate is holding on credit, each of which holds the project short of done; a green build is breadth, this measures depth), `splice_ctl.py` (the mechanical address-range merge for a parallel fan-out — splices a Worker's range-fragment into the canonical `.ctl`, refusing one that strays outside its routines), `ctl_to_hex.py` (migrate a decimal `.ctl` to hex addresses, purely notational), and `extract_bytes.py` (pulls the program bytes out of a snapshot for the `cmp`).
- `tools/disassembly.mk` — the shared build framework every project's `Makefile` `include`s (all targets: `all` (the default gate), `gate` — the gate with a verdict line that names the SkoolKit *and the gate* it ran under, says whether anything rebuilt, and flags a baseline recorded under a different gate — `verify-frag`, `coverage`, linters, `html`, `tap`). Single-sourced, so a fix reaches every game; mirrors SkoolKit's own `$(SKOOLKIT_HOME)/tools/disassembly.mk`.
- `assets/theme.ref` + `theme.css` + `theme.js` — the default site theme every project's `make html` ships: dark responsive layout, monospace listing with Z80 syntax highlighting, label-rendered operands, card-grid index, and no network fetch on any page. Every declaration in it is a default a project can change by adding; `game.ref.template` holds the ones a ref file has to own. See the Styling section of `references/html-docs.md`.
- `assets/` — starting templates: `Makefile.template` (the thin stub: config + `include` of the framework), `game.t2s.template` (tap2sna config), `game.ref.template` (HTML config), and `skoolkit.ini`.

## Output

A self-contained project directory: `Makefile`, `{game}.ctl`, `{game}.t2s`, the `.ref` files for HTML, a verified byte-identical `{game}.z80`, and the generated `{game}.asm`. The disassembly rebuilds and re-verifies from a clean checkout with one `make`.
