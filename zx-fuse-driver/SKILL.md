---
name: zx-fuse-driver
description: >-
  Drive a running ZX Spectrum / Z80 program under the FuseX emulator through its
  two programmatic interfaces — no GUI. (1) The gdbserver (GDB RSP over TCP):
  breakpoints, memory watchpoints, single-step, register/memory inspect and
  modify, Fuse's internal debugger — for debugging ("debug under Fuse", "why does
  it crash/reset at runtime", "set a breakpoint at $XXXX", "watch this address",
  "step through the loader", "registers when it reaches X", "inspect memory after
  load", "trap the game entry"). (2) The libfusex C ABI (in-process, via ctypes):
  inject keystrokes, step frames, read the 256x192 screen, peek/poke RAM, record
  RZX — for playing and exercising a program headlessly. Use this to confirm
  runtime behavior that reading the source CANNOT prove: "play this game", "drive
  it to game over", "read the score / lives / HUD off the screen", "does firing /
  scoring work", "do the controls actually move the player",
  "verify my change works in the emulator", "confirm the controls respond without
  CAPS SHIFT", "press keys and screenshot the running screen", "is it actually
  playable". Whenever the task is to see what a Spectrum program DOES at runtime
  (not what its code says) — after editing BASIC/asm, wiring up controls, or
  fixing a mechanic — reach for this; running it is the only way to know. The
  foundational runtime capability the zx-game-disasm and zx-tape-to-trdos skills
  build on.
---

# Driving ZX Spectrum programs under FuseX

FuseX exposes two programmatic interfaces to a running machine, both headless and scriptable — no GUI, no window, no focus stealing. This skill covers both. It is platform-generic across Z80 programs, and is the foundational runtime capability the `zx-game-disasm` and `zx-tape-to-trdos` skills build on — they reference this skill rather than re-deriving the mechanics.

## Two interfaces — pick by goal

| | **Debugger — gdbserver** | **Driver — libfusex** |
| --- | --- | --- |
| Wire | GDB RSP over TCP (external client) | C ABI in-process (`libfusex.dylib` via ctypes) |
| Question it answers | *Why does it do that?* (internals) | *Does it behave right?* (input → output) |
| Gives you | breakpoints, watchpoints, single-step, registers, memory, `monitor` | keystrokes, frame-step, 256×192 screen, peek/poke, RZX record |
| Machine state | **halts** at traps — inspect, then resume | **free-running** — step N frames and observe |
| Reach for it when | crashes, resets, loaders, hand-offs, "what's at address X" | playing, controls, scoring/lives, screen capture, playability |
| Driver | `scripts/gdb.sh`, `scripts/gdb-session.py` | `scripts/fuse_drive.py`, `references/driving.md` |

The two are independent — neither needs the other. Debugging a crash or reset: gdbserver. Confirming a game is playable (do the keys move the player, does firing score, do lives decrement): libfusex. Both drive the *same* emulator on the same program; run each in its own process.

## Driver — libfusex (play / input / screen)

`libfusex` is FuseX built as a shared library: `FuseX.app` ships it on macOS, and on Linux it comes from a FuseX build (see "Tools"). Load it with `ctypes`, boot a program, hold/release keys, step frames, and read the rendered screen — enough to play a game headlessly and verify it behaves. The full API, screen format, key mapping, gotchas, and a worked example are in **`references/driving.md`**; **`scripts/fuse_drive.py`** is a ready-to-use wrapper (load → boot → key tap → screen ndarray/PNG → peek/poke). The essentials:

