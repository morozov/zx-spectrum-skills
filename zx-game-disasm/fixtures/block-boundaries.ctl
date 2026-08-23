c $F000 A routine whose fragment must not swallow what follows it
@ $F000 label=first_routine
  $F000,3 Do something.
u $F003 Unused.
@ $F003 label=dead_bytes
c $F004 The block that owns the directives at its own address
@ $F004 isub=LD HL,LIMIT
@ $F004 label=second_routine
  $F004,3 Do something else.
D $F004 A description whose paragraph continues below.
. $79 ("G") - a bonus code, not an address.
c $F007 The last block
@ $F007 label=third_routine
  $F007,1 Return.
