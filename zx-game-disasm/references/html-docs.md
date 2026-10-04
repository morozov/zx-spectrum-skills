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
- **Conventions** — what an address on a page means, and what this project's relocatability claim is. Both are below; neither is answerable from anything else the site publishes.

Group them under index headings in the main `.ref` (`[Index:Reference:Reference]`, which `assets/game.ref.template` already declares with `Notes` and `Glossary` under it) so the site has a navigable structure rather than a flat list of routine pages.

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

## An address on the page needs a page that explains it

A routine page carries addresses in four forms and marks none of them. All four can sit on one page, say `asm/8A00.html`:

- the **address column** — `8A00`, `8A01`, `8A03` — bare hex, no `$`: where the byte sits in the snapshot the disassembly was cut from;
- an **unlinked name** — `LD HL,ATTR_BASE+$186` at `$8A14`, linking nowhere;
- a **linked name** — `LD HL,ATTR_BASE+$180` at `$8A19`, two instructions later, pointing at `4000.html#5980`; `JR NZ,draw_border` and `LD A,(player_lives)` are the same form with a plain label in it;
- a **raw number** — `LD DE,$0020`, `LD B,$12`: an operand the source binds to no name at all.

The middle two mean the same kind of thing and render differently. Both are attribute-file addresses in one routine, and `ATTR_BASE+$180` links only because it lands on a line start in the loading-screen block while `ATTR_BASE+$186` lands six bytes inside one. Turning on `LinkOperands` for `LD`, per *"Link every operand the reader will chase"* below, is what makes the difference visible: it converts an invisible property of the block's line breaks into a typographic distinction the reader can see and will read as meaning something. It means nothing.

**The page spells an operand the way the `.asm` spells it.** `skool2html` builds its parser with no `asm_mode`, so on its own it reads neither `@isub`/`@ssub` nor the `@equ` label map, and every named constant in the source comes out on the page as the number it stands for. The `html` target therefore loads `scripts/html_operand_subs.py` as `[Config] InitModule`: the wrapper parses the skool a second time in ASM mode and copies the operand text across, so `@isub=LD (BUFFER_BASE+$2E0),A` reaches the routine's page as `LD (BUFFER_BASE+$2E0),A` — the text `{game}.asm` carries — still linked to the buffer's page. Operand text only: the snapshot, the byte values and the reference graph are computed before the wrapper runs and are left alone, so the substitution cannot reach what the disassembly assembles to.

What it deliberately does not carry over is `@ofix`/`@bfix`/`@rfix`. A sub directive restates an instruction; a fix directive replaces it. The pages show the bytes of the game as it shipped, so an operand on them has to be another spelling of those bytes and never a correction to them — the fixed `.asm` is where a fix belongs, and `references/build-verify.md` covers that split.

A name in an operand is not relocation. A buffer whose block is pinned with `@ $F000 org` — say a routine reaches it from a map pointer with three `INC H`, so it sits exactly three pages above a map base that is itself pinned — keeps its symbolic operand and still cannot move at all. What the symbolic form buys is a name and one place to change it — not relocation, which is the section below and a separate question.

The reader who is handed the site and not the terminal cannot decode what they are looking at. Give them a conventions page. It is a reference page like the others listed under *"Reference pages"* above, grouped with them under `[Index:Reference:Reference]` — add it there rather than inventing a second place for it. The questions it has to answer, none of which anything else on the site answers:

- **what the address column is** — the address in the original image, and that page filenames and anchors use the same hex base as the `.ctl`;
- **what a name in an operand is** — either a label the disassembly assigned to that address, or an `@equ` constant, possibly with an offset on it. The `.asm` opens with an `EQU` block and the site has no equivalent, so give the constants and their values here: a reader who meets `SCREEN_BASE+$84C` on a routine page has nowhere else to resolve it. Say too that a name links only when its address starts a line of the block it lands in, so whether one is hyperlinked carries no information about what it is;
- **what a `$XXXX` operand is** — an operand the source binds to no name: a count, a mask, a port, or an address still unlabeled. Distinguish the ones that are working as numbers from the ones that are a naming job not yet done, and point at the gauge for how many of the latter are left;
- **that the page is not the `.asm`** — both come from the same `.skool`, and the operand text agrees, but the `.asm` is the fixed source: it carries `@ofix`/`@bfix` corrections the page does not, because the page shows the game as it shipped.

