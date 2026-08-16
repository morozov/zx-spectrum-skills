; Every kind lint-label-namespace reports, plus the case it must not report.
;
; $F010  SUBSUMED        a narrated behavior wearing move_player's prefix
; $F020  MISPARENTED     inside $F010, but prefixed with the outer move_player
; $F030  PRIVATE_HELPER  its own entry, reached only from move_player's
; $F040  clean           its own entry too, but called from two — a real sibling
; $F024  clean           a branch position under $F020: no narrative, no claim
; $F068  UNREACHED       prefixed on a catch that sits after it and is fallen into
@ $F000 label=move_player
c $F000 Move the player
@ $F010 label=move_player_run
N $F010 The running model, which a reader looks up as a unit.
@ $F020 label=move_player_down
@ $F024 label=move_player_down_apply
@ $F030 label=move_player_slide
c $F030 Move the player with momentum
@ $F040 label=move_player_fast
c $F040 Move the player one fast step
@ $F050 label=poll_input
c $F050 Poll the input
@ $F060 label=open_door
c $F060 Open the door
@ $F068 label=open_door_unlock_key1
@ $F06C label=open_door_unlock