- **Key codes are ASCII.** `keyboard_press(ord('t'))` presses T; lowercase means *unshifted*, so `ord('t')` matches an `INKEY$="t"` test but not `"T"` (which needs CAPS SHIFT). Space is `ord(' ')`, digits `ord('0')`. Pair every `keyboard_press` with a later `keyboard_release`, holding a few frames between.
- **The screen is one ZX palette index 0–15 per pixel** (0=black … 7=white, 8–15 bright). `Fuse.screen()` crops the 256×192 play area out of the bordered frame; unlit pixels carry the game's PAPER color, lit pixels the INK color — so color *is* readable.
- **Nothing is real-time.** `spectrum_do_frame()` runs one frame as fast as it can. A tape auto-load needs a few thousand frames before the program is up; step past it, then capture a frame and look before acting.
- **`fusex_peek(addr)` reads RAM** — a ground-truth oracle for a value you would otherwise scrape off the screen (e.g. a BASIC variable's bytes). Validation only; a real player reads the screen, not RAM.

On macOS `fuse_drive.py` finds the library and the ROMs in the installed `FuseX.app`, so it runs from any directory. `FUSEX_LIB` and `FUSEX_ROMS` override them; on Linux, set them.

## The debugger — gdbserver

Reading the disassembly tells you what the code *can* do; running it tells you what it *does*. Reach for the debugger when:

- A static read is ambiguous — a computed jump, self-modifying code, a value that depends on runtime state.
- You need the real register/memory state at a point (the entry, a hand-off, a collision).
- Something fails at runtime — a crash, a reset to `$0000`, a hang — and you need to see where and why.
- You want to confirm a hypothesis from the disassembly against the actual run.

## The two session models

Both drivers wrap the `z88dk-gdb` client (the client this stub was designed for). Pick by how many halted states you need.

### Batch — `scripts/gdb.sh`

One invocation = connect → run your commands (sharing one halted state) → detach. **Detach resumes the emulator**, so everything that must observe the same trap goes in one call.

```bash
scripts/gdb.sh "break 0x8050" "cont" "reg" "dis 0x8050"
```

Good for a single one-shot read: trap somewhere, inspect, done.

### Persistent — `scripts/gdb-session.py` (preferred for interactive work)

Keeps ONE `z88dk-gdb` alive via a small daemon, so the machine **stays stopped between commands and across separate shell invocations**. Only `stop` detaches (which resumes the emulator).

```bash
scripts/gdb-session.py start                   # connect, halted, ready
scripts/gdb-session.py cmd "break 0x9c40"
scripts/gdb-session.py cmd "cont" --timeout 45 # blocks in the daemon until the bp hits
scripts/gdb-session.py cmd "reg"               # read the trapped state — same session
scripts/gdb-session.py cmd "x /64 0xff49"
scripts/gdb-session.py stop                    # detach + tear down
```

This is the only practical way to watch a value evolve across breakpoint hits (`cont` / read / `cont` / read) without relaunching. One session at a time: state lives under `$GDB_SESSION_DIR` (default `/tmp/gdb-session`); run `stop` before a fresh `start`.

## Launch and connect

**Prefer headless.** Default to `scripts/fuse_drive.py gdbserver` (see "Headless (no GUI)" below): it opens no window, steals no focus, needs no display, and runs cleanly in CI or in parallel — the least disruptive choice, and the right one for almost all debugging. The GUI `.app` is the option for when a *human* needs to watch the game on screen while you work — reach for it only then. The two modes are driven identically; only the launch target differs.

```bash
python3 scripts/fuse_drive.py gdbserver 1337 \
  --tape=/abs/path/program.tzx --auto-load >/tmp/fuse.log 2>&1 &
FPID=$!                                # track this instance; clean up with kill "$FPID"
nc -z 127.0.0.1 1337 && echo ready     # port up = ready to connect
```

The macOS GUI `.app` (`FuseX.app/Contents/MacOS/FuseX`) takes the identical FuseX flags, with `--gdbserver-enable --gdbserver-port=1337` in place of the `gdbserver 1337` arguments, but opens a visible window — human-watching only, never an autonomous run.

Three things that bite (full detail in `references/protocol.md`):

- **With the GUI `.app`, use `=`-form options and exec the inner binary directly.** `--gdbserver-port 1337` (space form) and `open --args` both route the value to AppKit's `openFile:` and it is silently dropped. Always `--gdbserver-port=1337`.
- **Add `--gdbserver-wait` to halt before the first opcode** when you need to trap code that runs early (a loader, a relocator) before a client can attach. A client that disconnects resumes the machine, so wait for the port with `lsof -iTCP:1337 -sTCP:LISTEN` rather than `nc -z`, and set the breakpoints from the first client.
- **Snapshots load too.** `.tap`/`.sna`/`.z80`/`.szx` work with the same options; libspectrum picks the loader from the file class.

## Headless (no GUI) — the default

This is the mode to use unless a human needs to watch the game. `fuse_drive.py gdbserver PORT [FUSEX ARGS...]` boots the `libfusex` library installed with FuseX, serves the same gdbserver on `PORT` with no window, no focus stealing and no display dependency, and runs the machine at the Spectrum's speed until killed. Everything else is identical: the same FuseX flags after the port, the same `gdb.sh`/`gdb-session.py`, the same commands.

- **It finds the library and the ROMs** the same way the libfusex driver does.
- **Clean up by PID** (`kill "$FPID"`); the process is `python3`, not `FuseX`.

## Running multiple instances

Several FuseX instances run side by side, each on its own gdbserver port — useful for comparing two programs, or two states of one, at the same time. Give each a distinct port, one process each, and drive each by pointing the client at its port:

```bash
python3 scripts/fuse_drive.py gdbserver 1337 … >/tmp/fusex-a.log 2>&1 & PA=$!
python3 scripts/fuse_drive.py gdbserver 1338 … >/tmp/fusex-b.log 2>&1 & PB=$!
PORT=1337 scripts/gdb.sh "break 0x0038" "cont" "reg"   # drives instance A
PORT=1338 scripts/gdb.sh "break 0x0038" "cont" "reg"   # drives instance B
```

The instances are genuinely independent — separate register and memory state. Two caveats when running more than one:

- **`gdb.sh` takes the port via `PORT=`**; `gdb-session.py` takes `--port` **and** needs a distinct `GDB_SESSION_DIR` per instance (its daemon state defaults to `/tmp/gdb-session` and would otherwise collide).
- **Clean up by PID.** Kill only yours: `kill "$PA"`. A kill by name takes down *every* instance.

## Core command set (z88dk-gdb)

| Command | Does |
| --- | --- |
| `break <addr>` | execute breakpoint (hex `0x….`) |
| `cont` | run until a breakpoint; **blocks** (the timeout caps it) |
| `reg` | all registers + flags + the bytes at PC and SP |
| `dis <addr>` | disassemble ~10 instructions from `<addr>` |
| `x /<n> <addr>` | dump `n` bytes of memory (e.g. `x /128 0xfde8`) |
| `stepi` | single-step one instruction |
| `watch write <addr>` | write watchpoint (also `watch read`) |

Quirks: a bare repeated `dis` does **not** advance — pass the next address each time (compute it from the `;[addr] bytes` column). `I`/`R`/`IFF1`/`IFF2`/`IM` are in `reg` and writable by name (`set iff1 1`). For anything Fuse's debugger can do but the client cannot, use `monitor debugger <command>`: `monitor debugger break port write 0xfe`, `monitor debugger break time <tstates>`, `monitor debugger break <addr> if <expr>`. The debugger reads `$FE` as a variable that evaluates to 0, so write hex as `0xfe`. The command language is the `MONITOR/DEBUGGER` section of the Fuse man page, which `FuseX.app` ships under `Contents/Resources/man`. `references/protocol.md` covers the replies and the page's location on each platform. `monitor debugger` needs FuseX built from source from the [`main` branch](https://github.com/speccytools/fusex/tree/main) of `speccytools/fusex`.

## Reset detection — do this on every `cont`

A crash or failed load sends the Z80 to `$0000` to spin in ROM, and `cont` then waits forever. Always set a reset guard and read which breakpoint actually hit:

```bash
scripts/gdb.sh "break 0x0000" "break 0x8050" "cont" "reg"
```

`Hit breakpoint 1: @0` means reset/failure; `Hit breakpoint 2: @8050` means you reached the target. The session timeout is the backstop if nothing hits.

## State discipline

- **Never attach blind.** Read `reg` first to learn where PC is (ROM idle, mid-run, reset at `$0000`) before acting.
- **Track each instance's PID and kill by PID.** Capture `$!` at launch and `kill` that. A kill by name takes down every instance, including ones you did not start.
- **A silent, never-returning `cont` is a reset or a missed breakpoint**, not a slow run — the reset guard plus timeout turn that into an observable result.
- **`monitor debugger disassemble` returns nothing over RSP** (it only moves the GUI pane; by design). `monitor debugger print` does return its value. For disassembly use the client's own `dis` or raw `reg`/`x`. See `references/protocol.md`.

## Reference

- `references/protocol.md` — the complete gdbserver reference: enabling the server, halting before the first opcode, choosing/installing a client, connection mechanics, the full RSP packet table, memory watchpoints, the monitor command surface and the debugger man page, the raw-RSP wire format for Python scripting, and the known limits and caveats.
- `references/driving.md` — the complete libfusex reference: the C ABI symbol table, the ctypes driver pattern, ASCII key mapping, the 256×192 screen format and palette, booting a tape/snapshot, peek/poke, RZX/movie recording, the per-address execution profiler, gotchas, and a worked "play a game and read the screen" example.
- `scripts/gdb.sh`, `scripts/gdb-session.py` — the batch and persistent gdbserver drivers.
- `scripts/fuse_drive.py` — the libfusex driver wrapper (boot, key tap, screen → ndarray/PNG, peek/poke); importable or runnable as a smoke test.

## Tools

Verify each exists before use; name any that is missing.

- **FuseX** (gdbserver build) — the macOS `FuseX.app` for a visible window; `scripts/fuse_drive.py gdbserver` for a headless run. Built from source from the [`main` branch](https://github.com/speccytools/fusex/tree/main) of `speccytools/fusex`.
- **`z88dk-gdb`** — the canonical gdbserver client (install notes in `references/protocol.md`).
- **`libfusex`** — the C ABI library: `FuseX.app/Contents/Frameworks/libfusex.dylib` on macOS; on Linux, the `libfusex.so` that FuseX configured with `--with-null-ui` builds, set as `FUSEX_LIB`, with the tree's `roms/` as `FUSEX_ROMS`. Needs glib, gettext and libpng.
- **Python 3** — for `gdb-session.py`, `fuse_drive.py`, and any raw-RSP scripting. The libfusex driver also wants `numpy` and `Pillow`.
