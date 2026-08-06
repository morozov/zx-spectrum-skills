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

The project's `Makefile` carries **no build logic**. It sets the game's name, the five numbers, and a floor, then `include`s the skill's shared framework (`$(SKILL)/tools/disassembly.mk`) — exactly how SkoolKit's own disassemblies include `$(SKOOLKIT_HOME)/tools/disassembly.mk`. All the rules (the default gate, `gate`, `verify-frag`, `coverage`, the linters, `html`) live in the framework, so a project stays a dozen lines and a framework fix reaches every game without re-copying — no stale vendored Makefile. Start from `assets/Makefile.template`:

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

`make gate` runs the full gate into `build/make.log` (the ignored build directory), prints the last 40 lines plus an unmistakable verdict on failure, and exits with make's own status. Every verdict names the SkoolKit *and the gate* that produced it, and a passing one says **which** of two passing states it is:

```
GATE PASS, REBUILT [SkoolKit 10.1, gate 1/e70342a] — at least one generated file was regenerated from source; the round-trip cmp and the linters passed. Which files rebuilt is in the log: build/make.log
GATE PASS, NOTHING REBUILT [SkoolKit 10.1, gate 1/e70342a] — every generated file was already current; the round-trip cmp and the linters re-ran over the existing build, nothing was regenerated from source (log: build/make.log)
```

The gate asks make (`make -q`) whether any generated file is out of date *before* it builds, and reports that answer. It is a real distinction: `all` depends on the phony `test`, `lint` and `html`, whose recipes run every time, so a green `make` always means the `cmp` and the linters passed — but it does not by itself mean the `.skool`, the `.asm` or the `.bin` under them came from the sources as they stand now.

**`REBUILT` says "at least one", and that is all `-q` can say.** It is one bit over the whole artifact set, not a per-file answer: delete `$(GAME).fixed.z80` alone and the verdict is `REBUILT` while only `bin2sna.py` ran, the `.skool` never regenerated and `skool2html.py` never executed. Read the log for which files actually rebuilt; the verdict only tells you the tree was not entirely current.

**`NOTHING REBUILT` is the weaker claim, and the one to read twice.** It is a legitimate and common state — you ran the gate twice, or changed only a file no target depends on. But it says the round-trip was re-checked over artifacts an *earlier* run produced, and a corrupted incremental state survives it. Make deletes a target whose own recipe fails, so a red build leaves nothing behind — but a file written outside make still can: a redirect run by hand that dies mid-write leaves a zero-byte `.skool` newer than the `.ctl`, which make calls current and which everything downstream then agrees with. Before reporting a checkpoint green off a `NOTHING REBUILT`, make the build do the work — `make clean`, or remove the `.skool` so everything under it regenerates — and read the `REBUILT` verdict over a log that shows the whole chain running.

Also read the version. A gate that passed under a SkoolKit other than the one `requirements.txt` pins proved something about a toolchain the project does not ship.

#### A red verdict says how far from green, not just that it is red

The `.ctl` checks all run whatever any one of them reports, and the verdict names every check that failed with its own finding count:

```
GATE FAIL (make exit 2) [SkoolKit 10.1, gate 1/e70342a] — 3 of 11 checks failed, 60 finding(s): lint-publication 30, lint-byte-counts 20, lint-array-elements 10. The log accounts for 10 of the gate's 11 checks — no sweep reports the other 1, so they did not run. That count is a floor, not the distance to green. Every finding is above in full, not tailed. Full log: build/make.log.
```

That is the line to quote and to store. `1 check failed, 30 findings` and `3 checks failed, 60 findings` are different amounts of work, and a bare RED, or a verdict naming only the first check make happened to reach, cannot tell them apart. Make halts at the first prerequisite that fails, which is why `lint` runs its checks in its own recipe rather than listing them as prerequisites: with them listed, the gate stops at the first check that fails, and the findings of every check after it never reach the verdict.

**On a failing check the findings are printed whole, not tailed.** The tail exists for output nobody can plan against — `pasmo`'s hundreds of `WARNING: Var … never used` lines. Findings are the opposite: each one is a line of work, and a 40-line window over three checks' worth silently drops the ones past it. So the gate prints every check's output from the first check's banner to its summary line, and falls back to `tail -40` only when what failed was the build.

**The denominator is the gate's own total**, not the number of checks this run got to. Which sweeps run depends on what failed and on the scheduler, so a denominator taken from the run itself moves between two runs of the same tree — and a stored column of verdict lines then compares nothing. What did not run gets its own clause instead.

Four clauses appear when they apply, and each is there because its absence would make the count read as more than it is:

- **`The log accounts for N of the gate's 11 checks`** — no sweep reported the rest, so they did not run. The count in front of that clause is a **floor**. Clear the named checks and re-run before planning against it.
- **`(could not run)`** against a check, where a count would be — the check exited a way it does not define, so it was called wrongly or died before it could report. It has no finding count, and that is not a finding count of zero.
- **`(crashed)`** — the check printed a traceback. It exits the same way a check with findings does, so it is caught by its output rather than its status; what is above it is a stack trace, not work.
- **`(count unread)`** — the check failed and printed no count the gate could read. Its findings are in the output above; the total does not include them.

A build failure reads as one, and it reads as one whether or not any check also went red. The round-trip `cmp` and the `.asm` come before the checks in `all`'s prerequisite list, so sequentially a failure in either stops the run before a check has started:

```
GATE FAIL (make exit 2) [SkoolKit 10.1, gate 1/e70342a] — the build failed before any check ran, so no check has a finding count and none of them is what failed; the build's last 40 log lines are above. Full log: build/make.log.
```

That order is a sequential order only. Under `-j` — which nobody has to type, an inherited `MAKEFLAGS=-j4` is enough — `test`, `lint` and `html` are siblings, so a full sweep of findings can complete after `cmp` has already failed. Both are then in the log, and the gate leads with the build:

```
GATE FAIL (make exit 2) [SkoolKit 10.1, gate 1/e70342a] — the build itself failed (test), which is what to fix first: a finding count is a distance to green only over a tree that builds. 1 of 11 checks failed, 3 finding(s): lint-label-length 3. The build's last 40 log lines are above, then every finding in full. Full log: build/make.log.
```

`(test)` is the failing target make named. Read that clause first and stop planning against the counts after it: they were measured over a tree that does not build.

A failure after the checks — the site will not build, a dangling `#R` or a malformed macro in a `.ref` does it — gets the third wording:

```
GATE FAIL (make exit 2) [SkoolKit 10.1, gate 1/e70342a] — every check that ran was clean, so this is the build failing rather than a finding; its last 40 log lines are above. Full log: build/make.log.
```

