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

**The registry is `glossary.ref`.** Each `[Term:…]` declares the canonical term and the variants that must not appear. That file is not a prose page; it is what the checker reads.

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

**S6 — a bare `$XXXX` needs a name in the same sentence.** A label, a constant, or what the thing is. The reader came for the name; the address is the citation.

**S7 — no sentence opens on an address, `Slot N`, `Byte` or `Bit`.** Make a thing the subject.

**S8 — three or more items sharing a template are a `#TABLE`.** A record layout, an enum, a dispatch list. Written out as prose it is a table nobody can read.

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
