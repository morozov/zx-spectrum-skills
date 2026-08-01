# Authoring the TR-DOS loader (stage 2)

From the loading analysis, write `src/boot.asm` (the disk loader) and `src/boot.bas` (the BASIC bootstrap that carries it). The job: reproduce the tape loader's memory effect — same bytes at the same addresses, same hand-off — but read the payload with TR-DOS disk reads instead of tape reads.

## The BASIC bootstrap (`boot.bas`)

Same idiom as the tape original: a `REM` holding the machine code, autorun into a `USR` call.

```
 1 REM {XX}{XX}...   ; the loader bytes, as {hh} escapes
10 RANDOMIZE USR (PEEK 23635+256*PEEK 23636+N)
```

- `PEEK 23635+256*PEEK 23636` is `PROG`; `+N` is the byte offset of the first loader byte inside the program. The build substitutes the assembled loader for a `__LOADER__` placeholder (bas2tap reads `{hh}` as a literal byte).
- **Compute `N` empirically**, do not guess: run the real `boot.bas` through `bas2tap` with a known sentinel for `__LOADER__`, parse the tokenized program block, and find the sentinel's offset from `PROG`. `N` depends only on the text *before* the placeholder, not on the loader's length — so it is stable as the loader grows.
- `bas2tap -sboot -a10` names the file `boot` and autostarts at line 10.

## The TR-DOS sector read: `CALL $3D13`

The one primitive the loader needs. Register contract:

| Reg | Meaning |
| --- | --- |
| `DE` | FDD head position (track in `D`, sector in `E`) |
| `B`  | number of 256-byte sectors to read |
| `C`  | `$05` — the read-sectors command |
| `HL` | destination address |

The files are laid out **contiguously** on the disk in load order, and `$3D13` advances the head position as it reads. So the idiom is: `LD DE,($5CF4)` before each read to pick up where the previous read left off. `$5CF4` holds the live head position; after TR-DOS auto-runs `boot`, it points at the sector right after the boot file (i.e. the first payload block).

```
LD DE, ($5CF4)   ; restore the FDD head position
LD BC, $0705     ; B = 7 sectors, C = 5 = read command
LD HL, $9C40     ; destination
CALL $3D13
```

## The loading screen

The screen is stored compressed (Laser Compact, stage 3). Load the compressed self-extracting block to a high free address and `CALL` it; it unpacks itself to `$4000`.

```
LD DE, ($5CF4)
LD BC, <sectors>05
LD HL, $9C40     ; a high free area, clear of the screen
CALL $3D13
CALL $9C40       ; self-extracting screen, unpacks to $4000
```

The `laser521 -d` depacker is **position-independent** — it locates its source relative to `PC` (`CALL $1FC6` get-PC trick + `ADD HL,DE`) and writes to a fixed `$4000`. So `$9C40` is just a convenient high load address, not a requirement; any address clear of the screen and of the live code works. Decompress *before* loading the data if the data will overwrite the area the block was loaded to.

## The data — and the stack-overlap hazard (the hard part)

A tape loader reads the payload straight to its final home and freely clobbers the BASIC area, system variables, and stack — nothing needs them by then. A **disk** loader is itself resident code that is still running, and TR-DOS uses the machine stack throughout the read. So a block whose final home overlaps any live workspace cannot be read straight there.

The overlap is usually with one of: the running loader code, TR-DOS workspace, or — the easiest to miss — **the stack**.

After TR-DOS auto-runs `boot`, the loader runs with `SP` near the top of RAM. If the data block fills RAM to the top (final home reaching `$FFFF`), a direct read to that home overruns the stack as it climbs — including the read routine's own pushed return addresses. The `$3D13` call then **never returns**: it does not error (`rst $08`), does not reset, it just spins forever in TR-DOS's FDC step/settle delay. The hand-off `JP` is never reached. A read that ends below `SP` returns; one that crosses `SP` never returns, with or without a `$FFFF` wrap. The cause is the stack overlap, not the wrap.

Two fixes:

