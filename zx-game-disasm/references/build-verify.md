# Stage 4 — Build and verify

The verification is what separates a real disassembly from a plausible-looking one. The source must reassemble to the *exact original bytes*. This stage runs on every documentation pass, not just at the end — it is the seatbelt that catches a mis-typed `@isub` or a wrong block boundary the moment it happens.

## The round-trip

The chain, top to bottom:

```
snapshot (.z80)
  ├ extract_bytes.py → {game}.pristine.bin .............. the ground truth
  └ sna2skool.py  (+ {game}.ctl) → {game}.skool
       └ skool2asm.py → {game}.asm
            └ pasmo --bin → {game}.bin .................. the reassembled bytes
cmp {game}.pristine.bin {game}.bin ....................... must be identical
```

Two independent assemblers see the source: SkoolKit (`skool2bin`/`skool2asm`) and `pasmo`. Agreement between an extracted-from-snapshot binary and a reassembled-from-source binary is strong evidence the disassembly is faithful.

`scripts/extract_bytes.py` pulls the program region straight out of the snapshot:

```
python3 scripts/extract_bytes.py {game}.pristine.z80 {ORG} {SIZE} {game}.pristine.bin
```

Then `cmp {game}.pristine.bin {game}.bin` must print nothing. Any difference is a real defect — chase it before documenting further, because every comment past it describes bytes that may be wrong.

**`make` is the gate — the single one.** A unit of work is green only when the full **`make`** (the default `all` target) passes. `make` drives every check: the round-trip `cmp`, the `.ctl` linters, *and* the HTML build — and `skool2html` is the only step that reads the `.ref` catalogs and validates their content (the `#R` cross-references and the image/audio macros). It is not slow, so there is no separate "verify" target to run instead; a green `make` is the thing you can hand back at any moment for the user to build, boot, and steer. Run it after every small increment, and never report "green" or commit a checkpoint without it — a dangling `#R` in `sound.ref` or a malformed macro in `graphics.ref` only shows up in `make`, not in the round-trip alone.

