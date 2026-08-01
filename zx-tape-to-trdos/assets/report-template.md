# Loading analysis: {GAME NAME}

> What the tape loader does, block by block, and therefore what a TR-DOS disk loader must reproduce. This is the stage-1 report; the loader is authored from it in stage 2.

## 1. Game

| Field          | Value                     |
| -------------- | ------------------------- |
| Name           | {game name}               |
| Source tape    | {filename} ({tzx \| tap}) |
| Target machine | {48K \| 128K \| …}        |
| Analyzed       | {YYYY-MM-DD}              |

## 2. BASIC entry

- Autorun line (verbatim): `{e.g. RANDOMIZE USR (PEEK 23635+256*PEEK 23636+58)}`
- `PROG`-relative offset: `+{N}`
- Computed machine-code loader entry: `{$XXXX}` (PROG `{$XXXX}` + `{N}`)

## 3. Machine-code loader

| Property         | Finding                                                                                    |
| ---------------- | ------------------------------------------------------------------------------------------ |
| Location         | `{$XXXX}`                                                                                  |
| Self-decrypting? | {no \| yes — key `{$XX}`, decrypts span `{$XXXX}`..`{$XXXX}`}                              |
| ROM load routine | {`$0556` standard `LD-BYTES` \| shifted entry `$055A` (protection) \| custom at `{$XXXX}`} |
| Implication      | {what the routine choice means for header/flag handling}                                   |
| Interrupts       | {`DI`/`IM 1` \| left enabled \| …}                                                         |
| Stack setup      | {what SP is set to, if anything notable}                                                   |

## 4. Block table

Blocks in load order. Sectors = `ceil(bytes / 256)` (TR-DOS allocates whole 256-byte sectors).

| #   | On-tape form      | Destination | Length (bytes) | Length (sectors) | Screen?  | Encoding         | Compressed? |
| --- | ----------------- | ----------- | -------------- | ---------------- | -------- | ---------------- | ----------- |
| 1   | {headed/headless} | `{$XXXX}`   | {N}            | {N}              | {yes/no} | {none \| XOR … } | {yes/no}    |
| 2   | …                 | …           | …              | …                | …        | …                | …           |

## 5. Memory layout after load

Which ranges hold what once loading completes. Call out any range that overlaps the BASIC area or the system variables — that overlap is the reason a disk loader cannot reuse the tape load addresses verbatim.

| Range               | Contents                 | Notes                       |
| ------------------- | ------------------------ | --------------------------- |
| `{$XXXX}`–`{$XXXX}` | {screen \| code \| data} | {overlaps BASIC/sysvars? …} |

## 6. Hand-off

- Mechanism: {direct `JP {$XXXX}` \| `LD SP, {$XXXX}` then `RET` (stack-pointer jump) \| relocate-then-jump (move a block into place via `LDIR`/`LDDR` from a mover stub, then `JP`) \| other — describe}
- Final entry address control reaches: `{$XXXX}`
- For the SP-jump case: SP set to `{$XXXX}`; the word there (`{$XXXX}`) is the address `RET` pops and jumps to.
- For relocate-then-jump: mover stub copied to `{$XXXX}`; it moves `{N}` bytes from `{$XXXX}` to `{$XXXX}`, then `JP {$XXXX}`.

## 7. Implications for the TR-DOS loader

The actionable conclusion — what the disk loader you write next must do.

- **Final residence** — where each block must end up: {block 1 → `{$XXXX}`, block 2 → `{$XXXX}`, …}
- **Load-to-temp-then-relocate** — blocks that cannot be read straight to their final address (because it overlaps the running disk loader or TR-DOS workspace) and so need a temporary landing + `LDIR`: {block N → temp `{$XXXX}`, then move to `{$XXXX}`; suggested temp rationale}
- **Compression** — what to compress for disk vs load raw: {e.g. screen → compress (Laser Compact); data → raw}
- **Sector budget** — per-block sector counts and the total (the input to the monoblock directory-length patch in the `Makefile`): {boot {N} + screen {N} + data {N} = **{TOTAL}** sectors}
- **Hand-off to reproduce** — {restate the mechanism the disk loader must end with}

## 8. Open questions and risks

- {anything unresolved, any protection trick, any assumption the disk-loader author must verify before trusting this analysis}
