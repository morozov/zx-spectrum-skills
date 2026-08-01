# Deriving Z80 logic — shared comprehension methodology

This is the shared method for *understanding* a piece of ZX Spectrum machine code: recovering what it does and why, from the bytes plus, when useful, a live run. The deliverable of this work is an **understanding** — a written analysis, a block table, a characterization — not a build artifact. The tape-to-TR-DOS and game-disassembly workflows both lean on it; it is also the whole job when the user just wants "figure out how this code works."

It pairs with two siblings:

- **Run the code to understand it** — drive it under FuseX with the `zx-fuse-debug` skill (breakpoints, watchpoints, register/memory reads). Static reading and dynamic observation are complementary; combine them.
- **Write the understanding down well** — the documentation discipline lives in the `zx-game-disasm` skill's `comment-style.md` and `behavior-spec.md`.

## Static first, dynamic to confirm

Read before you run. A disassembly shows every path the code *can* take; a single run shows only the path it *did* take. So derive the structure statically, then use the emulator to resolve what static reading cannot and to confirm hypotheses.

Static reading recovers: the control-flow graph, each routine's inputs/outputs/ effects, data structures, and the idioms below. Dynamic observation resolves: computed jumps and jump tables, self-modifying code, values that depend on runtime state, and the real register/memory state at a chosen point. When the two disagree, the run is the ground truth about *this* execution — but ask why the static read was wrong, because the answer is usually a path you misread.

## Characterize each routine from the caller's side

For every routine, recover the contract a caller depends on, not the mechanism:

- **Purpose** — what it computes or does, in one line.
- **Inputs** — which registers/memory it reads as parameters.
- **Outputs** — which registers/memory it returns or mutates.
- **Side effects** — screen, sound, state flags, the stack.
- **Control** — how it ends (return, fall-through into the next routine, jump elsewhere) and what it calls.

Name routines and variables for purpose as understanding firms up; the name is the cheapest, highest-leverage piece of documentation.

## Z80 idioms worth recognizing on sight

Recurring shapes that tell you what a block is doing:

- **Copy / block move** — `LD A,(HL) / LD (DE),A / INC HL / INC DE / DJNZ`, or `LDIR`/`LDDR`. A copy loop whose body applies a transform is a *decoder*.
- **Relocation + self-decryption** — a bootstrap that copies itself to another address, often transforming each byte (`XOR key`, `INC A`, `ADD n`), then `JP`s there. The *real* code only exists after the copy runs; relocation is CPU-only, so let it run and read the destination.
- **Jump tables / dispatch** — an index scaled and added to a base, then an indirect `JP (HL)` or a `CALL` through a table. The table's entries are addresses or handler ids; its length comes from the dispatcher's index range, not from where the next block appears to start.
- **Self-modifying code** — an instruction that writes into a later instruction's operand. Watch for stores into the code region; the live byte at run time is the truth.
- **Bit-flag state** — `BIT`/`SET`/`RES`/`AND`/`OR` against a state byte. Recover the meaning of each bit and document it as a bitfield.
- **Port I/O** — `IN A,($FE)` (keyboard/EAR), `OUT ($FE),A` (border/speaker/MIC), `LD BC,$7FFD` / `OUT (C),A` (128K paging). These mark input, sound, and bank switching.
- **Timing loops** — `DEC r / JR NZ` with no other effect: a delay; its duration is computable in T-states (and confirmable with `#TSTATES` once disassembled).

These are shapes to recognize, not laws — verify each against the code in front of you.

## Using the emulator to resolve the unknowns

When static reading hits a wall, the `zx-fuse-debug` recipes resolve it:

- **A computed/indirect jump** — trap just before it, read the target register (`reg`), or watch where control lands.
- **A value that depends on state** — break at the point and read it (`x`/`reg`), or set a watchpoint on the variable and see who writes it and with what.
- **The real layout after a load/decrypt** — trap after the relocation/decode and dump the destination (`x /<n> <addr>`); the plaintext body is there.
- **A crash or reset** — set a reset guard (`break 0x0000`) alongside your target so a failed path is observable rather than a silent hang.

Read the block parameters from the disassembled code where you can; confirm at runtime only what static reading leaves genuinely open. Halting mid-load to "watch it" is usually less reliable than reading the loader's own literals.

## Close the loop: process the output and assess it yourself

Producing an annotation or an interpretation is half the job. When the work feeds a toolchain — a build, a rendered asset — run it through and judge the *output* yourself against the bar. A passing build proves only faithfulness: that the source round-trips to the original bytes. It never proves an interpretation is right — a comment correct, an address sound, a sprite decoded properly. Only call a piece done when you are satisfied with the processed result, not when it compiles.

Rendering an asset to check it is one such loop, and a strong one: a real asset looks like something. Analyze what you actually see. If a graphic comes out garbled or fragmented, the decode is almost always wrong — wrong width, wrong byte order, a missing mask, the wrong address or format — not the data. Do not rationalize the artifact. Find the routine that actually *draws* it and read the exact format from there; different objects use different formats, so one verified for a given object does not transfer to another.

## Discipline

- **No speculation.** Document what the code shows, statically or dynamically. When a routine's purpose is genuinely unclear, say so and move on rather than inventing a story — a confident wrong analysis costs more than an honest gap.
- **Trace every claim to evidence** — an address, an instruction, an observed register value. "This is the spawn routine" must point at the code that makes it so.
- **A boundary you cannot pin from usage is ambiguous, not decided.** A table whose only indexer is never reached has no determinable length from code flow; record the uncertainty instead of guessing silently.
- **Structure comes from the code that reads the data, not from appearance.** Which items form one logical object, and how many frames or elements each has, is defined by the code that consumes them — an index table plus the handler's counter that wraps at a fixed count means exactly that many elements. Grouping by visual similarity is guessing; it merges things the code keeps distinct.