Keep it to one page: a convention restated per routine has one place to edit and forty to go stale.

## "Relocatable" is a result the site has to state

`make coverage` prints `RELOCATABLE : 0 raw operand(s) into the game region`, and carries the caveat with it — 0 there is label-clean, not proven. `references/build-verify.md` holds the proof, its two non-obvious constraints, and the four things the operand count cannot see; agree with that file rather than re-deriving it. The reader of the built site gets neither. A project that has run the move-and-run proof and a project that has only ever been read statically render page-for-page identically.

The distinction the site must not blur: `skool2asm -s` proves the source is **label-clean** — no in-image operand renders as a raw address. It does not prove the program still works somewhere else in memory. "The build is green and `-s` passes, so the code is relocatable" is a false inference: a program can read `RELOCATABLE 0` and still break when a byte moves, and `references/build-verify.md` says why.

Put the project's actual status in one sentence on the conventions page, in one of three shapes:

- **Proof run** — name what was moved, by how much, what was observed running, and where it is recorded. "The program was rebuilt with its blocks permuted and played to level 3 under an emulator with identical behavior" is a claim a reader can weigh. "Relocatable" alone is not.
- **Proof not run** — "the source is label-clean: every in-image operand renders as a label. The program has not been rebuilt at a different address, so it is not known to be relocatable." Then stop.
- **Not claimed yet** — a project still in the labeling sweep opts out of the strict render by setting `ASM_FIXED_FLAGS =` empty in its Makefile. Nothing then gates the `.asm` on being label-clean, so neither shape above is available: say "the disassembly is still being labeled and makes no relocatability claim", and give the gauge's raw-operand count as the progress it is.

Silence defaults to the stronger claim, because the word already appears in the gauge output and the `.asm` a reader may also have, and these pages render exactly like a finished project's. Writing nothing makes a project that has run the proof look the same as one that has not.

## Defect catalogs carry IDs and evidence

Bugs, quirks, and graphic glitches get catalog pages with one anchored section per defect, so each has a stable ID that code comments and other pages point at:

```ini
[GraphicGlitch:enemiesTooLow:Front-facing enemies are drawn too low]
```

Each entry pairs the claim with rendered evidence (the sprite showing the stray pixels, the misaligned mask), the root cause traced to its routine, and the fix address. A project that releases its documentation in versions can add a changelog page for the disassembly itself.

## Styling

### Who owns which file, and why the order matters

Two readers use this section. Most of it addresses the project author. This first part addresses whoever edits the skill's own `assets/` — the rule it states is what keeps the rest of the section true.

> **A shared asset states defaults. Only the project states mandates.** Everything the theme ships must be reachable by *adding*. If the only way for a project to get what it wants is to write `none`, `static`, `auto`, `0`, `unset`, or a copy of the whole rule, the theme has stated a mandate and the theme is what changes.

The test that makes it operational: for every declaration you add to `assets/theme.css` or `assets/theme.ref`, write the line a project would put in `{game}.css` or `{game}.ref` to get the opposite, then read that line.

- It sets a **variable** → the declaration is a default. Ship it.
- It sets a **value** → the declaration is a default. Ship it.
- It sets `none` / `static` / `auto` / `0` / `unset`, or restates the theme's own selector to undo it → the declaration is a **mandate**. Hoist the constant into `:root` and read it at the use site.
- There **is no such line** → the declaration is a **mandate with no escape**. It belongs in `assets/game.ref.template`, not in `theme.ref`.