This is deliberately narrower than `make -k`. `-k` continues past *any* failed target, so a broken round-trip stops stopping the build — and what it continues past differs between make versions. What has to survive a first failure is the set of independent checks, not the build. So the checks aggregate and the build still halts, and the verdict — not the halt — is what keeps a one-line `cmp` from arriving buried among findings when `-j` ran them side by side.

#### The marker: which gate produced this verdict

PASS and FAIL are relative to a gate that moves independently of the project, so a verdict that does not name its gate stops meaning anything the moment either side moves. `gate 1/e70342a` in the sample verdicts is that name, in two halves:

- **`1`** — the generation the skill declares, in `SKILL.md`'s frontmatter (`metadata: gate:`). A human raises it in the same commit that changes what the gate accepts or rejects: a new gating check, a check that gains a finding kind, a rule that widens. It is the only half that says a changed verdict was *meant* to change, and it is what to cite.
- **`e70342a`** — a digest over the skill files the build runs and reads (`tools/`, `scripts/`, `assets/`; not `references/`, so editing prose does not move it). Nobody maintains it, and it moves on any edit to those files.

The two together are what makes the declaration trustworthy without anyone auditing it. One declared generation over two digests says the bytes of the gate moved and nothing was declared — which is how a lagging declaration becomes visible, instead of being taken on trust. A marker nobody updates is worse than none, because it reads as authoritative.

The digest is deliberately wider than the gate, and it errs on the safe side. It covers `scripts/` whole, and not every script is on the gate's path: `coverage_report.py` runs under `make coverage`, which `all` never invokes, so editing it moves the digest while what the gate accepts is untouched. A digest that moved when the gate's behavior did not costs a reader one comparison; one that sat still while a check changed is the whole failure this marker exists to prevent. So read a moved digest as *the gate's files moved* — the declared generation is what says the behavior did.

The digest is taken from file contents, never from `git rev-parse`. The skill is consumed through a symlink, a copy, or a checkout, and only the files are guaranteed: a copy is not a repo and has no revision to read, while a digest reads the same there as in the checkout it was copied from. Every part of the marker degrades to a word rather than to a failure — an unreadable `SKILL.md` gives `gate undeclared/…` and a machine with no `shasum`/`sha256sum` gives `…/unknown` — because a project whose marker cannot be read must still build.

`lint-baseline.txt` carries the same marker in its header, written by `make lint-baseline`, and the gate compares the two. When they differ the verdict says so, on a pass and on a failure both:

```
GATE FAIL (make exit 2) [SkoolKit 10.1, gate 2/3f19c04] — 1 of 11 checks failed, 4 finding(s): lint-array-elements 4. … Full log: build/make.log. lint-baseline.txt was recorded under gate 1/e70342a, so a finding this gate reports and that one did not is the gate moving, not this commit regressing — see the gate-boundary rule in references/build-verify.md.
```

A tree with **no** `lint-baseline.txt` gets its own clause, on a failure only — a commit that predates the baseline fails that way, and on a pass the absence is the right default for a new disassembly rather than something worth saying:

```
GATE FAIL (make exit 2) [SkoolKit 10.1, gate 2/3f19c04] — 4 of 11 checks failed, 50 finding(s): lint-data-structure 10, lint-publication 20, lint-names 10, lint-byte-counts 10. … Full log: build/make.log. There is no lint-baseline.txt in this tree, so this run accepted nothing — a commit that predates the project's baseline fails a gating check the way a regression does; see the gate-boundary rule in references/build-verify.md.
```

That clause is the difference between a red gate you investigate and one you can place in a sentence. Read it before reading the findings: **a red gate whose baseline was recorded under a different gate, or which has no baseline where the project has one, is not evidence about the commit.** It is also what makes the wrong fix unattractive — regenerating the baseline so the live gate passes bakes a different gate's checks into this project's accepted debt.

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
    verdict=$(make -C ../gate-check gate 2>/dev/null | tail -1)
    echo "$sha  ${verdict:-NO VERDICT (make could not run)}"
done
git worktree remove --force ../gate-check
```

This is a sanctioned use of a worktree. A *Worker* still never gets one, see `references/roles/manager.md`. Without this loop, the honest report is that the tip is green and the history is unverified.

`checkout -qf` is load-bearing. Plain `checkout` refuses only when the switch would *overwrite* a modified tracked file; where the file is byte-identical in both commits it carries the modification along silently, so the loop builds content that is in no commit and reports the verdict against a sha. A failed gate can leave the tree modified, which is exactly when someone runs this — and it fails in both directions: an edit that breaks the build reports every sha RED, one that fixes it reports a genuinely red commit green.

**Keep the verdict line, not just the red or the green.** The verdict is the last line the gate writes to stdout — make's own `*** Error 2` goes to stderr, which is why the loop drops stderr rather than folding it in — and it names the SkoolKit and the gate the run used, reports a baseline recorded under a different one, and carries the failing checks with their finding counts. A stored `RED: 4cf467a` is uninterpretable a week later; a stored `4cf467a  GATE FAIL (make exit 2) [SkoolKit 10.1, gate 2/3f19c04] — 3 of 11 checks failed, 60 finding(s): … recorded under gate 1/e70342a …` places itself, and a column of those lines is a backlog rather than a tally of reds. The denominator holds still across the column — it is the gate's 11, not the number of checks a given run reached — so two lines differ only where the tree differs.

The `${verdict:-…}` default covers the worst case, which is the one the loop must not print blank: a commit whose tree cannot build at all — no `Makefile` yet, or one that does not `include` the framework — writes no verdict line, and the run would otherwise report a sha and nothing beside it. `NO VERDICT (make could not run)` says the loop reached that commit and the commit had no gate to run, which is a different thing from failing one.

#### The gate-boundary rule

The loop runs *today's* gate against every commit, and the commits were made under the gates of their own day. Where those differ the loop is not measuring the commits at all. A commit made before the project added `lint-baseline.txt` fails a newly-gating check with no baseline to accept its findings, and a bare RED does not distinguish "this commit is broken" from "this commit predates the check".

So before reading a single verdict, find the boundary: compare the gate the run reports against the marker each commit's `lint-baseline.txt` carries. A commit whose baseline records a different gate is on the far side of one.

- **Run the range from the adoption commit forward.** A check enters a project at the commit that declares it — `# adopted: identity` in the baseline's header — so `git log -S'# adopted: identity' -- lint-baseline.txt` names the first commit that can be held to it. Everything earlier is out of scope by construction, not by diagnosis. This is the cheap answer and the one to reach for.
- **Or give each sha its contemporaneous debt.** In the throwaway worktree, after the checkout, run `make lint-baseline` before `make gate`; for a check the commit predates, that regeneration is a first adoption and needs the check's own `--adopt` (see "Adopting a check for the first time"). Nothing is committed — the worktree is deleted at the end — and the question it answers is "did this commit hold the line it had", which is the one "green at every commit" is actually claiming.

