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

## Prefer the native device over prose

Before you describe something in words, check whether SkoolKit can *express* it directly. A sprite rendered with `#UDG` beats a paragraph about its shape; a bitfield as a `#TABLE` beats a sentence listing its bits; a timing computed with `#TSTATES` beats a hand-estimated "about 3 ms"; a literal encoded as an `@isub` constant beats a comment naming its value. The native device is richer for the reader and is derived from the actual bytes, so it cannot drift out of sync. Prose is for the *why* that no device can carry — the game rule, the trade-off, the bug. `references/expressive-palette.md` is the full catalog of devices; reach for them.

A rendered image is a claim about the bytes, not a fact about the game. The attribute you pass to an image macro (`#UDG`/`#UDGARRAY`/`#FONT`) is a display choice you made. Never describe a sprite's color from it. The in-game color is whatever the draw code writes to the attribute file — trace it to a real value, or render at a neutral attribute and say the color is untraced. Any words around a rendered image must be traced, not invented.

## What not to comment

These add nothing; leave them bare:

- **`RET`** — self-evident.
- **`CALL`/`JP` to a well-named routine** — the name is the comment. Add prose only for non-obvious context (a side effect, why *here*).
- **A literal beside its named constant** — `SET SOUND_BIT_ALARM` needs no "(bit 3)"; the name suffices.
- **Spectrum architecture basics** — assume the reader knows screen memory layout, the attribute system, interrupt modes, the ULA port. Document the *game*, not the platform.
- **Empty or content-free structure** — a hand-drawn ASCII table in a comment (`; +------+------+`), a table header with no rows, a "table" that just re-lists a record's field names. It carries no data the reader can't already see, so it is bloat. Fill it with real values via `#TABLE`, express it with the right device (a tune is an `#AUDIO`, not a period/duration byte table — see `references/expressive-palette.md`), or delete it.

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

## Restraint over speculation

Document what you understand. When a routine's purpose is genuinely unclear, leave it with a bare disassembly and move on — do not invent a story. A confident wrong comment costs a future reader more than an honest gap. No speculation, no frequency hand-waving, no root-cause labels you have not verified against the code.

Work breadth-first, and let the breadth pass be **naming**, not deriving. Give every routine a label and at most a tentative one-line purpose from a quick structural read — enough to see the shape of the whole program. Do *not* thoroughly derive a routine's logic in this pass. Deriving a routine in full and then keeping only a one-liner is wasted work: the depth pass has to derive it again. A name on every routine beats a beautifully documented 10% and an undocumented rest.

Breadth-first is about *sequencing*, not a license to stay shallow. The end state is thorough: once you understand a routine, document it fully — the algorithm, the formula, the inputs and outputs, the quirks. Where the detail is genuinely known, lean long, not terse; a reimplementer would rather have too much than too little. Brevity belongs to two places only: the first breadth pass, and code you do not yet understand (where a one-liner plus an honest "purpose unclear" beats a confident invention).

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

Running the game under `zx-fuse-debug` is how you *acquire* a fact when the bytes are ambiguous. The code is what *supports* it. So the deliverable never cites the emulator: no "verified live", "measured under emulation", "reproduced under FuseX", "the play-observed color". A sentence that leans on a run is a sentence whose code backing was never found, wearing a citation that the reader cannot check and the next author cannot re-derive.

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

## Tone and tense

Present tense, describing the code as it stands. Short, linear sentences. The comment is for whoever reads the code next, with no memory of how it got there — so never narrate the editing ("changed to…", "now also…"). State what the code *is* and *does*.
