# The control file (.ctl)

The `.ctl` is the only file you hand-edit. It is a list of directives, each tied to an address, that tells `sna2skool` how to interpret the snapshot: where code and data live, what to name things, what to substitute, and what to say about it. `sna2skool` weaves the `.ctl` over the snapshot to produce the `.skool`.

The `.skool` and `.asm` are **generated and overwritten on every `make`**; an edit to either is silently lost. The project's `AGENTS.md` opens with this file contract so a cold agent sees it — keep that line intact.

The `.skool` is your feedback loop. Rebuild it after every `.ctl` change and read it to confirm instruction boundaries, byte lengths, and that no `overlapping instruction` warning appeared. Use the `.skool` — not the `.ctl` — to find the exact address and length of an instruction you want to comment.

## Addresses are hex, always

Every address in the `.ctl` is written in upper-case hex with a `$` prefix (`c $A891`, `D $A891`, `  $A891,3 …`). The build emits a hex `.skool` (`sna2skool --hex`), so a hex `.ctl` means an address reads the same in the file you edit and the file you read — no dec↔hex conversion in your head on any cross-reference, and that conversion-by-eye is exactly the error class the skill bans. (The `.ctl` validators parse addresses as hex, so a decimal `.ctl` is also *mis-validated*.) If you run `sna2ctl.py` for a first-cut hint, pass `--hex`, and keep every hand-edited address hex. To migrate an existing decimal `.ctl`, run `scripts/ctl_to_hex.py` — it is purely notational (the `.skool` is byte-identical), then run `make verify` and fix any ordering the validators now correctly flag. Lengths after a comma (`,3`) and `@equ` values stay as written.

The same rule covers **every address the reader sees**, not just directives: a raw `#R` reference is `#R$A891`, never `#R43153`; addresses quoted in comments, `.ref` catalogs, and `spec/*.md` are `$`-hex. (Better than a raw `#R$hex` is a label — `#R$A891(draw_car)` or a named ref — but when the address shows, it shows in hex.) Decimal digits appear only where the *value* is the point — a score, a count, a coordinate — with no conversion beside it. One base everywhere means an address greps identically in the `.ctl`, the `.skool`, the site, and the spec.

## Table of contents

