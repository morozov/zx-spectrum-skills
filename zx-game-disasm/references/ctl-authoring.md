# The control file (.ctl)

The `.ctl` is the only file you hand-edit. It is a list of directives, each tied to an address, that tells `sna2skool` how to interpret the snapshot: where code and data live, what to name things, what to substitute, and what to say about it. `sna2skool` weaves the `.ctl` over the snapshot to produce the `.skool`.

The `.skool` and `.asm` are **generated and overwritten on every `make`**; an edit to either is silently lost. The project's `AGENTS.md` opens with this file contract so a cold agent sees it — keep that line intact.

The `.skool` is your feedback loop. Rebuild it after every `.ctl` change and read it to confirm instruction boundaries, byte lengths, and that no `overlapping instruction` warning appeared. Use the `.skool` — not the `.ctl` — to find the exact address and length of an instruction you want to comment.

## Addresses are hex, always

Every address in the `.ctl` is written in upper-case hex with a `$` prefix (`c $A891`, `D $A891`, `  $A891,3 …`). The build emits a hex `.skool` (`sna2skool --hex`), so a hex `.ctl` means an address reads the same in the file you edit and the file you read — no dec↔hex conversion in your head on any cross-reference, and that conversion-by-eye is exactly the error class the skill bans. (The `.ctl` validators parse addresses as hex, so a decimal `.ctl` is also *mis-validated*.) If you run `sna2ctl.py` for a first-cut hint, pass `--hex`, and keep every hand-edited address hex. To migrate an existing decimal `.ctl`, run `scripts/ctl_to_hex.py` — it is purely notational (the `.skool` is byte-identical), then run `make` and fix any ordering the validators now correctly flag. Lengths after a comma (`,3`) and `@equ` values stay as written.

The same rule covers **every address the reader sees**, not just directives: a raw `#R` reference is `#R$A891`, never `#R43153`; addresses quoted in comments, `.ref` catalogs, and `spec/*.md` are `$`-hex. (Better than a raw `#R$hex` is a label — `#R$A891(draw_car)` or a named ref — but when the address shows, it shows in hex.) Decimal digits appear only where the *value* is the point — a score, a count, a coordinate — with no conversion beside it. One base everywhere means an address greps identically in the `.ctl`, the `.skool`, the site, and the spec.

## Table of contents