That last branch is the ref-file half of the rule, and it is the easy one to get backwards, so check it rather than believe it. `theme.ref` is parsed **last**, after every project ref, and last wins. `skool2html.py:183-196` in SkoolKit 10.1 builds the ref list in three passes: `glob({game}*.ref)` in the skool file's directory with `{game}.ref` forced to the front, then the files named in `[Config] RefFiles=`, then the ref files on the command line — where `theme.ref` is. `parse_ref_files` skips a path already in the list, so passing `{game}.ref` again after it changes nothing. `refparser.py:30-33` in SkoolKit 10.1: a plain `[Section]` **replaces**, a `[Section+]` **extends**, and inside a dictionary section a later `Key=` overwrites an earlier one.

So a key `theme.ref` states in `[Game+]` beats the project's value for that key, and a plain `[Template:*]` in `theme.ref` cannot be overridden by a project ref at all. The `+` suffix is generic — `refparser` accepts it on any section name, `[Template:Layout+]` included — but that does not help a project here: whatever a project builds, extension or not, the theme's plain section is parsed later and replaces it. The three templates the theme draws are the theme's, full stop.

That is why `theme.ref` holds nothing but those templates: `StyleSheet`, `AddressAnchor`, `CodeFiles`, `Release` and `Copyright` all live in `assets/game.ref.template`, which is parsed first and is the project's own file. The one layer that composes rather than clobbers is `-c` (`skool2html.py:197` in SkoolKit 10.1, applied after every ref), which is how the framework appends a project's own scripts to the theme's — `HTML_JS` in `tools/disassembly.mk`.

### What the theme ships

**Every site gets the skill's default theme** — the framework's `html` target passes `assets/theme.ref` (with `assets/theme.css` and `assets/theme.js`) and builds with `-H -a`. The stylesheet is the one part a project opts into by name, because SkoolKit's `StyleSheet` is a single ordered chain and only the project can own it; `assets/game.ref.template` declares that chain, so a site started from the template has it. By default every disassembly ships with:

- a dark, responsive layout (viewport meta, card-grid index, header bar);
- the code listing in a monospace face with prose in a reading face, both named once in `:root` as `--font-mono` and `--font-sans` and resolved from faces the reader's platform already has; the theme ships **no accent face and no game palette** — its `:root` colors are deliberately neutral;
- **Z80 syntax highlighting** — mnemonics, registers, immediates, strings and comments each colored, by the tokenizer in `assets/theme.js`. It ships with the site and fetches nothing;
- **operands rendered as label names** — `CALL draw_sprite`, never `CALL $8A42` — via `--asm-labels`, which is why the 0-auto-label bar matters to the HTML too;
- **`$`-hex values in prose in the monospace face** — `scripts/html_hex_mono.py` wraps each value (two or four hex digits after a dollar sign, never one or three) in `<span class="hex">` after `skool2html` runs, and the theme styles `.hex`. CSS cannot match text, so a build step does it; the framework's `html/.stamp` recipe runs it, so a project does nothing. It leaves the listing's instruction and label cells, `<code>`, `<pre>` and the head alone, and a second run changes nothing;
- comment-group hover: the rows a shared comment spans light up together, and only those — an uncommented row stays dark (see the empty-cell rule below).