(`make verify-frag` is the one narrower check, because it serves a need `make` cannot: it round-trips a single Worker's fragment in an isolated temp dir, safe to run alongside other Workers in a parallel fan-out. It is a pre-check before a Worker reports; the Manager still proves the integrated result with `make`.)

### What the round-trip does NOT prove

The round-trip proves one thing: the bytes are faithful. It proves *nothing* about whether your code/data map or your data-structure boundaries are correct. Mislabeled bytes still round-trip perfectly — the bytes are identical no matter how you label them. If you split a 5-byte table as 4 bytes and fold the 5th into the next block, mark a sprite row as a table entry, or disassemble a jump table as code that happens to reassemble to the same bytes, the `cmp` stays silent.

So byte-fidelity and *semantic* accuracy are two independent axes, and `make` green only covers the first. Validate the second from how the code actually uses the data:

- **Table lengths and array extents** come from the code that indexes them — the maximum index reached, the loop count, the stride. A table read with a 0–4 index is 5 entries; do not guess its end from where the next recognizable thing starts.
- **Sprite and tile extents** come from the draw routine — rows drawn, bytes per row.
- **A boundary you cannot pin from usage is genuinely ambiguous** — for example a data table whose only indexer is never called, so nothing reveals its length. When that happens, do not silently commit to a boundary and move on. Document the uncertainty (an `N` note: "table length unverified — no caller observed; assuming N entries from the layout") so a reader knows it is a guess, and the next pass or the user can resolve it. A confident wrong boundary reads as fact; an acknowledged guess invites correction.

## The Makefile

The project's `Makefile` carries **no build logic**. It sets the game's name, the five numbers, and a floor, then `include`s the skill's shared framework (`$(SKILL)/tools/disassembly.mk`) — exactly how SkoolKit's own disassemblies include `$(SKOOLKIT_HOME)/tools/disassembly.mk`. All the rules (`gate`, `verify-frag`, `coverage`, the linters, `html`) live in the framework, so a project stays a dozen lines and a framework fix reaches every game without re-copying — no stale vendored Makefile. Start from `assets/Makefile.template`:

```
GAME = {game}
ORG  =            # program origin
SIZE =            # program length in bytes
PC   =            # entry point
SP   =            # stack pointer
RELOC_FLOOR = 0x5B00   # refs at/above must be labels (below = ROM/screen)

ifndef SKILL
    $(error set SKILL to the zx-game-disasm skill directory)
endif
MK = $(SKILL)/tools/disassembly.mk
ifeq ($(wildcard $(MK)),)
    $(error $(MK): not found — set SKILL to the skill directory)
endif
include $(MK)
```

The framework locates the skill's `scripts/` relative to itself, so the project never points at them. `make` is incremental — run plain `make` while iterating, not `make clean && make`. The first run downloads and converts the tape (slow); after that only what you changed rebuilds. Plain `make` runs the round-trip, the linters, and the HTML build — the whole gate; `make clean` removes every generated file (`.skool`, `.asm`, `.bin`, `.z80`, `html`).

The default `make` builds the HTML site too, so one command produces the whole deliverable. It degrades gracefully: with no `.ref` files yet it is a basic site from the skool alone, gaining the catalog/reference pages as the `.ref` files appear.

### The toolchain the gate runs

The framework runs its tools from `PATH`. The recipes invoke a **variable** per tool — `$(SNA2SKOOL)`, `$(PASMO)`, … — so add a tool by adding its variable, never by writing the bare name into a recipe.

Before anything runs, `disassembly.mk` **preflights** the executables the requested goal can invoke and stops naming the ones it cannot find:

```
disassembly.mk:<line>: *** toolchain incomplete — not executable on PATH: bin2sna.py
skool2asm.py skool2html.py sna2skool.py tap2sna.py. The SkoolKit tools come …
```

The check runs while the makefile is *read*, before make compares one timestamp, because an absent toolchain is not a state in which "every target is up to date" carries any meaning. With nothing installed and nothing stale, make runs no recipe, invokes no missing tool, and exits 0 — and that 0 reads as proof of a round-trip that never ran.

The required set is **per goal**, so a goal is never blocked by a tool it cannot reach: `coverage`, `lint-comments` and the linters need SkoolKit alone and build on a machine with no assembler; `bin2tap.py` is required by `tap` and by nothing else. `clean` and the `.ctl`-only linters require nothing, and `gate` is exempt so it reaches its own recipe — it re-enters make for the build, the sub-make is preflighted, and the gate turns that failure into its verdict line. A goal the table does not name — a file target, or one a project added — is held to the default build's set.

### Reading the gate's result

**A build is green when `make` exits 0 — never because its output looks green.** Run the gate bare and read the status:

```
make                    # then check the exit status ($?)
make gate               # or: same gate, logged, ending in one verdict line
```

`make gate` runs the full gate into `build/make.log` (the ignored build directory), prints the last 40 lines plus an unmistakable verdict on failure, and exits with make's own status. A passing verdict names the SkoolKit that produced it and says **which** of two passing states it is:

```
GATE PASS, REBUILT [SkoolKit 10.1] — at least one generated file was regenerated from source; the round-trip cmp and the linters passed. Which files rebuilt is in the log: build/make.log
GATE PASS, NOTHING REBUILT [SkoolKit 10.1] — every generated file was already current; the round-trip cmp and the linters re-ran over the existing build, nothing was regenerated from source (log: build/make.log)
```

The gate asks make (`make -q`) whether any generated file is out of date *before* it builds, and reports that answer. It is a real distinction: `all` depends on the phony `test`, `lint` and `html`, whose recipes run every time, so a green `make` always means the `cmp` and the linters passed — but it does not by itself mean the `.skool`, the `.asm` or the `.bin` under them came from the sources as they stand now.

**`REBUILT` says "at least one", and that is all `-q` can say.** It is one bit over the whole artifact set, not a per-file answer: delete `$(GAME).fixed.z80` alone and the verdict is `REBUILT` while only `bin2sna.py` ran, the `.skool` never regenerated and `skool2html.py` never executed. Read the log for which files actually rebuilt; the verdict only tells you the tree was not entirely current.

**`NOTHING REBUILT` is the weaker claim, and the one to read twice.** It is a legitimate and common state — you ran the gate twice, or changed only a file no target depends on. But it says the round-trip was re-checked over artifacts an *earlier* run produced, and a corrupted incremental state survives it. Make deletes a target whose own recipe fails, so a red build leaves nothing behind — but a file written outside make still can: a redirect run by hand that dies mid-write leaves a zero-byte `.skool` newer than the `.ctl`, which make calls current and which everything downstream then agrees with. Before reporting a checkpoint green off a `NOTHING REBUILT`, make the build do the work — `make clean`, or remove the `.skool` so everything under it regenerates — and read the `REBUILT` verdict over a log that shows the whole chain running.

Also read the version. A gate that passed under a SkoolKit other than the one `requirements.txt` pins proved something about a toolchain the project does not ship.

Two traps make the eyeball check wrong:

- **Parallel branches finish out of order.** Under `-j` the HTML branch can print `touch html/.stamp` while the asm branch is failing, so the *tail* of the output — the natural place to look, since the log is long and full of `pasmo`'s `WARNING: Var … never used` notes — shows a success line for a red build. A `#R` to an unlabeled sub-block address makes `skool2asm` warn (`Could not convert address $7C0D to label`) and fail the `.asm`, and nothing in the tail says so.
- **A pipeline hides the status.** After `make | grep … | tail`, `$?` is *tail's* (bash's `PIPESTATUS` holds the rest). A scripted check through a pipe reports the wrong process. Redirect to a file and grep the file, or use `make gate`.

