# Fixture for validate_ctl_instruction_order.py: an `@` directive that sits after
# the line comment it belongs to.
#
# Covers both comment forms. A linter that recognizes a line comment only
# through the comma of an explicit length registers `  $F010 Comment` against no
# address at all, and anything misplaced beside it passes.
# `validate_ctl_lengths.py` rejects a length that restates the gap to the next
# entry, so the length-less form is the one the skill asks for in most places.
#
# Expected:
#
#   validate_ctl_instruction_order.py fixtures/comment-line-order.ctl
#   -> 2 violations: `@ $F010 label=reset_lives` after its length-less comment
#      line, `@ $F020 keep` after its `,3` one. Exit 1.
#
# Five controls must not be reported:
#
#   $F000 carries one of every directive, in canonical order: `@`, the entry
#     type, `D`, `N`, `R`, then the line comment.
#   `E $F000` closes the entry, so it trails the line comments of the entry it
#     ends and is still in order.
#   $F030 is the fix the two findings ask for - the `@` above its line comment.
#   `B $F040,8,4` is a sub-directive, not a line comment, and registers nothing
#     at $F040. Its leading `B` is also a hex word, which is why an address must
#     be `$HEX` or bare digits and not either alphabet.
#   `i $F048` terminates the image.
@ $F000 label=start
c $F000 Program entry
D $F000 Sets the level up, then runs the frame loop until the last life is lost.
N $F000 Frame loop entry.
R $F000 A Level number
  $F000 Save the caller's frame pointer.
  $F010 Reset the life counter.
@ $F010 label=reset_lives
  $F020,3 Restage the player sprite pointer.
@ $F020 keep
@ $F030 keep
  $F030 Player sprite pointer, patched at respawn.
E $F000 The loop exits only through the game-over path.
b $F040 Player sprite bitmap
  B $F040,8,4 Player, frame 0
i $F048