**Never report a bare RED across a gate boundary.** Report the verdict line, whose marker carries the gate, or say that the range spans a gate change and which commits are on which side. A loop that cries wolf gets ignored, and the next real red goes with it.

## When the bytes legitimately differ

Occasionally the *ideal* source and the *original* bytes disagree for a defensible reason — the original has a corrupted sprite byte, or you want the source to read correctly while still reproducing a quirky original. SkoolKit's fix directives let the source carry the clean form while the round-trip still matches:

- **`@isub`** — substitution applied when assembling (`-f 1` and up). Use it for the symbolic-constant substitutions of stage 3.
- **`@ofix`** — an original fix: the byte SkoolKit should emit to match the original even though the disassembly shows something else.

The framework builds *two* variants to keep this honest: a `non-fixed` source whose bytes must already match the original (proving no accidental drift), and a `fixed` source that applies the intended `@isub`/`@ofix` directives. Both must round-trip. If you only ever build the fixed variant you can hide a real mismatch behind a fix directive — so verify the non-fixed binary against the pristine one too.

## The linters

`make` runs ten `.ctl` linters (also runnable standalone as `make lint`, or from `scripts/`):

- `validate_ctl_address_order.py` — directives in ascending address order, and no two entry heads on one address. Equal addresses are ordinary between an `@`, an entry head and its `D`; between two entry heads they give the first a size of zero, which drops it out of every check that measures a block's extent.
- `validate_ctl_instruction_order.py` — at one address: `@` → block type → `D` → `N` → `R` → line comment.
- `validate_ctl_lengths.py` — no line-comment `LENGTH` that just restates the gap to the next entry.
- `validate_ctl_label_length.py` — labels within 24 characters.
- `validate_ctl_identity.py` — every entry titled, every sub-directive named.
- `validate_ctl_data_structure.py` — every data entry tiles and declares a stride.
- `validate_ctl_publication.py` — every page inside the program image, one page per thing, and each entry the type its bytes are.
- `validate_prose_names.py` — prose names a labeled slot by its label.
- `validate_ctl_byte_counts.py` — no instruction comment recites a byte count the listing already carries.
- `validate_ctl_array_elements.py` — every record of an array is annotated individually.

The first four exist because a `.ctl` that drifts out of order still *builds* but produces confusing diffs and makes `sna2skool` output unstable. Keeping the file canonical means a one-line documentation change shows up as a one-line diff. The last six are content checks, and they carry a baseline — see below.

`make lint` runs all ten whatever any one of them reports, and ends on a summary line — `LINT FAIL: 3 of 10 checks failed, 60 finding(s): …` — which is what the gate's verdict is built from. The `10` there is what this sweep covered; the verdict re-states the same failure against the gate's own 11. Each is also its own target (`make lint-publication`) for working one check at a time. `make lint-images` is the eleventh check and stands apart because it reads the built site rather than a text file, so it runs after `make html`; its summary line has the same shape and the verdict counts it with the rest.

`make` then runs one more check that is not a `.ctl` linter at all, because its subject is the built site:

- `validate_rendered_images.py` (`make lint-images`) — every image macro named an output file, and every named file is on the site.

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

Five checks:

- **UNTYPED** — a block with no sub-directives, a `B`/`W`/`T` span with no sublength, or the part of a block no render macro reaches, over the scalar threshold (8 bytes). *This is the first failing case and the one that matters*: the defect is a block with no sub-directives at all, so a rule written as "sub-directives must be typed" misses it entirely.
- **ZEROFILL** — needs `--bin`: an all-zero span over the threshold that is enumerated as a stride rather than declared a buffer. Nothing checks a stride over zeros (`162 % 2 == 0` passes for any even length), so `B $x,162,2` renders 81 rows of `DEFB $00,$00` and verifies nothing; `S $x,162` is one `DEFS` and states the claim the image can settle. It is scoped to the *span*, so a per-byte scalar carrying its own comment is untouched — a listing line is earned by what it documents, not by the bytes it holds.
- **TILING** — gaps, overlaps and leftovers against the block's size.
- **DIVISIBILITY** — `len % sublen == 0`. A list of 2-byte words cannot be 7 bytes.
- **POINTER** — needs `--bin`: a `B` span whose byte pairs all resolve to declared addresses is a pointer table wearing the wrong type. `W` makes it relocate.

A block drawn by an image or audio macro (`#UDGARRAY`, `#SCR`, `#FONT`, `#AUDIO`) is exempt from UNTYPED — the macro is the schema and the render proves it. Nobody should index 6144 screen pixels or 50 pitch periods to satisfy a linter.

The macro usually sits in the block's own prose. A beeper sound is the case where it cannot: the sound is code *plus* data — the table holds the pitch periods, the routine holds the cadence and cycle counts — so only the routine can produce it and the `#AUDIO` belongs there, not duplicated onto the table. Such a table reaches its render through the `#R` the author already wrote, on two conditions: the link is **mutual** (table and routine name each other), and the partner is a **code** block. Both are load-bearing. One-way would let an incidental `#R` to a noisy routine exempt a real blob; and a render on *data* draws that block's own bytes, so without the code condition a working sprite copy gets exempted by the source bank it is filled from — they name each other, the source is drawn, and the copy still holds whatever the capture caught.

**The exemption discharges over the bytes a macro reads, not over the block it appears in.** `#UDGARRAY`, `#UDG` and `#FONT` state their addresses, so the covered set is arithmetic over the macro text — an array's UDG specs are address ranges, each UDG is eight bytes at its own step, and an attribute spec adds one byte per cell, truncated at the array's cell count exactly as SkoolKit truncates it. What they cover is discharged; what they leave is reported as the remainder, because a block holding one sprite and 900 undescribed bytes is the blob the check exists to catch. `make lint-array-elements` reads the same coverage, so a span a macro draws is not asked to index its records there either. `fixtures/partial-render.ctl` is the constructed case, with the expected findings of both checks written into it.

`#FRAMES`, `#SCR`, `#AUDIO` and `#UDGS` name no byte range — a frame is defined by some other macro, `#SCR` reads a display file at its `df`/`af` bases, an `#AUDIO`'s delays come out of a simulated run — so their extent is not derivable from the text and they keep the whole-block exemption. That is the blind spot the check carries.

**The contract is on the entry, not on the letter that groups its page.** What an undeclared byte renders as does differ by type — `DEFS` under `s`, `DEFB` under `b`, `g` and `u`, `DEFM` under `t`, `DEFW` under `w` — but only under `s` is it unused space. Under every other type it is published as data on a page whose title implies the block was digested, with no directive anywhere claiming it, which is worse than a visible hole. A `u $C748` titled "Undetermined 5-byte block" that carries one `B $C748,5` while the entry runs on to $CFFF publishes everything past that directive as `DEFB`, declared by nothing.