### Proving a range of commits green

"Green at every commit" is a claim about *history*, and the tip building proves only the tip. To back it, build each sha in a separate worktree, cleaning between checkouts so no generated file from one commit satisfies the next (POSIX shell):

```
git worktree add --detach ../gate-check HEAD
for sha in $(git rev-list --reverse <base>..HEAD); do
    git -C ../gate-check checkout -qf $sha
    git -C ../gate-check clean -qfdx
    make -C ../gate-check gate >/dev/null || echo "RED: $sha"
done
git worktree remove --force ../gate-check
```

This is a sanctioned use of a worktree. A *Worker* still never gets one, see `references/roles/manager.md`. Without this loop, the honest report is that the tip is green and the history is unverified.

`checkout -qf` is load-bearing. Plain `checkout` refuses only when the switch would *overwrite* a modified tracked file; where the file is byte-identical in both commits it carries the modification along silently, so the loop builds content that is in no commit and reports the verdict against a sha. A failed gate can leave the tree modified, which is exactly when someone runs this — and it fails in both directions: an edit that breaks the build reports every sha RED, one that fixes it reports a genuinely red commit green.

## When the bytes legitimately differ

Occasionally the *ideal* source and the *original* bytes disagree for a defensible reason — the original has a corrupted sprite byte, or you want the source to read correctly while still reproducing a quirky original. SkoolKit's fix directives let the source carry the clean form while the round-trip still matches:

- **`@isub`** — substitution applied when assembling (`-f 1` and up). Use it for the symbolic-constant substitutions of stage 3.
- **`@ofix`** — an original fix: the byte SkoolKit should emit to match the original even though the disassembly shows something else.

The framework builds *two* variants to keep this honest: a `non-fixed` source whose bytes must already match the original (proving no accidental drift), and a `fixed` source that applies the intended `@isub`/`@ofix` directives. Both must round-trip. If you only ever build the fixed variant you can hide a real mismatch behind a fix directive — so verify the non-fixed binary against the pristine one too.

## The linters

`make` runs six `.ctl` linters (also runnable standalone as `make lint`, or from `scripts/`):

- `validate_ctl_address_order.py` — directives in ascending address order.
- `validate_ctl_instruction_order.py` — at one address: `@` → block type → `D` → `N` → `R` → line comment.
- `validate_ctl_lengths.py` — no line-comment `LENGTH` that just restates the gap to the next entry.
- `validate_ctl_label_length.py` — labels within 24 characters.
- `validate_ctl_identity.py` — every entry titled, every sub-directive named.
- `validate_ctl_data_structure.py` — every data entry tiles and declares a stride.

The first four exist because a `.ctl` that drifts out of order still *builds* but produces confusing diffs and makes `sna2skool` output unstable. Keeping the file canonical means a one-line documentation change shows up as a one-line diff. The last two are content checks, and they carry a baseline — see below.

