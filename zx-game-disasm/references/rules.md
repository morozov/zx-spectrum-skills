# Rules

This file is the skill's one normative rulebook. Every other reference is commentary: it explains and gives worked examples, and where it differs from this file, this file holds.

Read it in full, from the first line to the last, before the first edit of a session, and again after any owner call-out.

Each rule is a testable statement with an ID and an enforcer. Enforcers are named as follows:

- An upper-case name is a check kind, reported by the linters under that name.
- `lint-…` is a make target of the mechanical gate.
- `review-record` is the review record the Challenger writes and the commit hook reads.
- `review` is the Challenger, who answers every rule ID in this file on every diff. The Question column holds the yes/no question it asks of one unit, answered yes when the unit breaks the rule.

A rule with only `review` as its enforcer holds exactly as hard as one with a check. The mechanical gate passing says nothing about it.

"Reader-facing text" means every surface a reader of the site meets: entry titles, descriptions, notes, row comments, register rows, `.ref` pages and table cells, glossary terms, and `spec/*.md`.

## AUD: the reader and the register

| ID | Rule | Enforcer | Question |
| --- | --- | --- | --- |
| AUD-1 | Reader-facing text names things in the game's terms, for a person who likes the game and reads pages, and says what a thing is, not where its bytes sit. A listing entry whose subject is storage itself (a slot bank, a buffer, a table) names that storage. | HEADING_JARGON, review | Does this unit name or describe something in storage or listing vocabulary (addresses, records, bytes, pointers, slots, tables, buffers) where the game or the glossary has a word for it, when the unit's subject is not that storage itself? |
| AUD-2 | Persisted text states current fact and records nothing about who asked, what happened before, or how a fact was found. | DIARY, review | Does this unit record who asked for something, what an earlier version said, or how a fact was found? |
| AUD-3 | A sentence states what a thing is or does, and argues with no reading nobody offered. A defect statement may name the faulty behavior beside the intended one. | FOIL, review | Does this unit argue against a reading nobody offered, in the shape "X, not Y", "rather than" or "instead of", outside a statement of a defect? |
| AUD-4 | A name in reader-facing text is followed by no number the player cannot see: no state, type, slot, tile code, class, bit or record offset. | CODE_PAREN, CODE_ECHO, LAYOUT_ECHO, review | Does this unit put a code, a state number, a type number, a slot, a bit or an offset beside the name of a thing? |
| AUD-5 | Deterministic behavior is stated without frequency or probability words, and genuinely random behavior names its random source. | review | Does this unit describe deterministic behavior with "often", "usually", "chance", "%", "odds" or a similar frequency word? |
| AUD-6 | Reader-facing text says what the code does and claims nothing about the original author's intent unless it marks the claim as an inference. | review | Does this unit state what the original author intended as a fact? |
| AUD-7 | Uncertainty is typed at the claim with a trailing `?`, a `TODO:` line or `(unverified)`, and each marker carries an open dig-task. Prose hedges are absent. | DIARY, OPEN, review | Does this unit hedge with "apparently", "likely", "seems", "probably" or a similar word in place of a typed marker? |
| AUD-9 | Reader-facing text mentions no port or rebuild of the game, and no sentence justifies itself by what a reader might build from it. | review | Does this unit mention porting or rebuilding the game, or justify itself by what such a project would need? |

## EVID: evidence