`w` is the exception to UNTYPED, and only to UNTYPED. Its bytes render one `DEFW` per word whether or not a `W` directive repeats that stride, so "declare the stride" is a demand for a directive that changes nothing published; and a word that names a labeled address assembles as that label, which is the relocation an untyped byte span costs. A `w` entry still has to tile, and a bare one owes nothing beyond that: `make lint-array-elements` exempts it for the same reason, one `DEFW` per word being one element per row with no record size left in prose. A `W` sub-directive is asked the rest — do its words group into records, is each element annotated.

**Honest limit: tiling proves accounting, not meaning.** A wrong stride that happens to divide will pass, and a mis-typed field will tile. It is necessary, not sufficient. Its job is to make an unparsed span impossible to leave behind — not to prove the parse is right. Only the render, the round-trip and the relocation proof test meaning.

### The publication check

`make lint-publication` runs `scripts/validate_ctl_publication.py`. Every other check reads one entry and asks whether it declares its bytes. This one asks whether each entry should be an entry at all, and whether it is the thing its heading says — questions no amount of per-entry byte accounting reaches. Five kinds:

- **OUTSIDE** — an entry at an address the program image does not cover. Generated render-only data (sprite masks a build script produced) declared at `$1000` in a project whose image starts at `$4000` makes `skool2html` publish pages and memory-map rows for RAM the program never occupies, at addresses that are ROM on real hardware. A reader has no way to tell those pages from the ones documenting the game. Render-only data belongs in a `.ref` `[Graphic:]` entry or beside the script that generates it. `i` blocks are exempt: they publish no page, and the terminator sits at `ORG + SIZE` by construction.
- **FRAGMENTED** — three or more consecutive `b` or `w` entries, each with no sub-directive, all headed by the same thing. That is one structure cut into pages: a loading screen split into one entry per screen address the front-end writes to leaves no page saying what the whole of it is. The fix is one entry with one title and a sub-directive per part.
- **MIXED** — a `t` entry holding a sub-directive that is not `T`. A `t $9A40 Text: PAUSED` that runs to the next entry and swallows three `B` sub-directives publishes `pause_frames` — a counter the game bumps every frame — on a page headed "Text: PAUSED", under that title in the memory map. The fix is a split, one entry per thing.
- **MUTABLE** — a `b` or `u` entry the code stores into. `b $9A5C Game progress and option settings` publishes bytes the game writes — the level number, the lives count, the difficulty — as data the program was loaded with. `u` makes the same promise and more — nothing in the image reads or writes these bytes — so a store breaks it the same way. The fix is to retype the entry `g`, or to split the written bytes into a `g` entry when the rest of it really is untouched.
- **CONTRADICTED** — text that says nothing writes bytes the code stores to. `b $6B3C Undetermined - no reader or writer found in the image`, labeled `unused_6b3c`, over bytes the listing on that same page writes, is one. MUTABLE reports the letter, and the letter is the smaller error: a reader who has learned to distrust a `b` still has no way to distrust a sentence, and `unused_6b3c` is the string he greps for. The fix is to strike the claim and name what writes the bytes.

Consecutive entries always tile — the next entry's address is where the previous one ends — so contiguity carries no information and is not tested. What carries information is that the run says one thing N times. A row of small *distinct* tables states a distinct title on each and is not reported.

"The same thing" is the **head** of the title — the clause before its first `:`, `;`, `,`, `(` or dash, with any index stripped. A fragment of a structure is captioned the way a reader writes one: the structure's name, then a note about this fragment's part in it.

```
b $4060 Title-screen bitmap; start cell reused for the lives counter
b $4080 Title-screen bitmap; start cell reused for the timer
b $40C0 Title-screen bitmap; start cell reused for the room number
```

Comparing whole titles calls those three distinct and reports nothing. The distinguishing tail is not a second subject; it is a note about one address inside the one subject the head names.

Only `b` and `w` are tested. A `g` entry is one status variable and a `t` entry is one message, and having no sub-directive is the normal form for both, so three consecutive `Player N score` entries are the standard idiom rather than a structure cut up. `s` and `u` declare space, which is not a structure at all.

MIXED tests `t` and nothing else. A `b` or `g` entry legitimately mixes `B`, `W` and `S`, and a `w` entry carries its own stride with no sub-directive at all; `t` is the one type whose contents are a single kind by construction.

**MUTABLE reads the code, not the prose, and only one way round.** A vocabulary match over entry descriptions — "while", "set when", "cleared on", "counts", "current", "progress", "advances" — would flag every `b` entry using one of those words. The count is not the objection; a check firing on many data blocks is affordable if every finding is true. The objection is that nothing in the match is evidence: "non-zero while a bonus round runs" is a sentence, and a linter reading it is guessing at what its author meant. So the check reads the generated `.skool` instead, for the one Z80 addressing mode that names its target in the instruction: `LD (nn),A` and `LD (nn),rr` for BC/DE/HL/SP/IX/IY. A finding is then an instruction address, and there is nothing in it to argue with.

That evidence is sound and incomplete, and the asymmetry is the design. A store to `$9A66` proves `$9A66` is not static; silence proves nothing, because a routine writing through `HL`, `IX` or an `LDIR` names no target. A `g` entry with no absolute store to it can still be a map, a save area or an object record written every frame through a register pair. **A `g` entry that ought to be `b` is therefore not a check**: on this evidence it would report every such entry, and that one has to be found by reading the writers.

The check takes `--org` and `--size`, which the game Makefile already sets, and sweeps `$(CTL_EXTRA)` alongside `$(CTL)`. A page is a page whichever file declared it, and generated render-only data is exactly what goes in a second `.ctl`, which is why the check reads both. It takes `--skool` too, and that argument is required rather than optional, for the reason `lint-data-structure` is passed the image: a linter that silently skips half its checks is worse than one that is not wired up at all. This is why `make lint-publication` can need the disassembler where the other `.ctl` linters need no tool at all. For the same reason the check errors out on a `.skool` it cannot read — one holding no instruction line in the form `sna2skool.py --hex` writes — rather than finding no store in it and reporting the project clean.

**CONTRADICTED reads the prose, where MUTABLE refuses to.** The objection above is to a word standing in for evidence, not to reading words. "No writer found in the image" states the same fact `read_stores` returns, and returns it the other way round, so the finding is still an instruction address and the sentence is what it convicts. Five rules keep that anchor, and each of them drops findings a looser reading would report:

- **Only a writer is contradicted.** A store proves nothing about readers, and a byte written and never read is a real thing to document, so "no reader found in the image" stands.
- **A one-word characterization is read where it names the entry** — the title and the `@label` — and not inside a paragraph, where `unused` is about whatever the paragraph discusses. It is not read at all on a `g` entry: that letter already says the program writes these bytes, so `orphan_list_head` over the head of an orphaned-object list is a name, and the store that would convict it is the store the letter promised. A denial with a verb ("nothing writes", "never written") is a statement about writers wherever it stands, so it is read on any type and in the `D`/`N` text as well.
- **A claim written inside an entry is read over its own bytes.** `N $CB20 Spare bytes after the font` sits inside `b $C200` and speaks for $CB20 to the next address carrying text, not for the entry.
- **A writer the prose names is not a writer the prose denies.** "So these 52 bytes are never written by it" names its writer two clauses earlier. Both forms of naming count: the address, `#R$9BA8` or bare, and the label — `init_levels` is what the listing prints, so it is what an author writes.
- **`c` entries are not read.** A routine's description is about the data it touches, not its own bytes, so a denial there is about a table living elsewhere.

`fixtures/fragmented-structure.ctl`, `fixtures/outside-image.ctl`, `fixtures/entry-type.ctl` and `fixtures/contradicted-claim.ctl` hold a minimal case of each kind, with the expected finding stated in a header comment. The first two are run against `fixtures/no-stores.skool`, which yields no write target, so each is left proving its own kind alone. Run them after changing the check:

```
scripts/validate_ctl_publication.py fixtures/fragmented-structure.ctl \
    --org 0x4000 --size 8192 --skool fixtures/no-stores.skool
scripts/validate_ctl_publication.py fixtures/outside-image.ctl \
    --org 0x4000 --size 256 --skool fixtures/no-stores.skool
scripts/validate_ctl_publication.py fixtures/entry-type.ctl \
    --org 0x4000 --size 512 --skool fixtures/entry-type.skool
scripts/validate_ctl_publication.py fixtures/contradicted-claim.ctl \
    --org 0x4000 --size 256 --skool fixtures/contradicted-claim.skool
```

`contradicted-claim.ctl` carries the six controls with it — the `g` label, the paragraph word, the reader denial, the writer named by address, the writer named by label, and the sub-block note whose bytes hold no store — because each of them is a finding the check would report if a rule were dropped.

### The one-name-per-entity check

`make lint-names` runs `scripts/validate_prose_names.py`. `references/agents.md` states the rule — one canonical term per concept, anchored to the `@label` identifiers — and this check holds the part of it a machine can find. A project can end up with three names for two enemy slots: "enemy A", "first/second enemy" and "the chasing enemy", against labels `enemy_a` and `enemy_b`.

Most of that class is not machine-findable, and the check does not pretend otherwise. No tool can know that "the chasing enemy" means `enemy_a` rather than a third enemy. One form is findable, and it is the form that mints the aliases:

- **ALIAS** — a positional word ("first", "second", "other", "another", …) applied to a *slot family*. A slot family is a set of labels differing only in one slot token — an enumeration index — at the same place in the name: `enemy_a` and `enemy_b`, or `enemy_a_timer` and `enemy_b_timer`, give the family `enemy` with slots `a` and `b`. The labels are the project saying, in code, that these addresses are the members of one set and that each has a name. Prose that then says "the second enemy" has named a member a second way, and by the worst available name: position is not in the listing, is not searchable, and is a fact about the `.ctl`'s ordering rather than about the game.

Three restrictions keep the check on that class and off ordinary prose.

**Only an enumeration is a slot set.** An ordinal presupposes an order with a known start, and two token sets have one: digits, and letters running from `a`. `enemy_a`/`enemy_b` and `spr_wheel_0`..`_3` enumerate. The members of `step_x`/ `step_y`, `spr_arrow_l`/`_r` and `work_h`/`_x`/`_y` are an axis, a direction and a work register, and none of them has a first. Accepting any single letter mints families on ordinary-word stems, and reports "for the first step through 200, 150, 100" as an alias for `step_x`.

**Only the family's full stem counts as the noun.** "first cell" is ordinary prose about probe order; the finding would be "first probe_cell", were the family `probe_cell`. Matching a stem's last word alone would flag every ordinary sentence that uses that word — a check nobody would keep.

**Only a phrase that refers to a member is an alias.** "The second enemy" names the enemy. "The second-enemy bonus" names a bonus, and `second-enemy` is a hyphenated compound modifier — the hyphen is the writer saying so. The head noun there is `bonus`, a different entity with a name of its own, and substituting the label gives "the enemy B bonus", which is not idiomatic and is not the fix this check asks for. A referring use is rewritten to "enemy B"; an attributive one stands.

An alias with no positional word in it is settled by the author and held by the vocabulary section of the project's `AGENTS.md`, not by arithmetic over labels.

The sweep covers the `.ctl`, every `.ref` and `spec/*.md`: a term settles wherever nothing looks. Its baseline keys on `<file>:<phrase>` rather than an address, since a finding in a catalog table has no directive address and the phrase is its identity. The file has to be in that key: without it, an accepted phrase in a `.ref` and the same phrase newly written into the `.ctl` are one key with one count, so fixing the catalog pays for the new one and the gate stays green.

### The recited-length check

`make lint-byte-counts` runs `scripts/validate_ctl_byte_counts.py` over the `.ctl`'s instruction comments. One kind:

- **BYTE_SPAN** — a comment stating the size of the span its instructions work on. `Clear 163 bytes of the tile state map` sits on the row whose `LD BC` says so; the number is on the page twice, it buys the reader nothing, and it rots on the next resize or split, because the count is a fact about the current annotation rather than about the game.

A *rate* is the opposite case and is exempt: `6 bytes per enemy`, `8 bytes per tile`, `a 12-byte record stride`, `N bytes/<unit>` state the arithmetic that turns an index into an address, which a reader would otherwise recover by counting rows.

The check cannot tell the two apart by reading — "the 9-byte record" and "the 2848-byte working table" are one grammar, and only the second is a span. So the *author* declares which it is, by writing a rate as a rate. That is what makes the rule applicable: the fix is either to delete the number or to say what it is the size of. See `references/comment-style.md` for the rule and its worked example.

Scoped to instruction comments. A `D` or `N` note is exactly where a structure's shape belongs, stated once for the block; the defect is that sentence copied down onto a row that already carries the number.

### The rendered-image check

`make lint-images` runs `scripts/validate_rendered_images.py` **after** the site is built, because it reads what the build produced.

`make` proves the HTML *builds*, and `coverage` counts `#UDGARRAY` in the source. Both stay true after a change rewrites every image-file macro `(name)` into the frame-only form `(*name)`, which defines a frame and writes no file, and the site loses the images those macros rendered.

**The invariant: every image macro names an output file, and every named output file exists.** Not "as many files as macros". Those two totals differ for reasons that are all legitimate — several macros can name one file (a sprite rendered at its data block and again in the catalog), a `#FRAMES` macro writes one animation out of frames other macros defined, and a frame-only macro writes nothing. An inequality between the totals is not a defect, and equality is not proof. What does not legitimately differ is the per-macro claim: a macro naming `ship` claims `ship.png` is on the site, and either it is or it is not.