### The block-identity check

`make lint-identity` runs `scripts/validate_ctl_identity.py` and refuses a block a reader cannot identify. Three kinds:

- **UNTITLED** — a block directive with no title, following a data entry. It publishes under SkoolKit's default heading for its type — "Data at 5B08" for a `b` or `w` entry, "Text at" for `t`, "Game status buffer entry at" for `g`, "Unused RAM at" for `s` and `u`. Two causes need opposite fixes: one field that a stray block directive split out of the record above (delete the block directive), or a structure that was never titled (write the title). *The check does not choose between them.* No property of the directives tells them apart: a stray split and an untitled structure can both sit contiguously after the entry above, carry several labeled fields, and hold one to three sub-directives. So the message states both fixes and names the record, and the author answers the question it asks: are these bytes fields of that record? Guessing wrong in the fold direction buries a real structure inside an unrelated entry.
- **UNTITLED_ENTRY** — the same, but following code or opening the file. There is no record to fold into, so the fold is not available and the title is the fix.
- **UNDESCRIBED** — a sub-directive with no description anywhere and no `@ label=` on its address.

The trailing `i` block is exempt from the title rule: it publishes no page.

**What discharges UNDESCRIBED, and what deliberately does not.** A sub-directive is identified if it carries a description — trailing text, or a line comment at an address inside its span — *or* if its address carries an `@ label=`. The label names those exact bytes, renders on that row of the listing, and makes the span reachable by name from anywhere.

The entry's own title, `D` or `N` does **not** discharge it, however completely the schema is stated there. That is the exemption the check exists to refuse. Picture `S $7E04,2` and `S $7E07,1` as anonymous fill inside a player-state record whose `N` says "+4/+5 are the X/Y speeds" and "+7 is the frame counter": the schema is on the entry, the bytes are still anonymous, and neither is reachable by absolute address. Accepting "it is obvious from the record above" accepts exactly that.

Nothing else catches either form. Both round-trip, both tile, both can be fully labeled, and `coverage` reports NAMING 100% over a titleless block because it counts labels, not sentences.

### The data-block schema check

`make lint-data-structure` runs `scripts/validate_ctl_data_structure.py` over the `.ctl` and holds every data entry — every block type but `c` and `i` — to a **tiling**: starting at the block's address, its sub-directives cover every byte exactly once and sum to its size.

The defect it exists for is code annotated as an undifferentiated byte span. That reads as clean under every other check — the `-s` gate inspects operands and these are data, `coverage_report` counts the span as documented bytes — while nothing in it relocates. Prose is free: it can describe a span convincingly without committing to one verifiable claim about its layout. The tiling is that claim, in arithmetic.

Four checks:

- **UNTYPED** — a block with no sub-directives, or a `B`/`W`/`T` span with no sublength, over the scalar threshold (8 bytes). *This is the first failing case and the one that matters*: the defect is a block with no sub-directives at all, so a rule written as "sub-directives must be typed" misses it entirely.
- **ZEROFILL** — needs `--bin`: an all-zero span over the threshold that is enumerated as a stride rather than declared a buffer. Nothing checks a stride over zeros (`162 % 2 == 0` passes for any even length), so `B $x,162,2` renders 81 rows of `DEFB $00,$00` and verifies nothing; `S $x,162` is one `DEFS` and states the claim the image can settle. It is scoped to the *span*, so a per-byte scalar carrying its own comment is untouched — a listing line is earned by what it documents, not by the bytes it holds.
- **TILING** — gaps, overlaps and leftovers against the block's size.
- **DIVISIBILITY** — `len % sublen == 0`. A list of 2-byte words cannot be 7 bytes.
- **POINTER** — needs `--bin`: a `B` span whose byte pairs all resolve to declared addresses is a pointer table wearing the wrong type. `W` makes it relocate.

A block drawn by an image or audio macro (`#UDGARRAY`, `#SCR`, `#FONT`, `#AUDIO`) is exempt from UNTYPED — the macro is the schema and the render proves it. Nobody should index 6144 screen pixels or 50 pitch periods to satisfy a linter.