| ID | Rule | Enforcer | Question |
| --- | --- | --- | --- |
| EVID-1 | Every behavior and defect is documented from the code, and no reader-facing text cites a run, a recording or an emulator. | DIARY, review | Does this unit rest a claim on a run, a recording, an emulator or an observation in play? |
| EVID-2 | A claim the code cannot settle is stated as a condition. | review | Does this unit state as fact something the code cannot settle? |
| EVID-3 | A color in reader-facing text is the attribute value the draw code writes, traced to that code. | review | |
| EVID-4 | A number stated in player units (points, lives, seconds, Hz) is traced through the routine that displays or produces it. | review | |
| EVID-5 | A census of an address's writers covers the region: literal stores, `LDIR` destinations whose span reaches it, `IX`/`IY` bases within 128 bytes below it, and pointer seeds whose walk reaches it, each seed followed to every store it reaches. | review | |
| EVID-6 | A report of writers or readers reads "the writers found are X and Y", and claims no completeness the census did not establish. | review | |
| EVID-7 | A correction to a field names the operand it was read from. | review | |
| EVID-8 | An answer to "are you sure?" states exactly which bytes, slots or addresses the claim covers and what the image holds there. | review | |
| EVID-9 | Grouping, animation boundaries and identity come from the frame table and the handler's code. | review | |
| EVID-10 | A relocatability claim is made only after the program has been moved and run. | review | |

## HOME: one home per fact

| ID | Rule | Enforcer | Question |
| --- | --- | --- | --- |
| HOME-1 | A fact is stated once, at the entry it describes, and every other page links there. | review | Does this unit restate a fact that belongs to another entry or page, where a link would do? |
| HOME-2 | An entry's page describes only that entry. About any other entry it says at most which routine fills it. | DEIXIS, FOREIGN_LOGIC, review | Does this unit describe what another routine does, computes or relies on? |
| HOME-3 | Prose restates no game data: no lists of the levels that hold something, no counts per value, no claims about what no layout holds, no per-level cell counts. | NUMBER_LIST, CODE_LIST, LEVEL_FACT, review | Does this unit list, count or summarize values that the game's data tables already show? |
| HOME-4 | No entry lists the code that calls, reads or writes it. An `s` entry names the code that fills it, and `ListRefs` stays 0. | CALLERS, review | Does this unit list routines that call, read, write, set, clear or use the thing it describes? |
| HOME-5 | A comment repeats nothing its own row shows: no label words, no bytes, no index, no value in another base. | OPERAND_ECHO, DATA_ECHO, LABEL_ECHO, BASE_ECHO | |
| HOME-6 | A comment recites no span length the listing carries. A rate such as "9 bytes per slot" is allowed. | BYTE_SPAN | |
| HOME-7 | A picture or a sound is described in the game's units only: what it is, the event that draws or plays it, and the routine. This holds whether or not the page renders or plays it. | SYNTH_ECHO, PITCH, review | Does this unit describe what a picture shows, such as its shapes or the words on it, or a sound's pitch, contour or synthesis? |
| HOME-8 | An entry stands alone: its text reads true to a reader who arrived by a link. | DEIXIS, review | Does this unit lean on a neighboring entry with "the same", "then", "above", "below" or a position? |
| HOME-9 | A sentence that stays true when its addresses are swapped into a sibling's entry is written once, at the family head. | review | Would this sentence stay true word for word on a sibling entry of the same family? |
| HOME-10 | A link note, intro, caption or heading carries no count of what a list or page holds. | HEADING_JARGON, review | Does this unit count the items of a list, page or table? |
| HOME-11 | A routine's title and description carry the size of what it processes only when its behavior changes with that size. | review | Does this routine title or description state the size of the data it processes? |
| HOME-12 | Before an encoding is cut from a caller's comment, the variable's own entry states it. | review | |
| HOME-13 | Reader-facing text describes the program, and nothing about how its image was acquired: a distribution tape's blocks, its loader and how they are decoded live in the build files that load them (`.t2s`, `Makefile`). Code inside the image that loads data is the program, and is described. | review | Does this unit describe a distribution tape's blocks, its loader, or how the program's image was loaded or decoded from it? |
| HOME-14 | A defect's name says what goes wrong for the player, not how the code gets there. Its entry says what the player sees, what sets it off and why it lasts, in at most three short paragraphs, with the routine at fault linked. It carries no subsections, no RAM table, no step-by-step walk of the code and no fix. A fact several defects share is stated once, above them. | review | Does this defect title name the code's mechanism in place of what goes wrong for the player, or does this defect description walk the code step by step, list the state it leaves in memory, or propose a fix? |

