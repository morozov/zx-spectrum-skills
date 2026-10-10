# Rationale

Commentary. The rules are in `rules.md`. Where this file differs, `rules.md` holds.

This file holds the reasons some rules ship as a check and others have no check. A check ships when its precision pays for the attention its false hits cost. Otherwise the rule stays with the Challenger.

## Bare blocks (ENT-7)

`make coverage` calls a routine *explained* when no block in it is bare. A line-density figure can read the same for a disassembly averaging two comments per block and one averaging less than one, so coverage counts bare blocks.

A long single-entry, single-exit run whose one sentence is too thin for it has no check. Nothing structural separates it from a legitimate unrolled span, so it stays the Challenger's read.

## Spliced sentences (PROSE-8)

`SPLICE` fires on a pair of signals: the previous unit ended without terminal punctuation, and this one opens lowercase. Each signal alone also appears in correct prose, so the check fires only on the pair.

## Record offsets in code prose (AUD-4)

`LAYOUT_ECHO` tells a citation from a definition by location. An offset in a `c` block's prose is a citation, and an offset in a data block's `D` or `N` is the definition. A disassembly held to this bar cites none, so a hit is a defect.

## Dispatch codes in code prose (AUD-4)

`CODE_ECHO` reports a dispatch code named as a code in a `c` block's prose, such as "the walker (type 12)" or "Sentry behavior handler (enemy type 4)". The block type makes it decidable. The type-to-handler mapping lives in a data block, where the number is the entry's whole content, so a routine carrying it is named by its slot in another entry's table.

## Bare codes in notes (AUD-4)

Every other shape of a code in prose goes to the Challenger, who applies the deletion test in `comment-style.md`.

A pattern for a standalone `($XX)` in a `D` or `N` note reports mostly misses, among them `OUT ($FE),A` quoted in a note. Widening it to catch more citations adds misses faster than right hits. A widening keyed on one word of the game's vocabulary finds only the citations that use that word, and its misses are all entries that use it.

Many of the misses are the glyph catalog's own entries, such as `SHIELD pickup, glyph letter S (tile codes $A4-$A7)`, and a pattern separates those. A definition carries its `#UDGTABLE`/`#UDGARRAY` render and writes the code as a range. A defect and a definition can be the same directive type in the same file, and the difference is on the line. With the definitions filtered out, the findings worth acting on are still outnumbered by the ones an author reads and dismisses. The kinds of `scripts/lint_comments.py` feed the coverage verdict, so a kind at that precision costs more attention than it returns.

The same shape in `graphics.ref` lands on `#TABLE` rows. A check there reports the entries that define the encoding, the catalog row and the `N` note that states a record's fields. Each comes back as a finding to dismiss by hand.

## Titles that list several things (HEAD-3)

A title that carries a list can be legitimate or a defect, and nothing in its shape tells the two apart, so the Challenger asks HEAD-3.

## Entries that lean on a neighbor or describe another's logic (HOME-8, HOME-2)

Neither shape has a check precise enough to ship. The back-reference shape is a sentence opening on "then", "also" or "the same". That opening is correct when a routine refers to its own previous sentence, and a pattern cannot tell the two apart. The plumbing shape, scoped to catalog entries that render, has legitimate hits too, and a pattern narrowed until it catches only a known defect is a keyed match. `DEIXIS` reports the positional shape, "the routines below", and `FOREIGN_LOGIC` reports a data entry's sentence that links code beside a verb of computation. The Challenger asks the rest.
