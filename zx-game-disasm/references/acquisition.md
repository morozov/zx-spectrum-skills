# Stage 1 — Acquire a clean snapshot

SkoolKit disassembles a *snapshot*: RAM frozen with the game already loaded. The job of this stage is to produce that snapshot and the three numbers the pipeline needs.

- **`ORG`** — the first address of the program in memory (often `$4000`/16384 if the game lives from screen memory up, or higher).
- **`PC`** — the entry point the game starts executing at.
- **`SP`** — the stack pointer the game runs with.

These feed `tap2sna`/`bin2sna` and the Makefile. Get them wrong and the round-trip snapshot will not match a real run.

## Table of contents

- [Toolchain](#toolchain)
- [From a tape image (.tzx/.tap)](#from-a-tape-image-tzxtap)
- [From an existing snapshot (.sna/.szx/.z80)](#from-an-existing-snapshot-snaszxz80)
- [From a disk image (.trd/.scl)](#from-a-disk-image-trdscl)
- [Packed and multi-stage loaders](#packed-and-multi-stage-loaders)
- [Finding ORG, PC, and SP](#finding-org-pc-and-sp)

## Toolchain

The build runs SkoolKit (`tap2sna.py`, `sna2skool.py`, `skool2asm.py`, …) and `pasmo` from `PATH`. Install the Python packages in `requirements.txt` in any environment that puts them there.

- Pin the SkoolKit version in `requirements.txt` for a reproducible build.
- `pasmo` is a system binary, not a Python package.
- `scripts/extract_bytes.py` does `import skoolkit`, so the `python3` first on `PATH` must have SkoolKit installed. Otherwise it fails with `ModuleNotFoundError`.

**Build logic comes from the skill — the project does not vendor copies.** The `.ctl` validators, `coverage_report.py`, `lint_comments.py`, `splice_ctl.py`, *and the build rules* are skill tooling that evolves and gets fixed; a copy frozen inside a project goes stale the moment it changes, and the project then measures itself with an old gauge or builds with old rules. So they are single-sourced: the project `Makefile` is a thin stub that `include`s the framework `$(SKILL)/tools/disassembly.mk`, which holds every target and self-locates the skill's `scripts/`. `SKILL` has no default: set it to the skill's directory, in the environment or on the `make` command line. Do not copy the scripts or the build rules into the project; if the project holds a vendored `scripts/` copy or a fully expanded `Makefile`, delete the copy and replace the `Makefile` with the stub.

## From a tape image (.tzx/.tap)

`tap2sna.py` simulates a real tape load and writes a snapshot. This is the preferred path: it runs the game's own loader, so the result is exactly what the game expects in memory.

Drive it from a `.t2s` config file (see `assets/game.t2s.template`) so the URL, checksum, and pokes live in one tracked place:

```
tap2sna.py @{game}.t2s --reg pc={PC} --reg sp={SP} {game}.pristine.z80
```

A `.t2s` names the tape source and any RAM setup the disassembly needs:

```
https://example.net/Some%20Game.tzx
--tape-sum <md5-of-the-tape>
--ram sysvars                 # initialize the system variables area
--ram poke=23611,8           # FLAGS, etc. — only what the game relies on
```

`--tape-sum` pins the exact tape; if the download ever changes, the build fails loudly instead of silently disassembling a different dump. Pin tool and asset versions the same way you would any dependency.

If `tap2sna` cannot load the game (turbo loaders, custom decryption, anti-tamper), the loader itself needs live analysis. Drive it under FuseX with the **`zx-fuse-driver`** skill, applying the comprehension method in `../shared/disasm-analysis.md`, to learn where the payload lands; then capture a snapshot at the hand-off point. The `zx-tape-to-trdos` skill has tape-loader-specific trapping recipes for turbo and protected loaders.

## From an existing snapshot (.sna/.szx/.z80)

A snapshot is already a memory image — use it directly as the `sna2skool` input. Two cautions:

- **Format detection is by extension.** SkoolKit picks the parser from the file suffix. A `.sna` that is actually SZX content must be renamed to `.szx` or it is misread. When in doubt, check the header bytes.
- **The snapshot is one frozen moment.** If it was taken mid-game, RAM holds runtime state (sprites moved, score set), not the pristine post-load image. For a disassembly you want the snapshot taken right after loading completes, before the game logic mutates anything.

## From a disk image (.trd/.scl)

TR-DOS disk images hold files, not a memory image. Extract the game's code/data files and assemble a snapshot, or — simpler — boot the disk in an emulator and snapshot once loading finishes. SkoolKit's `sna2skool` reads `.trd`-resident data only after you have turned it into a snapshot or a raw binary at a known origin.

## Packed and multi-stage loaders

Many games ship compressed: a small unpacker runs first, inflates the real game elsewhere in RAM, then jumps to it. Disassembling the *packed* bytes is pointless — they are compressed data, not the code you want to document. You need the game *after* it unpacks.

The pattern:

1. **Snapshot the unpacker** at its origin, before it runs. Disassemble that small stub on its own (`sna2skool -s <start> -e <end>`) — it is usually a few hundred bytes and worth documenting as the boot stage.
2. **Let it run, then snapshot again** once the game is fully decompressed and initialized. This second snapshot is the source for the main disassembly.
3. **Disassemble each stage from its own snapshot.** Use the pre-decompression snapshot for the unpacker, the post-decompression snapshot for everything it produced. Mixing them disassembles bytes that never coexisted in memory.

Capture the post-decompression snapshot at the moment control reaches the game's real entry point — set a breakpoint there in the emulator, then save state.

## Finding ORG, PC, and SP

- **`ORG`** — the lowest address the program occupies. For a single-block game, it is where the loader places the block. Inspect the snapshot or the tape block header. Code that runs from `$4000` deliberately reuses screen memory as part of the program.
- **`PC`** — for a tape game, the BASIC bootstrap ends in `RANDOMIZE USR n`, where `n` is the entry. Read it from the BASIC, or from the `USR` argument the loader jumps to. For a snapshot, it is the saved `PC`.
- **`SP`** — the loader sets the stack before handing off; the snapshot records it. A game that relocates near the top of RAM often parks `SP` just below its own top.

Record all three in the Makefile (`ORG`, `PC`, `SP`) and the `.t2s`. They are the contract between the snapshot and the round-trip — `bin2sna` uses them to rebuild a snapshot that must match the original.
