@ $EC00 label=slot_spark_1
b $EC00 Guard sprite slots
B $EC00,32,8
@ $EC20 label=spr_spark_2
b $EC20 Guard sprites
B $EC20,32,8
@ $EC40 label=spark_frame
B $EC40,32,8
@ $F000 label=spr_guard_1
b $F000 Guard sprite source
B $F000,32,8
@ $F200 label=slot_x
B $F200,32,8
@ $9000 label=spr_stray
c $9000 Stray routine
@ $F400 label=tune_title
b $F400 Title tune
B $F400,32,8
@ $F420 label=tune_sprite_chime
b $F420 Sprite-collision chime
B $F420,32,8