The theme is the floor, not the identity — it is structural on purpose, so fifty games built with it do not all look like one game. Identity (the palette derived from the game's attributes, the accent face, the logo) comes from the project layer. Put every game-specific override in `{game}.css`, which loads last. The override points are `:root` — the palette, the tints and rules, and the four layout constants `--measure`, `--index-measure`, `--gutter` and `--header-height` — plus the per-section `--section-color`. Setting one of those is how a project changes a number the theme uses in several places at once: the gutter, for instance, is the wrappers' padding, the header row's inset, and half of `scroll-padding-top`.

A project that needs its own JavaScript on a generated page sets `HTML_JS` in its Makefile rather than `[Game] JavaScript=`; the framework appends it to the theme's script so neither displaces the other. Stylesheets, the INI, and rendered images are HTML-affecting sources the framework's `html/.stamp` does not know about, so the project Makefile adds them as extra prerequisites:

```
html/.stamp: $(wildcard *.css) $(INI)
```

- **Derive the visual identity from the game.** Colors come from the game's own attribute bytes — the palette the player actually sees on the playfield, HUD, and border — not from a designer's swatch. The logo is rendered from the game's glyph bitmaps with their own attributes (`Logo=#UDGARRAY…` over the title-screen data), never an imported image. The site should read as the game documenting itself.
- **A stylesheet must not name a face it does not load.** Every family in a `font-family` has to be either a face the page itself ships (an `@font-face` whose `src` is a file next to the stylesheet) or a face the reader's platform already has. A bare webfont name plus a generic — `'JetBrains Mono', monospace` — is neither: it renders in the named face for whoever installed it and in an unknown substitute for everyone else. Pulling the face from a third party over `@import` does not fix it, it only moves the failure onto the network. A built site is a directory of files someone opens from disk, so text that depends on a fetch is text that disappears offline, behind a blocker, or on an air-gapped machine — and it leaks every reader's IP to the font host on every page. The theme's two stacks are the pattern: name real per-platform faces, and reach the generic only on a system that has none of them. This is the defect class whose author is the last person able to see it, so it gets a trap entry below with the render that forces it.
- **The same argument reaches scripts.** A script loaded from a third-party host — a highlighter from a CDN, say — fails offline, behind a blocker and on an air-gapped machine the way a webfont does. Loaded synchronously in `<head>` from a host that drops packets, it is worse than a missing color: the page does not finish. The theme tokenizes Z80 itself in `assets/theme.js` and names no host at all. Keep it that way: a built site fetches nothing.
- **A custom game font is an accent, not the text face.** When the game's 8x8 font is extracted to a webfont (`Font={game}.woff2;{game}.ttf`), use it for headers, the logo, and small accents only; body prose and the code listing keep a proper reading face. A bitmap font at paragraph size is atmosphere on one line and an eyesore on a page.
- **The disassembly table lays out from its content.** Column widths are content-driven and code lines never wrap — a wrapped instruction reads as two. The source-side half of this rule is the 24-char label cap (`lint-label-length`): styling cannot fix a gutter a label forced open.
- **An empty comment cell is column, not annotation.** SkoolKit marks the comment class per *entry* — `<td class="comment-{annotated}">` — so every row of an annotated routine carries a `comment-1` cell, including the ones with nothing to say. Those come out exactly empty, with no whitespace inside. A `{game}.css` that restyles `td.comment-1` must leave `td.comment-1:empty` free of anything that reads as content: the background and the left edge carry the column band and have to run unbroken, but a box rule around a blank cell makes a bare `RET` look annotated. The theme's hover skips empty cells for the same reason.
- **Link every operand the reader will chase.** Extend `LinkOperands` beyond the call/jump defaults — `LinkOperands=CALL,DEFW,DJNZ,JP,JR,LD` — so pointer-table entries and immediate address loads hyperlink like calls do.
- **Bitmap art scales pixelated.** Every game image on the site is chunky 8x8-derived art; scale it with `image-rendering: pixelated` so it stays crisp at integer multiples. A blurred sprite is a wrong sprite.
- **A name and credit line are the author's call.** `Release=` names the disassembly and its version and renders under the game title on the index; `Copyright=` sets the site's credit line and renders in the footer. Both are in `assets/game.ref.template`. The theme hides `.subtitle:empty` and `footer .release:empty, footer .copyright:empty`, so an unset field takes no space and a set one reaches the page. `game.ref.template` also carries the hex page filenames and anchors (`CodeFiles={address:04X}.html`, hex `AddressAnchor`) that match a hex-addressed `.ctl` — one base everywhere, per `references/ctl-authoring.md`. Drop them together or not at all: a hex filename with a decimal anchor is two bases on one URL.
- **Prove it by looking at it.** After any styling change, render one sample of each page type — a code routine, a data block, a text block, a graphics-heavy page, a reference/catalog page, the index — in Chrome and check it reads decently: columns sized to content, no wrapped code lines, no gutter blowout, images at integer scale, sprites floating on the page (no opaque paper-color rectangle around a figure — see the transparency rule in `references/expressive-palette.md`), the accent font confined to accents. A stylesheet edit is verified by a rendered page, never by reading the CSS. What to look for while you are there is the trap list below.

## The rendered-page traps

This is the skill's one home for the defects that are invisible in the generated markup and obvious the moment a browser draws it. No linter and no reading of HTML finds them; rendering the site does. They belong here rather than scattered through the role files because they are the *content* of the render the checklist above and the reader pass in `references/orchestration.md` both demand: that pass is the procedure, this list is what it is looking for.

Read an entry as symptom → cause → check. Where a check is mechanical the entry says so and names the gate: **a documented trap is a gate not yet written**.

How to render one page, with `$CHROME` the Chrome binary, `$SITE` the absolute path of the directory `skool2html` writes the site into, and `$WORK` a temporary directory:

```
"$CHROME" --headless \
  --disable-gpu --hide-scrollbars --window-size=1280,1400 \
  --screenshot="$WORK/page.png" "file://$SITE/{game}/Graphics.html"
```

Then open the PNG and look at it. For overflow, a measurement beats an eyeball: append a `<script>` to a copy of the page that reports `document.documentElement.scrollWidth` against `window.innerWidth`, and run Chrome with `--dump-dom`. Anything wider than the viewport is horizontal scroll.

### The listing goes serif on a reader's machine

**Symptom.** The listing comes out in a serif face beside sans-serif prose. A disassembly page is mostly monospace — addresses, labels, byte columns, instructions, the whole listing — so a substituted mono face changes the shape of nearly every row, while the prose column beside it does not move. **Cause.** A stylesheet names `'Inter', sans-serif` and `'JetBrains Mono', monospace` and pulls both from `fonts.googleapis.com` with an `@import`. What the reader gets therefore depends on the reader: the same page renders in JetBrains Mono and Inter when that host is reachable, and in the browser's *generic* families when it is not. Those generics are a per-browser preference, not a constant. A profile that maps `monospace` to Menlo and `sans-serif` to Helvetica hides the defect; a profile whose fixed-width font is Courier New puts a serif slab under the entire listing against Arial prose. The fetch fails for a reader who is offline, behind a content blocker, or on an air-gapped machine — and a built site is a directory of files opened from disk, so those are ordinary conditions, not edge cases. **Check.** A screenshot on the author's machine proves the opposite of what is needed: it has the network, and may have the fonts installed besides. Force both halves of the failing case — cut the font hosts *and* pin the generic to a serif:

```
mkdir -p "$WORK/p/Default" && printf '%s' \
  '{"webkit":{"webprefs":{"fonts":{"fixed":{"Zyyy":"Courier New"}}}}}' \
  > "$WORK/p/Default/Preferences"
"$CHROME" --headless \
  --disable-gpu --hide-scrollbars --window-size=1280,1050 \
  --user-data-dir="$WORK/p" \
  --host-resolver-rules="MAP fonts.googleapis.com 0.0.0.0, MAP fonts.gstatic.com 0.0.0.0" \
  --screenshot="$WORK/page.png" "file://$SITE/{game}/asm/{ADDR}.html"
```

To name the faces rather than eyeball them, attach over `--remote-debugging-port` and call `CSS.getPlatformFontsForNode` on a `td.instruction` and a `td.comment-1`: it reports the family Chrome actually drew, which is the only answer `getComputedStyle` cannot give. **Fix.** The theme declares `--font-sans` and `--font-mono` in `:root` as stacks of real per-platform faces and every rule reads them, so no page waits on a download and the generic is reached only by a system carrying none of the named faces. The Styling rule *"A stylesheet must not name a face it does not load"* above is the general form. **Audit, not yet a gate:** `grep -n 'font-family' *.css` and confirm every value is a `var(--font-*)` or a stack whose first entry is either shipped by an `@font-face` next to the sheet or present on the platform. A project sheet re-opens the defect the moment it writes a bare webfont name.

### An empty comment cell is styled as an annotation

**Symptom.** A bare `RET`, or any row of an annotated routine with nothing to say, looks annotated: its comment cell carries the box rules, borders or hover highlight of a real comment, so a reader counts annotations that are not there. **Cause.** SkoolKit sets the comment class per *entry*, not per row — `<td class="comment-{annotated}">` — so every row of an annotated routine gets a `comment-1` cell, the empty ones included. **Check.** Render a routine that has uncommented rows and look down the comment column. **Theme default, not a gate:** the theme draws no top or bottom rule on an empty `comment-1` cell, and `theme.js` keeps the hover off those rows, so a site on the stock theme does not show the defect. A project stylesheet re-opens it by restyling `td.comment-1` without an `:empty` carve-out — the Styling rule above states the constraint.

### A long page title pushes the page sideways

**Symptom.** A long page title overflows the header: the logo keeps its natural width, the title cell grows, and past the viewport width the whole page, header and body, scrolls horizontally. A project stylesheet that puts `td.page-header` in a wider face makes it worse, and the theme on top of it widens the title cell further. **Cause.** `td.page-header` is `white-space: nowrap` and `td.logo` is `flex: 0 0 auto`, so the title sets a floor under the page width and the logo never gives ground. **Check.** Render the page with the longest `[Titles]`/`[PageHeaders]` string at 800 px and compare `scrollWidth` to `innerWidth`; shorten the title until they match.

### An image macro that renders nothing leaves a hole

**Symptom.** A paragraph introduces a sprite, and no sprite follows: the reader cannot tell whether the picture failed or was never claimed. **Cause.** A frame-only macro — `#UDGARRAY…(*name)` — defines a frame and writes no file; a frame renders nowhere unless some `#FRAMES`, `#UDGS` or `#COPY` macro consumes it and that macro itself names a file. A macro that names a file the build did not produce fails the same way. **Check — a gate.** `make lint-images` reports NOFILE for a macro that names no file and UNRENDERED for a named file the site does not have (`references/build-verify.md` has the full invariant). The render check that remains is the layout hole itself. A gate proves the picture exists, not that the paragraph around it reads.

### A large image alone on a line is not a block

**Symptom.** On a Graphics page the loading screen — a 512×384 image with nothing beside it — sits hard against the left margin, and the paragraph that follows it begins on the image's **last line**, tucked into the empty space at its bottom right. The page reads as though the prose collided with the picture. **Cause.** A `[Page:*]`'s `PageContent` is emitted into the page verbatim — macros expanded, nothing else added — and `#SCR` / `#UDGARRAY` expand to a bare `<img>`. An `<img>` is inline, so a full-screen picture flows as one very large word inside a paragraph and the next sentence continues on its baseline. **Check.** Render the page — the markup shows the `<img>` alone between two blank lines and looks entirely correct. **Fix.** Wrap a solo image in a block (`<div>`/`<p>`, centered) rather than leaving the macro loose in the text.

### Blank lines in a `.ref` page are not paragraphs

**Symptom.** A `[Page:*]` of several sections renders as a single unbroken wall of text, with its bold section headings sitting mid-line inside the paragraph above them instead of opening a section. **Cause.** The same verbatim emission as above: the ref section's blank lines survive into `<div class="page-content">` as whitespace, and HTML collapses whitespace. In the `.ref` source, and in the built markup, the paragraphs are visibly separated. **Check.** Render the page. This one is invisible in every other view — the source, a diff and a grep all show structure that the browser does not draw. **Fix.** Emit real block elements: `<p>` per paragraph, a heading element per heading.