## DEF: definitions of variables, tables and glossary terms

| ID | Rule | Enforcer | Question |
| --- | --- | --- | --- |
| DEF-1 | A definition says what the thing holds and how it is encoded: meaning, units, range and special values. | NON_ZERO, review | Does this definition say something other than what the thing holds and how it is encoded? |
| DEF-2 | A definition carries no logic that changes the value: no reset, wrap, increment, decrement or clear. | GLOSSARY_DEF, review | Does this definition say what changes, resets, wraps or clears the value? |
| DEF-3 | A definition carries no usage: nothing about what reads the value or what it selects. | GLOSSARY_DEF, review | Does this definition say what reads the value, what uses it or what it selects? |
| DEF-4 | A definition is true at power-on and carries no progress framing. | GLOSSARY_DEF, review | Does this definition describe the player's progress or a state that holds only during play? |
| DEF-5 | A one-byte variable's description is one sentence. | WORDY_VARIABLE | |
| DEF-6 | A glossary term is admitted only when the game or the project coined it and its name does not say what it is. Plain words and constants are never glossary entries. | GLOSSARY_IDENT, review | Is this glossary term a plain word whose name says what it is, or a constant? |

## ROW: data rows and tables

| ID | Rule | Enforcer | Question |
| --- | --- | --- | --- |
| ROW-1 | A data row's comment says what the row holds, opens on no index ("Code $12:", "Tile $21", "Type 3:") and quotes none of its own bytes. | DATA_ECHO, CODE_ECHO | |
| ROW-2 | The key a table is indexed by is stated once, in the block description. | review | Does this row comment or table cell restate the key the table is indexed by? |
| ROW-3 | A row comment names no code range. | DATA_ECHO, CODE_PAREN | |
| ROW-4 | Sub-blocks follow the record: one sub-block per record of the structure the code indexes. | ROW_WIDTH, review | |
| ROW-5 | A data run is 8 bytes per row unless the record the code indexes sets another stride. | ROW_WIDTH, STRIDE_APPEASE (advisory), review | |
| ROW-6 | A row whose only content would be its index has no comment, and the block's `N` note renders the thing. | DATA_ECHO, review | |
| ROW-7 | In a `.ref` `#TABLE`, a code appears only in a column of its own. | review | Does this table cell put a code beside a name in the same cell? |
| ROW-8 | A sentence about a whole run sits in the entry description, and a row comment describes only its own row. | review | Does this row comment describe the whole run or block in place of its own row? |
| ROW-9 | An array of records names or renders each record on its own line, by what the record holds. | lint-array-elements, review | |
| ROW-10 | A table the code reads as words, such as addresses, is typed `W`. Typed as bytes or as text cut into pairs, it renders as numbers or letters. | POINTER | |

## UNU: unused bytes

| ID | Rule | Enforcer | Question |
| --- | --- | --- | --- |
| UNU-1 | Unused bytes are typed `u`, titled "Unused bytes", and carry no description and no row comments. One unused byte inside a used table keeps the row comment `Unused`. | UNUSED_TEXT, lint-publication | |
| UNU-2 | Unused bytes carry no label that names a used thing. | UNUSED_LABEL | |
| UNU-3 | Unused bytes get no reason, no neighbors and no guessed purpose. Bytes that decode to something are described by what they decode to. | UNUSED_TEXT, review | Does this unit explain why bytes are unused, describe their neighbors or guess their purpose? |

## ENT: entries

