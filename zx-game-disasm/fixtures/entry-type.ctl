# Fixture for validate_ctl_publication.py MIXED and MUTABLE.
#
# Reproduces the two ways an entry ends up published as something it is not,
# each in its usual shape:
#
#   - a `t` entry that ran to the next entry and swallowed a runtime counter, so
#     the counter published on a page headed "Text: GAME OVER";
#   - `b` entries over bytes the program writes as it runs, published as data the
#     program was loaded with.
#
# The stores live in `fixtures/entry-type.skool`, which stands in for the .skool
# the build generates. Expected, with the image this fixture describes ($4000,
# 512 bytes):
#
#   validate_ctl_publication.py fixtures/entry-type.ctl \
#       --org 0x4000 --size 512 --skool fixtures/entry-type.skool
#   -> 1 MIXED finding at `t $4132`, and 2 MUTABLE findings, at `b $4110`
#      (2 of 2 bytes written) and `b $4112` (2 of 32), exit 1
#
# Both MUTABLE remedies lead with the retype. The count is the evidence, not a
# verdict on the bytes no store names, so `b $4112` is offered the split as the
# alternative rather than told to take it.
#
# Four controls must not be reported:
#
#   `b $4100` is a bitmap and nothing stores to it. The `DEFM` at $4132 spells
#     `LD ($4100),A` inside a string, which is a data operand and not a store.
#   `g $4142` is written and is already typed `g`.
#   `g $4143` is written only through HL, so no instruction names it. That is why
#     the converse - a `g` entry nothing writes - is not a check: on this evidence
#     it would report a status buffer the game clears every level.
#   `t $4132` is also stored into, at $4141. MUTABLE does not test `t`, so the
#     entry is reported once, as MIXED, and the fix is the split either way.
c $4000 Program entry
b $4100 Player sprite bitmap
B $4100,16,8
b $4110 Level number and lives
@ $4110 label=level
B $4110,1 Current level number.
@ $4111 label=lives
B $4111,1 Lives remaining.
b $4112 Enemy step table
B $4112,30,10
@ $4130 label=step_cursor
W $4130,2 Cursor into the table above, saved across the scan.
t $4132 Text: GAME OVER
T $4132,15
@ $4141 label=idle_ticks
B $4141,1 Frames the player has stood still.
@ $4142 label=door_open_flag
g $4142 Door-open flag
B $4142,1 Non-zero while the exit door is open.
@ $4143 label=door_map
g $4143 Door state map
B $4143,32,8
w $4163 Level pointer table
i $4200
