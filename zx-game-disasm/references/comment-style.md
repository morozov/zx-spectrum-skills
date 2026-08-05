# Comment style — the heart of the skill

The reassembly is mechanical. The documentation is the craft. This file is about what makes a disassembly worth reading: comments that let someone reimplement the game without ever seeing the Z80.

## The one principle

**Every comment must add information the code cannot show on its own.** The instruction already says *what* it does. Your job is the *why* — the game rule, the formula, the constraint, the consequence. If a comment only restates the instruction, delete it; a redundant comment is noise, and a stale one actively misleads.

The litmus test: could a reader who knows the Spectrum but not this game rewrite the routine in C from your comments alone? If yes, the documentation is doing its job. If the comments just narrate opcodes, it is not.

A second reader is an ML agent's trainer, who needs the game's state, actions, dynamics, and reward in concrete units. That is a sharper subset of the same work — both readers consume the behavior spec in `references/behavior-spec.md`. The practical effect on your comments: when a routine touches game state, motion, scoring, or fuel/lives, prefer numbers to adjectives. "1 pixel/frame", "awards 80 points", "depletes 1 unit every 8 frames" are trainable facts; "moves slowly", "scores some points", "uses fuel" are not.

**Bad** — restates the instruction:

```asm
LD A,MAX_ENERGY         ; Load MAX_ENERGY into A.
LD (player_energy),A    ; Store A into player_energy.
```

**Good** — states the intent, once, for the pair:

```asm
LD A,MAX_ENERGY         ; Refill the energy at the start of a life.
LD (player_energy),A    ;
```

## Document at the right altitude

Two altitudes, with the same division of labor as a method's doc comment and its body — and the line between them is *purpose/contract* vs *mechanism*:

- **Routine** (`D` for the description, `R` for registers) — the **contract**, written for the caller: what the routine does and why it exists, its inputs, outputs, side effects, and invariants. State the **purpose, not the mechanism** — name *what* it computes, not *how* the bytes do it. For a projectile routine the description says "fires a shot on a parabolic trajectory toward the player's current column"; it does *not* walk the math. A reader gets the contract without reading the body, exactly like a docstring.
- **Block and line** (`N` over a block, the instruction comment on a line) — the **mechanism**, written for the implementer: the algorithm and the math, explained well enough to **reimplement the routine in a higher-level language without disassembling it**. This is where the projectile's per-frame `dx`/`dy` step, the gravity increment, and the despawn test actually get explained.

That division *is* the deliverable. The contract tells a porter or an agent-trainer what the routine is for; the body comments tell them how to rebuild it; together they let someone rewrite the logic, or derive training state from it, without ever reading Z80. Neither restates the instruction — both state the game logic and the math the instructions encode.

Comment the mechanism at the altitude that carries meaning, not below it. State a calculation's formula **once**, at the block level, and leave the arithmetic uncommented — the formula is the line-level explanation, and per-instruction comments on the multiply and add would only restate it in pieces:

```
N $6E00 Screen attribute offset = (7 - row) * 8 + column.
```

A single-instruction comment earns its place only when that one instruction carries a non-obvious reason a constant or label cannot already convey.

**Derive a routine once; author the contract and the mechanism together.** As you derive the routine, write the body's mechanism comments, and write the `D` contract from the same understanding — purpose and contract at the top, the algorithm in the body, both produced in the one pass so they cannot drift apart. Never derive a routine in full, discard the understanding, and keep only a summary: a later pass then has to re-derive it in full, and the orphaned summary can silently contradict what that second derivation finds.

## One home per fact

Every fact gets exactly one home; everywhere else, link or stay silent.

- **`D`** — the contract: purpose in game terms, callers, the one player-visible consequence. One or two sentences.
- **`N`** — the mechanism model, *only where the code is non-obvious*, and mid-routine **stage directions** that assert game state ("The shot has just left the ship."), not code topology ("Main path: advance the shot").
- **Line comments** — what the instruction means for the game. Question on the test, answer on the branch: `; Is the ship frozen?` / `; Jump if so`. One brace-grouped comment per multi-instruction idea; silence for the obvious.
- **Never say it twice.** If the `D` states it, the `N` does not restate it, and the line comments do not restate the `N`. If the same sentence already exists in another block or a `.ref` page, cross-link it (`See #R…`) instead of copying it.

