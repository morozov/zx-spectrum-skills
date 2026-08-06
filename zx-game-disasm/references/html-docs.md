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

## Decode the game's formats

The stock macros render what they can address; a game's own formats — packed rooms, compressed sprites, custom string encodings, route tables — need a decoder. Register a project HtmlWriter and put the decoders there:

```ini
[Config]
HtmlWriterClass=:{game}.{Game}HtmlWriter
```

The class extends SkoolKit's `HtmlWriter`, and `.ref` pages call its methods with `#CALL:method(args)`. Write one decoder per format and render **every instance** from the snapshot's own bytes — all the rooms, the whole map, each mask — so the pages are computed from the data, never transcribed. A decoder is executable schema: rendering every instance correctly proves the format documentation the same way a `#UDGARRAY` proves an extent. Pair each render with a short storage section stating the format it decodes.

Two devices this unlocks beyond plain rendering:

- **Analytic variants** — the same data re-rendered with an interpretive twist: a map with a checkerboard BRIGHT overlay exposing tile boundaries, masks drawn over the map, room bounds outlined.
- **Computed statistics** — counts derived while decoding ("this object appears in 12 rooms"), emitted as tables. A number a script counts stays correct as the `.ctl` evolves; a number typed in prose rots.

## Memory maps

Ship more than one map. Alongside the everything-view, link SkoolKit's filtered maps — routines only, data only, messages only — and the **unused-address map**, so leftover space is a documented inventory rather than an omission. Retitle the index links so a reader knows what each map is before clicking:

```ini
[Links]
MemoryMap=[Everything] (routines, data, text and unused addresses)
RoutinesMap=[Routines] (just the routines)
DataMap=[Data] (just the data)
```

## Orientation pages

Open the site with the game, not the code. Reproduce the original instructions/manual as `[Page:...]` sections — the game's own voice is period documentation worth preserving — plus a controls page and a completion/how-to-win page. Where a diagram beats prose (the screen layout, the control cluster), make a small annotated image and ship it via `[Resources]`:

```ini
[Resources]
static-images/GameWindow.png=static-images
```

These pages are the reader's on-ramp; the catalogs and the behavior spec assume a reader who already knows what the game is.

## Defect catalogs carry IDs and evidence

Bugs, quirks, and graphic glitches get catalog pages with one anchored section per defect, so each has a stable ID that code comments and other pages point at:

```ini
[GraphicGlitch:enemiesTooLow:Front-facing enemies are drawn too low]
```

Each entry pairs the claim with rendered evidence (the sprite showing the stray pixels, the misaligned mask), the root cause traced to its routine, and the fix address. A project that releases its documentation in versions can add a changelog page for the disassembly itself.

## Styling

**Every site gets the skill's default theme — unconditionally.** The framework's `html` target passes `assets/theme.ref` (with `assets/theme.css` and `assets/theme.js`) and builds with `-H -a`, so by default every disassembly ships with:

- a dark, responsive layout (viewport meta, card-grid index, header bar);
- the code listing in a monospace face (JetBrains Mono) with prose in a reading face (Inter); the theme ships **no accent face and no game palette** — its `:root` colors are deliberately neutral;
- **Z80 syntax highlighting** (highlight.js with a registered Z80 grammar: mnemonics, registers, immediates, strings, comments each colored);
- **operands rendered as label names** — `CALL draw_sprite`, never `CALL $8A42` — via `--asm-labels`, which is why the 0-auto-label bar matters to the HTML too;
- comment-group hover: the rows a shared comment spans light up together, and only those — an uncommented row stays dark (see the empty-cell rule below).

The theme is the floor, not the identity — it is structural on purpose, so fifty games built with it do not all look like one game. Identity (the palette derived from the game's attributes, the accent face, the logo) comes from the project layer. The project's main `.ref` owns the whole `StyleSheet` chain — `StyleSheet=skoolkit.css;theme.css;{game}.css` — because `theme.ref` sets no `StyleSheet` of its own. skool2html parses the project ref first and `theme.ref` appends only its non-style baseline (`JavaScript`, `AddressAnchor`) via `[Game+]`, so the project's `[Game]` — StyleSheet, Logo, table columns — always wins. Put every game-specific override in that one stylesheet. The theme's `:root` variables and per-section `--section-color` are the override points. Stylesheets, the INI, and rendered images are HTML-affecting sources the framework's `html/.stamp` does not know about, so the project Makefile adds them as extra prerequisites:

```
html/.stamp: $(wildcard *.css) $(INI)
```

- **Derive the visual identity from the game.** Colors come from the game's own attribute bytes — the palette the player actually sees on the playfield, HUD, and border — not from a designer's swatch. The logo is rendered from the game's glyph bitmaps with their own attributes (`Logo=#UDGARRAY…` over the title-screen data), never an imported image. The site should read as the game documenting itself.
- **A custom game font is an accent, not the text face.** When the game's 8x8 font is extracted to a webfont (`Font={game}.woff2;{game}.ttf`), use it for headers, the logo, and small accents only; body prose and the code listing keep a proper reading face. A bitmap font at paragraph size is atmosphere on one line and an eyesore on a page.
- **The disassembly table lays out from its content.** Column widths are content-driven and code lines never wrap — a wrapped instruction reads as two. The source-side half of this rule is the 24-char label cap (`lint-label-length`): styling cannot fix a gutter a label forced open.
- **An empty comment cell is column, not annotation.** SkoolKit marks the comment class per *entry* — `<td class="comment-{annotated}">` — so every row of an annotated routine carries a `comment-1` cell, including the ones with nothing to say. Those come out exactly empty, with no whitespace inside. A `{game}.css` that restyles `td.comment-1` must leave `td.comment-1:empty` free of anything that reads as content: the background and the left edge carry the column band and have to run unbroken, but a box rule around a blank cell makes a bare `RET` look annotated. The theme's hover skips empty cells for the same reason.
- **Link every operand the reader will chase.** Extend `LinkOperands` beyond the call/jump defaults — `LinkOperands=CALL,DEFW,DJNZ,JP,JR,LD` — so pointer-table entries and immediate address loads hyperlink like calls do.
- **Bitmap art scales pixelated.** Every game image on the site is chunky 8x8-derived art; scale it with `image-rendering: pixelated` so it stays crisp at integer multiples. A blurred sprite is a wrong sprite.
- **A name and credit line are the author's call.** `Release=` names the disassembly and its version; `Copyright=` sets the site's credit line. The theme already sets hex page filenames and anchors (`CodeFiles={address:04X}.html`, hex `AddressAnchor`) to match the hex-addressed `.ctl` — one base everywhere, per `references/ctl-authoring.md`.
- **Prove it by looking at it.** After any styling change, render one sample of each page type — a code routine, a data block, a text block, a graphics-heavy page, a reference/catalog page, the index — in Chrome and check it reads decently: columns sized to content, no wrapped code lines, no gutter blowout, images at integer scale, sprites floating on the page (no opaque paper-color rectangle around a figure — see the transparency rule in `references/expressive-palette.md`), the accent font confined to accents. A stylesheet edit is verified by a rendered page, never by reading the CSS.