| ID | Rule | Enforcer | Question |
| --- | --- | --- | --- |
| ENT-1 | Every entry has a title, and every sub-directive carries a description or a label. | lint-identity | |
| ENT-2 | One structure is one entry, an entry holds one kind of thing, and its type is what its bytes are. | lint-publication | |
| ENT-3 | Strings that are parts of one message are one entry with one line per string. | review | |
| ENT-4 | A multi-byte data entry states its schema: stride, each field's meaning, the count and any sentinel. | lint-data-structure, review | |
| ENT-5 | An `s` entry names the code that fills it. Bytes nothing writes are `u`, and bytes that execute are `c`. | review | |
| ENT-6 | A routine description states the contract (purpose, inputs, outputs, side effects) in at most two sentences, unless it buys a table, a format or a state machine. | review | Does this routine description walk the mechanism, preview the call sequence, or run past two sentences without buying a table, a format or a state machine? |
| ENT-7 | Every basic block of a routine carries a comment, and a bare `RET` or a call to a well-named routine carries none. | RET_GROUP, review | |
| ENT-8 | A comment group covers one act: it spans no unconditional transfer, is entered only at its first row, and skips none of its own rows. | GROUP_SPLIT, GROUP_ENTRY, GROUP_SKIP, review | |
| ENT-9 | The `.ctl` writes every address as `$`-hex, in block addresses and `#R` references alike. | review | |
| ENT-10 | A `D`, `R` or `E` directive sits at an entry's own address. Prose inside a block is an `N` or a row comment. | lint-instruction-order | |

## GFX: graphics and fonts

| ID | Rule | Enforcer | Question |
| --- | --- | --- | --- |
| GFX-1 | Ordinary characters of a font carry no comments. | review | |
| GFX-2 | A font cell that draws something other than its character is rendered, named, and says which character it replaces. | review | |
| GFX-3 | Every block named as a sprite or a glyph renders it, at every address that holds the bitmap. | UNRENDERED, review | |
| GFX-4 | Sprite, glyph and bitmap data carries no per-row comments and no pixel legend. | review | |
| GFX-5 | Data is written in the default radix. | review | |
| GFX-6 | Every published picture is composed as the game draws it. | review | |
| GFX-7 | A sprite or frame caption names what it depicts and the mode it is drawn in, and says nothing about how the code switches to it. | review | Does this caption say how or when the code switches to the frame, sets the pointer or advances the animation? |
| GFX-8 | An animation has one lead note, and each frame note adds only what that frame depicts. | review | Does this frame note restate the animation's lead note? |
| GFX-9 | A thing is named for the glyph the player sees, its letter is read from how the game draws it, and its effect is read from the code. | review | |

## REG: register rows

| ID | Rule | Enforcer | Question |
| --- | --- | --- | --- |
| REG-1 | One `R` row names one register. | lint-registers | |
| REG-2 | A register row is a lower-case noun phrase with no final full stop that says what the register holds, with the encoding or limit that matters. | lint-registers | |
| REG-3 | A routine that takes a value in a register, or hands one back, has an `R` row for it, and its prose describes no register. | review | Does this description or note describe a register's input or output in prose? |
| REG-4 | An `R` row states a contract that the caller deliberately sets or uses, confirmed at the call sites. | review | |

## NAME: names, terms and labels

| ID | Rule | Enforcer | Question |
| --- | --- | --- | --- |
| NAME-1 | A thing has one name across labels, titles, descriptions, rows, `.ref` pages and the glossary. | lint-terms, TERM_LABEL, review | Does this unit name a thing by a word other than the one the rest of the project and the registry use? |
| NAME-2 | A rename or reclassification changes every mention of the thing, labels included, in one commit. The registry gets a row only when the old name is a synonym the project never uses for that thing, never for a word with a meaning of its own. | TERM_LABEL, lint-terms, review | Does this unit still call the renamed thing by its old name? |
| NAME-3 | A new term passes the admission test: the game's word first, a word free in the project, a contrast the code holds, and a name for the thing itself. | review | Does this unit introduce a term that is not the game's own word or that implies a contrast the code does not hold? |
| NAME-4 | A name asserts no classification the game lacks. | review | Does this unit classify things (as enemies, solid, hostile, active) in a way the code does not? |
| NAME-6 | Titles and prose name a thing in words and contain no constant's identifier. | IDENT_IN_PROSE, GLOSSARY_IDENT | |
| NAME-7 | A family has one prefix and one naming scheme, every member carries it, and its sibling families are checked in the same pass. | LABEL_PAIR, review | |
| NAME-8 | Text about a pickup names the pickup. Its glyph or container is named only where the text is about the picture or the tile, and a container before its reveal is a container, not a pickup. A pickup name is never an adjective for what it produced. | review | Does this unit name a pickup's glyph or container where it means the pickup, call an unrevealed container a pickup, or use a pickup name as an adjective for what the pickup produced? |
| NAME-9 | A name claims the nature its data has. | review | |
| NAME-10 | Prose names a member of a labeled slot family by its label and uses no positional word for it. | lint-names, review | |
| NAME-11 | Link anchors use dashes. | review | |
| NAME-12 | Frame numbers in labels, image names and captions are 1-based. A two-state sprite is named by its states. "Frame" names an animation frame. A state's name comes from the handler that owns the state, and the listing and the `.ref` pages use the same word for it. | review | |