**The family rule.** Before documenting the second sibling of any family — sound effects, per-enemy handlers, animation-frame tables, mirrored state records — write the shared mechanism **once**, at the family's head (the dispatcher, the shared primitive, the first table), and give each sibling only its deltas: which table, what it is in the game, when it triggers, its quirk. The hard test: **if a sentence would survive swapping its addresses into a sibling block, it is in the wrong place** — move it to the head. (A repeated *formula* is fine exactly when the underlying reality is repeated — sixty structurally identical room initializers may share a title pattern; seven different sound effects may not share a paragraph.)

Shared Z80 idioms — a CPL-abs trick, an LDIR fill, screen-third address math — are explained once, at the primitive or the first use, and referenced after. Never re-derive an idiom per call site. Snapshot/build provenance ("zero in this snapshot; the start-up copy fills it from the source area") is likewise stated once, at one block, and cross-referenced.

Worked example. Bad — a header longer than the routine it describes, stamped nearly verbatim across every sound effect:

> Plays one step of the door-opening creak and advances its 8-step sequence. Polled once per game frame by the main loop's sound dispatch; returns straight away while its counter #R$6D80 is 0 (disarmed). … Takes no register inputs and returns nothing; clobbers #REGa, #REGc, #REGde and #REGhl; its only side effect is speaker output via #R$6D90, which is patched to RET while the sound option is off. … #R$6D90's half-period is about 11*D T-states, so the period byte D maps to roughly 3.5MHz/(22*D). The 8 played periods 90, 80, 70, 60, …

Good — the polled-counter/mute mechanism documented once at the dispatcher and the tone primitive; then, per effect, only what makes it itself, plus the sound:

> The 8-step creak of a door opening; armed by
> #R$6DA0 and #R$6DB0. #AUDIO(…)

## The register contract is `R` lines, not prose

Never write "Takes no register inputs and returns nothing; clobbers …" — or any inputs/outputs/clobbers sentence — into a description. Register facts go in `R` lines (`I:`/`O:`), and only when **some caller acts on them**: a real parameterized subroutine, a flag a caller branches on. A routine in a fixed dispatch list, called for effect, gets no register prose at all — a Z-flag return is documented *because some caller loops on it*, never as a formality, and clobbers are not documented at all. A clobber note is legitimate only where a specific caller demonstrably depends on preservation.

## Prefer the native device over prose

Before you describe something in words, check whether SkoolKit can *express* it directly. A sprite rendered with `#UDG` beats a paragraph about its shape; a bitfield as a `#TABLE` beats a sentence listing its bits; a timing computed with `#TSTATES` beats a hand-estimated "about 3 ms"; a literal encoded as an `@isub` constant beats a comment naming its value. The native device is richer for the reader and is derived from the actual bytes, so it cannot drift out of sync. Prose is for the *why* that no device can carry — the game rule, the trade-off, the bug. `references/expressive-palette.md` is the full catalog of devices; reach for them.

A rendered image is a claim about the bytes, not a fact about the game. The attribute you pass to an image macro (`#UDG`/`#UDGARRAY`/`#FONT`) is a display choice you made. Never describe a sprite's color from it. The in-game color is whatever the draw code writes to the attribute file — trace it to a real value, or render at a neutral attribute and say the color is untraced. Any words around a rendered image must be traced, not invented.

## What not to comment

These add nothing; leave them bare:

- **`RET`** — self-evident. And never let a `{ }` comment group swallow a trailing `RET`: the group's text describes the logic above it, and the `RET` is infrastructure, not logic — close the group on the last instruction the text actually describes. If the *return itself* carries meaning ("HL holds the slot"), that is the routine's contract — say it in the `D`/`R` lines, not in a group stretched over the `RET`.
- **`CALL`/`JP` to a well-named routine** — the name is the comment. Add prose only for non-obvious context (a side effect, why *here*).
- **A literal beside its named constant** — `SET SOUND_BIT_ALARM` needs no "(bit 3)"; the name suffices.
- **Spectrum architecture basics** — assume the reader knows screen memory layout, the attribute system, interrupt modes, the ULA port. Document the *game*, not the platform.
- **Empty or content-free structure** — a hand-drawn ASCII table in a comment (`; +------+------+`), a table header with no rows, a "table" that just re-lists a record's field names. It carries no data the reader can't already see, so it is bloat. Fill it with real values via `#TABLE`, express it with the right device (a tune is an `#AUDIO`, not a period/duration byte table — see `references/expressive-palette.md`), or delete it.
- **The void contract** — "takes no register inputs and returns nothing" and its relatives. An absent contract is expressed by absence (see "The register contract is `R` lines, not prose").
- **Arithmetic lessons** — positional notation, two's complement, what a multiply-by-shifting is. The reader knows mathematics; state the formula the code computes, not the theory behind formulas.
- **A third telling** — the question/answer pair (`; Is he dead?` / `; Yes`) already covers the test and the branch; a block comment restating the same check on top of the pair is one telling too many.