Two kinds, because the failure this exists to catch removes the claim along with the file:

- **UNRENDERED** — the macro names a file and the built site has no such image.
- **NOFILE** — the macro names no file. `(*name)` defines a frame and writes nothing; `()` writes nothing either. A frame is legitimate only as an ingredient: some `#FRAMES`, `#UDGS` or `#COPY` macro must consume it, and the macro that does must itself name a file. An unconsumed frame renders nowhere.

UNRENDERED alone is silent through such a rewrite — once no macro names a file, no named file is missing. NOFILE is what refuses a macro that claims nothing. Counting files on disk is silent too: `--rebuild-images` does not delete stale output, so the site keeps its old `.png` files while nothing on it refers to them.

Where a macro states its filename is not the same for every macro, and the check follows SkoolKit's own parsers rather than guessing "the last bracketed group": `#UDGSw,h(fname)(uframe)` states it first and names a frame last; `#FONTaddr[,…][(message)][(fname)]` with one group has stated a message and no filename; `#UDG` and `#SCR` fall back to `udg.png` and `scr.png`. Within the spec, `(fname*frame|alt)` splits the alt text off first and the frame second, and a `.png` a spec spells out is the same file as one that leaves it off, because SkoolKit appends it.

### The known-failing baseline

`lint-identity`, `lint-data-structure`, `lint-publication`, `lint-names`, `lint-byte-counts`, `lint-array-elements` and `lint-images` land red on a mature project. That is not a reason to keep them out of the gate — it is the reason the baseline exists.

Left advisory, a check is never run: a defect it reports ships under `make gate` printing GATE PASS, while the check has the defect in its output the whole time.

So every one of them is in the default gate, and a project records the findings it starts with:

```
make lint-baseline        # re-records the current findings; it can only shrink
                          # the file, and fails without writing on growth
```

`lint-baseline.txt` lists one accepted finding per line, as `<check> <KIND> <$ADDRESS>  <message>`. The first three fields are the key; the message is for the reader. Four rules give it its shape:

- a finding whose key the file does not list **fails the build** — that is the new defect, and it is the whole point;
- a line the file lists that its check no longer reports **fails the build too**, so a fix takes its baseline entry with it in the same commit and the file cannot rot into a permanent excuse;
- a key is only compared against the check that wrote it, so a project may baseline one check and gate another cleanly;
- a key may repeat, and the count is part of the comparison: two findings of one kind at one address are two lines, and a third fails the build.

The key is the *address on the directive the finding points at* — never the line number, which churns on every unrelated edit above it, and never the message, which changes when a neighboring directive resizes. Counting repeats is what stops that address-only key from swallowing a second finding where one is already listed. Splitting an undescribed `M $7E04,2` into `M $7E04,2` plus `B $7E04,1` leaves two findings at `$7E04` against one accepted line, and the build fails — while a directive that merely moves down the file keeps its key and its count.

Two checks key on something other than an address, because their findings do not live on a directive: `prose-names` keys on `<file>:<phrase>` and `images` on the file or frame name. A phrase in a `.ref` catalog has no address, and the address of whatever `.ctl` line happens to carry it is not its identity. Counting repeats then reads as "thirteen occurrences of this phrase in this file are accepted", and the fourteenth fails the gate — but the *location* it prints is one of the thirteen, not necessarily the new one, and the report says so. Every occurrence is the same finding and takes the same fix.

`verify-frag` splices a Worker's fragment into a copy of the `.ctl` under the project's own filename, so those keys still match; a throwaway name would make every inherited finding look new.

The header records the gate the file was written under, one line beside the `# adopted:` declarations:

```
# gate: 1/e70342a
```

`make lint-baseline` writes it — on a run where every check recorded, so a refusal leaves the older stamp standing rather than claiming a recording that did not happen. A baseline is a statement about findings *a particular gate* reports, so without it a file that predates a check is indistinguishable from one that accepts it. The gate reads the line back and reports a mismatch in its verdict; see "The marker" above.

A check adopted by hand with `--adopt` rewrites the file through the check's own script, which does not stamp — re-run `make lint-baseline` afterwards, and the stamp comes back with the adoption in it. Until then the verdict says the baseline records no gate.

**The file only ever shrinks, and the tool holds that.** Regenerate it when a fix clears a finding — the shrunk file is the evidence, and the diff is how the debt is visible in review. Each check rewrites only its own lines, so re-recording one leaves the other's alone. A run that would add a key writes nothing, names the keys and exits non-zero, and `make lint-baseline` fails with it:

```
byte-counts: REFUSED to write lint-baseline.txt — 1 key(s) it does not list, and a
key this file gains is debt taken on, not debt inherited:
  + byte-counts BYTE_SPAN $9861
lint-baseline.txt is unchanged, so the gate still fails on them. Fix the finding,
then re-run.
```

Refusing is the shape that leaves the tree and the verdict agreeing. Writing the file and failing once would bury the finding just the same: the exit status is gone by the next command, `make gate` is green over the new line, and only a revert undoes it. Because nothing is written, the next thing anyone runs — the gate, the regeneration again, a colleague's build — reaches the same answer.

The checks run in one shell, so a refusal by one does not stop the rest: a check that has a fix to record still records it while another check is red. The refuser leaves its own lines exactly as it found them.

A rewording is not growth. The message is not part of the key, so when a check's wording changes, a regeneration rewrites the text of the lines it already owns and reports nothing added — the drift shows up as a diff and blocks nothing.

Never hand-edit the file to silence something you introduced either — the diff would show it growing, which is the same signal from the other direction.

#### Adopting a check for the first time

A project with no `lint-baseline.txt` is gated on everything, which is the right default for a new disassembly. The baseline is for a project that predates a check: its findings are debt the check inherited, and recording them is the one growth that is legitimate.

It is deliberately not reachable from `make lint-baseline`, which can only shrink. Adopt one check at a time, by running that check's own command with `--adopt`. `make -n lint-baseline` prints each command line as the project configures it, with the paths this project actually uses; copy the one you are adopting and append the flag:

```
$SKILL/scripts/validate_ctl_byte_counts.py src/{game}.ctl \
    --baseline lint-baseline.txt --write-baseline --adopt
```

The adoption is recorded in the file's own header, one line per adopted entry:

```
# adopted: byte-counts
# adopted: identity
```

Those lines are what the refusal reads, and they are the point of the design. Owning no lines cannot tell "this check has never run here" from "this check ran and came back clean", so if adoption were inferred from the lines, `--adopt` would walk a new finding straight into a clean check's section — the forbidden sequence, one flag deeper. A declared entry is refused whatever it currently lists, including nothing, and every successful regeneration declares the check it rewrote, because a check that regenerates here has run here.

