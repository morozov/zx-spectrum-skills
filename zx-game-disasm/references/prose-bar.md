# The prose bar

Commentary. The rules are in `rules.md`. Where this file differs, `rules.md` holds.

`comment-style.md` says what a comment is *for*. This says how well it has to be written, and gives the figures the prose bar holds a project to. The rules and their enforcers are in `rules.md`. The reasons some rules have no check are in `rationale.md`.

## Who the prose is for

A person who likes this game and wants to know how it worked. They read pages, and they read them in the game's terms (AUD-1). Write for them.

Two other readers exist and neither sets the register. A porter needs the format tables, and gets them from the same document. An agent-trainer needs the state addresses, and gets them from the behavior specification, which is written for them. Writing for either of those two produces exhaustive text nobody reads, because every rule written for a reader who greps can only ask for more.

## One term per thing

**T1 — one name per entity.** Every reference to the same thing uses the same words. That holds across the `.skool`, the `.ctl`, every `.ref` page, the spec, the entry titles, and the labels. A spelling variant is the same violation as a synonym.

**T2 — one meaning per name.** A word already used for one thing cannot name a second. If two things want the same obvious word, one of them gets another word.

**T3 — a coined term must not assert a classification the game does not have.** A qualifier implies a contrast set. Name the set, or drop the qualifier. "A solid object" claims there are non-solid ones; if what the code holds is an object that is mid-spawn or mid-explosion, then that is a state, and the sentence says so.

**T4 — a term change is retroactive and atomic.** Rename everywhere in one commit: prose, titles, labels, `@equ` names, ref pages, spec. A half-finished rename is worse than the original name. The reader now sees two terms and has to work out whether they are one thing.

**T5 – a term earns its standing from the registry.** This is the one the others depend on. A term reaches a later pass by being read off the work: you open a routine, its title and its neighbors supply the vocabulary, and you write with what you found. **T1 asks for consistency with the registry.** Whatever the file already says carries no weight of its own.

An unregistered term has no standing however often it appears, and the count is an aggravating factor. This is what `comment-style.md` already says about comment forms — "it is the house style" is not a defense — reaching vocabulary.

Reuse also *amplifies*. Sites multiply. The term climbs from prose into the label namespace and from there into everything built from it, so a word becomes a rename. And it accrues authority: the more sites it holds, the more it reads as settled vocabulary, so the less likely the next pass is to question it. Each pass makes the defect larger, costlier and more respectable, and the passes that entrench it are the ones that should have caught it.

**The admission test**, applied once, before a coinage is first used:

1. Does the game name it? Use the game's word.
2. Is the word free in this project?
3. Does the code hold the contrast the word implies?
4. Does it name the thing, or a property you inferred about it?

**The registry is `glossary.ref`, and `make lint-terms` reads it.** Publish the pairs as a `#TABLE` under a `Write | Not` header — the left cell is what to write, the right cell the forms that must not appear — and the check holds every other file to it, labels included. A rename lands its registry row in the same commit, so the gate fails until every mention has changed (NAME-2).

A row qualified by grammatical role – "zeros **as the verb**" – is not decidable by pattern, so it is counted in the report and left to a hand pass. The entity-level rules T1 to T5 are NAME-1 to NAME-4 in `rules.md`.

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

**S5 – two addresses per sentence at most.** A sentence that names a third reads as a list. Split it.

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

*A `.ref` `#TABLE` column that holds the code.* A catalog table may give the code a column of its own, beside the name and the render (ROW-7). A listing row never carries its code (ROW-1), and prose on a data block is a citation like any other: "the game font, for character codes $20 to $5A" is written "space through Z", or left out, since the block renders the glyphs.

*An `R` line.* A routine's register contract is where it establishes the convention its callers must honor — `I:HL address of the message (a $FF byte ends it)`. The implementer states it once; every caller that repeats it is citing.

*A platform encoding.* ULA bit 4, port `$FE`, an opcode byte. Not this program's to reassign, so no edit can falsify the sentence.

*A Z80 mnemonic.* `BIT 7`, `SET 3`, `RES 0` are instructions that read like codes.

This is AUD-4. Any kind of unobservable number is this one rule.

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
> **Good:** the same, with the row comment gone and an `N` note on the block, `N $A640 #UDGTABLE { #UDGARRAY2,7,...($A640-$A65E-2)(player_walk) } TABLE#`, so the page shows the player.

The block's own title decides (GFX-3): a title naming a sprite, bitmap, glyph, font, wordmark, logo or tileset owes a render macro in the block. A block *about* those things – a sprite pointer table, a glyph-code index, a bank's state flags – names them too and owes no picture.

## A title that lists things is a page that holds things

`validate_ctl_publication.py` already gates one page per thing. A title carrying a comma-separated list is how a page that holds several announces itself:

> Door-lock flags, the ladder-collision results, and the bonus timers

Ask the question the title raises. What do these share, that they are on one page? If the answer is nothing, the page is a bag and the seams are where the title puts its commas — split it. If the answer is that they are *interleaved*, so no address range separates them, say that in the description, because the reader is about to wonder the same thing.

Some lists are one thing. "Missile shot sprites, left and right" is one thing in two mirrored forms. The test is whether the reader would draw the same boundary (HEAD-3).

## An entry stands alone, and is about its own bytes

**An entry stands alone** (HOME-8). A reader arrives at a block by following a link and has not read the block above it, so a sentence that only makes sense after that block says nothing to the person actually reading it. It takes three shapes.

