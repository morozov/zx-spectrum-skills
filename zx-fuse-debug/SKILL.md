---
name: zx-fuse-debug
description: >-
  Debug a running ZX Spectrum / Z80 program live under the FuseX emulator via its
  gdbserver: set breakpoints and memory watchpoints, single-step, inspect and
  modify registers and memory, and drive Fuse's internal debugger. Use this
  whenever the user wants to run a Spectrum program under Fuse and observe or
  control it — "debug this under Fuse", "set a breakpoint at $XXXX", "watch this
  memory address", "why does it crash/reset at runtime", "step through the
  loader", "what are the registers when it reaches X", "trap the game entry",
  "inspect memory after it loads", or any live/dynamic analysis of Z80 code on
  the Spectrum. This is the foundational runtime-debugging capability that the
  zx-game-disasm and zx-tape-to-trdos skills build on; reach for it any time understanding the code is easier by running it than by reading it.
---

# Debugging ZX Spectrum programs under FuseX

FuseX ships a GDB Remote Serial Protocol (RSP) server. With it enabled, you attach over TCP and get the full dynamic-analysis toolkit: breakpoints, memory watchpoints, single-step, register and memory inspection and modification, and — through a `monitor` passthrough — Fuse's entire internal debugger command language, all without touching the GUI.

This skill is the runtime-debugging capability on its own. It is platform-generic across Z80 programs. The `zx-game-disasm` and `zx-tape-to-trdos` skills drive Fuse through it — they reference this skill rather than re-deriving the mechanics.

## When to use it

Reading the disassembly tells you what the code *can* do; running it tells you what it *does*. Reach for live debugging when:

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

Launch the GUI `.app` with the gdbserver enabled:

```bash
FUSEX=~/Applications/FuseX.app/Contents/MacOS/FuseX
"$FUSEX" --gdbserver-enable --gdbserver-port=1337 \
  --tape=/abs/path/program.tzx --auto-load >/tmp/fusex.log 2>&1 &
FPID=$!                                # track this instance; clean up with kill "$FPID"
nc -z 127.0.0.1 1337 && echo ready     # port up = ready to connect
```

Three things that bite (full detail in `references/protocol.md`):

- **With the GUI `.app`, use `=`-form options and exec the inner binary directly.** `--gdbserver-port 1337` (space form) and `open --args` both route the value to AppKit's `openFile:` and it is silently dropped. Always `--gdbserver-port=1337`.
- **Add `--gdbserver-wait` to halt before the first opcode** when you need to trap code that runs early (a loader, a relocator) before a client can attach.
- **Snapshots load too.** `.tap`/`.sna`/`.z80`/`.szx` work with the same options; libspectrum picks the loader from the file class.

## Running multiple instances

Several FuseX instances run side by side, each on its own gdbserver port — useful for comparing two programs, or two states of one, at the same time. Give each a distinct `--gdbserver-port`, exec the inner binary directly (one process per exec), and drive each by pointing the client at its port:

```bash
"$FUSEX" --gdbserver-enable --gdbserver-port=1337 … >/tmp/fusex-a.log 2>&1 & PA=$!
"$FUSEX" --gdbserver-enable --gdbserver-port=1338 … >/tmp/fusex-b.log 2>&1 & PB=$!
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

Quirks: a bare repeated `dis` does **not** advance — pass the next address each time (compute it from the `;[addr] bytes` column). `I`/`R`/`IFF1`/`IFF2`/`IM` are in `reg` and writable by name (`set iff1 1`). For anything Fuse's debugger can do but the client cannot, use the `monitor` passthrough (`monitor break port write $FE`, `monitor break time <tstates>`, conditional breakpoints `break <addr> if
<expr>`) — see `references/protocol.md`. The passthrough needs FuseX built
from the `automation` branch of `morozov/fusex`; upstream FuseX answers only its built-in monitor commands.

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
- **`monitor disassemble` returns nothing over RSP** (it only moves the GUI pane; by design). `monitor print` does return its value. For disassembly use the client's own `dis` or raw `reg`/`x`. See `references/protocol.md`.

## Reference

- `references/protocol.md` — the complete gdbserver reference: enabling the server, halting before the first opcode, choosing/installing a client, connection mechanics, the full RSP packet table, memory watchpoints, the monitor command surface, the raw-RSP wire format for Python scripting, and the known limits and caveats.
- `scripts/gdb.sh`, `scripts/gdb-session.py` — the batch and persistent drivers.

## Tools

Verify each exists before use; name any that is missing.

- **FuseX** (gdbserver build) — `~/Applications/FuseX.app/Contents/MacOS/FuseX`.
- **`z88dk-gdb`** — the canonical client (install notes in `references/protocol.md`).
- **Python 3** — for `gdb-session.py` and any raw-RSP scripting.