So the file states its own invariant, and a reader needs no history to check it: **for every declared entry the count is non-increasing, and the declared set grows only by a line you can read in the diff.**

One case needs the second granularity. A check that gains a new finding kind reports, on a mature project, debt that predates the kind — the `.ctl` was written before it existed — but it arrives under a check name the header already declares. Without a route it would be unadoptable, and the rational move would be to pin the skill version, which is the failure the baseline exists to prevent. `--adopt-kind` is that route, and it names the kind:

```
$SKILL/scripts/validate_ctl_publication.py src/{game}.ctl \
    --org <org> --size <size> --skool build/{game}.skool \
    --baseline lint-baseline.txt --write-baseline --adopt-kind CONTRADICTED
```

It records that kind's findings and nothing else — a key of any other kind in the same rewrite is refused — and it writes `# adopted: publication CONTRADICTED`. The tool cannot tell a kind the check has just gained from one it has always had, so this is the point where the diff line is the check: adopting a kind that is not new is visible in review, and it is the only growth review has to look at.

`fixtures/baseline-monotonic.sh` is the regression: it adopts two checks, introduces a finding at a new address and a second finding at an address the file already lists, and asserts both are refused with the file untouched; it rewords a message and clears the finding and asserts both are accepted; then it clears the check's last line and asserts that `--adopt` on that now-empty section is still refused, which is the case the header exists for.

### The comment-quality pre-filter (advisory)

`make lint-comments` runs `scripts/lint_comments.py` over the generated `.skool` and flags three mechanical comment defects a green build never catches: a comment on a bare `RET`, a comment that only restates the instruction, and a placeholder label (`work_b`, `helper_8e3a`, `L5B50`). The same command takes the `.ref` catalogs and `spec/*.md` and sweeps them for investigation and emulator vocabulary ("verified live", "under emulation", "not fully pinned") — those pages reach the same reader as the `.skool`, and an unswept one is where a claim sourced from a run survives. It also counts `OPEN`: the typed uncertainty markers (`(unverified)`, `TODO:`) that are *correct* where they stand and say the work behind them is unfinished — `make coverage` keeps a project short of the bar while any remain. It is **advisory** — outside the `make` gate — because a flag is a prompt to review, and a `RET` note occasionally carries a real return-state contract that an expert keeps. The Challenger runs it and decides.

It is deliberately small. The two checks that matter most are not scriptable and are the Challenger's responsibility, not the linter's:

- whether a comment adds what the code cannot show (needs comprehension), and
- whether a multi-line `{ }` comment spans *exactly* the instructions it describes — the comment text is word-wrapped across the grouped lines, so the checks that read one instruction skip the rows carrying a brace and leave their span to an expert reading. A group's interior rows carry none, so those are read like any other row.

`OPERAND_ECHO` is the exception, and it has to be: a group opens on the row that carries the operand its first sentence names, which is where an echo like `LD HL,tile_map ; {Clear … (tile_map)` lives, and skipping the brace-carrying rows would miss every echo on a row that opens or closes a group. It runs per row — each row's `#R` against that row's own operand — not per group. Widening it to the whole span, every reference against every operand under it, would report a group comment naming a routine its span calls, which is a paragraph doing its job, not a duplicate.

Relocatability (a raw address in a comment) is not re-checked here: `skool2asm --create-labels` already emits "Comment contains address …" and the build fails on it, which is both authoritative and more precise than a regex.

### The coverage report — the "is it done?" gauge

`make coverage` runs `scripts/coverage_report.py` and answers the question a green build cannot: *how close is this to the documentation bar?* A green, fully-labeled project is **breadth**; this measures **depth**. It reports, per code routine, whether the body is *explained* (commented at the right altitude), *skeletal* (a description over a bare body — the breadth-only trap that gets mislabeled "mature"), or *bare*. It also gauges the **catalog and audio**: how many catalog entries are still identified by an auto-label (`f9440`) rather than named; whether the game has sound code (speaker writes) but no `#AUDIO`; and the `#TABLE` and placeholder-label counts. A draft catalog or unrendered sound fails the gauge as surely as skeletal code does.

It **auto-discovers** the project's `.ctl` and *every* `.ref` file beside the skool, and prints what it scanned — so the catalog and audio counts never read as zero just because a caller forgot to pass `graphics.ref` or the project splits its sections across differently-named ref files. Catalog and audio content is found by **section type** (`[Graphic:]`, `[Audio:]`, `#AUDIO`, `#UDGARRAY`) wherever it lives; the filenames (`graphics.ref`, `sound.ref`) are a convention, not a requirement. So `coverage_report.py <game>.skool` alone gives the full picture; a missing-file false negative is not possible.

It counts **code only**: data blocks (the loading screen, level data, tables) are excluded, because data is documented by labels and native devices, not line comments — so the figure is not an average over code and data. Line density is shown only as a rough cross-check, never as the bar; the real signal is the fraction of routines with an explained body. The Manager runs this before reporting completion, and does not call a project mature while it says otherwise (see `references/roles/manager.md`). Whether each comment is *correct* and the catalogs and spec *complete* remains the Challenger's call.

#### The verdict answers for what the gate knows

A gauge that reaches "at or near the bar" from its own counts alone, while the gate holds recorded findings against the same project, is two instruments disagreeing about one question, with the more forgiving one printing the headline. A residual-gaps line below the verdict does not settle it, because a line under a verdict does not change the verdict.

So the gauge reads the gate's own inputs, both auto-discovered beside the skool and overridable with `--baseline` and `--html`:

- **BASELINE** — every finding recorded in `lint-baseline.txt`, per check. A recorded finding is unfinished work by construction: the gate passes because the project accepted it, not because it is fixed. Any non-empty baseline holds the verdict at NOT at the bar.
- **IMAGES** — the files the image macros name against the files the build wrote, the same survey `lint-images` gates on. The `INLINE GFX` line counts macros in the source, labeled as what it is: where the macros live, not what they produced. Only the findings the baseline does not already hold weigh on the verdict; a recorded one weighs once, under BASELINE.

Both appear in the verdict's reason list, not only in the report body:

```
BASELINE     : 100 known-failing finding(s) held by lint-baseline.txt
               (data-structure 40, identity 30, images 20, prose-names 10)
               — each one a defect the gate is passing on credit

VERDICT: NOT at the bar — 100 finding(s) recorded in lint-baseline.txt — the gate
passes because the project accepted them, not because they are fixed.
```

A *missing* `lint-baseline.txt` is not a clean one, and the report says so rather than reading zero findings as the gate passing on its own terms.

Shrinking the baseline to nothing is therefore part of reaching the bar, which is the only reading under which "at or near the bar" means anything.

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

