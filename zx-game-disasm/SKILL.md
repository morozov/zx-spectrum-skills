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
---

# ZX Spectrum game disassembly

Turn a ZX Spectrum game image into a fully annotated Z80 source that anyone can read, reassemble to the *exact original bytes*, and use to reimplement the game in a higher-level language. The toolchain is [SkoolKit](https://skoolkit.ca) (disassembly, round-trip, HTML) plus [pasmo](https://pasmo.speccy.org/) (independent reassembly check).

The deliverable is a project: a `Makefile`, a primary `.ctl` control file (the hand-edited source of truth), generated `.skool`/`.asm` intermediates, a verified byte-identical snapshot, and — optionally — an HTML documentation site.

## Two goals, always both

1. **Reassemblable and correct — the foundation.** The source reassembles to a byte-identical copy of the original. That round-trip is the hard floor, checked by **`make`** — the single gate that drives every check (round-trip, linters, and the HTML build that validates the `.ref` catalogs). If the bytes drift, the documentation describes code that no longer matches. Full correctness — every reference relocatable, every block named (no `L####` auto-labels) — is reached progressively as the map is understood, and `make coverage` tracks it (you cannot name a block before you have disassembled it). **"Relocatable" is claimed only after the program has been shifted and run** — the gauge counts operands, so it is blind to an address held as data, built from an 8-bit immediate, bound by an absolute `@equ`, or hiding in code annotated as bytes. The proof, its two non-obvious constraints, and how to bisect it when it fails are in `references/build-verify.md`. Relocatability is never inferred from a green build.
2. **Documented for two overlapping uses.** The comments must explain the *algorithms and game logic*, not the Z80 instruction semantics. Two readers consume that documentation, and the second is mostly a sharper-focused subset of the first:
   - **A human reimplementing the game** in another language. Needs the whole thing — rendering, input, sound, logic — well enough to rewrite it.
   - **An ML agent learning to play.** Needs the game expressed as a Markov decision process: the **state** (and *where in RAM* it lives, so it can be read live), the **actions** and their effects, the **transition dynamics**, and the **reward structure** — scoring, the fuel/life economy, win/lose conditions. It cares little about rendering, and it wants concrete units (speeds, frame counts, trajectories), not "moves the sprite."

Hold all of this at once. Every documentation pass ends with a build that proves the bytes still match. The capstone artifact that serves both uses is a **behavior specification** — a subsystem-by-subsystem account of how the game behaves, synthesized from the disassembly and stated in concrete numbers. A porter rewrites from it; an agent-trainer reads the MDP (state, actions, dynamics, reward) out of it. See `references/behavior-spec.md`.

## The five stages

Work in order, but the table is a logical order, not a strict schedule. In practice the first real moves are mapping data vs code and getting a warning-clean, byte-identical build — verification is established early and kept green from then on, not saved for the end. Stages 2–4 then interleave: you map a region, document its routines, rebuild, and move to the next. The bulk of the effort is stage 3, and it proceeds one routine at a time over many small steps, each leaving the build green.

| Stage | Goal | Reference |
| --- | --- | --- |
| 1. Acquire | Get a clean snapshot of the fully-loaded game in memory | `references/acquisition.md` |
| 2. Map | Separate code from data, find entry points, get a clean `.skool` | `references/ctl-authoring.md` |
| 3. Document | Annotate the `.ctl`, express it richly, synthesize the behavior spec | `references/comment-style.md`, `references/ctl-authoring.md`, `references/expressive-palette.md`, `references/behavior-spec.md` |
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

`references/orchestration.md` is the operating manual (phases, the protocol, the Manager loop); `references/roles/manager.md` is your contract; `references/roles/` holds the rest. Read them before disassembling a whole game.

## The mental model

SkoolKit disassembles a *snapshot* — a frozen image of RAM with the game already loaded. The `.ctl` control file is your annotations *over* that snapshot: where code starts and stops, what each address means, what to name it. `sna2skool` applies the `.ctl` to the snapshot to produce a `.skool` (the disassembly with your comments woven in). `skool2asm` turns that into assembly; `skool2bin` plus a `cmp` against the original proves the round-trip.

So the `.ctl` is the only file you hand-edit. Everything else is generated. Never edit the `.skool` or `.asm` directly — your changes would be overwritten on the next build, and they would not feed back into the round-trip check.

## Working discipline — iterate in green checkpoints

A full disassembly is a long effort, far too long to run blind: work in the wrong direction compounds, and a single broken boundary can leave the project unbuildable for a long stretch. So the unit of progress is not "the finished disassembly" — it is **a small, green checkpoint**, and you produce a steady stream of them, each leaving a buildable project.

The rules that keep it steerable:

- **Every checkpoint builds and round-trips.** At each checkpoint the project must `make` clean: the disassembly reassembles to byte-identical program bytes (the round-trip `cmp` in `references/build-verify.md`), the linters pass, and there are no build warnings. Never leave the project in a state that does not build across a checkpoint. A green checkpoint is one you could hand back right now and the user could build, boot, and inspect. "Builds" means a full `make`: the generated `.skool` *and* the human-readable `.asm` are produced as artifacts, not just the `.ctl` you edit. The `.asm` is the deliverable a reader opens — keep it current, even when a task only asks about the control file.
- **A green round-trip is not proof the map is right.** Byte-identity proves the bytes are faithful; it says nothing about whether your code/data split and data-structure boundaries are correct, because mislabeled bytes still round-trip (see "What the round-trip does NOT prove" in `references/build-verify.md`). Validate boundaries from how the code *uses* the data, and where a boundary is genuinely undeterminable, document the uncertainty rather than committing to a silent guess.
- **Keep increments small.** One region mapped, one routine documented, one data table laid out — then rebuild and verify. If a change cannot be made without breaking the build, it is too big; split it. Small steps mean a wrong turn costs minutes, not hours.
- **Breadth before depth — and breadth means *naming*, not deriving.** The first pass maps code vs data and gives every routine a label (and at most a tentative one-line purpose) from a quick structural read — never a full derivation of its logic. Deriving a routine in depth and then discarding that understanding for a one-line summary is wasted twice over: a later pass has to derive it again, and the throwaway summary can drift from what that second derivation finds. So derive each routine **once**, in the depth pass, and author its line-level annotations and its routine description *together* there — the description synthesized from the lines so the two cannot disagree. A shallow naming pass still reveals the shape of the whole game, so the Manager picks the high-impact systems to deepen instead of discovering late that the effort went to the wrong place.

The throughline: a steady stream of adversarially-verified, byte-identical green checkpoints is what makes a long effort *safe*. Each checkpoint is gated by the Challenger, so the work moves forward without trading correctness for completion. The Challenger is the quality gate.

## "Mature" is a measurement, not an impression

A disassembly where every routine has a label, a one-line description, and a green build *looks* finished — and calling it "mature", "mostly documented", or "nearly done" is a misjudgment. It is not finished: that is **breadth** (every routine *named*), and the depth — an explained *body* on every routine, the catalogs, the audio, the spec — is where most of the work lives and is usually barely begun. A green, fully-labeled `.ctl` whose routines all carry a `D` description is still far short of the bar, because those descriptions sit over bare bodies (the *skeletal* state).

So never characterize a project's state from an impression, and never from a count of `D` lines — a description on every routine is breadth, not depth. When you pick up an existing disassembly, **run `make coverage` first** and state where it stands in the gauge's terms (for example, "40% of routines explained, 60 skeletal, no audio"), never "mature". The gauge exists to replace the impression; if it says NOT at the bar, the project is not mature, however polished the labels look.

**Core principle — upgrade an existing project to the current standard.** This skill evolves; a project built to an older version is held to the bar as it stands *now*, not as it was. On picking one up, audit it against the current skill and upgrade it first — hex `.ctl`, the thin Makefile that includes the framework, named labels (no `L####` left for `lint-labels` to reject), inline-rendered sprites — then continue. Inherit the game's work, not its stale conventions. See the Manager's bootstrap in `references/roles/manager.md`.

## Stage 1 — Acquire a clean snapshot

SkoolKit needs the game *as it sits in memory after loading*, not the raw tape. For most tape games, `tap2sna.py` simulates the load and writes a `.z80` snapshot in one step. Snapshots (`.sna`/`.szx`/`.z80`) can be used directly. Disk images and packed/multi-stage loaders need more care — a compressed game must be captured *after* it decompresses itself, sometimes as two snapshots (one for the unpacker, one for the unpacked body).

The output of this stage is a snapshot plus three numbers the rest of the pipeline needs: the origin (`ORG`), the entry point (`PC`), and the stack pointer (`SP`). See `references/acquisition.md` for tape, disk, snapshot, and packed-loader recipes, and how to find `ORG`/`PC`/`SP`.

When `tap2sna` cannot load the game cleanly and you need to drive the loader live — turbo timing, decryption, relocation you must follow block by block — run it under FuseX with the **`zx-fuse-debug`** skill, and apply the general comprehension method in `../shared/disasm-analysis.md`. Capture a snapshot at the hand-off point once the game is in memory. (The `zx-tape-to-trdos` skill has tape-loader-specific trapping recipes if the loader is a turbo/protected one.)

## Stage 2 — Map code vs data

A bare disassembly treats every byte as code, which is wrong wherever the game stores graphics, tables, or text. The `.ctl` marks each region with a block type (`c` code, `b` bytes, `t` text, `w` words, `s` space, `g` game-status buffer). Getting these boundaries right is what makes the disassembly readable and what keeps `pasmo` from choking on data interpreted as opcodes.

Start the `.ctl` as one `b` block over the image and convert a region to `c` only as execution flow confirms it (see `references/agents.md`). `sna2ctl.py --hex` guesses code and data; read its output as a hint, never as the map. **Every `.ctl` address is hex** — see `references/ctl-authoring.md`. The `.skool` is your map: rebuild it after every change and watch for `overlapping instruction` warnings, which mean a block boundary falls mid-instruction.

## Stage 3 — Document

This is the work. Iterate on the `.ctl`: name routines and variables, define symbolic constants, write each routine's **contract** as its description (purpose, inputs, outputs, side effects — not the mechanism), explain its **algorithm and math at the line level** so it can be reimplemented without the Z80, and document data structures as you meet them. The altitude split — purpose/contract at the top, mechanism in the body — is in `references/comment-style.md`.

Documenting presupposes understanding. The method for *deriving* a routine's logic — static reading, Z80 idiom recognition, and dynamic confirmation when a static read is ambiguous — is the shared reference `../shared/disasm-analysis.md`. When reading the bytes is not enough (a computed jump, self-modifying code, a state-dependent value), run the game under the **`zx-fuse-debug`** skill and observe it. Derive first, then document what you derived.

A run supplies *you* with evidence; the code is what the documentation rests on. Every runtime finding must therefore land as a statement the code supports — the observation tells you where to look, and the routine that makes it true is what you write down. A fact you cannot get back out of the code does not ship, and the deliverable never cites an emulator (`references/comment-style.md`). The comment philosophy is the thing to internalize, not a list of directives: **every comment must add what the code cannot show.** Never restate an instruction; describe the *why*, the formula, the game rule. Read `references/comment-style.md` before writing comments — it is the heart of the skill — and `references/ctl-authoring.md` for the control-file syntax that expresses it (labels, `@isub` constants, numeric bases, `#TABLE`, `R` annotations, cross-references).

Work breadth-first: give every routine a one-line purpose before deep-diving any single algorithm. Skip routines you genuinely do not understand rather than speculating — a wrong comment is worse than none. Build often; small verified steps beat large unverifiable ones.

Express it richly. SkoolKit is a documentation toolkit with a large vocabulary, and the richer the disassembly, the more it is worth to the end user. Prefer the *native* device over prose: render a sprite with `#UDG`/`#UDGARRAY` instead of describing it, play a sound with `#AUDIO`, lay out a bitfield as a `#TABLE`, compute a timing with `#TSTATES`, encode a literal as an `@isub` constant, carry a bugfix in `@bfix`, record a cheat as a `[Poke:...]` section. Whenever you are about to write a sentence, check whether a device expresses the fact directly — it usually does. `references/expressive-palette.md` is the full catalog, grouped by purpose; reach into it liberally. The bar this aims at: a disassembly that renders the game's own levels and sprites from the data, generates derived facts with scripts, and builds a reference manual over the listing.

Once routines are annotated, synthesize the **behavior specification**: a subsystem-by-subsystem account (player, input, enemies, collision, fuel, scoring, …) of how the game behaves, in concrete numbers, each claim traced to a `.ctl` label. This is the artifact a porter or an agent-trainer actually consumes. `references/behavior-spec.md` covers how to organize it, the concreteness standard, and the MDP checklist (state addresses, actions, dynamics, reward) that makes it usable for training an agent, not only for porting.

## Stage 4 — Verify

Run `make`. It regenerates the `.skool`, emits the assembly, reassembles it, and `cmp`s the result against bytes extracted from the original snapshot. A clean `cmp` is the proof the source is faithful. The build also runs three linters that keep the `.ctl` consistent (address order, directive order within an address, no redundant lengths). See `references/build-verify.md` for the Makefile, the round-trip mechanics, and the `@ofix`/`@isub` fix directives for the rare bytes that differ between original and ideal source.

## Stage 5 — Publish (optional)

`skool2html.py` turns the `.skool` plus `.ref` files into a cross-linked HTML site: disassembly pages, graphics galleries (`#UDG`/`#FONT`), playable sound effects (`#AUDIO`), data tables, and a glossary. See `references/html-docs.md`.

## Tools

Verify each exists before use; name any that is missing.

- **SkoolKit** (`tap2sna.py`, `sna2skool.py`, `sna2ctl.py`, `skool2asm.py`, `skool2bin.py`, `bin2sna.py`, `skool2html.py`, `sna2img.py`) — the disassembly toolchain.
- **pasmo** — independent reassembly, to cross-check the round-trip.
- **Python 3** — runs the bundled `.ctl` linters and the byte-extraction helper in `scripts/`.

## Bundled resources

- `references/orchestration.md` and `references/roles/` — the multi-role workflow: the operating manual and the Manager / Worker / Challenger / Researcher contracts.
- `scripts/` — `.ctl` linters (`validate_ctl_address_order.py`, `validate_ctl_instruction_order.py`, `validate_ctl_lengths.py`, `validate_ctl_label_length.py` — caps label length at 24 chars so a long label can't open a wide gutter in the HTML listing), `validate_ctl_data_structure.py` (advisory: holds every `b`/`s` block to a tiling — sub-directives covering every byte exactly once — so code cannot hide as an undifferentiated byte span that relocates nothing), `lint_comments.py` (advisory comment-quality pre-filter: RET / restated / placeholder, plus the investigation-and-emulator vocabulary and the typed `(unverified)` / `TODO:` markers, swept across the `.skool`, the `.ref` catalogs and `spec/*.md`), `coverage_report.py` (the "is it done?" gauge — fraction of routines with an explained body, plus audio/table/placeholder gaps and the standing `(unverified)` markers, each of which holds the project short of done; a green build is breadth, this measures depth), `splice_ctl.py` (the mechanical address-range merge for a parallel fan-out — splices a Worker's range-fragment into the canonical `.ctl`, refusing one that strays outside its routines), `ctl_to_hex.py` (migrate a decimal `.ctl` to hex addresses, purely notational), and `extract_bytes.py` (pulls the program bytes out of a snapshot for the `cmp`).
- `tools/disassembly.mk` — the shared build framework every project's `Makefile` `include`s (all targets: `verify`, `gate` — the gate with a PASS/FAIL verdict line — `verify-frag`, `coverage`, linters, `html`). Single-sourced, so a fix reaches every game; mirrors SkoolKit's own `$(SKOOLKIT_HOME)/tools/disassembly.mk`.
- `assets/` — starting templates: `Makefile.template` (the thin stub: config + `include` of the framework), `game.t2s.template` (tap2sna config), `game.ref.template` (HTML config), and `skoolkit.ini`.

## Output

A self-contained project directory: `Makefile`, `{game}.ctl`, `{game}.t2s`, the `.ref` files for HTML, a verified byte-identical `{game}.z80`, and the generated `{game}.asm`. The disassembly rebuilds and re-verifies from a clean checkout with one `make`.