The macro usually sits in the block's own prose. A beeper sound is the case where it cannot: the sound is code *plus* data — the table holds the pitch periods, the routine holds the cadence and cycle counts — so only the routine can produce it and the `#AUDIO` belongs there, not duplicated onto the table. Such a table reaches its render through the `#R` the author already wrote, on two conditions: the link is **mutual** (table and routine name each other), and the partner is a **code** block. Both are load-bearing. One-way would let an incidental `#R` to a noisy routine exempt a real blob; and a render on *data* draws that block's own bytes, so without the code condition a working sprite copy gets exempted by the source bank it is filled from — they name each other, the source is drawn, and the copy still holds whatever the capture caught.

The exemption reads a macro's presence, not its extent.

**The contract is on the entry, not on the letter that groups its page.** What an undeclared byte renders as does differ by type — `DEFS` under `s`, `DEFB` under `b`, `g` and `u`, `DEFM` under `t`, `DEFW` under `w` — but only under `s` is it unused space. Under every other type it is published as data on a page whose title implies the block was digested, with no directive anywhere claiming it, which is worse than a visible hole. A `u $C748` titled "Undetermined 5-byte block" that carries one `B $C748,5` while the entry runs on to $CFFF publishes everything past that directive as `DEFB`, declared by nothing.

`w` is the exception to UNTYPED, and only to UNTYPED. Its bytes render one `DEFW` per word whether or not a `W` directive repeats that stride, so "declare the stride" is a demand for a directive that changes nothing published; and a word that names a labeled address assembles as that label, which is the relocation an untyped byte span costs. A `w` entry still has to tile, and what its words owe beyond that — do they group into records, is each element annotated — is `make lint-array-elements`' question.

**Honest limit: tiling proves accounting, not meaning.** A wrong stride that happens to divide will pass, and a mis-typed field will tile. It is necessary, not sufficient. Its job is to make an unparsed span impossible to leave behind — not to prove the parse is right. Only the render, the round-trip and the relocation proof test meaning.

### The known-failing baseline

`lint-identity` and `lint-data-structure` land red on a mature `.ctl`. That is not a reason to keep them out of the gate — it is the reason the baseline exists.

Left advisory, a check is never run: a defect it reports ships under `make gate` printing GATE PASS, while the check has the defect in its output the whole time.

So both checks are in `lint`, and a project records the findings it starts with:

```
make lint-baseline        # writes lint-baseline.txt from the current findings
```

`lint-baseline.txt` lists one accepted finding per line, as `<check> <KIND> <$ADDRESS>  <message>`. The first three fields are the key; the message is for the reader. Four rules give it its shape:

- a finding whose key the file does not list **fails the build** — that is the new defect, and it is the whole point;
- a line the file lists that its check no longer reports **fails the build too**, so a fix takes its baseline entry with it in the same commit and the file cannot rot into a permanent excuse;
- a key is only compared against the check that wrote it, so a project may baseline one check and gate another cleanly;
- a key may repeat, and the count is part of the comparison: two findings of one kind at one address are two lines, and a third fails the build.

The key is the *address on the directive the finding points at* — never the line number, which churns on every unrelated edit above it, and never the message, which changes when a neighboring directive resizes. Counting repeats is what stops that address-only key from swallowing a second finding where one is already listed. Splitting an undescribed `M $7E04,2` into `M $7E04,2` plus `B $7E04,1` leaves two findings at `$7E04` against one accepted line, and the build fails — while a directive that merely moves down the file keeps its key and its count.

**The file only ever shrinks.** Regenerate it when a fix clears a finding — the shrunk file is the evidence, and the diff is how the debt is visible in review. Each check rewrites only its own lines, so re-recording one leaves the other's alone. Every run names the keys it adds and the keys it drops:

```
identity: recorded 26 finding(s) in lint-baseline.txt
identity: 1 key(s) NOT in the previous baseline — a key this file gains is debt
taken on, not debt inherited:
  + identity UNDESCRIBED $7F29
```

Regeneration is routine, which makes a silent one the realistic way a defect gets buried, so the names are the point: a run that adds a key is a run to throw away. Never hand-edit the file to silence something you introduced either — the diff would show it growing, which is the same signal from the other direction.

