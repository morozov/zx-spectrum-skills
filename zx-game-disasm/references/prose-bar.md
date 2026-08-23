# The prose bar

`comment-style.md` says what a comment is *for*. This says how well it has to be written, in numbers a check can read.

Every rule here is measured. `make lint-prose` reports them, `make coverage` counts them, and a project does not reach "done" while any of them is unmet.

## Who the prose is for

A person who likes this game and wants to know how it worked. They read pages, they do not grep. Write for them.

Two other readers exist and neither sets the register. A porter needs the format tables, and gets them from the same document. An agent-trainer needs the state addresses, and gets them from the behavior specification, which is written for them. Writing for either of those two produces exhaustive text nobody reads, because every rule written for a reader who greps can only ask for more.

## One term per thing

**T1 — one name per entity.** Every reference to the same thing uses the same words. That holds across the `.skool`, the `.ctl`, every `.ref` page, the spec, the entry titles, and the labels. A spelling variant is the same violation as a synonym.

**T2 — one meaning per name.** A word already used for one thing cannot name a second. If two things want the same obvious word, one of them gets another word.

**T3 — a coined term must not assert a classification the game does not have.** A qualifier implies a contrast set. Name the set, or drop the qualifier. "A solid object" claims there are non-solid ones; if what the code holds is an object that is mid-spawn or mid-explosion, then that is a state, and the sentence says so.

**T4 — a term change is retroactive and atomic.** Rename everywhere in one commit: prose, titles, labels, `@equ` names, ref pages, spec. A half-finished rename is worse than the original name. The reader now sees two terms and has to work out whether they are one thing.

**T5 — a term already in the artifact is not evidence for the term.** This is the one the others depend on. A term reaches a later pass by being read off the work: you open a routine, its title and its neighbors supply the vocabulary, and you write with what you found. That feels like T1. It is not. **T1 asks for consistency with the registry, never with whatever the file already says.**

An unregistered term has no standing however often it appears, and the count is an aggravating factor. This is what `comment-style.md` already says about comment forms — "it is the house style" is not a defense — reaching vocabulary.

Reuse also *amplifies*. Sites multiply. The term climbs from prose into the label namespace and from there into everything built from it, so a word becomes a rename. And it accrues authority: the more sites it holds, the more it reads as settled vocabulary, so the less likely the next pass is to question it. Each pass makes the defect larger, costlier and more respectable, and the passes that entrench it are the ones that should have caught it.

**The admission test**, applied once, before a coinage is first used:

1. Does the game name it? Use the game's word.
2. Is the word free in this project?
3. Does the code hold the contrast the word implies?
4. Does it name the thing, or a property you inferred about it?

**The registry is `glossary.ref`, and `make lint-terms` reads it.** Publish the pairs as a `#TABLE` under a `Write | Not` header — the left cell is what to write, the right cell the forms that must not appear — and the check holds every other file to it.

Two limits, stated because a registry that claims more enforcement than it has is worse than none. A row qualified by grammatical role — "zeros **as the verb**" — is not decidable by pattern, so it is counted in the report and left to a hand pass. And the pairs are spellings and synonyms; the entity-level rules T1 to T5 above are the Challenger's, judged by reading.

## How long a description runs

The entry description is the **contract**: what the routine is for, and the one consequence a caller needs. One paragraph. Mechanism goes down a layer, to an `N` note at the instruction it describes.

Measured over the project, not over one entry:

| | bar |
| --- | --- |
| description, median words | 20 or fewer |
| description, p90 | 50 or fewer |

A ceiling on one description is the wrong instrument: a well-written disassembly still has descriptions that run past 50 words. What separates good prose from bad here is the middle of the distribution, not the tail.

## How a sentence reads

**S1 — one idea per sentence.** This is the rule that repairs the prose, it is what the Microsoft and Google style guides both actually say, and it is not mechanically checkable. It is the Challenger's, judged by reading.

**S2 — the project's sentence lengths are gated, not the sentence.**

| | bar |
| --- | --- |
| block prose, median words | 12 or fewer |
| block prose, p90 | 20 or fewer |

**S3 — the long-sentence tail is a report.** Sentences past 30 words are listed to be read, never failed. That is Microsoft's own rule and its own severity: `SentenceLength` is `level: suggestion`, `max: 30`. A hard cap is satisfiable by splicing one long sentence into two badly joined short ones, which is worse prose and a better number.

**S4 — no semicolon joining two clauses, and asides do not stack.** Never two asides in one sentence: no parenthetical inside a parenthetical, no colon and semicolon together.

**S5 — two addresses per sentence at most.** The exception is the stock forms `Used by the routines at …` and `Written by …`, which are a list and read as one.

Those two forms are exempt because **the caller is priced into the description budget, not into a backlink.** SkoolKit generates no "Used by" line. So a description that drops its caller clause drops the caller from the reader's reach on that page — the fact survives only at the call site, on a page this page does not link to. "One home per fact" would permit the call site to be that home, and it is not, because nothing points there. Keep the clause, and do not count it against the sentence budget.

