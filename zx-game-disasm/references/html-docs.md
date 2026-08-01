# Stage 5 — Publish HTML (optional)

`skool2html.py` turns the `.skool` plus a set of `.ref` files into a cross-linked documentation site: every routine on its own page, labels hyperlinked, plus gallery and reference pages you compose. This is optional — the `.asm` and `.ctl` are the primary deliverable — but it is what makes the work browsable by someone who will never open a terminal.

```
skool2html.py -d html -o {game}.skool {game}.ref
```

This page covers the graphics, audio, and reference-page essentials. The full catalog of expressive devices — every image macro (`#UDGARRAY`, `#UDGS`, `#SCR`, `#FRAMES`, `#PLOT`, `#OVER`), the computed-documentation macros (`#EVAL`, `#FOR`, `#TSTATES`, `#SIM`, `#PEEK`), and the `[Poke]`/`[Bug]`/`[Fact]` knowledge sections — is in `references/expressive-palette.md`. Reach for them: the richer the site, the more the disassembly is worth.

## Ref files

The main `{game}.ref` (start from `assets/game.ref.template`) configures the site and lists the extra ref files to include:

```ini
[Config]
RefFiles=graphics.ref;sound.ref;data.ref;notes.ref;glossary.ref
GameDir={game}

[Game]
Game={Game Title}
```

Each referenced file adds pages or sections. Split by concern — graphics, sound, data tables, prose notes, glossary — so each stays editable on its own.

## Graphics

Render sprites, tiles, and fonts straight from the snapshot with SkoolKit image macros in a `graphics.ref`:

- `#UDG$ADDR` / `#UDGARRAY` — user-defined graphics (8×8 tiles, sprite grids).
- `#FONT$ADDR,count` — a character set laid out as a strip.

`sna2img.py` does the same from the command line, useful for a one-off PNG (a repo screenshot, a font sheet):

```
sna2img.py -e 'FONT$7D00,96,56,2' {game}.szx font.png
```

Point each macro at the address the disassembly identified for that graphic, so the gallery and the `.ctl` annotations stay in sync.

## Sound

Spectrum sound is the beeper toggled on a timed loop. SkoolKit's `#AUDIO` macro synthesizes a playable WAV from the T-state delays between toggles, so the HTML page can *play* each effect. Audio macros belong in `sound.ref` (only `skool2html` processes it), one `[Audio:id:Title]` section per effect:

```ini
[Audio:chime:Bonus chime]
Produced by the routine at #R$C3A0.

#AUDIO(chime.wav)(30,[480,60]*5,480)
```

The delay list is the T-states between consecutive speaker flips; the speaker starts OFF. The list syntax supports repetition: `[x]*n` repeats a value, `[x,y]*n` repeats a pair, and nested lists flatten. Compute the delays from the sound routine's own loop timing:

- A `DEC r / JR NZ` loop starting at `N` runs `16*N - 5` T-states (each iteration is 4 + 12, the last 4 + 7). `N = 0` wraps to 256 iterations.
- For a per-frame effect (called once per 50 Hz interrupt), pad with the inter-frame gap: the 48K frame is 69,888 T-states, so the gap is roughly `69888 - active_time`.

Derive complex patterns with a small script rather than hand-counting, and put long delay lists in their own `[Section]` referenced via `#INCLUDE`.

## Reference pages

Compose prose and tables into their own pages via ref sections:

- **Data tables** — level layouts, enemy stats, object records. A `[Page:...]` with `#TABLE`s, linked from the index.
- **Notes** — implementation notes, the memory map, the boot sequence.
- **Glossary** — the domain terms the comments use, defined once.

Group them under index headings in the main `.ref` (`[Index:Reference:Reference]`) so the site has a navigable structure rather than a flat list of routine pages.