- [Block types](#block-types)
- [Nothing anonymous](#nothing-anonymous)
- [Labels and routine descriptions](#labels-and-routine-descriptions)
- [Line-level comments and the length rule](#line-level-comments-and-the-length-rule)
- [Symbolic constants](#symbolic-constants)
- [Numeric base formatting](#numeric-base-formatting)
- [Text blocks and string terminators](#text-blocks-and-string-terminators)
- [Data structures and tables](#data-structures-and-tables)
- [One page per thing](#one-page-per-thing)
- [Where an `N` note can land](#where-an-n-note-can-land)
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
| `u` | Unused: nothing reads or writes it | excluded or marked |

```
c $6F00 Start the game
b $9580 Sprite mask table
t $7B40 Name entry prompt
```

Wrong block types are the most common cause of an unreassemblable source: data disassembled as code produces invalid opcodes, and code marked as data drops out of the round-trip. When `pasmo` errors or `cmp` differs, suspect a boundary.

The dangerous boundary errors are the ones that *still reassemble*. If a block boundary falls one byte off — the last entry of a table folded into the next block, a sprite row labeled as a table value — the bytes are unchanged, so the round-trip stays green and the mistake is invisible to the build. Fix the boundary from how the code *uses* the data (the indexer's range, the draw routine's row count), not from where the next recognizable thing seems to start. See "What the round-trip does NOT prove" in `references/build-verify.md`.

### What `b`, `g` and `u` promise

`b` and `g` both render as `DEFB`. The letter is the only thing that distinguishes them, so it has to be the truth about the bytes.

`b` says these bytes are what the program was loaded with and stay that way: a table, a glyph set, a constant. `g` says the program writes here as it runs, and SkoolKit heads its page "Game status buffer entry at". The distinction is not cosmetic. It tells a reader whether a value can be trusted across a replay, tells a porter what to allocate rather than initialize, and tells an agent-trainer which addresses are the state its policy observes. A bonus flag that the game sets and clears every level, published as `b`, tells all three of them the wrong thing.

`u` is the third promise, and the strongest of them: nothing in the image reads this region and nothing writes it. It is for bytes that are in the address space because the loader left them there — a zero-fill tail, a gap between structures, whatever sat in RAM before boot — and SkoolKit heads its page "Unused RAM at". A store into a `u` region breaks that promise exactly as it breaks `b`'s, and the repair is the same letter: bytes the program writes are `g`.

The code settles which letter is right, and nothing else does. An address a routine stores to is not static, whatever the entry's description says about it; `make lint-publication` reads the generated `.skool` and reports a `b` or `u` entry the code writes into. The evidence runs one way only: a store proves mutation, while no store proves nothing, because a routine writing through `HL`, `IX` or an `LDIR` names no address in the instruction. So a `g` entry that ought to be `b` is not something a linter can find — settle that one by reading the writers.

That asymmetry also decides the fix. A store proves the entry is not what `b` promises, and the count of stores says nothing about the bytes no instruction names, so retype the entry `g`. Split the written bytes into a `g` entry of their own only when the rest of the entry really is a static table — a table with a runtime cursor glued to its tail — and read the writers to confirm it.

**The letter is not the only place the promise is made.** Consider this entry:

```
@ $7F20 label=unused_7f20
b $7F20 Undetermined - no reader or writer found in the image
```

Three claims, one fact. The letter says load-time data, the title says nothing in the image touches these bytes, the label says unused — and the listing three lines further down the same page shows the code storing to three of its sixteen bytes: `spawn_timer` from `$9C10`, `wave_index` from `$9C2E`, `shot_count` from `$A3B4`. The letter is the smallest of the three errors. A reader who has learned to distrust a `b` still has no way to distrust a sentence, and `unused_7f20` is the string he greps for.

So settle all three from the one fact, and `make lint-publication` holds all three: it reports text that says nothing writes these bytes over an address the code stores to. Four things keep that a fact rather than a reading of prose.

- It reads a denial of a **writer** only. "No reader found in the image" is a claim a store leaves standing, and a byte written and never read is a real thing to document.
- A denial that **names the writer it excludes** is not denying that writer, so it is not reported: "nothing writes them individually; the only writer is the room reset (`#R$6C40`)". Name it either way the listing offers — the address, or the label, which is what the listing actually prints.
- Text written **inside** the entry speaks for its own bytes. The title and a `D`/`N` at the entry's address speak for everything it publishes; a `D`/`N` further in, or the description on a sub-directive, speaks from its address to the next address carrying text. So `N $F3A0 Spare bytes after the font` is checked against $F3A0 onwards and not against the whole entry.
- A bare `unused` / `unreferenced` / `orphan` in the title or the `@label` is read as a denial on every type **but `g`**, whose letter has already said the program writes these bytes. `orphan_list_head` on a `g` entry names what the list holds; there is no claim there to strike and no letter to correct. A denial with a verb is read on `g` too — an entry saying "nothing writes these" over a store contradicts itself whatever its letter is.

Write what the code shows instead. Name the routine that sets the bytes. Where you have not found what uses them, say that and no more: "purpose undetermined" is honest, while "no writer found in the image" is a claim, and a claim has to have been checked.

### An entry holds one kind of thing

An entry is one page and one memory-map row, so everything inside it is filed under its title. Keep the contents to the kind the type declares: a `t` entry is a message, and a runtime counter that happens to sit past the message's last character is a separate entry, not a `B` sub-directive riding along on a page headed "Text: PAUSED". `make lint-publication` reports a `t` entry holding a sub-directive that is not `T`.

The other data types are not held to this, and deliberately: a `b` or `g` entry legitimately mixes `B`, `W` and `S`, and a `w` entry carries its own stride with no sub-directive at all. `t` is the one type whose contents are a single kind by construction.

### Growing the map

The all-bytes baseline grown into code from the entry (see `references/agents.md`) rests on a few operational facts:

- `sna2ctl`'s heuristic code/data guess is a hint, not the map. It mislabels graphics and data tables as code, and every wrong boundary spawns phantom label references — a flood of `--create-labels` warnings that are pure noise. Keep its output under `build/` as a starting hint, never as the source of truth.
- Byte-identity does not prove the map (see above): a whole region wrongly labeled code or data still round-trips green. Confirm each boundary from how the code *uses* the bytes — an address written via `LD (nn),A` is a variable, not an instruction operand.
- Self-modifying code hides variables *inside* code: an instruction toggled between `LD A,n` and `RET` to enable a routine, an `HL`/`A` value stored into an operand byte. When a reference lands mid-instruction, suspect such a variable. Mark those bytes a `b`/`B` data sub-block and document the patch; do not force them to code.

## Nothing anonymous

A reader meets the disassembly one page at a time, and every entry becomes a page. So **every entry carries a title, and every sub-directive says what its bytes are.** `make lint-identity` gates both.

```
b $7F08                            <- publishes as "Data at 7F08"
B $7F08,1                          <- a row of DEFB that nothing explains
```

An untitled entry does not go unheaded; it gets SkoolKit's default heading for its type, from the `[Titles]` templates: `Data at` for `b` and `w`, `Routine at` for `c`, `Game status buffer entry at` for `g`, `Text at` for `t`, `Unused RAM at` for `s` and `u`. The page exists, the reader can reach it, and it says nothing about the block that its address does not.

Neither form fails anything else. Both round-trip, both tile, both can be fully labeled, and `make coverage` counts both as documented — a titleless block reads as 100% NAMING, because the gauge counts labels and a label is not a sentence.

**An untitled entry has two causes and they need opposite fixes.** Either it is one field that a stray block directive split out of the record above it — in which case delete the block directive, leave the sub-directive where it is, and the field returns to its record — or it genuinely starts a structure that was never titled, in which case write the title. Nothing in the file tells the two apart: you decide by asking whether these bytes are fields of the record above. Get it wrong in the fold direction and a real structure disappears into an unrelated entry, which is worse than the untitled page you started with. The linter reports both fixes and names the record; it does not choose.

The one exemption is the trailing `i` block. It publishes no page — it marks where the disassembly stops — so it needs no title.

**A sub-directive is identified when it carries its own description, or when its address carries an `@ label=`.** A description is trailing text on the directive or a line comment inside its span; a label names those exact bytes, renders on that row, and makes the span reachable by name from anywhere in the disassembly. Either one, and the bytes have a name a reader can use.

**The entry's own title, `D` or `N` does not discharge it**, however completely the schema is stated there. This is the exemption the rule exists to refuse. A record whose `N` says, in as many words, "+4/+5 are the X/Y speeds" and "+7 is the pass counter" over anonymous `S` sub-directives still leaves those bytes nameless and unreachable by absolute address. "It is obvious from the record above" is exactly the reasoning the rule refuses. A rule you cannot state is not a rule.

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

### An underscore is a claim, and the build checks it

`walk_player_left` tells a reader that these bytes are part of `walk_player`. That is a claim about the code, not decoration, and `lint-label-namespace` decides it. Containment for a routine means dominance — every path that reaches this address passes through the one the prefix names — so the check builds a control-flow graph across every `c` entry from the generated `.skool` and asks the dominator tree. Four ways the claim comes out false:

- **A private helper wearing the entry's name.** `walk_player_slide` is a separate routine called from exactly one place, inside `walk_player`. Two addresses that read as alternatives, one qualified and one not, where only the unqualified one is ever invoked and a caller has no way to tell. A public sibling is a different thing and passes: `print_string_wide` beside `print_string`, called from many sites, offers a choice that exists.
- **A behavior wearing another's name.** `walk_player_ice` carries its own `N` narrative — a reader looks it up as a unit, it is not a branch position — while the prefix files it as part of `walk_player`. A behavior with its own story takes a name of its own, outside the other's namespace.
- **A prefix that skips a level.** `walk_player_left` sits inside `walk_player_ice`, not directly inside `walk_player`, so one family reads at two depths and the reader of the normal-floor code has no way to know `walk_player_left` is not also theirs.
- **A containment the flow refuses.** `ladder_grab_rung1` is prefixed on `ladder_grab`, which sits *after* it and is fallen into — the containment runs the opposite way to the claim. This is the kind that catches a family where one member's name is a prefix of another's without being its parent.

Three things the check leaves alone, and they are the shapes to reach for. A prefix on *data* associates and claims nothing — `hit_door_addr` names the variable `hit_door` works on, and there is no control flow to falsify. A stem that is not itself a label asserts nothing about an address, which makes `slide_left` under `walk_player_slide` the deliberate form: branch labels stemmed on the behavior's distinguishing word. And a run of branch positions — `slide_left`, `slide_left_dir`, `slide_left_step`, `slide_left_done` — are stages of one behavior, not nested inside each other, even though each dominates the next. So only a narrated label can be the *inner* behavior a prefix is told it skipped, which is what keeps a sequence of stages from collapsing into `slide_left_dir_step_done`.

### What the suffix encodes

A family reads when every member answers the same question — which direction, which stage, which floor — and stops reading when the suffixes turn out to be four kinds of thing at once. A `walk_player_*` family holding a gate state (`_active`), a floor type (`_ice`), a direction (`_left`) and an activity (`_push`) gives no notion to read them against, so no reading of any single one is available. Decide the question the suffix answers before the family grows past two members. `validate_ctl_label_namespace.py --report-families` prints every family with its members, which is the worklist for a project that already has some.

Four rules no check can decide:

- **Never abbreviate a phrase to its distinguishing-looking half.** Say a game's setting is ICE FLOOR; `walk_player_ice` keeps the half that also names the ICE-SKATES pickup, so a reader takes the routine for the pickup's. When the whole phrase will not fit, shorten a word across the family — never drop one.
- **Name the job, not the mechanism.** A count or a data shape is mechanism: two step sizes is how the style is built, not what the routine does. That routine moves the player straight from the current frame's controls, keeping no momentum between frames, so it is `use_direct_steering` and the two steps belong in the comment.
- **A behavior takes an imperative verb.** The name says what invoking it does. Branch positions inside it need no verb — they are places, not operations.
- **Alternatives take parallel shapes.** Two implementations of one choice must be recognizable as a pair: `use_direct_steering` and `use_momentum_steering`, both reading as *use the ___ steering*, not one verb-led and one noun-led.

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

`make lint-array-elements` checks this (`scripts/validate_ctl_array_elements.py`): it flags a directive standing in for ≥10 records, and an array-sized span with no sub-directive at all — the second being the form that hides from every other check, since declaring nothing leaves nothing to inspect. It is in the build gate, against the baseline.

Either spelling of the annotation satisfies it, because both put one named row per record in the listing. One `B` per record carries the name in its own description, as `room_maps` does above; one `B` carrying the stride, with a `  $ADDRESS text` line comment per record, carries it on the rendered statement, which is the cheaper form for a long table because the stride is written once:

```
b $7D80 Per-type starting energy
D $7D80 Indexed by enemy type (0 to $0F). #R$7DA0 copies the entry for its type into a
D $7D80 new enemy's record +$04, its starting energy.
B $7D80,16,1
  $7D80 Type $00: no enemy
  $7D81 Type $01: spider
…
```

#### What is not a record array

A byte run is not a record array just because a number divides into it, and the check must not ask a bitmap to name its pixel rows. Four things disqualify a span, and each is the `.ctl` already saying what the bytes are — so the exemption is earned by a declaration, never asserted in prose:

- **A render covers the block** — a macro in its own prose, or on a code partner the two name each other through, exactly as the [tiling contract](#the-tiling-contract) reads it. A sprite's pixel rows, a screen's cells and a tune's note bytes are not records to index; the render is the schema and drawing it is the proof.
- **The entry is `w`** — the entry type declares the element. One `DEFW` per word is one element per row, so no record size is left in prose. A `W` sub-directive that groups words into multi-word records is still asked to name them.
- **The stride is one byte** — a scalar has no fields, so there is no record layout to state. What the index means belongs in the block's `D`, and the tiling contract gates that the block has one.
- **A page or more at a power-of-two stride of ≥16 bytes** — a record size is whatever its fields sum to (3, 5, 6, 96) and lands on a power of two by coincidence. A page-sized region cut at a power-of-two width is a geometry: a screen, a sprite bank, a tile grid, a work buffer. This is the loosest of the four and it costs something — a genuine array of 16- or 32-byte records spanning a page goes unasked — but the tiling contract still holds that span to declaring its stride and covering the block.

Two floors sit under all four, and neither is a declaration — they are sizes below which the check does not ask at all:

- **Too small to be a table** — a span under `--min-span` (40 bytes), or one cut into fewer than `--min-records` (10) records, is not reported. This is what keeps a sprite's eight pixel rows and a nine-byte record out of the findings without any exemption being earned.
- **Nearly complete counts as complete** — a span is reported only once `--min-records` of its records carry no line comment. A table with 91 of its 100 records annotated reads clean; the check is after the array nobody indexed, not after the last nine rows of one somebody did.

The first of the four is the one to reach for. When a span is silent only because it is a geometry, a scalar run, or under a floor, that is the check declining to ask, not a statement that the bytes are understood.

### The tiling contract

Everything above is advice until something checks it, and advice is what gets skipped on the one region nobody understood. The checkable form of "a data block states what its bytes mean" is a **tiling**: for every data entry — every block type but `c` and `i` — starting at the block's address, the sub-directives cover every byte exactly once and sum to the block's size. No gaps, no overlaps, no leftovers. A block that states nothing about its bytes fails. `make lint-data-structure` enforces it, and it is in the build gate.

The contract is on the *entry*, not on the letter that groups its page. What an undeclared byte becomes differs by type — `DEFS` under `s`, `DEFB` under `b`, `g` and `u`, `DEFM` under `t`, `DEFW` under `w` — and only under `s` is it unused space, under a note that says what it is. Under every other type it is worse: the byte is *published as data* on a page whose title says the block was digested, and no directive anywhere claims it. A `u` entry titled "Undetermined 5-byte block" that carries one five-byte `B` but runs on for two kilobytes publishes every byte past that directive as `DEFB` under that title.

`w` is the one type that answers the schema question by itself, so it is exempt from UNTYPED. Its bytes render one `DEFW` per word whether or not a `W` repeats that stride, and a word that names a labeled address assembles as that label — so there is no stride left to declare and nothing left to hide as a literal. A `w` entry still has to tile, and a `W` sub-directive that groups its words into multi-word records still has to name them — that is the array-element question `make lint-array-elements` asks, above. What that check does *not* ask of a bare `w` entry is a record size, for the same reason: the entry type already gave one.

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

**But `s` is a claim, and its proof is a writer.** Every other category is proven by something exercised — the render is drawn, the code round-trips, the stride divides — and "buffer" must cost the same. `s` says *the game fills this at runtime*, so **name the code that fills it**, with `#R`. Without a named writer the claim is free, and a claim that costs nothing is how an unparsed span gets waved through: `s` + `S addr,len` will silence *any* block, including executable code, and every check still reads green.

So when nothing writes a region, it is not a buffer:

- **nothing reads or writes it** → `u` (Unused). A block whose own prose says "no path reaches this" and whose type says "the game fills this at runtime" is contradicting itself to clear a flag. `u` keeps the bytes as `DEFB`, so the round-trip is unaffected.
- **the bytes are executed** → `c`, and the disassembly proves it.
- **you have not found the writer yet** → that is the honest state, and the flag belongs there until you do. Do not spend an `s` to make it quiet.

Nothing mechanical enforces this — the same is true of "the render is drawn" and "the code round-trips", whose proofs live in the HTML build and the round-trip rather than in a linter. The buffer's proof lives in the trace, and it is the Challenger's to check.

Two things to get right, as of SkoolKit 10.1:

- **`S` compacts to `DEFS` only for a *uniform* run.** Where the bytes are not uniform — a buffer holding what the loader left behind at the capture point, say, `00 00 … 3C 40 00 FF` — SkoolKit falls back to `DEFB` to protect the round-trip. So `S` is the *claim* and the compaction is a *bonus the bytes may not allow*. Do not judge the annotation by whether the listing got shorter. Where a long `S` holds a few stray bytes in a sea of zeros, compact it with a partition: one sublength list that sums to the span's length, alternating the stray islands and the zero runs (`S $F400,1024,2,62,2,62,…`). Each zero run becomes one `DEFS` and each island one `DEFB`, under one directive and one description. The list states statement boundaries rather than a stride, so neither `lint-data-structure` nor `lint-array-elements` reads it as records.
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

## One page per thing

Every entry in the `.ctl` becomes a page on the site and a row in the memory map. The set of entries is therefore a claim in its own right — *these are the things this disassembly documents* — and it is wrong in seven ways that no per-entry check can see. `make lint-publication` gates the first five, `make lint-names` and `make lint-images` the last two, and `build-verify.md` describes them.

**Publish only what the program occupies.** An entry outside the program image publishes a page for RAM the program never uses. Generated render-only data — sprite masks a build script produced — declared below the image's origin gets pages and memory-map rows for addresses that are ROM on real hardware, and nothing on those pages tells a reader they are not part of the game. Render-only data belongs in a `.ref` `[Graphic:]` entry or beside the script that generates it, never in the address space.

**One structure is one entry, not a run of pages.** A structure split into one entry per address the code writes to gets a page and a memory-map row per part, and no page anywhere says what the whole of it is. The signature the check reads is a run of three or more consecutive `b` or `w` entries, each with no sub-directive, all headed by the same thing — the clause before the title's first `:`, `;`, `,`, `(` or dash, with any index stripped. Three entries reading "Title-screen bitmap; start cell reused for the lives counter", "…for the timer" and "…for the room number" are one title screen: what follows the semicolon is a note about one address inside the subject the head names, not a second subject. The fix is one entry, one title, and a sub-directive per part — which is what [the tiling contract](#the-tiling-contract) asks for anyway.

**A page holds one kind of thing.** The inverse of the fragmented structure: a `t` entry that runs past its message publishes what follows — a counter the game bumps every frame, say — on a page headed by the message, and under that title in the memory map. The check reads a `t` entry holding a sub-directive that is not `T`; see [What `b`, `g` and `u` promise](#what-b-g-and-u-promise) for why only `t` is held to it. The fix is a split, one entry per thing.

**A page is the type its bytes are.** A `b` entry publishes its bytes as data the program was loaded with, so one holding what the game writes — a level number, a lives count — misstates every one of those bytes. The check reads the generated `.skool` for the addresses the code stores to and reports a `b` or `u` entry containing one, so the finding is an instruction address rather than a reading of the entry's prose. Retype the entry `g`, or split the written bytes into a `g` entry of their own when the rest of it really is untouched.

**A page does not deny what its own listing shows.** A title, description or label saying that nothing writes the bytes is contradicted by the listing on the same page when it shows the code storing to them. The same store that settles the letter settles the sentence and the label, and the check reports all three — see [What `b`, `g` and `u` promise](#what-b-g-and-u-promise) for what it reads as a denial and what it deliberately does not.

**One entity, one name.** `references/agents.md` states it — one canonical term per concept, anchored to the `@label` identifiers, never a synonym for something a label already names. Three names for two enemy slots ("enemy A", "first/second enemy", "the chasing enemy") against labels `enemy_a` and `enemy_b` read fine page by page and leave a reader crossing pages to translate.

`make lint-names` holds the one part of that arithmetic can settle. Where the labels declare a **slot family** — a set differing only in one slot token, at the same place in the name (`enemy_a` / `enemy_b`, `enemy_a_timer` / `enemy_b_timer`) — prose must not name a member by its position. "The second enemy" is the worst available name: it is not in the listing, it is not searchable, and which member is "second" is a fact about the `.ctl`'s ordering rather than about the game. Write the slot's own name, or give the thing you actually mean a label.

The slot tokens have to *enumerate* for that to hold: digits, or letters running from `a`. `step_x` / `step_y` are the components of a vector, `spr_arrow_l` / `_r` a pair of directions, and neither set has a first member — "for the first step through 200, 150, 100" is ordinary prose about a sequence of periods, not an alias for `step_x`.

Nor is a hyphenated compound modifier an alias. "The second-enemy bonus" names a bonus; the hyphen is you saying `bonus` is the head noun. That entity has a name of its own, and "the enemy B bonus" is worse wording than what you wrote. It is the *referring* use — "the second enemy", naming the enemy — that has to become "enemy B".

An alias with no positional word in it — "the chasing enemy" — is beyond any linter: no tool can know it means `enemy_a` rather than a third enemy. That one is settled when the name is chosen and held by the vocabulary section of the project's `AGENTS.md`.

**Every image macro must produce an image.** A `#UDGARRAY` in the `.ctl` is a claim that a picture appears at that block. The claim is checkable — `make lint-images` compares the filenames the macros declare against the files the site build wrote — and it is not the same claim as "the HTML built". The frame-only `(*name)` defines a frame and writes no file, so a `.ctl` that writes it in place of `(name)` builds green and publishes no image. Write `(name)` to publish the image, `(name*frame)` to publish it *and* define the frame for a `#FRAMES` animation; `(*frame)` alone publishes nothing and is only ever an ingredient of an animation that does.

## Where an `N` note can land

Two placement rules, both enforced by checks that name neither, and both hit when moving a fact out of a description into the body.

**An `N` sits after the entry's `@ … label=` line, never before it.** `lint-instruction-order` reads the directives at an address in order and fails on a note that precedes the label.

**Attach it to an unlabeled row.** A note on a *labeled* address reads as that label's own behavior, and `lint-label-namespace` then wants the label renamed to match what the note says. Land it on a row inside the block instead, and the note describes the act rather than renaming the entry.

The pair matters because a cross-reference sometimes has to live in the body rather than beside a render — a data block's render exemption needs its partner named by `#R`, and stripping that sentence from the prose beside the clip closes the exemption from another file. Put the link back somewhere in the body, under these two rules, and both checks pass.

## Register annotations and cross-references

Mark a routine's intentional inputs and outputs like function parameters:

```
R $ADDRESS I:A object type to spawn
R $ADDRESS O:HL address of the allocated slot
```

Document only registers that are real parameters, not every register the body touches.

Every row names its register: `O:` with nothing after the colon is not a row. Say that result in the description.

One register per row, always. `R $ADDRESS I:HL destination, DE source, B byte count` is three rows: one `I:HL`, one `I:DE`, one `I:B`. Never list several registers in a row's description, never put two `I:`/`O:` fields in one row, and never describe the registers of a routine in its `D` or `N` prose instead of rows. The same goes for a description that says "HL and DE ...". A reader scans the register table by the register column.

The text of a row is a noun phrase in one style across the project:

- It starts in lower case and ends without a full stop: `I:HL address of the message (a $FF byte ends it)`. A leading digit, `$`, `#R` or an acronym (`Z`) is not a capitalized word.
- It says what the register holds, with the encoding or limit that matters: `I:C row count (0 draws none)`, `O:A 1 when the door is locked, 0 when open`. A bare noun (`destination`, `attribute`) fails; `unchanged` is the one one-word row, for a register the routine preserves.
- Routines that do the same job at different sizes carry parallel rows.

`make lint-registers` gates all of it: one register per row, a lower-case phrase, no final full stop, no one-word role.

In comment text, reference addresses with `#R$XXXX` (SkoolKit resolves it to the label) and register names with `#REG` macros (`#REGhl`, `#REGbc`, `#REGde`, `#REGa`). The `I:`/`O:` fields in `R` directives use bare register names — that is SkoolKit syntax — but in prose always wrap them.

## Validation rules

The build runs ten `.ctl` linters; violations fail the build. The first four keep the `.ctl` mechanically consistent so diffs stay clean and `sna2skool` never silently reorders; the last six hold it to the contracts above.

1. **Address order** — every directive in ascending address order.
2. **Instruction order** — directives at the *same* address follow the canonical sequence: `@` → block type (`c`/`b`/…) → `D` → `N` → `R` → line comment.
3. **No redundant lengths** — a line comment's `LENGTH` must not equal the gap to the next documented address.
4. **Label length** — 24 characters, fixed by renaming.
5. **Block identity** (`validate_ctl_identity.py`) — every entry titled, every sub-directive described or labeled. See [Nothing anonymous](#nothing-anonymous).
6. **Data-block schema** (`validate_ctl_data_structure.py`) — every data entry tiles and declares its stride. See [The tiling contract](#the-tiling-contract).
7. **Publication** (`validate_ctl_publication.py`) — every published page inside the program image, no structure cut into a run of same-titled pages, no `t` entry holding something that is not text, no `b` or `u` entry over bytes the code writes, and no entry whose title, description or label denies a writer the listing shows. It takes the generated `.skool` as well as the `.ctl`, because the store instructions are what settle `b` against `g` — and what settle the sentence. See [One page per thing](#one-page-per-thing).
8. **One name per entity** (`validate_prose_names.py`) — prose names a labeled slot family's member by its label, never by its position. See [One page per thing](#one-page-per-thing).
9. **No recited lengths** (`validate_ctl_byte_counts.py`) — an instruction comment must not state the size of the span it works on; a rate ("6 bytes per enemy") is the exemption. See `references/comment-style.md`.
10. **Array elements** (`validate_ctl_array_elements.py`) — every record of an array of records is named on its own line, and a span that is not a record array is exempt by a declaration rather than by assertion. See [Data structures and tables](#data-structures-and-tables).

A twelfth check, `validate_rendered_images.py` (`make lint-images`), gates the built site rather than the `.ctl`: every image macro must name an output file, and every named file must be under `html/`. It runs after `make html`, because its subject is what the build produced.

Run the `.ctl` ones yourself while editing (`python3 scripts/validate_ctl_address_order.py {game}.ctl`) rather than waiting for the full build.

Checks 5 through 10 land red on a mature `.ctl`, so a project records the findings it starts with in `lint-baseline.txt` (`make lint-baseline`) and the gate holds that line: a finding the file does not list fails the build, and a line it lists that the check does not report fails the build too, so a fix takes its baseline entry with it in the same commit. The file only ever shrinks. Never hand-edit it to silence something you introduced — see [build-verify.md](build-verify.md#the-known-failing-baseline).
