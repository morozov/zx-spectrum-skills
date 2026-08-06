# Driving FuseX with libfusex (the C ABI)

`libfusex` is FuseX built as a shared library. Load it in-process with `ctypes` and drive the machine directly: boot media, hold and release keys, step frames, read the rendered screen, peek and poke RAM, and record RZX files and movies. No TCP, no external client, no window. This is the interface for *playing and exercising* a program — proving a game is playable, that controls respond, that scoring and lives work — as opposed to the gdbserver, which is for inspecting internals.

- **The library must come from the [`automation` branch](https://github.com/morozov/fusex/tree/automation) of `morozov/fusex`.** Upstream's library exports only `fusex_display_info` and `fusex_display_frame`, so the `fusex_peek`, `fusex_peek_block` and `fusex_get_reg` rows below are missing from it.
- **Library and ROMs.** On macOS the library is `FuseX.app/Contents/Frameworks/libfusex.dylib` and the ROMs are in `FuseX.app/Contents/Resources`, under `~/Applications` or `/Applications`. On Linux, set `FUSEX_LIB` to the `libfusex.so` of a `--with-null-ui` build and `FUSEX_ROMS` to its tree's `roms/`; `/usr/lib/libfusex.so` and `/usr/share/fusex` are tried when they are unset. `FUSEX_LIB` and `FUSEX_ROMS` override the defaults on every platform. Pass the ROM directory as `--rom-dir`, and the working directory stops mattering.
- **Wrapper**: `scripts/fuse_drive.py` resolves both paths and wraps the calls below.
- **When a symbol is missing**, `ctypes` raises `AttributeError` on first use and says nothing about why. The library carries no export list: it exports whatever Fuse's objects define, so Fuse's own functions are callable alongside the `fusex_*` additions. `nm -gU libfusex.dylib` is the authoritative answer for a given copy.

## The C ABI

| Symbol | Signature | Does |
| --- | --- | --- |
| `fuse_init` | `int(int argc, char **argv)` | Boot with FuseX CLI args. Returns 0 on success. Once per process. |
| `spectrum_do_frame` | `void(void)` | Advance one frame, as fast as possible — **not** real-time. |
| `keyboard_press` | `void(int key)` | Press a key. `key` is ASCII for letters, digits and space (see below). |
| `keyboard_release` | `void(int key)` | Release a key. Always pair with the matching press. |
| `joystick_press` | `int(int which, int button, int press)` | Joystick button hold or release. |
| `fusex_display_info` | `fusex_display_info_t *(void)` | Display geometry: `width`, `height`, `border_width`, `border_height`. |
| `fusex_display_frame` | `fusex_display_frame_t *(void)` | The indexed framebuffer, one palette index 0–15 per pixel, border included. |
| `fusex_peek` | `int(int addr)` | Read one memory byte. Ground-truth oracle — validation only, never a player's input. |
| `fusex_peek_block` | `void(int addr, int len, unsigned char *buf)` | Read `len` bytes from `addr`. |
| `writebyte_internal` | `void(uint16_t addr, uint8_t val)` | Write one memory byte. |
| `fusex_get_reg` | `int(int which)` | Read a Z80 register: 0 `PC`, 1 `SP`, 2 `AF`, 3 `BC`, 4 `DE`, 5 `HL`, 10 `IX`, 11 `IY`. |
| `snapshot_write` | `int(const char *path)` | Write a snapshot (`.szx`/`.z80`) of the current state. |
| `snapshot_read` | `int(const char *path)` | Load a snapshot. |
| `rzx_start_recording` | `int(const char *path, int embed_snapshot)` | Begin recording an RZX input replay. |
| `rzx_stop_recording` | `int(void)` | Stop RZX recording. |
| `rzx_playback` | `int` (data) | Non-zero while an RZX is playing back. |
| `movie_start` / `movie_stop` | `void(const char *)` / `void(void)` | Record / stop an FMF movie (render to MP4 with `fmfconv`). |
| `fuse_end` | `int(void)` | Tear down the emulator. |

## Booting

`fuse_init` takes the same argument vector as the FuseX CLI. The first element is the program name; the rest are flags and a media file. `.tap`/`.tzx` tapes want `--auto-load` (types `LOAD ""` and starts the tape); `.sna`/`.z80`/`.szx`/`.trd` snapshots load directly. Keep the argv array alive for the life of the emulator.

```python
args = [b"fusex", b"--no-banner", b"--rom-dir", ROMS, b"--auto-load", b"/abs/path/game.tap"]
argv = (ctypes.c_char_p * len(args))(*args)
assert lib.fuse_init(len(args), argv) == 0
for _ in range(2500):   # step past the tape load — nothing is real-time
    lib.spectrum_do_frame()
```

There is no fast-forward flag: each `spectrum_do_frame` call runs one frame. Tape loading through the ROM loader costs a few thousand frames; a snapshot boots in one. **After booting, capture a frame and look at it** before you assume the program is where you think — do not blind-step into an attract loop or a `0 OK` prompt (a tape built without an auto-start line stops at the prompt after load).

## Input — keys are ASCII

`keyboard_press` and `keyboard_release` take Fuse's key code, which is the ASCII code for printable keys. Letters are their lowercase ASCII value and register **unshifted**:

- `ord('t')` presses the T key with no shift. A program testing `INKEY$="t"` matches; one testing `INKEY$="T"` does **not** (that needs CAPS SHIFT). This is a real gameplay fact, not an emulator quirk — if a game's controls only respond with CAPS SHIFT held, its `INKEY$` comparisons are uppercase.
- Space is `ord(' ')` (32), digits `ord('0')`…`ord('9')`. Enter is `0x100`, CAPS SHIFT `0x101`, SYMBOL SHIFT `0x102`.

Hold a key across frames, then release — a single press and release with no frames between may be missed by a program that samples the keyboard once per game loop. `Fuse.tap` in `scripts/fuse_drive.py` holds for four frames.

## Observation — the screen buffer

`fusex_display_frame()` points at the whole display, border included, one byte per pixel, each the **ZX palette index 0–15** of that pixel. `fusex_display_info()` gives its size and border widths; the play area is the 256×192 window inside the border. A pixel is its INK color where the bitmap is set, its PAPER color where clear — so the buffer already resolves ink and paper, and color is directly readable. The buffer is borrowed: copy it before stepping again.

```
index:  0 black  1 blue   2 red    3 magenta  4 green  5 cyan  6 yellow  7 white
        8..15 = same hues, bright.   RGB = (192 normal | 255 bright) per channel.
```

`Fuse.screen` in `scripts/fuse_drive.py` crops the play area into a `(192, 256)` array, and `Fuse.to_rgb` renders it with this palette.

Reading a HUD value (score, lives) off the screen is a matter of locating its character cells (row × 8, col × 8) and matching digit glyphs, or — for a quick check — testing whether a cell has any non-PAPER pixel. For an exact oracle, `fusex_peek` the variable in RAM instead.

## Recording a run

Wrap a play session in `rzx_start_recording(path, 1)` … `rzx_stop_recording()` to capture a deterministic input replay; the RZX re-drives the identical run later (and renders to MP4 via the movie API + `fmfconv`). RZX and movie recording is the reproducible way to hand a playthrough to a human or to re-inspect exact frames.

Boot an `.rzx` the same way as any other medium, with `--auto-load run.rzx` in the `fuse_init` argv. `ctypes.c_int.in_dll(lib, "rzx_playback").value` reads non-zero until the recording runs out.

## Which addresses executed: the profiler

FuseX's Z80 profiler charges each instruction's t-states to the address it started at, across the whole 64K address space — ROM included, and the ROM dominates the count on any run that touches the loader or a system routine. The same library exports it, so `ctypes` reaches it directly:

| Symbol | Signature | Does |
| --- | --- | --- |
| `profile_start` | `void(void)` | Zero the per-address t-state totals and start counting. |
| `profile_finish` | `void(const char *path)` | Write the map, then stop counting — **both only if `fopen` succeeds**. |
| `profile_active` | `int` (data) | Non-zero while counting. |

`profile_finish` writes one CSV line per address that accumulated any t-states — `0x5b2a,1606` — and omits the rest, so the file *is* the set of addresses an instruction began at. Two things about the pair are not in its name:

- **A failed write returns like a successful one.** An unwritable path makes `profile_finish` print one line to stderr and return, having written no file *and* left `profile_active` set. The return type is `void`, so a driver that reads the file back gets a stale map or a `FileNotFoundError` with nothing naming the cause. Check `ctypes.c_int.in_dll(lib, "profile_active").value` after the call: 0 means the map was written.
- **Only `profile_start` zeroes the totals.** `profile_finish` leaves them standing, so `start … finish … step … finish` writes a second map that still carries the first run's counts. One `profile_start` per map.

Wrap an RZX playback in the pair to get a map of a reproducible run rather than of whatever happened this time. Bound the stepping by the recording, not by a frame count: a fixed count large enough to play the RZX out keeps free-running once it ends, and everything after that point is this session's own behavior, not the recording's.

```python
lib.profile_start.argtypes = []
lib.profile_finish.argtypes = [ctypes.c_char_p]
lib.fuse_init(...)                # boot the .rzx
lib.profile_start()
while ctypes.c_int.in_dll(lib, "rzx_playback").value:   # exactly the recorded run
    lib.spectrum_do_frame()
lib.profile_finish(b"/tmp/run.profile")
assert ctypes.c_int.in_dll(lib, "profile_active").value == 0, "profile_finish failed"
executed = {int(l.split(",")[0], 16) for l in open("/tmp/run.profile") if l.strip()}
```

**A hit proves code; a miss proves nothing.** Only the first byte of an instruction is charged, so an instruction's operand bytes never appear, and any path this run did not take is absent whether it is code or data. Read the map as positive evidence, and widen the run before reading anything into a gap.

**A hit is evidence about the memory that ran, which is not always the memory you are reading.** Two filters make the difference:

- **Drop everything below `$4000`.** Those are ROM addresses, and they say nothing about the program.
- **Profile the state you are asking about.** A run that includes the tape load spends its RAM hits in the loader, and the loader's memory is not the loaded game's — its buffers, and bytes the game has not written yet, sit where the post-load map has code and data. Boot the post-load snapshot instead.

## Gotchas

- **Not real-time.** Frame counts, not wall-clock. Budget a few thousand frames for a tape load; step in chunks and re-check the screen.
- **Pass `--rom-dir`.** Without it, the boot searches the current directory for ROMs and fails with a missing-ROM error. Give media as absolute paths.
- **One machine per process.** The library holds a single global emulator. For independent states use `snapshot_write`/`snapshot_read` around a start snapshot, or separate processes.
- **`peek` is an oracle, not a controller.** Use it to *verify* what the screen shows, never as a shortcut that bypasses reading the display.
- **Palette RGB is 192/255**, not 205 — match it if you need pixel-exact color comparison against a reference capture.

## Worked example — play and verify

Boot a tape, confirm it is running, move the player, fire, and read the HUD. `scripts/fuse_drive.py` packages this; the shape is:

```python
RIGHT, FIRE = 'p', ' '                    # the game's keys, from its controls screen
f = Fuse().boot_media(TAP)                # load + start
f.save_png("start.png")                   # LOOK before acting
for _ in range(6): f.tap(RIGHT)           # move right; re-capture to confirm motion
for _ in range(20): f.tap(FIRE); f.tap(RIGHT)  # fire while sweeping; watch score/lives change
f.save_png("after.png")
```

If the move key moves the player and the fire key changes the score or lives, the controls and the fire path work — verified end-to-end, with no reliance on reading the disassembly.