## HEAD: titles and headings

| ID | Rule | Enforcer | Question |
| --- | --- | --- | --- |
| HEAD-1 | A title says what the entry is. | lint-identity, review | Does this title fail to say what the entry is? |
| HEAD-2 | A page heading names what the reader browses, in the game's terms, with no storage vocabulary and no count. | HEADING_JARGON, review | Does this heading use storage vocabulary or count its contents? |
| HEAD-3 | A title holds one thing, unless its list names one thing in mirrored forms. | review | Does this title list several things that share nothing but a page? |
| HEAD-4 | A caveat never titles an entry whose body derives the mechanism. | review | Does this title announce a doubt that the entry's own body resolves? |

## PROSE: sentences

| ID | Rule | Enforcer | Question |
| --- | --- | --- | --- |
| PROSE-1 | A description is sentences a person reads aloud, with no formulas, shift or mask notation, primed variables or code arithmetic. | review | Does this description contain a formula, shift or mask notation, or arithmetic written as code? |
| PROSE-2 | A description says what the routine does, and the instruction comments say how. | review | Does this description walk the steps the instructions take? |
| PROSE-3 | A sentence carries one idea, joins no two clauses with a semicolon, and stacks no asides. | review | Does this sentence carry two ideas, join clauses with a semicolon, or nest one aside inside another? |
| PROSE-4 | A bare `$XXXX` has a name in the same sentence, and no sentence opens on an address, `Slot N`, `Byte` or `Bit`. | review | Does this sentence open on an address, a slot number, "Byte" or "Bit", or carry a bare address with no name? |
| PROSE-5 | Three or more items sharing a template are a `#TABLE`. | review | Does this unit list three or more items in one template as running prose? |
| PROSE-6 | Prose uses noun phrases, with labels only in operands and `R` rows, and never writes `label (#R$addr)` for one symbol. | IDENT_IN_PROSE, SELFLINK, review | Does this unit use a label or identifier as a noun in a sentence, or write a label beside its own link? |
| PROSE-7 | A comment refers to code and data by `#R` or by label and contains no raw address. | review | |
| PROSE-8 | Each comment unit is complete on its own, and no sentence runs across two units. | SPLICE, ELLIPSIS, review | Does this unit finish a sentence that the unit above it left open, or leave one open for the unit below? |
| PROSE-9 | A value and its meaning are joined by a word: "0 for lift A, 1 for lift B", "1 if the key is held". | BARE_VALUE | |

## TYPO: typography

| ID | Rule | Enforcer | Question |
| --- | --- | --- | --- |
| TYPO-1 | A full stop ends a sentence. A noun-phrase row, caption, title or table cell takes none. | FRAGMENT_STOP, review | Does this unit end a noun phrase with a full stop? |
| TYPO-2 | Prose uses × for dimensions (`8×8`) and products (`row × 32`), − for minus, → for arrows, ≥ ≤ ≠ for comparisons, ° for angles, ♭ and ♯ for notes, an en dash for ranges and a spaced en dash for a parenthetical dash. Quoted game text and macro parameters keep their bytes. | TYPOGRAPHY | |
| TYPO-3 | Hex in prose has two or four digits. | review | |