1. **Move the stack below the data**, as the loader's first act:
   ```
   LD SP, <addr>   ; below the data destination
   ```
   Then read straight to the final home. Simpler and faster (no relocation). A natural `SP` value is the one the game itself sets at its entry. The read may overshoot `$FFFF` by a sector of padding, which wraps into the paged-in TR-DOS ROM and is ignored — harmless once the stack is out of the way.

2. **Load to a temp area below the stack, then relocate up** with `LDIR`/`LDDR` to the final home. Use this when there is no `SP` value clear of both the data and the loader, or when the game being converted had a relocating tape loader you want to mirror.

Either way the rule is the same: **the sector read must not touch the live stack** (or the loader code, or TR-DOS workspace).

### Whole-sector overshoot

TR-DOS reads whole 256-byte sectors. A block ending exactly at `$FFFF`, read directly to its home, makes the final sector's read overshoot `$FFFF` and wrap to `$0000`. Those wrapped bytes hit the paged-in TR-DOS ROM and are discarded — harmless. Do not mistake the overshoot for the failure cause; check the stack.

## When the body fills all of RAM

A payload that ends well below the top of RAM leaves a depacker or a load-to-temp area somewhere to live. A body that fills RAM almost to `$FFFF` leaves no free high region — the niche above it can be a few dozen bytes, too small for a ~70-byte decompressor. Two facts unlock it:

- **The loading screen is reclaimable if the game clears it on entry**, redrawing `$4000`–`$5AFF` as its first act. Confirm this in stage 1 (see `analysis-techniques.md`). If so, the loading-screen region is don't-care after hand-off and is the depacker's home — the only RAM clear of the body.

- **Decompress the body in place.** Store it ZX0- (or ZX7-) compressed, read the blob so it ends at `$FFFF`, and forward-decode it to its home in place. The compressor reports a **delta** — how many bytes the compressed data's end must sit above the decompressed data's end so the write pointer never overtakes the unread source. It must fit the headroom above the body's top. `dzx0_standard` / `dzx7_standard` are plain forward decoders — in-place is just a source placed at the top.

Putting the depacker in the screen, two details matter:

- **Use the pixel area, not the attributes.** Bytes that land in the attribute file (`$5800`–`$5AFF`) show as mangled color cells. Park the depacker in the bitmap and blank the attributes (`LD (HL),0` across `$5800`–`$5AFF`) so its bytes read as black on black.
- **Clear the screen first.** `CALL CLS` before unpacking the loading image, so it draws onto a clean field rather than over TR-DOS leftovers.

The depacker can be a separate disk file or inlined into the boot REM and relocated out before the decode. Inlining saves a file and a read but needs the loader's own address — see below.

## Finding the loader's own address (the ROM PC trick)

A loader that relocates inlined data needs its own runtime address, but it runs from the BASIC REM at `PROG + N`, and absolute self-references assembled at ORG 0 are wrong there — which is why a simple loader only ever `CALL`s fixed addresses. Do **not** hardcode `PROG + N`: `N` is a property of the BASIC text, and duplicating it in the loader couples the two silently.

Use the ROM "`LD HL, PC`" trick: `$1FC6` pops its return address into `HL` and jumps back, leaving `HL` = the address right after the `CALL`. Add the assembly-time offset to the inlined block:

```
LD DE, block - pc - 1   ; offset from the address after the CALL, less 1
INC E                   ; finalize the offset and reset the Z flag for $1FC6
CALL $1FC6              ; HL = address immediately after this CALL
pc:
ADD HL, DE              ; HL = runtime address of `block`
```

The `-1` / `INC E` resets the Z flag (which `$1FC6` requires) while leaving `DE` at the true offset; keep the offset's low byte clear of `$FF` so `INC E` does not carry into `D`.

## Hand-off

Reproduce the analysis's hand-off style:

- **Direct jump** — `JP <entry>`.
- **Stack-pointer jump** — `LD SP,<v>` then `RET` (the entry word sits at `<v>`).
- **Relocate-then-jump** — move the block into place, then `JP <entry>`.

A game that sets its own `SP` and `DI` at the entry needs no stack setup from the loader — but the loader still needs a safe stack *during* the read (see above). Confirm the entry address and the first bytes there against the analysis; verify in stage 4 that the breakpoint at the entry sees them.
