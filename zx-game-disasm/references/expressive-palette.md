# The expressive palette — say it in SkoolKit, not in prose

Commentary. The rules are in `rules.md`. Where this file differs, `rules.md` holds.

SkoolKit is a documentation toolkit, not just a disassembler. It gives you a large vocabulary of macros and directives for expressing what the code means, and the guiding principle is simple: **prefer the native device over prose.** A sprite is richer rendered from its own bytes than described in words. A sound effect is richer played than transcribed. A bitfield is richer as a table, a timing as a computed value, a constant as a substituted symbol. Reaching for the right device makes the disassembly both richer for the reader and self-maintaining — derived from the actual snapshot, so it cannot drift.

So when you are about to write a sentence, ask whether SkoolKit has a device that *expresses the fact directly*. Usually it does. This file is the catalog; reach into it liberally. Exact parameters are in the official docs — skool macros at <https://skoolkit.ca/docs/skoolkit/skool-macros.html> and ASM directives at
<https://skoolkit.ca/docs/skoolkit/asm.html>. Verify a macro's signature there
before relying on a parameter; do not guess.

## Table of contents

- [Cross-references and navigation](#cross-references-and-navigation)
- [Numbers, registers, and text](#numbers-registers-and-text)
- [Structured documentation: tables and lists](#structured-documentation-tables-and-lists)
- [Graphics rendered from the snapshot](#graphics-rendered-from-the-snapshot)
- [Audio you can play](#audio-you-can-play)
- [Computed documentation](#computed-documentation)
- [Symbolic constants and substitution modes](#symbolic-constants-and-substitution-modes)
- [Fix modes: express original vs corrected](#fix-modes-express-original-vs-corrected)
- [Game-knowledge sections: pokes, bugs, facts](#game-knowledge-sections-pokes-bugs-facts)
- [Reach, but stay grounded](#reach-but-stay-grounded)

## Cross-references and navigation

Turn every mention of an address or page into a live link, so the disassembly is navigable instead of a flat listing.

- **`#R$XXXX`** — link to the routine/data entry at an address (resolves to its label). Use it for every address you name in prose. `#R$8050@code` targets a named instruction; `(text)` overrides the link text.
- **`#Daddr`** — expands to the *title* of the entry at an address. Reference a routine by its purpose without retyping the title.
- **`#LINK(PageId#anchor)(text)`** — link to any other page (a reference page, the glossary).
- **`#PC`** — the address of the nearest instruction; handy inside generated text.
- **`@remote=code:addr`** — declare an entry that lives in *another* skool file so cross-binary `JR`/`JP`/`CALL` references hyperlink correctly (multi-load games).

## Numbers, registers, and text

- **`#Nvalue`** — render a number in the reader's chosen base (honors `--hex`/`-D`/ `-H`), so one source serves both decimal and hex builds.
- **`#REGhl`, `#REG(text)`** — style register names consistently in prose.
- **`#CHRnum`** — a character by code (with a ZX Spectrum mapping flag); express a control code as its glyph.
- **`#STRaddr`** — pull a terminator-delimited string straight out of memory, so documented text comes from the bytes, not a hand copy.
- **`#SPACE[n]`**, **`#RAW(text)`** (suppress macro expansion), **`#HTML(text)`** (HTML-only literal), **`#VERSION`** — finer text control.
- **Numeric base prefixes** in data sublengths (`b` binary, `c` character, `d` decimal, `h` hex) and `C $addr,c` for character operands — see `references/ctl-authoring.md`. Data stays in the default radix (GFX-5), and ASCII loads show as characters.

## Structured documentation: tables and lists

Whenever a fact has structure — a bitfield, an enum, a record layout, a stat block, a level legend — express the structure, do not flatten it into a sentence.

- **`#TABLE(class) { =h Header | ... } { cell | ... } TABLE#`** — bordered tables with header/row/colspan markers. The canonical home for bit fields, value enumerations, object stat blocks, and memory-map layouts.
- **`#UDGTABLE ... UDGTABLE#`** — same, but HTML-only (use when cells contain images that have no ASM rendering).
- **`#LIST(class) { item } LIST#`** — bulleted lists for ordered steps or enumerations that are not tabular.

A table earns its place only by carrying **data the reader cannot get otherwise**. A header with no rows, a table that just restates a record's field names, or a hand-drawn ASCII-art grid in a comment (`; +------+------+`) is *bloat* — it adds nothing and pads the disassembly. Delete it, or fill it with the actual values (the periods, the counts, the addresses) pulled from the data. And never hand-draw a table in prose when `#TABLE` would render one from the bytes; never tabulate at all what a richer device expresses directly — a *tune* is not a table of period and duration bytes, it is an `#AUDIO` you can play (see below).

## Graphics rendered from the snapshot

This is the biggest expressive win and the most underused. The game's graphics are *in the snapshot* — render them, do not describe them. Point each macro at the address your disassembly identified for that graphic, so the picture and the data block stay in sync.

**No prose where the render is authoritative.** Once a macro renders the asset, the *render* is the documentation of what it looks like — so do not write prose that re-describes the picture ("a 16×16 red bird facing left", "three frames of a walk cycle"). That prose is redundant with the image, and worse, it can *contradict* it — a wrong color name or a transposed letter beside a correct render is the classic catalog defect. Prose earns its place only by adding what the render *cannot* show: the asset's identity and name, its **trigger** (when and why the game draws it), the **routine** that draws it (`#R`), and **code-derived** facts (frame count, dimensions, the table it indexes). Describe the cause and the meaning; let the macro show the appearance. A derived cadence cuts the same way: "a new frame every 4 interrupts" is a fact about the code, "so the walk looks smooth" is a description of the render.

**A sprite floats on the page — it never ships its paper as a frame.** In the game a sprite is drawn over the playfield, so its paper pixels are the playfield; rendered to a PNG they become an opaque rectangle in the game's background color, which reads as a black (or paper-color) frame the moment the page background differs.

First, one project-wide line — SkoolKit renders transparency-designated pixels opaque by default (`PNGAlpha` is 255):

```ini
[ImageWriter]
PNGAlpha=0
```

Then, per sprite, in order of fidelity:

1. **The game has masks** — use them: the mask spec (`#UDG$addr,attr:$maskaddr`, and per-UDG in `#UDGARRAY`) renders masked-out pixels transparent (mask 1 over an unset pixel), and the render then proves the mask data the same way it proves the bitmap.
2. **No masks — derive them.** A sprite is a set pixel figure; derive its mask topologically: flood-fill the unset pixels from outside the bounding box — everything reached is *around* the figure and becomes mask (transparent); unset pixels *enclosed* by the figure are its interior and stay paper. A face keeps its eye holes; the void around it vanishes. Generate the masks in a project decoder (or a small script emitting mask data) and render with the standard mask spec, so derived masks and game masks read identically.
3. **The quick floor** — for a sprite with no enclosed paper at all, `tindex=<paper color index>` on the macro (indices 1-15; 1 is black) makes the paper color itself transparent with no mask involved. It punches holes through enclosed paper too, which is why it is the floor and not the rule.

Backgrounds, full screens, and playfield captures keep their paper: they *are* the background. The rule is for figures that sit on one.

**A frame-pointer entry says which address space it points at.** A game that `LDIR`s its sprites from a source area into a working bank has each bitmap at *two* addresses, and a frame table holds one of them — usually the working copy, because that is what the draw code reads. Annotate the entry with the address it actually holds *and* the source it mirrors, so neither identity is lost:

```
W $9472,4,2 Walk cycle, working copy (source #R$D1C0)
```

Get this wrong and the table documents addresses the bytes do not contain. It is easy to get wrong, because the source area is where the sprite is *cataloged* and the working copy is where it is *used*, so the cataloged address is the one that comes to mind. Read the entry's real value out of the image before naming it. Type it `W`, never `B`: a pointer held as bytes names nothing and relocates nothing (see the pointer category in `references/ctl-authoring.md`).

**Name the routine that actually drives these bytes.** Where a game has two similar systems — a player-fired shot and a scripted enemy shot, say — the plausible attribution and the true one come apart, and a catalog entry that credits the wrong driver reads perfectly. Trace the `#R` you write to the code that reads the bytes, and do not infer it from a name that sounds like a match.

- **`#UDGaddr[,attr,scale,...]`** — one 8×8 tile/sprite cell, with attribute, scale, flip/rotate, and masking.
- **`#UDGARRAYwidth(...)`** — a grid of UDGs: a full multi-cell sprite, a tile set, an animation strip. Supports per-cell masks and crops.
- **`#UDGSwidth,height(...)(uframe)`** — a UDG array populated dynamically via frame references with `$x`/`$y` placeholders (procedural layouts).
- **`#FONTaddr[,chars,...](text)`** — render the game's own character set, or a sample string in it.
- **`#SCR[scale,x,y,w,h,df,af,...]`** — a screenshot assembled from the display and attribute files: show an actual screen the game builds. The captured loading screen is the standard case; it is covered below.
- **`#FRAMES`, `#COPY`, `#PLOT`, `#OVER`** — compose, copy, edit pixels in, and superimpose frames to build animations or annotated diagrams from real data.

Masking (`mask=1` OR-AND, `mask=2` AND-OR), `{x,y,w,h}` cropping, `scale`, and `flip`/`rotate` apply across the image macros. Render sprites *with their mask* so transparency reads correctly.

The annotation *is* the deliverable — annotate the asset in place so `skool2html` renders it in the build. Do not hand-render graphics to throwaway files to "see" them and then describe what you saw; a private render the reader never gets is not documentation.

**The disassembly is the source of truth for every resource; the `.ref` pages are indexes over it.** A resource — a sprite frame, a tile set, a sound, a level — is *established* at its own block in the `.ctl`: rendered, schematized, and indexed there. The `.ref` catalog then *collects* what the `.ctl` already shows, in one digestible place, and links back. Author in that order: the block first, the catalog entry from the block. A resource that exists only in a `.ref` page has no home in the disassembly itself.

- **At the block (the `.ctl`)** — render each individual resource right where its bytes live, so reading the disassembly at that address *shows* it. One macro per resource: each sprite *frame* at its frame's block, each sound (`#AUDIO`) at the data table or player routine that owns it. The device is an `N` directive on the data block: `N $9A40 #UDGTABLE { #UDGARRAY2,14,4,2($9A40-$9A41-1-16)(walker-f1) } TABLE#` — walker frame 1, rendered at `$9A40`. A bare `b $9A40` under a sprite label, with the picture living only in a `.ref`, is **not** rendered inline. And inline means **complete**: every frame block in the bank, not a token corner of it — a "first half rendered" state is an open task, not done. If a game's sprite bank sits far from the code, the render still belongs at the bank; the frame *pointer tables* near the code get per-element comments linking each entry to its frame's block (see `references/ctl-authoring.md` on record-by-record data markup), so the reader can navigate from the table into the rendered frames.
- **In the index (the `.ref`)** — the digest view where the reader sees all assets of a type at once: the animation's frames grouped into a `#FRAMES` sequence, the sprite gallery, the sound list. This is where frames are assembled into a moving whole; the blocks render them one at a time.

Make the index *usable*: group images by what each thing *is*, a labeled grid or table reading value → function → image, not a flat unlabeled dump of cells.

**The loading screen is a resource, and it is one picture.** When the screen the tape painted survives into the snapshot, it is a captured asset like any other and it occupies two blocks: 6144 bytes of display file and 768 bytes of attributes, at `$4000` and `$5800`. Those are two halves of one image, not two data blocks that happen to be adjacent — 768 bytes of color with no pixels to color document nothing, and a page headed "loading screen attributes" tells a reader less than the picture does. So the screen is **one entry**, headed by what it is, covering both halves, with the render on it. Split it per screen address and you get a run of pages that each say the same thing about a different corner of one picture, with the picture itself nowhere — the shape `lint-publication` reports as FRAGMENTED (see `references/ctl-authoring.md`).

`#SCR[scale,x,y,w,h,df,af,...][{crop}](fname)` covers both halves in one macro: `x,y,w,h` are character cells and default to the whole 32×24 screen, and `df`/`af` are the display- and attribute-file base addresses, defaulting to `$4000` and `$5800`. A screen sitting at those addresses therefore needs no coordinates at all — the whole render is the `D` of the entry at the display-file address:

```
g $4000 Loading screen
D $4000 … #UDGTABLE { #SCR2(loading_screen) } TABLE#
```

A screen held somewhere other than screen RAM names both bases in the sixth and seventh slots — `#SCR2,0,0,32,24,$A000,$B800(title_screen)`. There is no second macro for the attribute half; it is already in this one. Then the graphics catalog collects it like any other asset, linking back to the block.

**The letter still follows the writes.** A picture is not exempt from what `b` promises. Where the front-end prints into the captured screen — a menu line, a score readout, an options page — the program writes those bytes as it runs, so the entry is `g`. A captured screen nothing writes — one the loader parked in a buffer, one the program only blits from — is `b`. `lint-publication` reports a `b` entry the code stores into, and it misses the ones written through `HL` or an `LDIR`, so read the writers rather than waiting for it. The repair is the letter and never a split: carving the written cells into their own entry is exactly the run of pages this rule exists to prevent. See "What `b`, `g` and `u` promise" in `references/ctl-authoring.md`.

Inside the entry, name the cells that earn a name — the fixed screen addresses the front-end writes into, each with a `label` and a comment where its bytes are. The spans between them exist only to cut the bitmap at those addresses, so give them **no element size**: a display-file byte belongs to one scanline of one character row, and nothing there repeats at a fixed width. The render is the block's schema.

**The catalog bar: every asset identified and named.** A finished catalog has one entry per thing the game draws — each sprite, enemy, object, pickup, effect — *identified from the code and named for what it is*, never left as an auto-label (`f9440`, `a9440`) or a "not yet named" row. Give each entry its frames, dimensions, behavior, and the handler that drives it; render its animation with `#FRAMES`; and trace every claim to the code. The shape is a `[Graphic:id:Title]` section per entity (player, each enemy, each effect) with its own prose and frames. `scripts/coverage_report.py` counts auto-labeled and "not-yet" entries as **draft** — a catalog that still identifies objects by their address is breadth, not done.

Render composed graphics through their real indirection. A value that selects a tile is rarely `value→glyph`: it indexes a cell table that yields the actual glyphs, often with a separate value→attribute table alongside, so rendering `value..value+n` directly produces garbage. Find the routine that *draws* the thing and follow its lookups — value → cell table → glyphs — and read color from the code's attribute table, not from the cell index. Then look at every rendered frame before committing: a green build proves byte-identity, never that an image decoded correctly. Assess each frame yourself (see `references/comment-style.md`), ideally against a reference such as a community map, to confirm colors, layout, and which cells really are the thing you think they are.

**Name an entry after the glyph the player sees; derive its effect from the code.** The reader identifies a pickup by the letter it shows and an enemy by what its sprite looks like, so the *name* must match that on-screen identity: a pickup that draws **S** is `pickup_S` / "Shield", **L** is "Laser" — never an invented synonym ("force field", "beam gun") that the glyph does not say. This does not conflict with deriving meaning from code: the *effect* is read from the code (what picking up **S** actually does), but the *name* tracks the glyph, and the **glyph→effect mapping itself is confirmed in the code** — trace which letter's pickup triggers which behavior, so you never swap them (is it **D** or **B** that doubles the score? the handler says, not a guess). A label whose name contradicts its glyph is a defect even when the effect prose is right.

**A letter is not the agent's to OCR off the render.** Reading a letter by eye off a rendered sprite is an 8-pixel guess, and it confuses the lookalike pairs — **H/M**, **B/D**, **O/Q/0**, **S/5**, **I/1**. So the render is never your authority for a letter, and you never flip a committed or already-derived letter on the strength of your own eye: that is how a correct "M" becomes a wrong "H". How a glyph's letter is *authoritatively* established depends on how **this** game draws it — read that from the code; do not assume a mechanism. When a letter is genuinely ambiguous, it is a dig-task, never an autonomous relabel.

**A correct render with a wrong label is still wrong — fix the label, not the render.** Rendering the sprite faithfully and then mis-annotating it (the wrong color name, the wrong entity identity) is a common and deceptive failure: the picture looks right, so the error hides in the prose. When the catalog and the render disagree *about shape or identity* — a garbled decode, a mismatched entity, a wrong color name — the render is the truth about the *pixels*, so fix the annotation to match what is actually drawn. But this rule is about shape, not text: it never licenses OCR'ing a letter off the render to overturn a code-traced character or a committed label (see above). Do **not** reach for `zx-fuse-driver` to "re-derive" what already renders correctly; dynamic derivation is for behavior you cannot read statically, not for a labeling mistake you can fix by reading the code.

## Bespoke renders: compose the game's own screens

The top tier of expressiveness, past the built-in macros: a small **project-owned Python generator** that composes the game's *actual screens* — a whole level/room map assembled from its tile and layout tables, every character's full animatory-state gallery, a board mid-game — and writes them as image assets the documentation embeds. This is what separates a top-quality disassembly from a merely complete one; it shows the game as the game draws it, from the very tables the disassembly mapped.

The mechanism is a standalone build-step script (it lives in the *project*, e.g. `utils/`, because it encodes that game's data layout — the one place project-owned code is right), using SkoolKit's own image library so the output matches the built-in renders:

```python
from skoolkit.image import ImageWriter
from skoolkit.graphics import Udg, Frame
from skoolkit.snapshot import get_snapshot

snapshot = get_snapshot('game.pristine.z80')      # the bytes you already verify
# read the game's layout/tile tables out of `snapshot`, build the grid of Udgs
# exactly as the drawing routine does (value -> cell table -> glyphs -> attr),
udgs = [[Udg(attr, snapshot[a:a+8]) for ... ] for ... ]
ImageWriter().write_image([Frame(udgs, scale=2)], open('map.png', 'wb'))
```

The pattern scales from a play-area map through full animatory-state galleries to schedule and timetable tables. Two rules keep it honest:

- **Derive from the same data the disassembly documents.** Read the tile sets, the layout tables, the attribute tables straight from the snapshot, through the indirection the *drawing routine* uses. A render hand-built from a community map instead of the game's own tables is decoration, not documentation.
- **Worth it only when the content is structured data.** Levels, room maps, schedules, board states — things the game itself assembles from tables — earn a bespoke render. A handful of sprites does not; the inline `#UDGARRAY` and the `#FRAMES` catalog already cover those.

The same generator can emit **annotations, not just images**: read each level or room from the binary and *write the control file* — deriving spawn coordinates, item and portal positions, entity types, and the cross-reference labels, then injecting the macros into the prose. Any fact that is *derived from the bytes* (a coordinate, a count, a classification) is better generated than hand-typed, so it cannot drift from the data.

And a composed map can be made **navigable**: an HTML image-map over the rendered level turns each room region into a link to the code that implements it — the player clicks the place in the game world to reach its routine. When a game is built from rooms or screens, make the map the index into the disassembly.

## Audio you can play

Sound is documented the way graphics are: **played, not transcribed** — and to the same source-of-truth rule. Each effect's **`#AUDIO` renders inline at the block that owns it** — the note/period data table, or the player routine for a computed effect — so the disassembly itself is audible at that address; `sound.ref` is the *index*, one **`[Audio:id:Title]`** section per effect collecting the playable `#AUDIO` with the routine that produces it (`#R`) and its trigger (when it plays). Not the cadence and not the pitch: the clip already plays both, so the tone formula is stated once at the primitive that implements it and no per-effect entry repeats it (`references/comment-style.md`, "Never describe a medium in its own units"). A game with sound code — speaker writes, `OUT ($FE),A`, AY writes (`$FFFD`/`$BFFD`), or ROM-beeper calls — and zero `#AUDIO` is undocumented, however green the build; `scripts/coverage_report.py` flags that, and reports the inline-audio count alongside it.

**No prose where the render is authoritative** — the same rule as graphics. The `#AUDIO` *is* the documentation of what the effect sounds like, so do not write prose describing the sound ("a rising warble", "a short descending blip"), and do not state its pitch: a frequency in Hz is that same description with a number on it, and the clip already plays it. Prose adds only what playback cannot convey: the **trigger** and the **routine** (`#R`). Let the `#AUDIO` be heard; document the cause.

**A tune is an `#AUDIO`, not a byte table.** The temptation, faced with a note/period/duration data table, is to transcribe it into a `#TABLE` of "tune byte | period | duration" rows. Do not — those columns just re-list bytes the reader can already see in the data block, and a header with no insight is bloat. What the reader actually wants is to *hear* it: render the tune with `#AUDIO` (simulate the player routine over the table, or build the delay list from it). The table data feeds the `#AUDIO`; it is not the documentation.

**Inline `#AUDIO` needs an ASM guard.** `skool2asm` rejects unsupported macros by default, so a bare `#AUDIO` at a `.ctl` block fails the ASM build the moment it is rendered inline ("Found unsupported macro: #AUDIO"). Wrap each inline occurrence as **`#HTML(#AUDIO(...)...)`** — it expands to nothing in ASM mode and renders normally in HTML. Do *not* reach for `handle-unsupported-macros=1`: that silences every unknown-macro error globally and weakens the warning-clean gate. (`.ref`-file audio needs no guard — only `skool2html` reads it.)

- **`#AUDIO(fname)(delays)`** — synthesize a playable WAV from an explicit T-state delay list (factor reusable lists into `[XxxDelays]` includes).
- **`#AUDIOsim,...`** — *simulate the actual sound routine* and render what it really produces. Prefer this form: it plays the code, not a hand-built approximation. When the effect calls the ROM beeper, document the `DE`/`HL` parameters.

Each *index* section in `sound.ref` derives its timing from the producing routine, so the prose and the WAV both come from the code. See `references/html-docs.md` for delay-list syntax and the timing formulas.

## Computed documentation

The strongest form of "richer is better": let SkoolKit *compute* facts from the real code and snapshot, so the documentation is correct by construction and updates itself when the bytes change.

- **`#PEEKaddr`** — the byte currently at an address. Quote initial values from the snapshot instead of transcribing them.
- **`#EVALexpr[,base,width]`**, **`#IFexpr(t,f)`** — evaluate and branch on arithmetic in the documentation (derive a count, a size, a screen offset).
- **`#FOR`, `#FOREACH`, `#WHILE`, `#MAP`, `#LET`, `#FORMAT`, `#DEF`** — loop, map, template, and define reusable macros. Generate a table of N entries from the data rather than hand-typing it; map an enum value to its name; define a project macro for a recurring annotation idiom.
- **`#SIM`, `#TSTATES`** — run the code in the simulator and read out register state, or compute an instruction sequence's exact T-state timing. The honest way to document "this loop takes ~3 ms": derive it.
- **`#POKES`, `#PUSHS`/`#POPS`** — patch the working snapshot (then restore it) so an image or sim macro can show a *variant* state (a sprite in a different frame, a screen mid-animation).

## Symbolic constants and substitution modes

Encode meaning into the source itself, not only the comments.

- **`@isub=LD A,CONST`** — substitute a symbolic name for a literal (the default ASM mode). A meaningful literal gets its name through a targeted `@isub`; `@equ` is for a value with one meaning program-wide. See `references/ctl-authoring.md`.
- **`@ssub` / `@rsub`** — deeper substitution tiers (`-s` / `-r`): `@ssub` makes code more relocatable via labels without adding/removing code; `@rsub` makes it unconditionally relocatable even if code must move. Reach for these when you want a *relocatable* source, not just a faithful one.
- **`@equ=label=value`** — emit an `EQU` in the ASM output for a constant.
- **`@keep`** — stop SkoolKit replacing a numeric operand with a label (when the number is genuinely a number, not an address).
- **`@nowarn` / `@ignoreua`** — silence a specific, understood warning (an address that is deliberately not a label; a comment address that should not be converted). Use sparingly and only where you have verified the warning is noise.

## Fix modes: express original vs corrected

A disassembly can show the game *as shipped* and, separately, *as it should have been* — a powerful way to document bugs concretely. The fix directives carry the corrected form while the round-trip still reproduces the original bytes.

- **`@ofix`** (`-f 1`) — fix a faulty operand.
- **`@bfix`** (`-f 2`) — fix a bug by replacing instructions without moving any entry points.
- **`@rfix`** (`-f 3`) — fix a bug that needs code to move.
- **Block forms** — `@bfix-begin` / `@bfix+else` / `@bfix+end` (and the `isub`/ `ssub`/`rsub`/`ofix`/`rfix` equivalents) insert, replace, or remove spans. Block markers: `>` insert before, `+` insert after, `|` overwrite, `/` drop trailing comment lines.

Pair a `@bfix` with a `BUG:` narrative (see `references/comment-style.md`): the prose explains the bug, the directive *is* the fix, and the reader can build either version.

## Game-knowledge sections: pokes, bugs, facts

Not everything is code-level. SkoolKit has ref-file sections for the player-facing knowledge a good disassembly accumulates, collected into their own pages:

- **`[Poke:id:Title]`** — a documented cheat (the classic infinite-lives POKE), with the address and effect.
- **`[Bug:id:Title]`** — a game bug, reproduced and explained.
- **`[Fact:id:Title]`** — trivia and behavioral facts worth recording.

These, plus custom `[Page:...]` reference pages and a `[Glossary]`, are wired into the site index via the main `.ref` file (see `references/html-docs.md`). Use them so discoveries land in a durable, browsable place instead of a loose comment.

A complete disassembly builds a whole **reference-manual layer** this way, over the code listing: Bugs, Trivia/Facts, Pokes/cheats, Glossary, Credits, a Walkthrough, even a "Graphic glitches" page documenting the original's rendering quirks — plus multiple filtered memory-map views (Everything / Routines / Data / Messages / Unused) and a named page for each structured data block. That layer is what makes a disassembly read as a manual, not a dump. The register each page is written in is in `references/html-docs.md`.

## Reach, but stay grounded

Richer is the goal, but never at the cost of truth. Two guards from the rest of the skill still apply:

- **Verify the syntax.** These macros have many parameters and their forms are version-specific — image-macro syntax shifts between SkoolKit releases (in v10 the `#UDGARRAY` UDG address specs go inside **parentheses**, not after a `;` as older docs show). Check the official docs *and the installed version* for a macro's exact signature before relying on it, and confirm the build stays warning-free after adding it. A malformed macro that fails to expand is a build break, not a richer page.
- **Express facts, not guesses.** A rendered sprite, a computed timing, a substituted constant are all claims about the code — they must be correct. The no-speculation rule (`references/comment-style.md`) covers macros too: do not render a "sprite" from bytes you have not confirmed are a sprite.

## When the stock palette runs out, decode it yourself

A format the macros cannot express — packed rooms, compressed sprites, a custom string encoding — is not a license to describe it in prose. Register a project `HtmlWriterClass`, write a decoder, and `#CALL` it from the pages; rendering every instance from the live data is the same proof at a higher power. See "Decode the game's formats" in `references/html-docs.md`.
