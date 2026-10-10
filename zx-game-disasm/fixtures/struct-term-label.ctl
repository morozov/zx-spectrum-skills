@ $EC4B label=enemy_spark
c $EC4B Update the spark
@ $EC80 label=guard_spark
c $EC80 Draw the spark
@ $ECC0 label=guard_post
b $ECC0 Enemy-post table
B $ECC0,16,8
@ $ECD0 label=post_table
b $ECD0 Guard post table
B $ECD0,16,8
@ $ECE0 label=update_saw_bot
c $ECE0 Saw-bot behavior handler
@ $ED00 label=drone_spin
c $ED00 Spin the drone
