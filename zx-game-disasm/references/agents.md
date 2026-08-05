# Working rules for a disassembly project

The rules every `zx-game-disasm` project runs under. A project keeps no copy of them, because a copy in each project rots: when the framework gains a linter or renames a target, the copies keep telling agents to run the old one.

Read alongside: `ctl-authoring.md` (how to write the `.ctl`), `comment-style.md` (what a comment may claim), `build-verify.md` (the round-trip and the gates).

## The build

The **gate** is `make`: it reassembles the disassembly and `cmp`s it against the pristine bytes, runs the `.ctl` linters, and builds the HTML (the only step that validates the `.ref` catalogs). It is not slow.

```sh
make                      # the gate: round-trip cmp + .ctl linters + HTML
make lint-baseline        # re-record the gating checks' findings (only ever shrinks)
make coverage             # the "is it done?" gauge
make verify-frag FRAG=…   # round-trip one fragment in isolation
make clean                # remove generated files
```

## Non-negotiables

- **Every checkpoint is green.** `make` passes: byte-identical round-trip, linters clean, and `skool2asm --create-labels` emitting **zero** warnings. Never leave the project red across a checkpoint. Keep increments small.
- **Never hand-edit a generated file.** The `.skool`, `.asm`, `.bin` and `.z80` are generated; edits to them are overwritten and never reach the round-trip. The `.ctl` is annotation *over* the snapshot.
- **The toolchain runs from `PATH`.** Install the packages in `requirements.txt` so `make` and the SkoolKit tools find them there.
- **Never write a raw address in a comment.** `skool2asm`'s address-to-label scan rejects any address-shaped token in a comment and the build fails on the warning. Reference code and data by `#R$<hex>` or by label. A fixed hardware address with no `.ctl` block is described functionally; its number belongs in `spec/`, not in the comment.
- **Map by growing code from the entry.** The image starts as one `b` block; convert a region to `c` only as execution flow confirms it. Do not trust `sna2ctl`'s heuristic guess.
- **Keep it relocatable.** Label the program's own code and data so references resolve to labels, not raw hex; leave genuinely fixed addresses (screen, sysvars, ports) absolute. A green build does **not** prove relocatability: the gauge counts operands, so it cannot see an address bound to an `@equ`, stored as data, built from an 8-bit immediate, or hidden in a byte blob that is really code. Claim it only after the shifted/permuted build runs identically.
- **Document the game, not the Z80.** Comments explain algorithms, rules and state in concrete numbers — never restate what an instruction does.
- **Render/play the artifact; never transcribe it.** A sprite is documented by its `#UDG`/`#UDGARRAY`/`#FRAMES` render and its glyph-derived name; a sound by its `#AUDIO`. The description states FUNCTION — movement, targeting, points, collision, phases — never what the pixels look like or what the sound's Hz are. The macro plays the real thing. The one thing prose may add is a fact the render cannot assert: a *traced* color (the attribute the draw code writes, not the render's display attribute), or a *derived* cadence.
- **Name an asset from the whole artifact, not one frame or one read.** A rotating sprite passes through poses that look like other objects, and a handler that copies a constant reads exactly like one that tracks. Measure the bitmap; watch the motion.
- **One canonical term per concept.** A reader must never map two words onto one thing, and one word must never name two things. Anchor terms to the `@label` identifiers; never invent a synonym for something a label already names.
