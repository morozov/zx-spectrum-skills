# Working rules for a disassembly project

The rules every `zx-game-disasm` project runs under. A project keeps no copy of them, because a copy in each project rots: when the framework gains a linter or renames a target, the copies keep telling agents to run the old one.

Read alongside: `ctl-authoring.md` (how to write the `.ctl`), `comment-style.md` (what a comment may claim), `build-verify.md` (the round-trip and the gates).

## The build

The **gate** is `make`: it reassembles the disassembly and `cmp`s it against the pristine bytes, runs the `.ctl` linters, and builds the HTML (the only step that validates the `.ref` catalogs). It is not slow.

```sh
make                      # the gate: round-trip cmp + .ctl linters + HTML
make gate                 # the same gate, logged, ending in one verdict line
make lint-baseline        # re-record the gating checks' findings (only ever shrinks)
make coverage             # the "is it done?" gauge
make verify-frag FRAG=…   # round-trip one fragment in isolation
make clean                # remove generated files
```

`make gate`'s verdict names the SkoolKit *and the gate* it ran under, and distinguishes a build that regenerated something from one that found every file current:

```
GATE PASS, REBUILT [SkoolKit 10.1, gate N/e70342a] — …
GATE PASS, NOTHING REBUILT [SkoolKit 10.1, gate N/e70342a] — …
```

`gate N/e70342a` is the gate itself: the generation `SKILL.md` declares, then a digest over the skill files the build runs. **Never report or store a bare GREEN or RED — report the verdict line.** The skill and a disassembly move independently. A verdict that does not name its gate stops meaning anything the moment either side moves, so a bare GREEN in a log is uninterpretable a week later. When a failing verdict says the project's `lint-baseline.txt` was recorded under a different gate, the finding is the gate moving and not the commit regressing; `build-verify.md` carries that rule.

Read the difference. `NOTHING REBUILT` re-ran the round-trip and the linters over artifacts an earlier build produced; it is not evidence that the sources as they stand now assemble. `REBUILT` says at least one generated file came from source — which ones is in the log, not in the verdict. Force the whole chain — `make clean`, or remove the `.skool` — before reporting a checkpoint green. See `build-verify.md`.

## Non-negotiables

- **Every checkpoint is green.** `make` passes: byte-identical round-trip, linters clean, and `skool2asm --create-labels` emitting **zero** warnings. Never leave the project red across a checkpoint. Keep increments small.
- **Never hand-edit a generated file.** The `.skool`, `.asm`, `.bin` and `.z80` are generated; edits to them are overwritten and never reach the round-trip. The `.ctl` is annotation *over* the snapshot.
- **The toolchain runs from `PATH`.** Install the packages in `requirements.txt` so they are on it. The build refuses to start when a tool it needs is missing, whether or not the tree is up to date.
- **Never write a raw address in a comment.** `skool2asm`'s address-to-label scan rejects any address-shaped token in a comment and the build fails on the warning. Reference code and data by `#R$<hex>` or by label. A fixed hardware address with no `.ctl` block is described functionally; its number belongs in `spec/`, not in the comment.
- **Map by growing code from the entry.** The image starts as one `b` block; convert a region to `c` only as execution flow confirms it. Do not trust `sna2ctl`'s heuristic guess.
- **Keep it relocatable.** Label the program's own code and data so references resolve to labels, not raw hex; leave genuinely fixed addresses (screen, sysvars, ports) absolute. A green build does **not** prove relocatability: the gauge counts operands, so it cannot see an address bound to an `@equ`, stored as data, built from an 8-bit immediate, or hidden in a byte blob that is really code. Claim it only after the shifted/permuted build runs identically.
- **Document the game, not the Z80.** Comments explain algorithms, rules and state in concrete numbers — never restate what an instruction does.
- **Render/play the artifact; never transcribe it.** A sprite is documented by its `#UDG`/`#UDGARRAY`/`#FRAMES` render and its glyph-derived name; a sound by its `#AUDIO`. The description states FUNCTION — movement, targeting, points, collision, phases — never what the pixels look like or what the sound's Hz are. The macro plays the real thing. The one thing prose may add is a fact the render cannot assert: a *traced* color (the attribute the draw code writes, not the render's display attribute), or a *derived* cadence (arithmetic over the table values and the loop that drive it — frames per step, counter reload, entries per cycle — stated in those units) **where the cadence is part of the rule the reader needs**, not merely because it can be computed. The second test is the same one a timing has to pass: see "A comment never echoes the implementation" in `references/comment-style.md`. Both halves are bounded the same way: the reader re-derives them from the code. A stopwatch is not a derivation, and the failure it produces is a frame rate or a duration in seconds measured under emulation, which is a property of that run, not of the game, and which every delay anchored to it inherits. Seconds derived from a frame count come from that count and a nominal frame rate the reader can see you assuming; seconds derived from the instructions come from `#TSTATES`, which computes them from the bytes. Running the game is how you *find* any of this — `zx-fuse-driver` is there to be used, and `comment-style.md` says when to reach for it — but the run is the lead and the code is what the claim stands on.
- **Name an asset from the whole artifact, not one frame or one read.** A rotating sprite passes through poses that look like other objects, and a handler that copies a constant reads exactly like one that tracks. Measure the bitmap; watch the motion.
- **One canonical term per concept.** A reader must never map two words onto one thing, and one word must never name two things. Anchor terms to the `@label` identifiers; never invent a synonym for something a label already names. `make lint-names` holds the part of this that arithmetic can settle — a labeled slot family (`ship_a` / `ship_b`) must never be named by position in prose ("the second ship").
