# Fixture for validate_ctl_instruction_order.py: a .ctl that has not been through
# ctl_to_hex.py.
#
# A linter whose every pattern requires the `$` of a hex address matches nothing
# in a decimal .ctl and reads it clean whatever it holds. This is
# `comment-line-order.ctl` with the same violations written in decimal.
#
# Expected:
#
#   validate_ctl_instruction_order.py fixtures/decimal-addresses.ctl
#   -> 2 violations: `@ 61456 label=reset_lives` after its length-less comment
#      line, `@ 61472 keep` after its `,3` one. Exit 1.
#
# A finding names the address in hex - $F010 and $F020 here - whichever form the
# .ctl is written in.
@ 61440 label=start
c 61440 Program entry
D 61440 Sets the level up, then runs the frame loop until the last life is lost.
N 61440 Frame loop entry.
R 61440 A Level number
  61440 Save the caller's frame pointer.
  61456 Reset the life counter.
@ 61456 label=reset_lives
  61472,3 Restage the player sprite pointer.
@ 61472 keep
@ 61488 keep
  61488 Player sprite pointer, patched at respawn.
E 61440 The loop exits only through the game-over path.
b 61504 Player sprite bitmap
  B 61504,8,4 Player, frame 0
i 61512