A *connective* pointing at the previous block: "More of the same leftover", "The stunned player then draws again". The "same" and the "then" name a paragraph that reader never saw.

A *position* standing in for a description: "The page above the sprite bank." Above is an address relation, and the page shows no map — so this locates the block by a neighbor instead of saying what it is. The address is already in the heading. Say what the bytes are.

A *description that restates its own title* and adds nothing else. If the title is "Back buffer and work RAM" and the description says where it sits, the entry has one fact in it and has spent a paragraph not saying it.

**An entry is about its own bytes** (HOME-2). A sprite entry owes what the sprite is, the event that draws it, and the routine — not the plumbing by which a pointer comes to hold it. Which slot the handler writes, which field it swaps, what happens to the player afterwards: that is the handler's, and it is already documented there.

> **Bad:** Stunned-player sprite the trap installs into the player's sprite pointer (slot 1) during its hold state (#R$B7E2). The stunned player then draws again.
>
> **Good:** The player while the trap holds it, drawn through its hold state (#R$B7E2)

A frame caption names the object and the mode it is drawn in, and nothing about how the code switches to it (GFX-7): `Trap releasing the player, frame 1`.

Nothing in a project states its callers (HOME-4): no `Used by #FOREACH(EREF…)` note, no "called by" or "dispatched by" clause in a description, and no generated line. `skoolkit.ini` sets `ListRefs=0`, so `sna2skool` writes neither the entry-level "Used by" nor the "This entry point is used by …" line at an entry point. A routine can have any number of callers, the list is not what the page is about, and the toolchain tracks the references anyway. What a routine does at its callers' request is its own description. A variable's entry does not list its writers or readers either: what a routine does to the variable is said at the routine.

## A rendered thing is not described in words

Where the page renders the artifact — an `#AUDIO` clip, a `#UDGARRAY` sprite, a `#FRAMES` animation — the render *is* the description. Prose beside it that says what the picture looks like, or what the sound sounds like, is the author doing by hand and badly the job the device does exactly.

For sound this has a second, sharper form: **prose that says how the tone is produced.** Frame counts, cycle counts, T-states, a period computed from a counter. That is the synthesis, and the clip *is* the synthesis. Writing it out is the same defect as listing the notes.

> **Bad:** 7 frames of 12 cycles each, with the period computed as 2*counter + 10 and held flat within each frame.
>
> **Good:** The chime a key makes as the player picks it up. Played by #R$6E90 when the key is taken.

An entry beside a clip owes three things: **what the sound means in play, the event that fires it, and the routine.** Nothing else. If that leaves the entry short, the entry is finished — it was never missing a paragraph about periods.

The production method is not deleted, it is *placed*. The algorithm belongs in the routine's body, at the instructions that implement it, where a reader is reading code. The period formula belongs once, at the tone primitive that computes it, because every effect shares it. Both are "one home per fact"; the catalog is not that home.

This is HOME-7. It reaches block prose and any `.ref` section that carries an `#AUDIO`. Instruction comments are where the algorithm belongs.

## Unused bytes say nothing

A block nothing uses has one fact: it is unused. The entry type `u` and the title "Unused bytes" say it, and the entry carries no description and no row comments (UNU-1). One unused byte inside a used table keeps the row comment `Unused`, because there the row is the only place that says so.

An unused block owes no proof that it is unused, no reason, no neighbors and no guessed purpose (UNU-3). No census of which routines do not read it, no account of which fill stops short of it, no note on why no stride could be found. That is the author's working-out. The test: move the bytes somewhere else, and the title must still be true. When the bytes decode to something – a message, a sprite, a table – the entry is that thing, described as such.

> **Bad:** Undetermined zero-fill tail of the state block before the sprite bank; no reader found, and the only writer is the level-setup clear, whose fill stops seven bytes in.
>
> **Bad:** Nothing in the image reads these bytes, and the values vary from one to the next, so nothing fixes a stride: the size is the whole claim, and the listing shows the bytes.
>
> **Good:** `u $B3F0 Unused bytes`, with no description and no row comments.

Unused bytes carry no label that names a used thing (UNU-2), and they have no layout: a check that asks them for a stride, a tiling, a type or a description is a check to fix (WORK-2).

**Type it `u`.** `s` asserts the game fills the block at runtime, and `ctl-authoring.md` makes that claim cost a named writer. A block nothing writes is unused, and typing it `s` makes a claim about the game that is false.

## What the prose never does

- **Claim what the original author intended.** Say what the code does. An inference is marked as one, in the reader's own words.
- **Narrate the investigation** (AUD-2), on any page the reader opens.

## What the prose is allowed to do, and should

Ask a question. The question/answer pair over a test and its branch is the house form. Say plainly where you do not follow the original author. Naming the thing you cannot explain is worth more than a paragraph of derivation that cannot be checked.

## What runs

- **`make lint-prose`** – Vale, carrying the Microsoft style and the ZXDisasm rules. Errors fail, and warnings and suggestions report. Setup and the filter are in `build-verify.md`.
- **`make lint-comments`** — the checks that need the listing rather than the sentence.
- **`make coverage`** — counts what the two of them found, and is where "done" is decided.

## Done

A project is done only when `make coverage` reports no prose gap. That is the same kind of bar as a bare basic block: a disassembly whose prose cannot be read is unfinished, however green its round-trip.
