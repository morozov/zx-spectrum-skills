# Fixture for validate_ctl_instruction_order.py: entry-level directives at an
# address that is not an entry.
#
# SkoolKit renders `D`, `R` and `E` only at an entry's start, and `sna2skool`
# drops one written at any other address without a warning.
#
# Expected:
#
#   validate_ctl_instruction_order.py fixtures/entry-directives.ctl
#   -> 3 findings: `D $F004`, `R $F004` and `E $F004`, all inside `c $F000`.
#      Exit 1.
#
# Three controls must not be reported:
#
#   `D`, `R` and `E` at $F000, the entry's own address.
#   `N $F004`, which renders mid-block.
#   `@ $F004 label=...`, which is not entry-level.
@ $F000 label=start
c $F000 Program entry
D $F000 Sets the level up.
R $F000 I:A level number
  $F000 Save the caller's frame pointer.
@ $F004 label=reset_lives
D $F004 Resets the life counter.
N $F004 The life counter restarts here.
R $F004 I:B life count
  $F004 Reset the life counter.
E $F004 Falls through to the frame loop.
E $F000 The loop exits only through the game-over path.
i $F008