A project with no `lint-baseline.txt` is gated on everything, which is the right default for a new disassembly. Adopt the baseline only where the findings predate the check.

### The comment-quality pre-filter (advisory)

`make lint-comments` runs `scripts/lint_comments.py` over the generated `.skool` and flags three mechanical comment defects a green build never catches: a comment on a bare `RET`, a comment that only restates the instruction, and a placeholder label (`work_b`, `helper_8e3a`, `L5B50`). The same command takes the `.ref` catalogs and `spec/*.md` and sweeps them for investigation and emulator vocabulary ("verified live", "under emulation", "not fully pinned") — those pages reach the same reader as the `.skool`, and an unswept one is where a claim sourced from a run survives. It also counts `OPEN`: the typed uncertainty markers (`(unverified)`, `TODO:`) that are *correct* where they stand and say the work behind them is unfinished — `make coverage` keeps a project short of the bar while any remain. It is **advisory** — kept out of `make` — because a flag is a prompt to review, and a `RET` note occasionally carries a real return-state contract that an expert keeps. The Challenger runs it and decides.

It is deliberately small. The two checks that matter most are not scriptable and are the Challenger's responsibility, not the linter's:

- whether a comment adds what the code cannot show (needs comprehension), and
- whether a multi-line `{ }` comment spans *exactly* the instructions it describes — the comment text is word-wrapped across the grouped lines, so the per-instruction checks skip braced groups entirely and leave their span to an expert reading.

Relocatability (a raw address in a comment) is not re-checked here: `skool2asm --create-labels` already emits "Comment contains address …" and the build fails on it, which is both authoritative and more precise than a regex.

### The coverage report — the "is it done?" gauge

`make coverage` runs `scripts/coverage_report.py` and answers the question a green build cannot: *how close is this to the documentation bar?* A green, fully-labeled project is **breadth**; this measures **depth**. It reports, per code routine, whether the body is *explained* (commented at the right altitude), *skeletal* (a description over a bare body — the breadth-only trap that gets mislabeled "mature"), or *bare*. It also gauges the **catalog and audio**: how many catalog entries are still identified by an auto-label (`f9440`) rather than named; whether the game has sound code (speaker writes) but no `#AUDIO`; and the `#TABLE` and placeholder-label counts. A draft catalog or unrendered sound fails the gauge as surely as skeletal code does.

It **auto-discovers** the project's `.ctl` and *every* `.ref` file beside the skool, and prints what it scanned — so the catalog and audio counts never read as zero just because a caller forgot to pass `graphics.ref` or the project splits its sections across differently-named ref files. Catalog and audio content is found by **section type** (`[Graphic:]`, `[Audio:]`, `#AUDIO`, `#UDGARRAY`) wherever it lives; the filenames (`graphics.ref`, `sound.ref`) are a convention, not a requirement. So `coverage_report.py <game>.skool` alone gives the full picture; a missing-file false negative is not possible.

It counts **code only**: data blocks (the loading screen, level data, tables) are excluded, because data is documented by labels and native devices, not line comments — so the figure is not an average over code and data. Line density is shown only as a rough cross-check, never as the bar; the real signal is the fraction of routines with an explained body. The Manager runs this before reporting completion, and does not call a project mature while it says otherwise (see `references/roles/manager.md`). Whether each comment is *correct* and the catalogs and spec *complete* remains the Challenger's call.

## Reading build warnings

The `skool2asm` step is configured to fail on `WARNING`, because the warnings that matter here are not cosmetic:

- **`overlapping instruction`** — a block boundary or a comment length falls mid-instruction. The map is wrong; fix the block type or the length in the `.ctl`.
- **Unresolved label / address** — a `#R$XXXX` points at an address with no label, or an `@isub` references an undefined constant.

Treat a warning as a failed build. A clean `make` with a silent `cmp` is the only green state.

**Fix or name a warning; do not blanket-suppress it.** When a `skool2asm` warning is a genuine false positive — a deliberate reference SkoolKit cannot resolve, an intentional unlabeled access — silence *that one line* with an **`@nowarn`** directive in the `.ctl`, with a comment saying why. A whole game warrants only a handful of `@nowarn`s. It is the escape hatch, not the default: prefer fixing the map or adding the missing label.

