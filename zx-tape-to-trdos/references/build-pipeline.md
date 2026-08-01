# Building the disk image (stage 3)

The `Makefile` turns the original tape plus `src/boot.asm`/`src/boot.bas` into a `*.scl`. This doc records the pipeline and the gotchas that are easy to get wrong.

## Pipeline

```
tape (.tzx.zip)
  └ wget → unzip → tzx2tap ........................ raw byte source
       └ tapto0 (in a tmpdir) ..................... headerless blocks: screen, data
            ├ screen: 0tobin → [decode] → .scr
            │    └ laser521 -d → binto0 3 → 0tohob → screenz.$C
            └ data:   0tobin → [decode] → .bin
                 └ binto0 3 → 0tohob → data.$C
src/boot.asm → pasmo → boot.bin
  └ sed __LOADER__ → boot.bas → bas2tap → tapto0 -f → 0tohob → boot.$B
createtrd + hobeta2trd (boot.$B, screenz.$C, data.$C) + monoblock patch → .trd
  └ trd2scl → .scl
```

Notes per stage:

- **Source.** `tzx2tap` is fine here — we only need the block *bytes*, and its turbo-timing lossiness does not affect byte content. (It IS unusable for the stage-1 analysis *load*; different concern.)
- **Extraction.** `tapto0` writes headerless blocks as `headless.000`, `headless.001`, … A game's screen and data are typically two consecutive headerless blocks. Run `tapto0` in a `mktemp -d` and copy the outputs out — you cannot use `tapto0 -f` because same-tap headerless files overwrite each other.
- **Decode.** If stage 1 found the loader applies a per-byte transform (`XOR`/`INC`/…), decode the raw block to its in-memory form here, with a small script in the project's `tools/` that applies that transform. If the loader stores bytes straight (no encoding), there is no decode step — go straight from `0tobin` to the `.scr`/`.bin`. Name the intermediates after what they hold: call a block "encoded" only if it is.
- **Screen compression.** `laser521 -d screen.scr screenz.bin` produces a self-extracting compressed block (depacker + data). It runs at build time (laser521 is the PC port of Laser Compact 5.2.1) — the compressed screen is NOT a pre-built source file. `binto0 screenz.bin 3` re-wraps it as a type-3 (CODE) `.000`; `0tohob` makes the hobeta `.$C`. The loader's `CALL`-the-screen address is just where you load this block (the depacker is position-independent).
- **The `.000 → .bin → .000` round-trip** (data and screen) converts the headerless `tapto0` `.000` into a proper type-3 `.000`. Name the two `.000`s distinctly (the tape extract vs the binto0 output) or they collide.
- **Boot file.** `pasmo --bin src/boot.asm boot.bin`; `sed` the `hexdump -ve '1/1 "{%02x}"'` of `boot.bin` into `__LOADER__` in `boot.bas`; `bas2tap -sboot -a10`; `tapto0 -f`; `0tohob`.

## Compressing the body (ZX0 / ZX7)

When the disk loader expands the body at run time (in place, or to a low home), the build compresses it with ZX0 or ZX7 and vendors the matching Z80 decoder in `lib/` (`dzx0_standard.asm` / `dzx7_standard.asm`). ZX0 is the newer, smaller format — prefer it. Two traps:

- **ZX0 has two incompatible formats.** Modern ZX0 (`einar-saukas/ZX0`) emits the **v2** format; z88dk's bundled `z88dk-zx0` is **v1.5** and emits the retired v1 format, which the canonical v2 `dzx0_standard` decoder cannot decode — it silently hangs (the loader never reaches the entry). Match the compressor to the vendored decoder: build the canonical compressor from `einar-saukas/ZX0` source and vendor its `z80/dzx0_standard.asm`, or use z88dk's compressor with z88dk's v1 decoder. ZX7 has no such split, so its decoder is portable.
- **In-place placement.** For an in-place decode the compressor's reported `delta` sets the safety margin (see `loader-authoring.md`); load the blob ending at `$FFFF` (`load = $10000 − size`) and have the loader read it by sector count to that address.

## The monoblock `.trd`

The loader reads by **sector count**, not by named file, so the files must be contiguous and the catalog must present them as one blob:

1. `createtrd <tmp>` — empty image.
2. `hobeta2trd` each file in load order: `boot.$B`, `screenz.$C`, `data.$C` (this places them contiguously from track 1).
3. Patch the **first** catalog entry's sector count (offset 13) to the **sum** of all files' sector counts, so `boot` appears to span the whole payload. Sum the per-file sector byte (offset 14 of each hobeta file). `printf` only speaks octal for raw bytes: `printf "\\$(printf %o $total)"`.
4. Zero the remaining catalog entries (16 bytes each from offset 16): the screen and data are now hidden inside the `boot` blob.
5. `mv` the tmp image to the target (build into a temp file, rename on success, so a failed build leaves no half-image).
6. `trd2scl` → `.scl`.

`sectors = ceil(bytes / 256)`. TR-DOS auto-runs the file named `boot`; it loads only `boot`'s BASIC, which then sector-reads the rest.

## macOS / parallel-make gotchas

- **Do not name a make variable `TMPDIR`.** `mktemp` reads `$TMPDIR` from the environment, and make re-exports any override; if one recipe sets `$(eval TMPDIR=$(shell mktemp -d))` and then `rm -r`s it, a later recipe's `mktemp` targets the deleted dir and fails — which forces a confusing two-pass build. Use a non-shadowing name (`WORK`, …).
- **Multi-target rules race under `make -j`.** `a b: prereq` runs the recipe once per target, so under `-j` the shared extraction recipe runs twice concurrently and races on its tmpdir. Use a GNU make 4.3+ **grouped target**: `a b &: prereq` (recipe runs once, produces both). With these two fixes a single `make` completes in one pass.
