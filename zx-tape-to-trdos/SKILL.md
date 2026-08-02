---
name: zx-tape-to-trdos
description: >-
  Convert a ZX Spectrum tape game (.tzx/.tap) into a working TR-DOS disk
  version (.trd/.scl), end to end. Use this whenever the user wants to make a
  disk version of a cassette game, port a tape loader to TR-DOS, write the disk
  loader/boot for a game, build the .trd/.scl, or asks "how do I get this tape
  game to load from disk" — even if they only say "analyze the loader" (that is
  just the first stage). Covers four stages: analyze the tape loader, author
  the disk loader + BASIC boot, build the disk image, and verify it under FuseX.
  Drives FuseX (via z88dk-gdb) to read the tape loader and to verify the
  result.
---

# Tape → TR-DOS disk conversion

Turn a tape game into a TR-DOS disk version that loads and runs from disk. The deliverable is a project: a `Makefile`, `src/boot.asm` + `src/boot.bas`, and a built `*.scl`.

The work is four stages, in order. Each builds on the previous; do not skip ahead.

| Stage | Goal | Reference |
| --- | --- | --- |
| 1. Analyze | Recover what the tape loader does, block by block | `references/analysis-techniques.md`, the `zx-fuse-driver` skill, `assets/report-template.md` |
| 2. Author | Write the TR-DOS loader (`boot.asm`) and BASIC boot (`boot.bas`) | `references/loader-authoring.md` |
| 3. Build | Extract, compress the screen, assemble the `.trd`/`.scl` | `references/build-pipeline.md` |
| 4. Verify | Boot the `.scl` under FuseX and prove it reaches the game | `references/verification.md`, the `zx-fuse-driver` skill |

## The mental model

A tape game is a tiny BASIC bootstrap (`RANDOMIZE USR …`) that hands off to a machine-code loader, which reads the payload off tape and jumps into the game. To run the same game from disk you must reproduce the *effect* of that loader — the same bytes at the same addresses, the same hand-off — using TR-DOS disk reads instead of tape reads. Stage 1 recovers those facts; stages 2–4 build and prove the disk loader that reproduces them.

## Stage 1 — Analyze

Run the tape loader live under FuseX and produce a **loading analysis** report. This answers: what does the loader do block by block, where does each block end up, how is each encoded, and how does control reach the game?

This is applied code comprehension: the general method (static reading plus live analysis) is the shared reference `../shared/disasm-analysis.md`, and the live driver is the **`zx-fuse-driver`** skill. This stage applies them to a tape loader.

Workflow (full detail, including the tape-specific trapping recipes, in `references/analysis-techniques.md`):

1. Launch FuseX with the `.tzx` natively (`--no-traps --no-fastload --auto-load`). Never convert `.tzx`→`.tap` for the load — `tzx2tap` flattens turbo timing and the loader resets.
2. Read the BASIC as BASIC: get `N` from `RANDOMIZE USR (PEEK 23635+256*PEEK 23636+N)`, read `PROG` (`$5C53`) live, entry = `PROG + N`.
3. Disassemble from the entry; follow any relocation/decryption to the real body. Characterize: turbo vs ROM loader, self-decryption, each block's destination/length/flag, the error path, the hand-off style.
4. Record the block table (sectors = `ceil(bytes/256)`), the memory layout, and — the payoff — the **implications for the disk loader**: final residence of each block, which blocks need load-to-temp-then-relocate, what to compress, the sector budget, and the hand-off to reproduce.
5. Write the report from `assets/report-template.md`.

The block table, entry address, and hand-off from this report are the direct inputs to stage 2.

## Stage 2 — Author the loader

From the analysis, write `src/boot.asm` (the TR-DOS loader) and `src/boot.bas` (the BASIC bootstrap that embeds it). See `references/loader-authoring.md`.

The core is reproducing the tape loader's memory effect with TR-DOS sector reads (`CALL $3D13`) and the same hand-off. The non-obvious hazard is that a block whose final home reaches the top of RAM overlaps the loader's **stack**, and a direct read there clobbers the read routine's own return chain so it never returns. The fix is to keep the destination clear of the live stack (move `SP` below it, or load to a temp area below it and relocate up). `references/loader-authoring.md` has the patterns.

## Stage 3 — Build the disk image

Write the `Makefile` that: downloads the tape, extracts the headerless blocks, decodes them if the loader applied an encoding, compresses the loading screen with `laser521`, assembles `boot.asm` and embeds it in `boot.bas`, then assembles the contiguous monoblock `.trd` and converts to `.scl`. See `references/build-pipeline.md` for the whole pipeline, the tools, and the macOS build gotchas.

## Stage 4 — Verify

Boot the built `.scl` under FuseX and prove the loader reaches the game's entry with the right bytes there. See `references/verification.md`. Two hard rules: never write the user's FuseX preferences (CLI flags only), and never let the emulated game run free — keep it halted at a breakpoint or stop the emulator (a free-running game plays sound).

## Tools

Verify each exists before use; name any that is missing.

- **FuseX** (gdbserver build) + **`z88dk-gdb`** — read the tape loader (stage 1) and verify the result (stage 4). The driver and its mechanics are the **`zx-fuse-driver`** skill; use it rather than re-deriving them here.
- **pasmo** — assemble `boot.asm`.
- **bas2tap** — tokenize `boot.bas`.
- **zxspectrum-utils** (`tapto0`, `0tobin`, `binto0`, `0tohob`, `hobeta2trd`, `createtrd`) — block extraction and TR-DOS file/image assembly.
- **laser521** (Laser Compact 5.2.1) — compress the loading screen at build time.
- **zx0**, built from [einar-saukas/ZX0](https://github.com/einar-saukas/ZX0) — compress the game when the build packs it. z88dk's `z88dk-zx0` emits an incompatible format (see `references/build-pipeline.md`).
- **tzx2tap** — tape conversion (for byte extraction only; never for the analysis load).
- **trd2scl** — `.trd` → `.scl`.

## Output

A self-contained project directory: `Makefile`, `src/boot.asm`, `src/boot.bas`, and the built `{Game}.scl`. One `make` builds the disk image reproducibly from a clean project directory.