`pasmo` reports a second class — **`WARNING: Var Lxxxx is never used`** — when an auto-label (`L####`, minted by `--create-labels` for a block the `.ctl` never named) is defined but unreferenced. `@nowarn` does *not* touch these (it is a `skool2asm` directive; `pasmo` never sees it). These do **not** fail the build: an `L####` is an unnamed block, and you cannot name a block before you have disassembled it, so early on the map is full of them. Naming is **progressive** — `make coverage` reports it as a percentage (`NAMING: 94% of labels named, 59 auto-labels remain`), and **100% is a done-criterion, not a per-commit gate**. Name each block as you derive it; reach 0 auto-labels before claiming the work mature. Name an unreferenced block `data_unused_<addr>`; a *named* unused symbol still draws a `pasmo` "never used" note, and that is fine; the gauge counts only the `L####` kind.

## Relocatability: a green build does not prove it

`skool2asm --create-labels` makes *code* references (JP/CALL/JR targets) relocatable on its own, and it warns ("No label for address") when a referenced address is a *line-start* in a block but has no label. It does **not** warn when a reference points at an address *inside* a multi-byte data line (mid `DEFB`/`DEFW` run). Those references render as raw hex (`LD A,($XXXX)`), are not relocatable, and the build stays green and warning-clean regardless. So a clean build proves the bytes are faithful but not that the source is relocatable — a third axis beyond the semantic one in *What the round-trip does NOT prove*.

To make a program-body data variable relocatable, split its block so the variable is its own labeled element; the reference then resolves to a label. Expect a cascade: splitting a packed block exposes each neighboring referenced byte as a new line-start that needs its own label.

Policy — label the program's own code and data, keep fixed hardware absolute:

- **Label** the program's body and its own data, including a variable block that lives in repurposed RAM. The label also names the runtime state for a reader or an agent-trainer, so it doubles as documentation. For a game that takes the machine from a floor (e.g. `$5B00`) up, **not one** absolute reference may point at or above that floor.
- **Keep absolute** genuinely fixed hardware addresses *below* the floor — the ROM (`$0000-$3FFF`) and the screen and attributes (`$4000-$5AFF`). These do not move with the program, so naming them adds nothing.

### References that don't land on a boundary — the `LBL+1` technique

Splitting a block works when the target byte *can* become a line-start. Some cannot: a reference into the **operand of an instruction** — self-modifying code that patches a `CALL`/`LD` operand, or an overlapping-instruction trick where a jump lands on the second byte of the previous instruction. You cannot put a label mid-instruction, and `--create-labels` leaves the operand raw. Sort each raw operand into one of three fixes:

- **A data-block field** → split the block and give the field its own exact-address label. Resolves in the default build, no offset needed.
- **Working RAM above the program image** (buffers the game never ships) → an `@equ` constant, referenced as `base+offset`.
- **Mid-instruction in code** (SMC, overlapping instructions) → the **`LBL+1`** technique: label the *instruction's* line-start, then rewrite the raw operand to `label+offset` with an **`@ssub`** directive — SkoolKit does **not** emit it automatically. For a `CALL $0000` at `enemy_handler_call` whose operand the code patches:

      @ssub=LD (enemy_handler_call+1),A

  renders `LD (enemy_handler_call+1),A`, now relocatable. `@ssub` is a *safe substitution* — byte-identical by SkoolKit's definition — so it reassembles to the exact original bytes.

**`@ssub` only renders under `skool2asm -s`.** The default `--create-labels` build ignores it, so the operand still reads raw in the deliverable `.asm` the gauge sees. `-s` (ssub mode) is also a **strict static relocatability gate**: it fails on *every* unresolved in-image address. The framework builds the fixed asm with `-s` **by default** (`ASM_FIXED_FLAGS ?= -s`), so the relocatability gate is the standard, not a per-project opt-in. But it fails while the map is still raw, so a project in the breadth/labeling sweep opts **out** — sets `ASM_FIXED_FLAGS =` (empty) in its Makefile — and runs the whole sweep (data splits, `@equ`, `@ssub`) under the default build first. When no raw in-image reference remains, it removes that line to restore the standard `-s` gate. (`-s` checks instruction operands; an absolute pointer baked in a *data table* still slips past it — see the dynamic check below.)

