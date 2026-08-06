# Fixture for validate_ctl_publication.py CONTRADICTED (and MUTABLE over `u`).
#
# Reproduces the class: an entry whose prose says nothing writes these bytes,
# over addresses the code stores to.
#
#   @ $6B3C label=unused_6b3c
#   b $6B3C Undetermined - no reader or writer found in the image
#
# The stores live in `fixtures/contradicted-claim.skool`, which stands in for the
# .skool the build generates. Expected, with the image this fixture describes
# ($4000, 256 bytes):
#
#   validate_ctl_publication.py fixtures/contradicted-claim.ctl \
#       --org 0x4000 --size 256 --skool fixtures/contradicted-claim.skool
#   -> 3 CONTRADICTED findings, at `b $4002` (its title and its label), at
#      `u $4012` (its title) and at `$406A` (the `N` inside `g $4062`);
#      3 MUTABLE findings, at `b $4002`, `u $4012` and `u $4082`, exit 1
#
# The letter and the sentence are separate findings on the same bytes: MUTABLE
# reports that a written entry is typed `b` or `u`, CONTRADICTED reports the
# claim, and $4002 and $4012 carry both. `u $4082` carries only the letter — no
# sentence of its denies a writer — which is why it is here.
#
# Six controls must not be reported:
#
#   `g $4022` is labeled `orphan_list_head` and stored into. On a `g` entry the
#     letter already says the program writes these bytes, so a one-word
#     characterization in the title or the label is a name, not a denial, and the
#     store that would convict it is the store the letter promised.
#   `g $4032` denies a writer and names it: `#R$40C2` is the entry the store
#     lives in, so the sentence states the fact rather than contradicting it.
#   `g $4042` says "unused" inside a paragraph, about five of its own fields.
#     Read there, the word is about whatever the paragraph discusses.
#   `g $4052` carries the denial on `N $405A`, which speaks for $405A..$4061.
#     The store is at $4052, outside those bytes, so nothing is contradicted.
#   `g $4072` names its writer by label rather than by address — `init_levels` is
#     what the listing prints — and a writer the prose names is not one it denies.
#   `u $4092` says "Unused" over bytes no instruction stores to, and `c $40A2`
#     denies a writer for a table living somewhere else, which is what a routine's
#     description is about.
@ $4002 label=unused_4002
b $4002 Undetermined - no reader or writer found in the image
B $4002,16
@ $4012 label=tail_pad
u $4012 Unused tail of the state block
B $4012,16
@ $4022 label=orphan_list_head
g $4022 Head of the orphaned-object list
B $4022,16
@ $4032 label=level_clear_slot
g $4032 Level-setup work buffer
D $4032 Nothing in the image writes this byte individually; the only writer is the level-setup clear (#R$40C2), which zeroes the whole block.
B $4032,16
@ $4042 label=object_record
g $4042 Slot-2 object record
D $4042 Fields: +$00 is the direction. +$02 to +$06 are unused by the handlers. +$07 is the patrol timer.
B $4042,16
@ $4052 label=back_buffer
g $4052 Back buffer
B $4052,8 Cells the front end repaints.
N $405A Unused tail of the back-buffer page; nothing writes these bytes.
B $405A,8
@ $4062 label=wave_state
g $4062 Wave state
B $4062,8 The script cursor and its per-level counters.
N $406A Nothing writes the spare tail of the block.
B $406A,8
@ $4072 label=level_table
g $4072 Level table
D $4072 Nothing writes these bytes once the game is running; `init_levels` fills them at boot.
B $4072,16
@ $4082 label=data_4082
u $4082 Undetermined block - no reader found in the image
B $4082,16
@ $4092 label=quiet_pad
u $4092 Unused pad the loader left behind
B $4092,16
@ $40A2 label=enable_gate
c $40A2 Enable gate
D $40A2 The pitch table below it is never written; the gate byte is patched in place.
@ $40C2 label=init_levels
c $40C2 Level setup
i $4100