## STE: Simplified Technical English

The writing rules of ASD-STE100, the controlled language of technical documentation. Its dictionary is not adopted. The terminology registry holds the project's words, and a word of a label or of a glossary term is a technical name.

| ID | Rule | Enforcer | Question |
| --- | --- | --- | --- |
| STE-1 | A sentence holds at most 25 words. | STE_LENGTH | |
| STE-2 | A verb is in the active voice. | review | Does this unit use the passive voice where an active verb with a stated actor would say the same thing? |
| STE-3 | A verb is in the simple present, the simple past or the simple future tense. | review | Does this unit use a progressive, perfect or other compound tense? |
| STE-4 | No -ing form appears, except in a technical name. | STE_ING | |
| STE-5 | A noun cluster holds at most three nouns. | review | Does this unit stack four or more nouns in a row? |
| STE-6 | A paragraph holds at most six sentences. | STE_PARAGRAPH | |

## VIS: renders, layout and color

| ID | Rule | Enforcer | Question |
| --- | --- | --- | --- |
| VIS-1 | A render sits in a block-level `N` note or page block (`#UDGTABLE`), and never inside a description sentence, a row comment or a running paragraph. | INLINE_RENDER, review | |
| VIS-2 | Every color has a stated role, one role per token, the palette includes the game's own attribute colors, and no color is assigned by section position. | review | |
| VIS-3 | Headings and blocks on a page share the content column's edges, and a heading fits on one line. When lines run long, the column width changes; a width cap on prose alone is never the fix. | HEADING_WRAP, review | |
| VIS-4 | Explanatory text under a heading is a paragraph element, present because of its content. | review | |
| VIS-5 | The listing's comment column is part of the listing table, with no box, border or background break of its own. | review | |
| VIS-6 | A visual change is accepted only on rendered screenshots of every affected page kind, read back by the reviewer. | review-record, review | |
| VIS-8 | A built site fetches nothing, and every font it names is shipped beside it or present on the reader's platform. | review | |
| VIS-9 | The listing's code rows keep one even pitch, and a comment's length never changes the code rows' spacing. | review | |
| VIS-10 | Design work runs in four steps: specialists name each problem with its root cause and a prescribed fix; an independent challenger with no stake in the proposal reviews each prescription; only what passes is implemented, exactly as prescribed; then the result is rendered and reviewed. | review | |
| VIS-11 | A page that lists entries orders them in a way the reader can name. Things the game shows go in the order the game presents them, such as inhabitants by the level they first appear on. Sounds go by when a game plays them, with entries of one kind kept together, such as the title and game-over tunes. Any other list follows an order with a meaning to the reader, such as defects by what they cost the player. A list with no such order, such as a glossary, is alphabetical. Address order belongs to the memory maps alone. | review | |

## WORK: how to work

| ID | Rule | Enforcer | Question |
| --- | --- | --- | --- |
| WORK-1 | An edit touches only what the request names. A sweep covers mentions of the named thing and siblings that pass the stated test entry by entry. | DELETION_SCOPE, review-record, review | |
| WORK-2 | When a check fires on content the rules call correct, the check is fixed with a fixture, and content is never reshaped, padded or retyped to quiet a check. | STRIDE_APPEASE (advisory), review-record, review | |
| WORK-4 | No diff of any file type is committed or reported done without a Challenger verdict on that exact diff, whatever the mechanical gate says. | review-record | |
| WORK-6 | A commit happens only once the review record matches the staged diff. | review-record, review | |
| WORK-7 | A call-out is fixed as a class through the call-out protocol below. | review | |
| WORK-8 | A working file is never swapped to test another version. Another revision is tested in a worktree under `build/`, as `make gate-index` does. | review | |
| WORK-9 | A call-out is a defect to fix, and the fix is decided from the evidence and stated. | review | |
| WORK-10 | A request to validate is answered by checking the claims and the gate, with no new analysis the task did not ask for. | review | |
| WORK-12 | A tool built for the work is validated against cases with known answers before its output is trusted. | review | |
| WORK-13 | A contribution taken over is brought to the standard of its neighbors. | review | |
| WORK-14 | Every checkpoint passes the mechanical gate (`make`), with a byte-identical round-trip and zero `skool2asm` warnings, and its verdict line is reported whole. | review-record | |
| WORK-15 | A project holds the disassembly, its game's inputs and the settings only that game needs. A tool, config or rule that holds for any game lives in the skill, which the build reads it from, and no project keeps a copy. | review | |

