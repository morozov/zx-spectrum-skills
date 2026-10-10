# Standing rules

Every item is a check. A Worker applies each one before it reports. A Challenger refutes against each one, and a violation is a REJECT or a SPLIT, not a note. The rules are general unless marked as a project's own.

## Provenance

- Persisted content states what is true or required. That covers rules, comments, pages and commit messages.
- It never records who asked for something, when, or what happened before. No "the owner said", "call-out", "as requested", "previously", "was found".
- A reader needs the rule or the fact. How it came to be written is not theirs to read, and it dates the text the day the situation changes.

## Register rows

- One `R` row per register. `R $A I:HL destination, DE source, B byte count` is three rows. No row names two registers, and a routine's registers are never described in its prose instead of in rows.
- A row is a lower-case noun phrase with no final full stop, and says what the register holds, with the encoding or limit that matters: "pointer to the string (bit 7 set marks the final character)", "number of bytes to copy (0 copies 256)". A bare noun such as "destination", "source" or "attribute" tells the reader nothing. Routines that do the same job at different sizes carry parallel rows.
- A routine that takes a value in a register, or hands one back, has `R` rows for it. A prose sentence such as "advances HL" is a missing row. Run `scripts/register_usage.py SKOOL --ctl CTL` to list candidates, and confirm each against the code.
- A row states a contract: the caller deliberately sets the input, or deliberately uses the output. A register that merely holds a leftover value another routine happened to read is a defect, documented where it is read, and gets no row. Before adding a row, read the call sites and confirm the caller sets or uses the value on purpose. Dataflow shows that a value flows, never that anyone meant it to.

## Callers

- Nothing in a project states who calls or uses a routine. Never author a `Used by` line, an `EREF` note, a "called by" or "dispatched by" clause, and never leave `ListRefs` above 0 in `skoolkit.ini` (the template sets 0). The list is not what a page is about, it repeats on every page, and a routine with a thousand callers would make it unreadable. The toolchain tracks the references; the reader follows the operand links.

## Unused bytes

- An unused entry is titled "Unused bytes" and has no description and no row comments. The title and the entry type say it; repeating "Unused." under them is noise. A single unused byte inside a used table keeps its "Unused." row, because there the row is the only place that says so.
- Never explain why bytes are unused: no "nothing reads these", no "the copy stops where they begin", no census of readers.
- Never describe the neighbors. The test: move the bytes somewhere else and the title and description must still be true.
- Never guess a purpose. Say more only when the bytes decode to something you can state, such as a message, a sprite or a table.
- Unused bytes have no layout by definition. A check that asks them for a stride, a tiling, a type or a description is a linter bug. Fix the linter, never bend the data. (`validate_ctl_data_structure.py` and `validate_ctl_identity.py` already exempt `u` entries.)

## One entry per thing

- Strings that are parts of one message are one entry with one line per string. Two lines of a prompt, or a banner and the blank that erases it, are not adjacent entries. The test: do the titles differ only by "line 2" or by what the blank is for? Merge them.

## Fonts and graphics

- Do not comment ordinary characters of a font.
- A cell that draws something other than the character its code stands for is an exception. Render it, say what it is (copyright sign, left arrow), and say which character it replaces. Where it is used is a further column, never a substitute for what it is.
- A comment that names a role but does not show the glyph leaves a reader with no idea what the glyph is. Show the glyph.
- Every block named as a sprite or a glyph renders it. If the bitmaps exist at two addresses, both render, from the source bytes when the slot's own bytes in the image are not yet the sprite.
- Sprite, glyph and bitmap data carries no per-row comments, and no comment says which pixel means what. The render shows the picture.
- Data is written in the default radix, never in binary.
- A render of raw tiles in memory order is never published. Only composed pictures are.

## Names

- One prefix per kind of thing, applied to every member of the family before moving on. When one family gets a prefix, check its sibling families for the same gap. (Example: sprites `spr_`, their source bitmaps `src_`, animation tables `anim_`.)
- A family has one prefix and one naming scheme, and every member carries it. That includes the members of a page that merged several entries.
- A pickup name is not an adjective for what it produced. Write "the enlarged ship", not "the ENLARGE ship". The name stays where it names the pickup, its container or its glyph.
- A name must not claim a different nature from its data. `work_` read as temporary storage for real sprites. Name data by what it is, not by how it is staged.
- Link anchors use dashes, never underscores. The casing of a display name is the author's call.

## Comments sit at the layer they describe

- A sentence about a whole run (a layout, a slot size) belongs in the entry description. A row comment describes that row. A comment beside the first row that describes the whole run is on the wrong layer.
- A data run uses the default row width of 8 bytes unless the structure dictates another. A stride picked to quiet a linter is a defect.

## Numbers and counts in prose

- A count of things in a link note, an intro or a caption ("5 shipped bugs", "the first four entries") is stale the moment the list changes. Say what the page is, not how many it holds.
- A routine's title and description do not carry the size of what it processes ("Clear the 768-byte buffer", "fills all 768 cells") unless the behavior changes with it. Say what the routine does to the thing. The size belongs on the data's own page, where its length is defined.
- Hex values in prose have two or four digits, never three. The site wraps each in a muted monospace pill in a build step (`html_hex_mono.py`), never a loud color.

## Prose reads as prose

- A description is sentences a person reads aloud. It does not contain formulas ("cell = BASE + (Y'>>3)*32 + (X'>>3)"), primed variables, shift or mask notation, or arithmetic written as code. Say it in words: "the column is the X position divided by eight". The instruction comments and the register rows carry the exact operations. A description that has to be decoded is not finished.
- A description says what the routine does, not how. A conversion is "converted to the tile-map cell it falls in", not the shifts, scales and base it is built from. Those are on the instructions, one comment each, and restating them in the description makes a second copy that drifts.

- A full stop closes a sentence. A row that is a noun phrase, such as a data row naming what it holds or a code row reading `Fire held`, takes none; an imperative or a clause keeps it.

## Evidence

- Document a defect or a behavior from the code. A recording or a run only locates where to look. It is never required, never cited, and never what the reader has to trust.
- A disassembly says what the code does, never how often it happens. No frequencies.
- A claim the code cannot settle is stated as a condition ("if the return trip ends where the shot started, the path repeats"). It is not shipped as a hedge, and not as a typed marker the gate counts.
- "Are you sure?" asks for precision. Say exactly which bytes, slots or addresses the claim covers and what the image holds there. Do not generalize from the part you checked.

## How to work

- A call-out from a reviewer is a defect to fix. Decide from the evidence, act, and say what was decided.
- Taking over a contribution means bringing it to the standard of its neighbors: trigger, mechanism, why it persists, state, fix.
- When asked to validate, validate: check the claims and the gate. Do not start new analyses the task did not ask for.
- A tool you build gets validated against cases whose answers are already known before its output is trusted.
- A Challenger reviews a change before it is committed.