**S6 — a bare `$XXXX` needs a name in the same sentence.** A label, a constant, or what the thing is. The reader came for the name; the address is the citation.

**S7 — no sentence opens on an address, `Slot N`, `Byte` or `Bit`.** Make a thing the subject.

**S8 — three or more items sharing a template are a `#TABLE`.** A record layout, an enum, a dispatch list. Written out as prose it is a table nobody can read.

## A number the player cannot see does not belong in prose

Not a state index, not an object type, not a tile or slot code, not a bit position, not a record offset. Say what happens:

> **Bad:** enters the falling state (state 2) · the bird (type 17) · a solid tile is a wall or a floor (tile codes $10-$1F) · player B's pointer (slot 1)
>
> **Good:** enters the falling state · the bird · a solid tile is a wall or a floor · player B's pointer

The `#R` reference already in the sentence is the reader's way to the encoding. Repeating the code beside the name is noise they did not ask for, and it rots: reassign the codes and every sentence citing one is silently false without a word of it changing.

**Keep a number the player meets, or a port must reproduce.** Scores, lives, speeds, durations, counts of things on screen. The shape tells them apart — an unobservable number is labeled by an *encoding* noun (`state 2`, `type 17`, `slot 1`), a kept one by a *domain* noun (`500 points`, `3 lives`, `250 frames`).

**Four exemptions, all structural.**

*A table row whose number is its key.* `{ $02 | silver key | … }` — strike the code and the row is about no code. This is the row, **not** the block it sits in: "the game font, for character codes $20 to $5A" is prose on a data block and is a citation like any other. Write "space through Z", or nothing, since the block renders the glyphs.

*An `R` line.* A routine's register contract is where it establishes the convention its callers must honor — `I:HL address of the message (a $FF byte ends it)`. The implementer states it once; every caller that repeats it is citing.

*A platform encoding.* ULA bit 4, port `$FE`, an opcode byte. Not this program's to reassign, so no edit can falsify the sentence.

*A Z80 mnemonic.* `BIT 7`, `SET 3`, `RES 0` are instructions that read like codes.

`CODE_ECHO` gates it over every block comment of every block type.

**Every kind of unobservable number is one rule** — type codes, tile ranges and state numbers alike. If a fourth kind turns up, it is this rule, not a new one.

## A thing the reader can see or hear is shown at its own block

The catalog page is an **index**. It exists to show everything at once — every sprite, every frame, every effect, side by side — and that is a different job from documenting one block. Someone following a link to `$A640` lands on a page titled "Player sprite: walking frame" and, if the block renders nothing, reads sixteen rows of hex.

So: **if a block encodes one element the reader can see or hear, that block shows it.** A sprite frame, a font glyph, a tile group, a fragment, a sound effect. One `#UDGARRAY`, `#FONT` or `#AUDIO` line, derived from the same bytes the listing below it already prints. The index still indexes; it is not a substitute.

> **Bad:**
> ```
> ; Player sprite: walking frame
> @label=player_sprite_walk
> b$A640 DEFB $18,$18  ; {Working copy of the walking-frame bitmap, 2 bytes per row.
> ```
>
> **Good:** the same, with `#UDGARRAY2,7,...($A640-$A65E-2)(player_walk)` in the block comment, so the page shows the player.

`UNRENDERED` gates it, and the block's own title decides: a title naming a sprite, bitmap, glyph, font, wordmark, logo or tileset, with no render macro anywhere in the block. A block *about* those things — a sprite pointer table, a glyph-code index, a bank's state flags — names them too and owes no picture, so that vocabulary is excluded.

## A title that lists things is a page that holds things

`validate_ctl_publication.py` already gates one page per thing. A title carrying a comma-separated list is how a page that holds several announces itself:

> Door-lock flags, the ladder-collision results, and the bonus timers

Ask the question the title raises. What do these share, that they are on one page? If the answer is nothing, the page is a bag and the seams are where the title puts its commas — split it. If the answer is that they are *interleaved*, so no address range separates them, say that in the description, because the reader is about to wonder the same thing.

Not every list is a defect. "Missile shot sprites, left and right" is one thing in two mirrored forms. The test is not the comma; it is whether the reader would draw the same boundary.

No check ships. Titles that carry a list are rare, and a legitimate one is as common as a defect, so a pattern here reports one defect for every one it gets wrong.

## An entry stands alone, and is about its own bytes

Two rules the Challenger reads for, because neither is decidable by pattern.

**An entry stands alone.** A reader arrives at a block by following a link, not by scrolling into it, so a sentence that only makes sense after the block above says nothing to the person actually reading it. It takes three shapes.

A *connective* pointing at the previous block: "More of the same leftover", "The stunned player then draws again". The "same" and the "then" name a paragraph that reader never saw.

A *position* standing in for a description: "The page above the sprite bank." Above is an address relation, and the page shows no map — so this locates the block by a neighbor instead of saying what it is. The address is already in the heading. Say what the bytes are and what touches them.

