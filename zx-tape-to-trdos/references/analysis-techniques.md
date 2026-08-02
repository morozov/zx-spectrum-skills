# Analysis techniques and patterns

Patterns that recur in tape loaders. Use them to recognize what a loader is doing and to translate that into the disk-loader implications the report must state. These are recurring shapes, not laws — verify each against the game in front of you.

The general method for deriving Z80 logic — static reading, idiom recognition, dynamic confirmation — is the shared reference at `../shared/disasm-analysis.md`. The live driver (enabling the FuseX gdbserver, the `gdb.sh`/`gdb-session.py` session models, the command set, reset detection, state discipline) is the **`zx-fuse-driver`** skill — use it for everything about running the loader. This doc is the tape-loader-specific layer: the patterns below, and the trapping recipes in "Driving the loader under FuseX" at the end.

## Why this analysis exists

On the Spectrum there is no shared filesystem: every tape game carries its own loader. To load the same game from a TR-DOS disk you must reproduce the _effect_ of that loader — get the same bytes to the same addresses and hand control over the same way — using disk reads instead of tape reads. So the analysis has to recover three things: **what ends up where**, **how blocks are encoded on the way in**, and **how control reaches the game**.

## BASIC is just a bootstrap; the ASM rides in a REM

You cannot load-and-run raw machine code on a Spectrum, so every tape game ships a tiny BASIC program whose only job is to hand off to machine code. **The usual shape is one REM, one USR, one hand-off.** The two views matter:

- **PROG is BASIC, not ASM.** Never disassemble PROG as Z80. Read it _as BASIC_ (detokenize). The machine code is embedded inside a `REM` line — often a high, non-listable line number — but it is still just a line in the BASIC program.
- The BASIC program is the orchestration layer. Read it to find the `RANDOMIZE USR (PEEK 23635+256*PEEK 23636+N)` call (and any `POKE`s). `PEEK 23635+256*PEEK 23636` is `PROG` (`$5C53`); `+N` is the offset into the REM where the code sits. The loader entry is `PROG + N`.
- **Disassemble only from the USR target** (`PROG + N`), not from PROG. On 48K `PROG` is normally `$5CCB`, but it shifts, so read it from memory live.

So the method is: read BASIC → follow the `USR <address>` → disassemble there. The disk version reproduces the same bootstrap (see `loader-authoring.md`), so the report records `N` and the resulting entry address.

To read the BASIC without it autorunning, either trap at the USR target (the trap fires after the BASIC block has loaded but as it hands off), or poke the high byte of NEWPPC to suppress autorun (`POKE 23619,128` / `set 23619 128`) and read it at leisure.

## Loader characterization

Once you are at the USR target, characterize the machine code. It is usually one of these, and turbo loaders are common — do **not** assume a ROM loader:

- **Relocating / self-decrypting bootstraps.** The entry often copies itself to high RAM, decrypting as it goes, then `JP`s there — so the _real_ loader only exists after the copy runs. Recognize a short copy loop (`LD A,(HL) / <transform> / LD (DE),A / INC DE / INC HL / DJNZ`) ending in `JP <high addr>`. The transform can be `XOR key`, `INC A`, etc. Relocation is CPU-only (no tape), so let it run and trap at the destination to read the plaintext body.
- **Custom turbo loaders.** These bypass the ROM and read the EAR port directly with their own edge detection — look for `IN A,($FE) / RRA / AND $20 / …` in a timing loop. Block destination and length come from whatever registers the loader sets before its load call (commonly `IX`=dest, `DE`=length, `A`=flag) — read them from the disassembly, not from any ROM convention. A turbo load that fails typically resets (`JP NC,$0000` or similar): use the reset guard from the `zx-fuse-driver` skill.
- **ROM-based loaders.** Some games do use the ROM. The standard tape load entry is `LD-BYTES` at `$0556`; protected ones call a few bytes in (e.g. `$055A`) to skip header/flag handling and defeat generic copiers. There the convention holds: `IX`=destination, `DE`=length on entry.

## On-tape encoding

Some games store blocks XOR'd or otherwise transformed on tape and decode them during load (so a raw rip looks like garbage). The reliable source of truth is the loader disassembly: does it apply a per-byte transform around its load (`XOR key`, `INC A`, `ADD n`, …)? If yes, the on-tape bytes are encoded and the in-memory bytes after load are the decoded form. If the load just stores bytes straight, there is no per-byte encoding (a turbo loader's framing may be the only "encoding").

When you can also get the raw on-tape bytes, corroborate by diffing them against the in-memory range captured from FuseX (`x /<n> <addr>`) after the load. Note the extraction caveat for turbo games: `tapto0`/`0tobin` read a _TAP_, and converting a turbo `.tzx` to TAP is lossy — so for turbo blocks the in-memory capture is the dependable side of the diff, and a raw extraction may need the TZX block data read directly rather than via `tapto0`.

An encoding can chain steps, for example an `XOR` with a key, then a rotate, then an add, per byte. The disk version stores the _decoded_ bytes, so the disk loader needs no decode step — but the report must flag the encoding so whoever prepares the files decodes them first.

## Hand-off styles

Ways a loader passes control to the game:

- **Direct jump** — the loader ends in `JP <entry>`. Simplest case.
- **Stack-pointer jump** — the game fills essentially all of low RAM, leaving no room for a resident loader, stack, or return address. So instead of `CALL game` / `RET`, the loader sets `LD SP, <value>` and executes `RET`, popping the game's entry address off `<value>` and jumping into the just-loaded data. Recognize it by the absence of a final `JP` and the presence of an `LD SP` right before `RET`.
- **Relocate-then-jump** — the loader moves a just-loaded block into its final home (often a region the loader itself occupies) and then `JP`s the entry. Because the move can overwrite the loader, it first copies a small mover stub to a safe spot and runs it there. This is the hand-off equivalent of load-to-temp-then-relocate.

The disk loader must reproduce whichever style the original uses. Confirm the entry empirically — disassemble the final transfer and, for the SP-jump, read the word at `SP`.

## Why blocks often need load-to-temp-then-relocate

This is the single most important implication to get right. On tape the payload is read straight to its final home and overwrites the BASIC area and system variables — harmless, because nothing else needs them by then. But a _disk_ loader is itself resident code, and TR-DOS reserves working RAM during a load. If a block's final address overlaps the running disk loader or TR-DOS workspace, reading it straight there corrupts the load.

The usual answer: read such a block to a free temporary address, then `LDIR` it down to its real home as the last step before hand-off. Part of this analysis is identifying _which_ blocks need this and proposing a safe temporary address (somewhere not touched by the loader, the screen, or the final data).

## Is the loading screen reclaimable?

When the payload fills almost all of RAM there is no free region for the disk loader's depacker, and the loading-screen area `$4000`–`$5AFF` becomes the only fallback work area — but only if the game does not read it after entry. To check whether the game redraws it, trap the entry (after the full real-time load) and disassemble its first instructions. A screen clear there (`LD HL,$4000 / LD BC,$17FF / LD (HL),0 / LDIR`, then an attribute fill) means the loading screen is purely cosmetic and the region is free for the disk loader to use. Record the finding — it decides where the disk loader's depacker can live (see `loader-authoring.md`, "When the body fills all of RAM").

## Screen compression (note it here, do it in stage 3)

The 6912-byte loading screen compresses well (Laser Compact packs it into a self-depacking block the loader just `CALL`s). The actual compression happens in the build (stage 3, `build-pipeline.md`) — but the analysis should note that the screen is a compression candidate and report its raw size, because that decision changes the disk sector budget.

## Sector arithmetic

TR-DOS allocates whole 256-byte sectors. For each block, sectors = `ceil(bytes / 256)`. The disk loader reads by _sector count_, not by named file, so the build lays the files out contiguously and then patches the first directory entry's length to the **sum** of all files' sectors so the whole thing reads as one monoblock. So the report's sector budget (per block and total) is exactly the number the eventual build step needs. Report raw, uncompressed sector counts, and separately note where compression will shrink them.

## Driving the loader under FuseX

The generic driver — enabling the gdbserver, the batch `gdb.sh` and persistent `gdb-session.py` session models, the `z88dk-gdb` command set, reset detection, and state discipline — is the **`zx-fuse-driver`** skill. Read it first; what follows is specific to trapping and reading a *tape loader*.

**Launch to trap the loader entry.** Load the `.tzx` natively — never convert it, since `tzx2tap` flattens turbo timing and the loader resets — and add `--no-traps --no-fastload` so the BASIC block loads in real time instead of via ROM traps. Without them the bootstrap runs and the loader is already past `PROG+N` before you can attach, so a `break <entry>` never fires:

```bash
python3 ../zx-fuse-driver/scripts/fuse_drive.py gdbserver 1337 --no-traps --no-fastload \
  --tape="/abs/path/Game.tzx" --auto-load >/tmp/fusex.log 2>&1 &
```

These flags only affect standard ROM loads; the turbo data block is real-time regardless. (If you don't need the entry trap, attach mid-load and disassemble the resident loader from memory.)

**Recipe A — find the loader entry.** Read the BASIC's `RANDOMIZE USR (PEEK 23635+256*PEEK 23636+N)` for `N`, read `PROG` (`$5C53`) live, entry = `PROG + N`. Trap there with a reset guard:

```bash
gdb.sh "break 0x0000" "break 0x<entry>" "cont" "reg" "dis 0x<entry>"
```

**Recipe B — read the loader live; follow relocation/decryption.** When the entry copies and decrypts itself to high RAM then `JP`s there, trap the destination and read the plaintext body:

```bash
gdb.sh "break 0x<dest>" "cont" "reg" "x /128 0x<dest>" "dis 0x<dest>"
```

Read the body for the block loads (destination/length/flag, from whatever registers the loader uses) and the final transfer.

**Recipe C — capture the hand-off.** Block destinations/lengths are usually literal in the disassembly (`ld ix,…` / `ld de,…` before each load call). For the hand-off, disassemble the loader's final transfer and distinguish the styles (direct `JP`, `LD SP` + `RET` stack-jump — read the word at `SP` for the entry, relocate-then-`JP`) as described under "Hand-off styles" above.

**A post-load trap costs the full real-time load.** Trapping at the entry is quick (only the small BASIC block loads first); trapping after the screen/data load waits for the whole turbo load, which can run minutes. Raise the timeout and background that call, or use `gdb-session.py` to stay halted. Most of the analysis — entry, loader body, block table, hand-off — is read statically from the trapped entry and needs no full load; only runtime confirmation of the final memory layout does.