`ASM_FIXED_FLAGS` is the only place those flags are stated, and `verify-frag` reads the same variable: a Worker's self-check renders the fixed source with the project's flags and assembles it, so a fragment that leaves an in-image operand raw is red where its author can see it, and a project that has opted out is not held to a gate its own build does not run. Assembling matters on its own: an `@ssub=LD (lbl+1),A` whose label does not exist renders without a warning and fails only at `pasmo`. `fixtures/verify-frag-flags.sh` exercises both directions and that case.

`scripts/coverage_report.py` reports the static signals — `L####` auto-labels (unnamed blocks) and raw operands at/above the game floor. But a label-clean source is **still not proven relocatable**. The gauge counts *operands*, and four things hide from it:

- an **`@equ` binding a program-owned address to an absolute constant** — a hard-coded address wearing a symbolic name;
- an address stored as **data** (a pointer table held as `DEFB` bytes);
- an address **synthesized from an 8-bit immediate** (`ADD A,$E0` building a buffer page), which no label can even be substituted into;
- **code annotated as a byte blob**, where every operand is data.

A project can read `RELOCATABLE 0`, `NAMING 100%` and every routine body-explained over a program that breaks if a single byte moves.

### Proving it: move the program and run it

The only proof is dynamic: move the code, rebuild, and confirm it behaves identically under the **`zx-fuse-driver`** skill. Two static checks come first, and the second one decides which form of the move is available at all. Run both before choosing a form, not after planning an insertion the image cannot fund.

**Pre-check 1: list the `@equ` values at/above `RELOC_FLOOR`.** Each one is either a genuinely fixed address — screen, attributes, I/O ports, ROM entries, the stack top — or a relocatability hole wearing a name. Anything else should be a label on the block instead.

**Pre-check 2: measure the largest *contiguous* reclaimable span above the insertion point.** The question is never how many surplus bytes a project has in total; it is whether one span holds the whole displacement. A shift pads the head of the region it moves by N and gives N bytes back from a single span above that head, and everything between pad and span moves by exactly N. Split the reclaim between two spans and the displacement splits with it: the bytes lying between the two move by only the share of the pad taken above them, and no partial share of 257 has both bytes non-zero — under 256 the high byte is untouched, and 256 itself leaves every low byte alone. Part of the image then moves by an amount the both-bytes rule rejects, which hides a defect there as thoroughly as not moving it at all. A reclaim *below* the insertion point is the same failure pointing the other way: it drags the region between itself and the pad downward by its own count, and leaves the region above the pad short by that much. So only one number answers this check — the size of the largest single span above the insertion point.

Count only spans the map declares surplus, and read each *span's* own annotation rather than its enclosing entry's type. A span counts when the map says what the bytes are and why nothing uses them; a span whose annotation records only a search that came up empty is undetermined, not proven dead, and a zero fill in the snapshot is not dead space if the program writes it at runtime. Bound the search at the lowest `org` pin, because nothing above it moves.

**Whatever moves, the screen must stay put.** The display file is hardware-fixed at `$4000`, and a post-load image begins *with* the captured loading screen, so it starts at `$4000` too. Bumping the one `ORG` drags the screen bytes along, and that tests nothing: the code still writes to the absolute screen address, so the moved copy is inert and any misbehavior is unattributable — a real relocation bug looks exactly like the displaced picture. Move the program's own blocks, and verify the screen and attribute bytes are untouched.

**Every address must change in both bytes.** A displacement that is a multiple of 256 leaves every low byte unchanged, so code that manipulates only an address's high byte keeps working by accident and the defect hides. A displacement below 256 leaves the high byte unchanged for every address whose low byte does not carry. So the displacement must have both bytes non-zero, and **257 is the smallest value that does**. This is one rule with two costs: for a shift it is a quantity of space you must find, for a permutation it is a criterion for picking a block you already have.

**The permute is the primary form.** Move one block to a different position in the image; every block between its old and new position is displaced by that block's size. Choose a moved block whose *size* has both bytes non-zero, and check the moved block's own displacement — the combined size of the blocks it jumps — the same way. It is primary because it needs not one spare byte, because it holds the image size constant by construction, and because the both-bytes rule is satisfied by choosing among blocks rather than by finding space. A permutation also reverses the order of the blocks it jumps, which no shift does.

**The shift is the easier form, when the space check clears 257.** Insert padding at the head of the span you mean to move — the code region's first byte — and reclaim the same count from one proven-dead span above that head, so the image size holds, nothing else drifts and the alignment-pinned buffers stay put. The pad and the reclaimed span bracket the region that moves, which is what pre-check 2 measures. That head is not `RELOC_FLOOR`: the floor is where symbolic references become mandatory. The state blocks between the floor and the pad stay where they are, which is what lets an oracle read them at fixed addresses. A size change invalidates the comparison. One pad at a known address and N bytes reclaimed from a known span is less to assert than a permutation, which claims one block moved, everything between displaced and everything outside untouched. That is why it is worth taking when it is available. **It is not available when the largest span above the insertion point is under 257 bytes**: no size-preserving shift of that image can change both bytes of every address. **"There is no room" is never a reason to skip the proof — only a reason to use the other form.**

**A floor is not enough: name the fixed-placement regions.** Some work areas are alignment-constrained and must be pinned with their own `org`, exactly like the screen — their addresses are computed from their own page, so moving them breaks the arithmetic that finds them. A pinned region above `RELOC_FLOOR` is one the floor alone calls movable. List them explicitly; pinning one is correct annotation, not a defect.

**Check that the oracle can fail.** Drive both images under `zx-fuse-driver` against an oracle of fixed-address state below the moved region — never state that moves with the code, such as an RNG seed in the moved region. Then sabotage a single operand back to a raw absolute address and confirm the oracle diverges. An oracle that stays identical under that control proves nothing.

### When it fails: bisect what moves, not how far

The *displacement* barely matters — a relocation defect breaks the program at 8 bytes as thoroughly as at 128. It only tells you *that* something is wrong. To find *what*:

- **Bisect the moved span.** Under a shift, insert the pad at successively later labels so only code from that label onward moves; under a permutation, shorten the hop so fewer blocks are displaced. BROKEN means the defect is inside the span that moved; IDENTICAL means outside it. Each run halves the span, so a handful of runs narrows it to one routine. The bisect is the one place a shift stays available on a tight budget, since it needs only as many bytes as the current step.
- **Choose an oracle outside the moved span.** State inside the moved region reads at a stale address and reports differences that are entirely your probe's fault — an RNG seed in that region does exactly this. A position or timer in low RAM is a valid oracle; a counter that moves with the code is not.
- **Do not rationalize the residual.** A remaining gap explained as inherent — a slightly slower loop in a game that runs interrupts-off and paces itself by execution speed — is a tidy story that makes it somebody else's problem. A plausible mechanism is not evidence, and a residual that survives a confident explanation is exactly where the bug is.

Claim "relocatable" only when the proof has run, never from a green, label-clean build.