## The call-out protocol (WORK-7)

1. **Answer first when the call-out is a question.** Answer it from the rules and the code before any edit. When the answer shows no defect, say so and stop.
2. **Classify it against the rules.** Search this file and the terminology registry. When a rule exists, name its ID and say why it was missed: no detector, a detector too narrow, or a skipped review. When none exists, add one here, stated as the class.
3. **Remove every contradiction.** Search the skill and the project for the old wording and for every example of the opposite, and fix or delete each.
4. **Write the guard before the fix.** Put the owner's text in verbatim as the bad fixture and the corrected text as the good fixture. Build or extend the detector, or add the review question. Run it and show it fires on the bad fixture and stays silent on the good one. When the rule exists, fix its guard and add no second sentence for it.
5. **Sweep with the guard.** Fix every instance of the shape in the project. Each entry the owner did not name passes the stated test on its own. Nothing is deleted that the test does not condemn entry by entry.
6. **Keep one plan.** State it in one line before editing. After reverting your own edit, stop, re-read the call-out and the rules, and restate the plan.
7. **Gate and review.** Run `make gate`, then the Challenger on the diff, which writes the review record. Fix what it finds and review again, since the diff hash has changed.

## Pre-flight checklists

Apply the listed rules before writing.

| Task | Rules |
| --- | --- |
| A data row comment or sub-block | ROW-1 to ROW-9, PROSE-9, HOME-5, AUD-4, TYPO-1, TYPO-2 |
| A routine description (`D`/`N`) or instruction comment | ENT-6 to ENT-8, ENT-10, HOME-1, HOME-2, HOME-4 to HOME-6, HOME-9, HOME-11, HOME-12, PROSE-1 to PROSE-9, STE-1 to STE-6, AUD-3, AUD-4, REG-3, TYPO-1, TYPO-2 |
| A variable or table definition | DEF-1 to DEF-5, PROSE-9, HOME-2, HOME-4, HOME-12, ENT-4, ENT-5, UNU-1 to UNU-3 |
| A glossary entry | DEF-1 to DEF-6, NAME-1, NAME-3, NAME-6 |
| An entry title or page heading | HEAD-1 to HEAD-4, NAME-6, AUD-1, HOME-10, TYPO-1 |
| A sprite, glyph or sound entry | GFX-1 to GFX-9, HOME-7, VIS-1, EVID-3 |
| A label, term or classification change | NAME-1 to NAME-12, WORK-1 |
| `.ref` page prose | HOME-1 to HOME-3, HOME-10, HOME-13, HOME-14, STE-1 to STE-6, AUD-1, AUD-3, AUD-4, ROW-7, VIS-1, TYPO-1, TYPO-2, VIS-11 |
| CSS, theme or layout | VIS-2 to VIS-10 |
| An owner call-out | WORK-7, WORK-1, WORK-9 |
| A gate finding | WORK-2 |
| Before reporting or committing | WORK-4, WORK-6, WORK-14 |

A retired rule's ID is not reused, so a range such as NAME-1 to NAME-12 spans a retired ID such as NAME-5, and VIS-2 to VIS-10 spans VIS-7.