- [Block types](#block-types)
- [Labels and routine descriptions](#labels-and-routine-descriptions)
- [Line-level comments and the length rule](#line-level-comments-and-the-length-rule)
- [Symbolic constants](#symbolic-constants)
- [Numeric base formatting](#numeric-base-formatting)
- [Text blocks and string terminators](#text-blocks-and-string-terminators)
- [Data structures and tables](#data-structures-and-tables)
- [Register annotations and cross-references](#register-annotations-and-cross-references)
- [Validation rules](#validation-rules)

## Block types

Every region of the snapshot gets a block type. This is the stage-2 map. The letter starts a block; the block runs until the next block directive.

| Directive | Meaning | Renders as |
| --- | --- | --- |
| `c` | Code | disassembled instructions |
| `b` | Bytes (data) | `DEFB` |
| `t` | Text | `DEFM` (characters) |
| `w` | Words | `DEFW` |
| `s` | Space (zeros/uninitialized) | `DEFS` |
| `g` | Game-status buffer | labeled `DEFB`/`DEFW` variables |
| `u` | Unused | excluded or marked |

```
c $6F00 Start the game
b $9580 Sprite mask table
t $7B40 Name entry prompt
```

Wrong block types are the most common cause of an unreassemblable source: data disassembled as code produces invalid opcodes, and code marked as data drops out of the round-trip. When `pasmo` errors or `cmp` differs, suspect a boundary.

The dangerous boundary errors are the ones that *still reassemble*. If a block boundary falls one byte off — the last entry of a table folded into the next block, a sprite row labeled as a table value — the bytes are unchanged, so the round-trip stays green and the mistake is invisible to the build. Fix the boundary from how the code *uses* the data (the indexer's range, the draw routine's row count), not from where the next recognizable thing seems to start. See "What the round-trip does NOT prove" in `references/build-verify.md`.

### Growing the map

The all-bytes baseline grown into code from the entry (see `references/agents.md`) rests on a few operational facts:

- `sna2ctl`'s heuristic code/data guess is a hint, not the map. It mislabels graphics and data tables as code, and every wrong boundary spawns phantom label references — a flood of `--create-labels` warnings that are pure noise. Keep its output under `build/` as a starting hint, never as the source of truth.
- Byte-identity does not prove the map (see above): a whole region wrongly labeled code or data still round-trips green. Confirm each boundary from how the code *uses* the bytes — an address written via `LD (nn),A` is a variable, not an instruction operand.
- Self-modifying code hides variables *inside* code: an instruction toggled between `LD A,n` and `RET` to enable a routine, an `HL`/`A` value stored into an operand byte. When a reference lands mid-instruction, suspect such a variable. Mark those bytes a `b`/`B` data sub-block and document the patch; do not force them to code.

## Labels and routine descriptions

```
@ $ADDRESS label=entry_name
c $ADDRESS Title of the routine
D $ADDRESS Description paragraph — what the routine does and why.
N $ADDRESS Narrative: the algorithm, step by step. Use a lone dot for a paragraph break.
```

`@ label=` names the address; SkoolKit resolves every reference to it automatically, so you never hand-write the address in a comment again. Name for *purpose* (`spawn_enemy`, `player_energy`), not mechanism (`loop_routine_3`).

The first name is rarely the final one. As you understand a routine better, a truer name appears — rename it. This is cheap precisely because references resolve through the label: change the `@ label=` line and every `#R` pointer and operand follows. Do not agonize over a perfect name on first contact; give it your best current understanding and refine as the picture fills in.

**Keep a label to 24 characters or fewer.** Labels never wrap in the HTML listing — they are code identifiers — so the label column sizes to the longest label on its page. One over-long internal label opens a wide empty gutter across every row of that page. The cap is a build gate (`lint-label-length`), and the fix for a violation is always to *rename* the label, never to widen or clip the column in CSS. When a `verb_noun_qualifier` name runs long, shorten a word (`controls` → `ctrl`, `quadrant` → `quad`) across the whole family so the naming stays coherent.

A routine has more than one named address. Every internal branch target the disassembler splits out — loop tops, per-case branches, shared tails — is an entry point, and the auto-generated `<routine>_0`, `<routine>_1`, … labels are as opaque as raw hex. A reader following `JR NZ,parse_3` learns nothing. Name each for what that branch *does* (`parse_loop`, `parse_done`, `read_kempston`) as part of documenting the routine, so the control flow reads in words. A referenced data sub-block — a table the code indexes — is an entry point too and earns a name.

`D` is the one-line-to-one-paragraph contract: what a caller needs to know. `N` is for the longer algorithm story when one is warranted — multi-paragraph, the formula, the state machine, the edge cases.

**`D` and `R` are entry-level — they render only at a block start.** An "entry" is an address declared with a block-type line (`c`/`b`/…). A branch target or internal label inside a block (the `*` sub-entries) is *not* an entry, so a `D` or `R` written at a mid-block address is **silently dropped** by `sna2skool` — no warning, the contract and register table just vanish from the `.skool`/`.asm`. Only `N` and instruction comments render mid-block. So when several CALLable subroutines are lumped into one `c` block, only the first (the block start) gets a visible `D`/`R`. To give an interior subroutine its own contract description or `I:`/`O:` register table, **split it into its own `c` entry** at that address (a clean RET/CALL boundary makes this safe and byte-identical). Catch this by grepping the generated `.skool` for the `D` text you wrote — if it is absent, the directive landed at a non-entry address. The build stays green either way, so the round-trip will not flag it.

**One paragraph per directive line — never hard-wrap.** Each `D` at the same address renders as its own paragraph, separated by a blank comment line. Splitting one sentence across several `D` lines produces a blank `;` mid-sentence. Write the whole paragraph on a single `D` line and let `skool2asm` word-wrap it (`Set-line-width` in `skoolkit.ini` sets the width); use a second `D` line only for a genuine second paragraph. The same holds for `N` and for instruction comments. See `references/comment-style.md` for what each paragraph should say.

## Line-level comments and the length rule

A comment on an instruction (or a run of instructions) is keyed by address and an optional length:

```
  $ADDRESS[,LENGTH] Comment text
```

`LENGTH` lets one comment span several instructions that form one logical step:

```
  $7A26,5 Award the spider's points to the player.
```

spans the two instructions in those 5 bytes under a single comment. Group instructions that do one thing; do not comment each in a sequence that shares an intent.

**Length rule:** omit `LENGTH` when it equals the distance to the next documented address — it is redundant and the linter rejects it. Specify `LENGTH` only when the comment must span fewer or more bytes than the gap to the next entry.

**Comment on an instruction boundary.** A comment line whose address falls *inside* a multi-byte instruction silently forces SkoolKit to split the block there. The half-instruction reassembles to different bytes, the round-trip breaks far away (the size change shifts every later address), and no warning points at the comment. Confirm the address is the opcode's first byte — not a displacement or immediate — before commenting. When a round-trip breaks with a `+N` length change and an opcode (not operand) mismatch, suspect a comment or directive landing mid-instruction. Take comment addresses from the *generated* `.skool`/`.asm`, which honors data sub-blocks split out of a code block (e.g. self-modified operand bytes); a throwaway disassembly that forces everything to code hands you boundaries that fall mid-instruction once those data bytes are restored.

## Symbolic constants

Replace magic numbers with names. This is what makes a disassembly read like source rather than a hex dump.

Define constants as `EQU` lines with the `>` directive, anchored at the origin:

```
> $4000 COLOR_BLACK   EQU $00
> $4000 COLOR_YELLOW  EQU $06
> $4000 MAX_ENERGY    EQU $3F
```

Substitute them into instructions with `@isub`:

```
@ $6A12 isub=LD A,MAX_ENERGY
```

Now the disassembly shows `LD A,MAX_ENERGY` and reassembles to the same byte. **Every literal that has a named meaning should use `@isub`** — `LD`, `CP`, `BIT`, `SET`, `RES`, `AND`, `OR`, any instruction. Build higher-level constants from bit positions to show intent:

```
> $4000 DOOR_STATE_MASK EQU 1<<DOOR_BIT_OPEN|1<<DOOR_BIT_LOCKED
```

Layer constants: raw values (`COLOR_YELLOW`) and domain aliases (`COLOR_ENEMY = COLOR_RED`). Use the domain name in game contexts and the raw name for UI chrome.

**`@equ` vs `@isub` — scope is the whole point.** `@equ=NAME=value` does two things: it emits an `EQU` line *and* registers `NAME` as the label for the address equal to `value`. SkoolKit then stamps `NAME` onto every operand in the program whose value equals that address. For a unique 16-bit address — a ROM entry, a system variable, a fixed hardware base (screen, attributes, font, tile-map) — that is exactly right: `CALL $1601` becomes `CALL CHAN_OPEN` everywhere, always correctly. For a small or common value it is a disaster: a `COLOR_BLACK=$00` turns every `LD BC,0` into a "color", a `TILE_EMPTY=$20` relabels a `+32` stride, a control-bit constant relabels every matching `SET n`. So reserve `@equ` for values with a single meaning program-wide. A small in-game literal — a color, bit index, tile value, port number, control mode — belongs in a targeted `@isub` (which touches only the instruction you name) or, when it is a one-off that does not recur, in the instruction's comment. This is the limit on "every literal that has a named meaning": it holds for the targeted `@isub`, not for a globally registered `@equ`.

**`@isub` pitfall — no bare small literals in the replacement.** When an `@isub` replacement contains a small literal that equals a defined constant's value, SkoolKit substitutes the constant's name into your replacement. `@isub=LD HL,ATTR_BASE+1` can come out as `LD HL,ATTR_BASE+SOUND_ON` when some constant equals `1` — nonsense. The substitution touches only instructions you `@isub`, so the fix is to write the symbolic name you intend or leave the colliding operand un-subbed. Read the generated `.asm` for the routine after adding `@isub`s; the collision shows up only in the output.

`@isub` is the first tier of a larger family. The deeper substitution modes (`@ssub`, `@rsub`) and the fix directives (`@ofix`, `@bfix`, `@rfix`) let the source express a relocatable form or a corrected-vs-original form while still round-tripping, and `@keep`/`@nowarn`/`@ignoreua` manage label substitution and warnings. See `references/expressive-palette.md` for the full set and when to reach for each.

## Numeric base formatting

Show values in the base that conveys meaning.

**Data bytes** — prefix the sublength in a `b`/`B` block:

| Prefix | Format | Output |
| --- | --- | --- |
| `b` | binary | `%11111111` |
| `c` | character | `"A"` |
| `d` | decimal | `255` |
| `h` | hex | `$FF` |

```
  $9580,2,b2 Top row mask.
```

renders `DEFB %11111111,%11000000`. Use binary for bitmaps and masks where individual bits matter.

**Instruction operands** — `C $addr,c` displays operands as characters until reset with `C $addr,h`:

```
C $8E40,c3 Set the round display to "00".
C $8E43,h
```

renders `LD HL,"0"` instead of `LD HL,$3030`. Prefer expressions that show a boundary's intent: `CP "9"+1` reads better than `CP ":"` for a digit-overflow check. Combine with `@isub` so the reassembled source carries the readable form.

## Text blocks and string terminators

ZX games often terminate a string by setting bit 7 of its last character. A plain `t` block renders that byte as an opaque number (`"0 START GAM",$C5`). To get the readable `"0 START GAM","E"+$80` form, give the string an explicit `T` sub-directive that splits the final byte into its own size-1 char element: `T addr,len,(len-1):1`. SkoolKit's char base renders a lone high-bit byte as `"X"+$80`; a multi-byte char run does not.

Pitfalls:

- Emit one `T` per string, not one per block — a whole-block `T` makes a single over-long `DEFM` that trips the line-width linter.
- A standalone terminator (a length-0 string before the marker) must be the bare length `1`, not `0:1` — a zero-length char run crashes `sna2skool`.
- A `T` that overlaps an existing sub-directive also crashes it; compute each string's extent only up to the next directive.
- Splitting a string makes its start a line-start, so every string the code references now needs a label — that is correct relocatability work. Split only runs that are genuinely text; leave non-text data un-split rather than expose unidentified bytes you would have to guess-name.

## Data structures and tables

When code references a structured value — a bitfield, an enum, a record layout — document it where it is defined, with a `#TABLE`:

```
D $7F40 #TABLE(default) { =h Bit | =h Meaning | =h Values }
  { 0 | Sound | 0 = off, 1 = on }
  { 1-2 | Difficulty | 0 = easy, 1 = normal, 2 = hard }
TABLE#
```

**A binary data block is documented by its *schema* — what the bytes mean.** A label (`tile_anim_frames`) and a one-line title are not the schema; they say *that* it is animation data, not how to *read* it. For an array of multi-byte records — an object/enemy table, an animation-frame list, a level map — state, in the block's `D` (often as a `#TABLE` of offset → field → meaning):

- the **stride** — bytes per record;
- each **field**'s offset within the record, its meaning, units, and range;
- the **count** of records, and any **sentinel** that ends or empties an entry.

Then a reader can decode any entry straight from the bytes, and a porter can rebuild the structure, without reverse-engineering the consumer. Derive the layout from the code that *indexes* the block — the stride is in its `ADD HL,DE` / `INC`-by-N step, the field offsets in its `(IX+n)` reads — never guess it by eye.

And **lay the bytes out at that stride** so the structure is *visible*, not a flat `DEFB` run: a `B addr,len,stride` sub-directive (or `W` for word fields) renders one record per line, and **each record gets its own annotated sub-line naming it**. A stride directive alone documents the span, not the contents — the reader gets "96 bytes per room" and still cannot find room 12. `room_maps` is the model:

```
b $7A40 Per-room tile maps
D $7A40 The 50 rooms' tile maps laid end to end, 96 bytes per room: a 12x8 grid of tile codes, one row of 12 after another. Records run in room order.
B $7A40,96,12 Room 1
B $7AA0,96,12 Room 2
…
```

Each record is addressable: the `D` carries the schema, the stride renders the 12x8 grid as eight rows, and the per-record line says *which* room this one is. One `B $7A40,4800,96` in place of those 50 lines would render the rows and name none of them; a bare `b $7A40` under a label, with no title, schema or stride, is worse again — an undocumented blob.

Name records by what the reader is looking for, not by ordinal position, and use the number the game *shows*. Where a counter is 0-based and the caption prints it plus one, record 0 is annotated `Room 1` — and the `D` states that convention, so the two readings cannot be confused.

`make lint-array-elements` checks this (`scripts/validate_ctl_array_elements.py`): it flags a directive standing in for ≥10 records, and an array-sized span with no sub-directive at all — the second being the form that hides from every other check, since declaring nothing leaves nothing to inspect.

### The tiling contract

Everything above is advice until something checks it, and advice is what gets skipped on the one region nobody understood. The checkable form of "a data block states what its bytes mean" is a **tiling**: for every `b`/`s` block, starting at the block's address, the sub-directives cover every byte exactly once and sum to the block's size. No gaps, no overlaps, no leftovers. A block that states nothing about its bytes fails. `make lint-data-structure` enforces it.

This matters because prose is free. It can describe a span convincingly without committing to one verifiable claim, and a byte block is where code goes to hide: held as data, an embedded address is a literal byte that no shifted build relocates, and every other check still reads green. The tiling moves the claim somewhere arithmetic can test it. It invents no notation — every directive below is stock SkoolKit. The vocabulary was always there; only the contract was missing.

A block claims exactly one category per byte, and each is *proven* by something being exercised rather than by prose asserting it:

| Category | Declared as | What proves it |
| --- | --- | --- |
| Rendered asset | `#UDGARRAY` / `#FRAMES` / `#SCR` / `#FONT` / `#AUDIO` | the render is drawn; a wrong extent draws wrong |
| Code | a `c` block | it disassembles, and the round-trip reassembles it |
| Element array | `B`/`W`/`T addr,len,sublen` | `len % sublen == 0`, and the tiling |
| Pointer | `W`, never `B` | the operand resolves to a label, so it relocates |
| Text | `T addr,len` | renders as `DEFM`; terminators are visible |
| Buffer | `s` block + `S addr,len` | a **writer**: the code that fills it, named with `#R` |
| Scalar | `B addr,n`, n ≤ 8 | the name is the schema |

**The buffer category: never enumerate a run you have nothing to say about.** An uninitialized region or a work buffer is an `s` block with an `S addr,len` — one line stating its size — not a `b` block enumerated byte by byte into a wall of `DEFB $00,$00,…`. Thirty-two zero bytes enumerate to four `DEFB` listing lines; the same span as `s` + `S` is one. Every listing line is a row on the HTML page, so an undeclared run reads as a stray blob and crowds out the one-byte variables around it.

**But `s` is a claim, and its proof is a writer.** Every other category is proven by something exercised — the render is drawn, the code round-trips, the stride divides — and "buffer" must cost the same. `s` says *the game fills this at runtime*, so **name the code that fills it**, with `#R`, exactly as a load-bearing variable lists its readers and writers. Without a named writer the claim is free, and a claim that costs nothing is how an unparsed span gets waved through: `s` + `S addr,len` will silence *any* block, including executable code, and every check still reads green.

So when nothing writes a region, it is not a buffer:

- **nothing reads or writes it** → `u` (Unused). A block whose own prose says "no path reaches this" and whose type says "the game fills this at runtime" is contradicting itself to clear a flag. `u` keeps the bytes as `DEFB`, so the round-trip is unaffected.
- **the bytes are executed** → `c`, and the disassembly proves it.
- **you have not found the writer yet** → that is the honest state, and the flag belongs there until you do. Do not spend an `s` to make it quiet.

Nothing mechanical enforces this — the same is true of "the render is drawn" and "the code round-trips", whose proofs live in the HTML build and the round-trip rather than in a linter. The buffer's proof lives in the trace, and it is the Challenger's to check.

Two things to get right, as of SkoolKit 10.1:

- **`S` compacts to `DEFS` only for a *uniform* run.** Where the bytes are not uniform — a buffer holding what the loader left behind at the capture point, say, `00 00 … 3C 40 00 FF` — SkoolKit falls back to `DEFB` to protect the round-trip. So `S` is the *claim* and the compaction is a *bonus the bytes may not allow*. Do not judge the annotation by whether the listing got shorter, and do not "fix" a non-compacting `S` — it is already correct.
- **An empty span's stride is not a claim about its bytes, so do not enumerate it.** This is where the tiling contract answers to itself. The contract exists to move a claim somewhere arithmetic can test it — and over a span of zeros, arithmetic *cannot* test a stride. `120 % 2 == 0` passes for any even length; it verifies nothing. So a door state map of 120 zero bytes is not an element array to lay out at `B $x,120,2`: that renders **60 rows of `DEFB $00,$00`** under one shared comment, quadrupling the very layout creep this rule exists to stop, and buying no verification for it. Declare it `s` + `S $x,120` — one `DEFS`, the tiling satisfied, the size checked — and put the 60×2 runtime layout in the `N` prose, which is where a claim about *runtime* state belongs, because the image holds no bytes to check it against. Enumerate a stride only where the bytes are real: that is where it is testable and where the rows show something.

**The scope is the span, not the block, and a line is earned by what it documents.** A zero byte that carries its own comment — `B $7F0B,1  Pause flag: non-zero while the game is paused` — has earned its line; the row exists for the annotation, not the byte. Sixty identical rows under one comment have not. So the rule bites on a *span* over the scalar threshold, never on a block: a record of per-byte scalars is a run of length-1 spans and is untouched, while one undifferentiated 120-byte span is exactly what it catches.

That distinction decides what you actually change. **The zero span always takes `S`; the block only becomes `s` if the whole of it is a buffer.** `S` is legal inside a `b` block, so a mixed block keeps its type and compacts just the run:

```
b $8140 Real bytes, then a zero run
B $8140,8      the real data, enumerated because the bytes are real
S $8148,32     the run — one DEFS, not four rows of DEFB $00
```

Change the block to `s` only when there is nothing else in it, as for a wholly empty state map.

**Variable-length data needs no grammar — enumerate it.** A disassembly has one immutable instance, so a length-prefixed list is declared entry by entry, lengths as they actually are, and the tiling proves the enumeration is complete:

```
B $x,1        the length byte
T $x+1,N      the string
W $x+1+N,2    the next pointer — a label, therefore relocatable
```

The pointer must be `W`. A pointer living inside a byte blob is the same defect wearing a different hat, and typing it is what makes it relocate.

Properly typed data also renders better for free: `W` gives `DEFW door_frame_0` instead of `DEFB $C0,$7E` — readable *and* relocatable in one move — and `T` gives `DEFM "PAUSE","D"+$80`. The contract costs nothing you did not already owe.

**Its limit: tiling proves accounting, not meaning.** A wrong stride that happens to divide will pass, and a mis-typed field will tile. It is necessary, not sufficient — its job is to make an unparsed span impossible to leave behind. Only the render, the round-trip and the relocation proof test whether the parse is right.

For an **array of records**, go one level finer — this is the norm, not a nicety for long sections only: mark up each element with its own **inline comment** (`  $addr,len  Label`), so an opaque run becomes a self-describing, indexed list and a reader can address "frame 7" without counting bytes. A sprite-frame array names every frame; level and spawn-slot tables name every entry:

```
b $9A00 Four arrays of walking-enemy sprites (2x2 tiles x 4 frames = 128 bytes each).
  $9A00,32,2 Frame 1
  $9A20,32,2 Frame 2
  $9A40,32,2 Frame 3
  $9A60,32,2 Frame 4
```

The block `D` states the schema once; the per-record inline comments then say *which* record each row is (Frame 3, Room 5, wave 2). A reader scanning the data sees the structure without counting bytes. For a *pointer* table — frame pointers, handler addresses — each element's comment links its target (`  $9440,2 Frame 1 — #R$F020`), so the table navigates into the blocks it points at. Do not comment every byte of a uniform blob, but a table whose elements mean different things is not a uniform blob.

Describe a variable by *what its value represents* — physical meaning, units, range, special values — not where it is used:

> **Bad:** Used as a delay counter in the sound loop. **Good:** Alarm beep period (0–127). Lower = higher pitch. Counts down each frame.

For load-bearing variables, list the routines that read and write them using cross-references, so a reader can trace data flow.

**Give structures a field-and-flag vocabulary and spend it everywhere.** A multi-byte record's fields get names (`enemy.counter_and_flags`), flag bits get named values (`flags_FACING_LEFT`), and bounded quantities get named endpoints (`lives_MIN`..`lives_MAX`); comments then use those names instead of re-deriving offsets and bit masks in prose. One naming, many uses: the same vocabulary appears in the `g`-block schema, in every comment that touches the field, and in the behavior spec — so a rename is a grep, and a mismatch is visible instead of silent.

Hunt for those readers and writers in the `.skool`/`.ctl`, not by grepping the generated `.asm` for the raw address. `skool2asm --create-labels` auto-labels any referenced line-start, data bytes included, as `L<hex>`, so a referenced `$8E00` renders as `L8E00` and a grep for `$8E00` finds none of its readers. Before calling a variable unused, grep for the bare hex without the `$` (it matches both forms) or for the assigned label — better, label the variable yourself first so every reference renders through your name.

The `g` block is also the agent-facing memory map: a live agent reads game state straight from these addresses. Documenting it richly serves both the human porter and the MDP described in `references/behavior-spec.md`.

## Register annotations and cross-references

Mark a routine's intentional inputs and outputs like function parameters:

```
R $ADDRESS I:A Object type to spawn.
R $ADDRESS O:HL Address of the allocated slot.
```

Document only registers that are real parameters, not every register the body touches.

In comment text, reference addresses with `#R$XXXX` (SkoolKit resolves it to the label) and register names with `#REG` macros (`#REGhl`, `#REGbc`, `#REGde`, `#REGa`). The `I:`/`O:` fields in `R` directives use bare register names — that is SkoolKit syntax — but in prose always wrap them.

## Validation rules

The build runs three linters (`scripts/validate_ctl_*.py`); violations fail the build. They keep the `.ctl` mechanically consistent so diffs stay clean and `sna2skool` never silently reorders.

1. **Address order** — every directive in ascending address order.
2. **Instruction order** — directives at the *same* address follow the canonical sequence: `@` → block type (`c`/`b`/…) → `D` → `N` → `R` → line comment.
3. **No redundant lengths** — a line comment's `LENGTH` must not equal the gap to the next documented address.

Run them yourself while editing (`python3 scripts/validate_ctl_address_order.py {game}.ctl`) rather than waiting for the full build.

`validate_ctl_data_structure.py` is a fourth, **advisory** and outside the build gate: it holds every `b`/`s` block to the tiling contract above. Run it as `make lint-data-structure`.