## The comment never repeats its own operand

With labels rendered into operands everywhere (`.skool`, `.asm`, the site's `CALL erase_door`), an instruction already names and links the thing it touches. A comment that references that same symbol says it twice on one row, and an ellipsis chain hand-splices what a comment group exists for. Both are linted (`OPERAND_ECHO`, `ELLIPSIS`) and gate the coverage verdict.

> **Bad:** `LD (door_anim_phase),A  ; clear the phase (#R$7F30)...` `CALL erase_door  ; ...and erase the door via #R$8D40.`
>
> **Good:** `LD (door_anim_phase),A  ; clear the phase` `CALL erase_door  ; erase the door`

When one thought genuinely spans several instructions, use a `{ }` comment group over exactly those rows — never `...` fragments stitched line to line.

## Decimal equivalents

Give a decimal equivalent only for a value that means something in the human world — a level number, an iteration count, a pixel distance — not for memory addresses. `$7A26` as an address stays hex; `$0F` as "15 lives" earns its `(15)`.

## Documenting the non-obvious

The comments that matter most capture what a reader could never reconstruct:

- **Bugs and quirks.** Flag them explicitly. They are facts about the artifact and often the most valuable thing in the disassembly.

  ```
  N $6E50 BUG: the boundary check uses < instead of <=, so the sprite can
  N $6E50 appear one pixel outside the play area for a single frame.
  ```

- **Fall-through.** When a routine runs into the next one rather than returning, say so: `This routine continues into #R$6B00.`

- **Multiple entry points.** Document each with its own `N` paragraph and its own contract.

- **Coordinate conventions.** In sprite and collision code, state the frame of reference once — e.g. `(x+1, y+2)` relative to the sprite's top-left corner — so every offset after it reads cleanly.

## The depth standard

The bar is *depth*, far past a routine-level one-liner pass: nearly every code routine has an explained body, sound is rendered with `#AUDIO`, and data tables are laid out with `#TABLE`. Concretely:

- **every routine's body is explained**, at the right altitude — most instructions carry a game-term comment, the rest are covered by a block comment, and `RET` and well-named calls stay bare. A routine with a description but a bare body is *skeletal*: that is breadth — a name and a summary — not done.
- unique addresses replaced by symbolic constants; ambiguous small literals explained in the instruction's comment, not forced into a global constant (see `references/ctl-authoring.md` on `@equ`);
- every variable and table named — no raw hex, no `work_b`/`helper_xxxx` placeholders;
- sound documented with `#AUDIO`, bitfields and tables with `#TABLE`;
- inline critiques of the original author's odd choices, written from full comprehension — never as a hedge for what you failed to understand.

The last bullet above is the sharp one: calling out a questionable original decision is not the same as admitting your own uncertainty — the former requires understanding the code completely.

`scripts/coverage_report.py` (`make coverage`) measures the floor — the fraction of routines with an explained body, plus audio/table/placeholder gaps — so "is it done?" is a measured claim, not an impression. It counts code only; data blocks (loading screen, level data) are documented by labels and native devices, not line comments, so they are excluded. A skeletal-heavy project is not mature, however green the build.

**These principles are the bar — no project defines it.** Any existing disassembly, including one built with this skill, falls short of some principle somewhere; that is a defect in the project, queued for its upgrade — never a precedent. "Project X does it too" is not a defense. Judge by the rule.

## Restraint over speculation

Document what you understand. When a routine's purpose is genuinely unclear, leave it with a bare disassembly and move on — do not invent a story. A confident wrong comment costs a future reader more than an honest gap. No speculation, no frequency hand-waving, no root-cause labels you have not verified against the code.

Work breadth-first, and let the breadth pass be **naming**, not deriving. Give every routine a label and at most a tentative one-line purpose from a quick structural read — enough to see the shape of the whole program. Do *not* thoroughly derive a routine's logic in this pass. Deriving a routine in full and then keeping only a one-liner is wasted work: the depth pass has to derive it again. A name on every routine beats a beautifully documented 10% and an undocumented rest.

Breadth-first is about *sequencing*, not a license to stay shallow. The end state is thorough — but **thoroughness lives at the lines, not in the header**. Once you understand a routine, explain its algorithm fully at the instructions and block comments that implement it. The routine description stays one or two sentences: what it does for the game, who calls it and when, the one non-obvious consequence. Length tracks **contract complexity, never routine size** — 250 lines of hairy movement logic can still take one sentence; a long description is earned only when it buys a data-format table, a state machine, or a derivation, never a longer paragraph. If your header restates what the body's comments already say, or previews the call sequence the reader is about to see, cut it from the header.

A fast breadth pass is unreliable in a way a green build never catches. Hand-converted addresses come out off by eye, and architectural claims guessed from a routine's callers turn out wrong. Derive an address, never convert it by eye. Treat every breadth-pass name and one-liner as provisional — the depth pass derives the routine for real and confirms or replaces it. There is no separate summary to re-verify, because the routine description is written from that line-level derivation (see "Document at the right altitude").

## The deliverable never narrates the investigation

The disassembly is written in timeless present about the game, as if the author always knew. How a fact was obtained is not content: no "traced", "verified", "confirmed", "measured under emulation", "observed in play", "not fully pinned", "this pass" — and no references to working notes or ledgers. The disassembly *is* the provenance; the investigation lives in dig-tasks and commit messages. The same goes for grading your own honesty: text that calls itself "honest" or labels a claim "PROVISIONAL:" is the working diary leaking into the reader's document.

Uncertainty is still first-class — but **typed, not smeared**:

- **An unknown purpose**: leave the block an honest name (an auto-label, or a `data_<addr>`) and either silence or observed usage — "Written by #R$6F20; nothing reads it." A dead byte is "Unused." — no eulogy.
- **A specific open question**: one greppable marker at the exact claim — a trailing `?` on the doubted clause, a `TODO:` line, or a parenthesized `(unverified)` on the one field that is not derived — never a prose hedge ("apparently", "likely", "whether this ever happens is unverified") spread across the sentence, and never a confidence label in reader-facing text. The confident parts of the sentence stay flat. A marker is legitimate *and* it is the project saying the work is unfinished: it owes an open dig-task, it holds the project short of done (`make coverage` counts them as OPEN), and it is retired by deriving the claim — never by deleting the marker.
- **A stated assumption** is fine when the reader needs it: "~5 s, assuming the 50 Hz frame interrupt."

Before/after. Bad:

> ; Player 2 jump cooldown (record +9), the player-2 counterpart of ; #R$7C09. While non-zero it counts down player 1's timer … — an apparent ; cross-wire whose intent is unverified.

Good — the mirror stated once at the record's head, the doubt typed and pointed:

> D $7C10 Player 2's record mirrors player 1's (#R$7C00); only the two bytes below differ. … ; Jump cooldown — counts down player 1's timer, not player 2's. Deliberate?

The rule governs **every artifact the reader opens** — the `.ctl` comments, the `.ref` catalogs, the behavior spec, the built pages — because they are one document to the person reading them. Scope it to comments and the vocabulary simply moves: lint the `.skool` alone, and the violations settle in the catalogs and the spec. `make lint-comments` takes the `.ref` files and `spec/*.md` for that reason.

### A run is evidence for the author, never support for the reader

Running the game under `zx-fuse-driver` is how you *acquire* a fact when the bytes are ambiguous. The code is what *supports* it. So the deliverable never cites the emulator: no "verified live", "measured under emulation", "reproduced under FuseX", "the play-observed color". A sentence that leans on a run is a sentence whose code backing was never found, wearing a citation that the reader cannot check and the next author cannot re-derive.

Two repairs, both real. **Re-derive the observation as a code fact** — the observation was right, so find what makes it true:

> Bad: it does not follow the platform: verified in emulation, it stayed at (96, 120) across 300 frames while the platform moved over its full x 16–200 range.
>
> Good: it does not follow the platform: the update writes a fixed X and a fixed Y each frame — the platform's position is never read.

**Or drop the measurement to what the code fixes.** A frame rate measured under emulation is a property of the run, not of the game; the code fixes only the ratio, so state the ratio and anchor the seconds to a nominal frame rate the reader can see you assuming.

### A caveat cannot title an entry whose body derives the mechanism

A heading like "Not fully pinned statically", over a body that then explains the cause from the code, denies its own page — the reader is told the entry failed and then reads the answer. It happens when two questions get one verdict. How a stuck shot *stays* stuck is in the collision code; how it *entered* that state is a sub-pixel path no static read produces. Only the second is open.

State the mechanism you have and stop. The open half goes to a dig-task, never to a caveat paragraph and never to a re-scoped title — silence about an unanswered question is the honest form, because the disassembly claims only what it says. The typed marker above is the one in-text allowance, and it is for a doubted *claim*, not for a question the page never raises.

## Comments must be relocatable

The disassembly stays relocatable, so a comment must never hard-code an address, hex or decimal. Refer to code or data by its label — through the `#R` macro, which renders the symbolic label and survives relocation, or by the symbolic name itself. `skool2asm` auto-flags a bare address in a comment ("Comment contains address … not converted to a label") and fails the warning-clean build.

## Prose discipline — voice and cross-references

- **Write noun phrases, not identifiers.** In descriptions and `N` lines, say "while the player is stunned or paused (#R$7F21, #R$7F24)", never "while input_lock (#R$7F25), player_stun (#R$7F21) or player_pause (#R$7F24) hold". Labels belong in operands and `R` lines; prose is for a person. The human form is one noun phrase, one link: "the jump timer at #R$7F28".
- **Never write `label (#R$addr)` for the same symbol.** `#R` renders as the label, so this produces "ship_x (ship_x)" in the built site. Link a symbol at its first mention in a block; use the bare name after. Keep the cross-reference budget human: a description carries 0–2 `#R` links, not a link per clause.
- **State conclusions, not derivations.** Keep arithmetic only where a porter needs it (table strides, address math), stated once at the block level. Do not chain "…, so …, so …" proofs, and do not transcribe data into prose — no inline byte lists, no Hz/ms conversion per entry, no `#TABLE` that mirrors the `DEFB` block below it. Render or play the artifact instead (`references/expressive-palette.md`).
- **Vary the rhythm.** If ten consecutive descriptions open with the same verb, or every clause hangs on the same appositive dash, rewrite until the block reads as written, not generated. Numbered scaffolding ("Stage 1: … Stage 18:") is bureaucracy — name the phases with stage directions instead.
- **Proofread in the reader's medium.** After editing prose, read the affected page in the built HTML, not the `.ctl`. The `.ctl` is the source; the page is the artifact — link duplication, transcribed tables, and metronome rhythm are visible only there.

## Tone and tense

Present tense, describing the code as it stands. Short, linear sentences. The comment is for whoever reads the code next, with no memory of how it got there — so never narrate the editing ("changed to…", "now also…"). State what the code *is* and *does*.

Personality is welcome at low frequency, anchored to verified fact — a dozen beats per project, not per page: a dry aside on a proven oddity, a one-word judgment on the original programmer's choice ("roundabout", "redundantly") written from full comprehension. Never signpost it ("interestingly", "it's worth noting") — the observation either carries itself or doesn't belong.

The target register, in examples — economical, concrete, alive:

- "Everything starts here once the game has loaded." — an entry routine's description, in full.
- "Has the player reached the water?" / "If not, move the player" — question on the test, answer on the branch.
- "The player has just started falling." / "Out of time." — stage directions asserting game state, not code topology.
- "A quick and dirty way to pick a random lane." — opinion in two adjectives.
- "Perhaps this unused table was once meant for a second player." — a hedge that is a falsifiable hypothesis, not insurance.

Never in the register: "This routine is responsible for…", "Takes no register inputs and returns nothing", "identified via tracing", a paragraph where a rendered image or an `#AUDIO` would do, or the same sentence in two blocks.
