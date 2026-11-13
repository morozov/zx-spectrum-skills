; A label prefix across a dispatch table: the table's path into a routine
; counts as a way in, though the routine also has a code predecessor.
;
; $8004  UNREACHED  the dispatcher enters helper ($9000) through the table, and
;                   helper jumps to $8004 without passing through $8001
@ $8000 label=routine
c $8000 A routine that hands off to a helper
@ $8001 label=routine_stage
@ $8004 label=routine_stage_done
@ $9000 label=helper
c $9000 A helper the dispatcher also enters
@ $A000 label=dispatch_table
b $A000 The dispatch table
