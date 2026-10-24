# FuseX gdbserver — complete reference

FuseX exposes a GDB Remote Serial Protocol (RSP) server through its debugger build. With it enabled, a client attaches over TCP and can set breakpoints and memory watchpoints, single-step, inspect and modify memory and registers, and, through `monitor debugger`, drive Fuse's full internal debugger command language.

This is the protocol and mechanics reference behind `SKILL.md`. It is platform-generic across Z80 programs; project-specific findings (a game's relocator, a loader bug) belong in that project's own notes, not here.

## Table of contents

- [Enabling the server](#enabling-the-server)
- [Loading a program at startup](#loading-a-program-at-startup)
- [Halting before the first opcode](#halting-before-the-first-opcode)
- [Choosing and installing a client](#choosing-and-installing-a-client)
- [Connection mechanics](#connection-mechanics)
- [RSP packets supported](#rsp-packets-supported)
- [Memory watchpoints](#memory-watchpoints)
- [Monitor commands](#monitor-commands)
- [Raw RSP for Python scripting](#raw-rsp-for-python-scripting)
- [Known limits and caveats](#known-limits-and-caveats)
- [See also](#see-also)

## Enabling the server

Four ways — pick whichever fits the workflow.

**Headless, no window:** `scripts/fuse_drive.py gdbserver 1337` serves the gdbserver from the `libfusex` library (see `SKILL.md`). The FuseX flags below follow the port.

**CLI flag on the macOS GUI app (one-shot, no state):**

```bash
~/Applications/FuseX.app/Contents/MacOS/FuseX \
    --gdbserver-enable --gdbserver-port=1337
```

- **Use the `=` form for options that take a value, and exec the inner binary directly.** AppKit routes each option's space-separated value (e.g. `1337` in `--gdbserver-port 1337`) to `application:openFile:` as a file to open; the value then does not take effect. Pass `--gdbserver-port=1337`. Invoking `MacOS/FuseX` directly is the most reproducible path from a script.
- **Port 1337 is the convention.** The bundled drivers take another one through `PORT=` or `--port`.

**Cocoa preference (macOS, persistent):** _Preferences → Debugger → "Enable advanced (gdbserver) debugger"_, bound to user-defaults key `gdbserverenable`; the port is `gdbserverport`.

**`defaults write` (macOS, scriptable persistent):**

```bash
defaults write org.fuse-emulator.fusex gdbserverenable -bool YES
defaults write org.fuse-emulator.fusex gdbserverport  -int  1337
```

Takes effect at next launch.

## Loading a program at startup

```bash
.../MacOS/FuseX --gdbserver-enable --gdbserver-port=1337 \
    --tape=/abs/path/program.tzx --auto-load
```

`--auto-load` types `LOAD ""` (or the machine's equivalent) and starts the tape; the program loads in real time. `.tap`/`.sna`/`.z80`/`.szx` work the same way — libspectrum picks the loader from the file class. When `gdbserver` is enabled the emulator skips its startup `settings.debugger_command`; drive everything via the client instead.

## Halting before the first opcode

By default the program runs from launch and only stops once a client attaches and traps it. Anything that executes before you connect — a loader, a relocator, ROM entry code — has already run by then. Add `--gdbserver-wait` to halt at the entry PC before the first opcode:

```bash
.../MacOS/FuseX --gdbserver-enable --gdbserver-port=1337 --gdbserver-wait \
    --tape=/abs/path/program.tzx --auto-load
```

The emulator comes up halted and blocks until the client attaches and resumes, so a connecting client finds the PC at the very start with nothing executed. This is the flag for breakpoints on early code. A client that disconnects resumes the machine, so two things release the halt before any breakpoint is set:

- **A readiness probe that connects**, such as `nc -z`. Wait for the listening port with `lsof -iTCP:1337 -sTCP:LISTEN` instead.
- **A `gdb.sh` batch that ends**, because it detaches. Set the early breakpoints and `cont` in the first batch, or hold the machine with `gdb-session.py`.

`--gdbserver-wait` is command-line only, has no effect without `--gdbserver-enable`, and is not persisted.

## Choosing and installing a client

| Client | Use it for |
| --- | --- |
| `z88dk-gdb` | Interactive Z80 debugging, `.map` symbols. The canonical client; this stub was designed against it. |
| Raw RSP (Python) | Scripted automation, fast round-trips (see below). |
| Stock GNU gdb | Unverified — FuseX keeps `pc` 16-bit and omits the standard `af` flags type, so a clean connect is not confirmed. Prefer the other two. |

**Use `z88dk-gdb` from a [z88dk nightly build](http://nightly.z88dk.org/) or from z88dk master.** Release v2.4 predates the client's FuseX support: memory watchpoints sent to the gdb remote backend (so `watch write`/`watch read` set *real* watchpoints, not a local-only list), the Z80 interrupt/refresh registers surfaced over `g`, a `g`-packet overflow fix, a clean exit on end of input, and confirmation prompts that proceed when stdin is not a tty.

Both bundled drivers pipe their commands in, so a command that would prompt for confirmation — a bare `delete` ("delete all breakpoints? (y/n)") is the common one — proceeds rather than hanging the session. The practical consequence: in a driven session a bare `delete` removes *all* breakpoints without asking. Scope it with `delete <id>` when you mean a specific one.

```bash
z88dk-gdb -h 127.0.0.1 -p 1337 -x /path/to/prog.map
```

- Pass `-x <map>` even with no symbols — point it at an empty file (`touch /tmp/empty.map`). The flag is required.
- Use `-h 127.0.0.1`. `-h localhost` resolves to `::1` and fails — the stub is IPv4-only.
- **Release v2.4 lacks the watchpoint support** — its `watch` updates only a local list and never reaches the target. If you end up on that build, set watchpoints with the raw `Z2`/`Z3` packets or `monitor debugger break write`/`break read` instead. With a nightly build, `watch write`/`watch read` just work.

## Connection mechanics

On attach the stub replies to the client's `?` packet with `T02thread:p01.01;` — it traps as if hit by SIGINT. Register reads (`g`) then return live Z80 state.

**The open port is enough.** The stub waits for the first emulated frame before it handshakes, so once `nc -z 127.0.0.1 1337` returns a client can attach. Under `--gdbserver-wait`, probe with `lsof` instead (see above).

The stub advertises in `qSupported`:

```
PacketSize=4000;qXfer:features:read+;qXfer:auxv:read+;vSpectranext+
```

`qXfer:features:read:target.xml` returns 18 × 16-bit registers in this order:

```
af bc de hl sp pc ix iy af' bc' de' hl' ir iff1 iff2 im clockl clockh
```

`ir` is the combined interrupt/refresh register (`I` high byte, `R` low byte). `iff1`/`iff2`/`im` and `clockl`/`clockh` (the emulator's T-state counter) live in fuse-emulator features. So `I`, `R`, `IFF1`, `IFF2`, `IM` are first-class registers over `g`/`G`/`p`/`P` — read them structurally rather than scraping `monitor debugger print z80:iff1`.

## RSP packets supported

| Packet | Behavior |
| --- | --- |
| `g` / `G` | Read / write the 18-register bank |
| `p` / `P` | Read / write a single register by index |
| `m` / `M` | Read / write memory in the currently-paged Z80 address space |
| `X` | Write memory with binary-escaped payload |
| `Z` / `z` | Set / remove breakpoint or watchpoint by type: `0`/`1` execute, `2` write watchpoint, `3` read watchpoint, `4` access. `length` honored. |
| `c` | Continue |
| `s` | Step one instruction. Advances exactly one instruction and traps, correct across branches. |
| `vCont` | Advertises `c;C;s;S;` |
| `H` | Thread select — always OK (single-threaded) |
| `D` | Detach — replies OK, cleans up breakpoints, resumes the emulator |
| `?` | Stop reason |
| `qRcmd` | `monitor` command (see below) |
| `qSupported`, `qXfer:features:read`, `qXfer:exec-file:read`, `qAttached`, `qfThreadInfo`/`qsThreadInfo`, `qC` | Standard probes |
| `vFile:*` | Host file I/O |
| `vSpectranext:*` | Custom extension matching `spectranet-gdbserver` on real hardware |

Anything else gets an empty reply (the GDB "unsupported" signal).

## Memory watchpoints

`Z2`/`Z3`/`Z4` set write / read / access watchpoints on the Z80 logical address space, honoring length; they trap when the program touches the range. The stop reply names the watched address — `T05watch:5c78;…`. Removal is the matching `z2`/`z3`/`z4`. With a nightly build of `z88dk-gdb` the easy path is its native `watch write <addr>` / `watch read <addr>` (which send a real `Z2`/`Z3` to the backend); raw RSP is the alternative.

Quick check against a cold 48K machine (the ROM increments `FRAMES` at `0x5C78` every frame). Via `z88dk-gdb` (or `gdb.sh`):

```
watch write 0x5c78   -> Adding write watchpoint at '0x5c78'
cont                 -> traps; stop reply T05watch:5c78; PC just past the ROM's
                        LD ($5C78),HL store, HL = the freshly incremented FRAMES
```

Or directly over raw RSP:

```
Z2,5c78,1   -> +$OK
c           -> +$T05watch:5c78;thread:p01.01;   traps on the write to 0x5C78
z2,5c78,1   -> +$OK
c           -> +                                runs free once removed
```

Port, time, and event watchpoints have no RSP type — use `monitor debugger` (`break port write`, `break time`, `break event`).

## Monitor commands

`qRcmd` talks to Fuse's internal debugger. Upstream FuseX answers only its built-ins: `monitor help`, `monitor reset`, `monitor dump`, and the Spectranet and XFS commands. **FuseX built and installed from the [`automation` branch](https://github.com/morozov/fusex/tree/automation) of `morozov/fusex` adds `monitor debugger <command>`**, which runs `<command>` through `debugger_command_evaluate`, the same parser that reads commands typed into the debugger window:

```
monitor debugger break port write 0xfe
monitor debugger break 0x8000 if z80:hl == 0x1234
monitor debugger print z80:pc
```

The stub must be halted, which it is from attach until the client resumes it. The command runs on the emulator thread, and the machine stays halted afterwards. The debugger's own `continue`, `next` and `finish` do not resume emulation. Only the client's `cont` (RSP `c`) does.

**Numbers are decimal unless prefixed with `0x`.** `$name` is a debugger variable, so `$FE` evaluates to 0 and `break port write $FE` watches the wrong ports. Write `0xfe`.

Highlights of the command language:

| Capability | Syntax |
| --- | --- |
| Conditional execute breakpoint | `break <addr> if <expr>` |
| Memory read / write watchpoint | `break read <addr> [if …]`, `break write <addr> [if …]` |
| I/O port read / write watchpoint | `break port read <port> [if …]`, `break port write <port> [if …]` |
| Frame-time breakpoint | `break time <tstates> [if …]` |
| Peripheral / event breakpoint | `break event <area>:<detail>` — e.g. `tape:play`, `beta128:page`, `rzx:end` |
| Page-aware address | `RAM:<page>:<offset>`, `ROM:<page>:<offset>`, `Spectranet`, `Timex DOCK`, … |
| System variable in conditions | `z80:i`, `z80:r`, `z80:iff1`, `z80:iff2`, `z80:im`, `z80:wz`, `ula:last`, `ula:mem7ffd`, `ay:current`, `spectrum:frames`, `tape:microphone` |
| Direct memory or register write | `set <addr> <value>`, `set z80:hl <value>`, `out <port> <value>` |
| One-shot breakpoint | `tbreakpoint <addr> [if …]` |
| Skip N hits | `ignore <id> <count>` |
| Delete one / all breakpoints | `clear <addr>`, `delete [<id>]` |

Addresses accept `0x1234` or `source:page:offset`. A port below `0x100` matches on the low byte only, so `0xfe` matches any port whose low byte is `0xFE`. `if` expressions use a C-subset evaluator: arithmetic, comparisons, bitwise, logical, and `[]` for memory dereference. The full language is the `MONITOR/DEBUGGER` section of [the Fuse man page](#the-debugger-man-page).

### Replies

| Outcome | Console (`O…`) output | Reply |
| --- | --- | --- |
| Command succeeded | whatever it printed (`print 2+3` → `0x5`) | `OK` |
| Parse or evaluation error | the error text | `E01` |
| Bare `monitor debugger` | `Usage: debugger <command>` | `E01` |
| Any other unknown monitor command, such as `monitor break …` | none | `E04` |

`disassemble` succeeds but prints nothing, as [Known limits and caveats](#known-limits-and-caveats) describes.

### The debugger man page

The man page documents the command language, but not the gdbserver or the `monitor debugger` wrapper. FuseX installs it as `man1/fuse.1`.

On macOS it is inside the app bundle at `FuseX.app/Contents/Resources/man`. Read it with `man -M <FuseX.app>/Contents/Resources/man fuse`, using the `FuseX.app` that `scripts/fuse_drive.py` resolves. On Linux the page goes under the install prefix's `share/man`, and `man fuse` finds it.

## Raw RSP for Python scripting

The wire format is simple: outgoing `$<payload>#<8-bit hex checksum>`; acknowledge incoming `+` and reply `+` to received packets; `monitor <text>` is `qRcmd,<text-in-hex>`. A driver fits in ~50 lines:

```python
import socket
def cksum(b): return f"{sum(b) & 0xff:02x}".encode()
def send(s, p): s.sendall(b"$" + p.encode() + b"#" + cksum(p.encode()))
def recv(s):
    buf = b""
    while True:
        c = s.recv(1)
        if c == b"+": continue
        if c == b"$": break
    while True:
        c = s.recv(1)
        if c == b"#":
            s.recv(2); s.sendall(b"+"); return buf.decode(errors="replace")
        buf += c
def mon(s, cmd):
    send(s, "qRcmd," + cmd.encode().hex())
    while True:
        r = recv(s)
        if r.startswith("O") and r != "OK":
            print(bytes.fromhex(r[1:]).decode(errors="replace"), end=""); continue
        return r
s = socket.create_connection(("127.0.0.1", 1337))
send(s, "qSupported:"); recv(s)
send(s, "?"); recv(s)               # halts on attach
mon(s, "debugger break 0x8000 if z80:hl == 0x1234")
send(s, "c"); print(recv(s))         # blocks until breakpoint fires
send(s, "g"); print(recv(s))         # all 18 registers as hex
```

The `g` dump is 36 hex bytes, little-endian per word, in the register order above.

## Known limits and caveats

- **No source-level debugging.** No DWARF, no symbol tables on the wire. Symbol resolution is the client's problem (`z88dk-gdb -x <prog>.map`); raw-RSP scripts carry their own address tables.
- **Memory access is logical-address-space-only.** `m`/`M`/`X` see whatever is currently paged in. For a paged-out bank use page-aware monitor addresses (`RAM:5:0x0`), or page it in (`monitor debugger set ula:mem7ffd <value>`).
- **`monitor debugger disassemble` returns nothing over RSP** (by design — it only moves the GUI pane). `monitor debugger print` does return its value. Disassemble with the client's `dis` or raw `g`/`m` plus a local disassembler.
- **Stock GNU gdb compatibility is unverified.** Use z88dk-gdb or raw RSP.
- **`open --args` is hostile to FuseX argv** (macOS GUI). Use direct exec.

## See also

This document is the agent-facing reference for the gdbserver. The truth for the server internals is the [FuseX](https://github.com/speccytools/fusex) source:

- `man/fuse.1`, section `MONITOR/DEBUGGER` — the internal debugger command language behind `monitor debugger`. The installed copy is described in [The debugger man page](#the-debugger-man-page).
- `debugger/arch.h` — the served target description (the register layout above).
- `debugger/gdbserver.c`, `debugger/gdbserver_remote_commands.c` — RSP dispatch and the built-in monitor commands. `monitor debugger` is in `debugger/gdbserver_remote_commands.c` on the [`automation` branch](https://github.com/morozov/fusex/tree/automation) of `morozov/fusex`.
- `fuse.c` (startup gdbserver wiring) and `fusepb/xibs/Preferences.xib` (the Cocoa preference) — where the enable/port settings are bound.
