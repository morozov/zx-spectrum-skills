# Verifying the disk image (stage 4)

Prove the built `.scl` boots and the loader reaches the game's entry with the correct bytes there. Driving mechanics (launch, `gdb.sh`/`gdb-session.py`, `z88dk-gdb` commands, reset guard) are the **`zx-fuse-driver`** skill; this doc is the disk-verification recipe and its two hard rules.

## Two hard rules

1. **Never write the user's FuseX preferences.** Enable the gdbserver with CLI flags only — `--gdbserver-enable --gdbserver-port=1337`. Do NOT `defaults write org.fuse-emulator.fusex …`; it mutates persistent state you do not own.
2. **Never let the emulated game run free — it plays sound.** Keep the machine halted at a breakpoint, or stop the emulator process (`kill "$FPID"`). `gdb.sh` *detaches* on exit, which RESUMES the emulator — so after a `gdb.sh` call either the machine is halted at a breakpoint you set, or you must stop the process immediately. During a `cont`, only let it run toward a breakpoint that fires *before* the game executes (the entry), so it never free-runs. For multi-step inspection keep it halted with `gdb-session.py` and stop the process instead of running `stop`.

## Launching a disk

```
python3 ../zx-fuse-driver/scripts/fuse_drive.py gdbserver 1337 \
  --machine=pentagon /abs/path/Game.scl >/tmp/fuse.log 2>&1 &
FPID=$!
```

- Passing the `.scl` as the file argument inserts it in the Beta drive.
- `--machine=pentagon` boots a Pentagon, which **auto-runs the `boot` file** on the disk. FuseX's default 48K machine has no TR-DOS.
- A plain launch may sit idle in the TR-DOS ROM for a moment before auto-boot completes — do not mistake that for failure. If auto-boot does not fire (the disk was inserted after TR-DOS came up), `monitor reset` with the disk present re-triggers it.

## The verification: trap the entry

Attach early (the machine halts on attach, before the loader has run), set a breakpoint at the game's entry address (from the analysis), let auto-boot run the loader into it, and confirm both the hit and the bytes there.

```
# one batch session, then kill so nothing free-runs
TIMEOUT=90 gdb.sh "break 0x<entry>" "cont" "reg" "x /4 0x<entry>"
kill "$FPID"
```

PASS = `Hit breakpoint @<entry>`, `PC=<entry>`, and `x` shows the entry opcodes the analysis expects (e.g. `F3 31 …` = `DI; LD SP,…`). The breakpoint catches the hand-off *before* the game executes, so this never makes sound.

For a compressed body, also spot-check that it *decoded* correctly, not just that control arrived: compare `x` dumps at the body start, middle, and entry against the original block. For an **in-place** decode add the top-of-RAM tail (e.g. `x /16 0xffc0`) — source and destination overlap most there, so a write-overtakes-read bug (wrong `delta`, wrong load address) corrupts the tail first while the entry may still look right.

## Reading a failure

A `cont` that never hits the entry within a generous timeout is a failure — and the *shape* of the failure tells you what is wrong. Set the entry breakpoint plus guards and see which (if any) fires:

- **Hangs** — entry never fires, and neither does the error vector (`0x0008`) nor reset (`0x0000`): the loader is stuck, classically the data read trampling the live stack so `$3D13` never returns (see `loader-authoring.md`). Sample `reg` after the timeout — a spin in the TR-DOS FDC delay loop confirms it.
- **Reset** — `0x0000` fires: the load failed and the loader/ROM reset. (Note `0x0000` is also the normal boot vector, so do not set a `0x0000` guard across a `monitor reset`; use it only on a load already in progress.)
- **Reached but wrong bytes** — entry fires but `x` shows garbage: the data landed at the wrong offset; recheck the destination math.

### Bisection to localize a hang

To isolate *why* a read hangs without rebuilding, trap the read entry (`break 0x3d13`, `cont` to the data read, confirm `BC`/`HL`), then patch a register (`set bc 0x<n>05` to change the sector count, or `set sp 0x<v>`) and `cont`, watching the read's return address / `0x0008` / `0x0000`. Reducing the read until it stops crossing a live region (and starts returning) pinpoints the overlap. Keep it halted and stop the process when done.