A *description that restates its own title* and adds nothing else. If the title is "Back buffer and work RAM" and the description says where it sits, the entry has one fact in it and has spent a paragraph not saying it.

**An entry is about its own bytes.** A sprite entry owes what the sprite is, the event that draws it, and the routine — not the plumbing by which a pointer comes to hold it. Which slot the handler writes, which field it swaps, what happens to the player afterwards: that is the handler's, and it is already documented there.

> **Bad:** Stunned-player sprite the trap installs into the player's sprite pointer (slot 1) during its hold state (#R$B7E2). The stunned player then draws again.
>
> **Good:** The player while the trap holds it, drawn through its hold state (#R$B7E2).

The good form names the object and the frame: "Trap release frame 1 (state 4); stepped by #R$B7E2."

**Why no check.** Both shapes fail the bar. The back-reference — a sentence opening on "then", "also", "the same" — is almost always a routine referring to its own previous sentence, which is correct. The plumbing shape, scoped to catalog entries that render, is rare, and its hits include legitimate ones. A pattern narrowed until it catches the known instance is the keyed match this skill rejects elsewhere; the precision is what decides, and here it decides against.

## A rendered thing is not described in words

Where the page renders the artifact — an `#AUDIO` clip, a `#UDGARRAY` sprite, a `#FRAMES` animation — the render *is* the description. Prose beside it that says what the picture looks like, or what the sound sounds like, is the author doing by hand and badly the job the device does exactly.

For sound this has a second, sharper form: **prose that says how the tone is produced.** Frame counts, cycle counts, T-states, a period computed from a counter. That is the synthesis, and the clip *is* the synthesis. Writing it out is the same defect as listing the notes.

> **Bad:** 7 frames of 12 cycles each, with the period computed as 2*counter + 10 and held flat within each frame.
>
> **Good:** The chime a key makes as the player picks it up. Played by #R$6E90 when the key is taken.

An entry beside a clip owes three things: **what the sound means in play, the event that fires it, and the routine.** Nothing else. If that leaves the entry short, the entry is finished — it was never missing a paragraph about periods.

The production method is not deleted, it is *placed*. The algorithm belongs in the routine's body, at the instructions that implement it, where a reader is reading code. The period formula belongs once, at the tone primitive that computes it, because every effect shares it. Both are "one home per fact"; the catalog is not that home.

`SYNTH_ECHO` gates this, and it decides by location rather than by reading: synthesis vocabulary in block prose or a `.ref` section that carries an `#AUDIO`. Instruction comments are never reported — the body is exactly where the algorithm should be.

## Unused bytes owe one line

A block nothing uses has one fact: it is unused. Write that, and stop.

If something about it is genuinely worth knowing, that is welcome and it is one sentence — the bytes decode to a message the programmer left, the block pads an alignment the next table needs, the values are the loader's leftovers from the BASIC area. Trivia is content. A reader enjoys it.

What an unused block never owes is **the proof that it is unused**. No census of which routines do not read it. No account of which fill stops short of it. No note on why no stride could be found. That is the author's working-out, and the reader did not come for it.

> **Bad:** Undetermined zero-fill tail of the state block before the sprite bank; no reader found, and the only writer is the level-setup clear, whose fill stops seven bytes in.
>
> **Bad:** Nothing in the image reads these bytes, and the values vary from one to the next, so nothing fixes a stride: the size is the whole claim, and the listing shows the bytes.
>
> **Good:** Unused.
>
> **Good:** Unused. The loader's leftovers from the old BASIC area, kept because the image runs contiguously into the level table.

`EULOGY` gates it at a couple of dozen words over the block comment and its gutter together. A cap is the right instrument here, and only here: the content of an unused block is bounded by what exists to say, which is one fact and perhaps one more. Everywhere else the bar is a distribution, for the reason under "How a sentence reads".

**Type it `u`, not `s`.** `s` asserts the game fills the block at runtime, and `ctl-authoring.md` rightly makes that claim cost a named writer. A block nothing writes is not a buffer — it is unused, and typing it `s` buys an exemption from this rule by making a claim about the game that is not true.

## What the prose never does

- **Claim what the original author intended.** Say what the code does. An inference is marked as one, in the reader's own words.
- **Narrate the investigation.** Already `comment-style.md`'s rule; the checker reads it over the `.ref` pages and the spec too.

## What the prose is allowed to do, and should

Ask a question. The question/answer pair over a test and its branch is the house form. Say plainly where you do not follow the original author. Naming the thing you cannot explain is worth more than a paragraph of derivation that cannot be checked.

## What runs

- **`make lint-prose`** — Vale, carrying the Microsoft style plus the rules above that a regex can decide. Errors fail; warnings and suggestions report. Setup and the filter are in `build-verify.md`.
- **`make lint-comments`** — the checks that need the listing rather than the sentence.
- **`make coverage`** — counts what the two of them found, and is where "done" is decided.

## Done

A project is not done while `make coverage` reports a prose gap. That is not advice about polish. It is the same kind of bar as a bare basic block: a disassembly whose prose is unread-able is not a finished disassembly, however green its round-trip.