`scripts/coverage_report.py` reports the static signals — `L####` auto-labels (unnamed blocks) and raw operands at/above the game floor. But a label-clean source is **still not proven relocatable**. The gauge counts *operands*, and four things hide from it:

- an **`@equ` binding a program-owned address to an absolute constant** — a hard-coded address wearing a symbolic name;
- an address stored as **data** (a pointer table held as `DEFB` bytes);
- an address **synthesized from an 8-bit immediate** (`ADD A,$E0` building a buffer page), which no label can even be substituted into;
- **code annotated as a byte blob**, where every operand is data.

A project can read `RELOCATABLE 0`, `NAMING 100%` and every routine body-explained over a program that breaks if a single byte moves.

### Proving it: shift the program and run it

The only proof is dynamic: move the code, rebuild, and confirm it behaves identically under the **`zx-fuse-driver`** skill. Two constraints decide whether the test means anything, and a naive bump of the single `ORG` gets both wrong.

**Shift only the program; the screen must stay put.** The display file is hardware-fixed at `$4000`, and a post-load image begins *with* the captured loading screen, so it starts at `$4000` too. Bumping the one `ORG` drags the screen bytes along, and that tests nothing: the code still writes to the absolute screen address, so the moved copy is inert and any misbehavior is unattributable — a real relocation bug looks exactly like the displaced picture. Insert padding at `RELOC_FLOOR` instead, the boundary the project already declares as the game's own, and verify the screen and attribute bytes are untouched.

**Shift by 257, not 256.** Any multiple of 256 leaves every address's low byte unchanged, so code that manipulates only the high byte keeps working by accident and the defect hides. 257 is the smallest shift that perturbs both bytes of every symbol.

**No headroom? Permute instead.** Check the top before choosing an amount — the image may be pinned there too, with the stack growing down into the gap. An image that fills RAM cannot be shifted anywhere, so reorder its own blocks — `ABC` → `CAB` — choosing a moved block whose *size* has both bytes non-zero. Every block after it is displaced by that size: the same disruption, and it needs not one spare byte. **"The program fills RAM" is never a reason to skip the proof — only a reason to change its form.**

**Keep the image size constant**, reclaiming the inserted bytes from a proven-dead region, so nothing else drifts and the alignment-pinned buffers stay put. A size change invalidates the comparison.

**A floor is not enough: name the fixed-placement regions.** Some work areas are alignment-constrained and must be pinned with their own `org`, exactly like the screen — their addresses are computed from their own page, so moving them breaks the arithmetic that finds them. A pinned region above `RELOC_FLOOR` is one the floor alone calls movable. List them explicitly; pinning one is correct annotation, not a defect.

**The cheap pre-check, before any of this:** list the `@equ` values at/above `RELOC_FLOOR`. Each one is either a genuinely fixed address — screen, attributes, I/O ports, ROM entries, the stack top — or a relocatability hole wearing a name. Anything else should be a label on the block instead.

### When it fails: bisect the anchor, not the amount

The shift *amount* barely matters — a relocation defect breaks the program at 8 bytes as thoroughly as at 128. The amount only tells you *that* something is wrong. To find *what*:

- **Bisect which code moves.** Insert the pad at successively later labels so only code from that label onward shifts. BROKEN means the defect is at or after the anchor; IDENTICAL means before it. Each run halves the span, so a handful of runs narrows it to one routine.
- **Choose an oracle below the shift point.** State inside the shifted region reads at a stale address and reports differences that are entirely your probe's fault — an RNG seed in that region does exactly this. A position or timer in low RAM is a valid oracle; a counter that moves with the code is not.
- **Do not rationalize the residual.** A remaining gap explained as inherent — a slightly slower loop in a game that runs interrupts-off and paces itself by execution speed — is a tidy story that makes it somebody else's problem. A plausible mechanism is not evidence, and a residual that survives a confident explanation is exactly where the bug is.

Claim "relocatable" only when the proof has run, never from a green, label-clean build.
