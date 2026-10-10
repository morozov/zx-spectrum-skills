@ $F000 label=player_record
b $F000 Player record
B $F000,1 Player X position
B $F001,1 Player Y position
@ $F002 label=test_state
S $F002,6 Unused
B $F008,8
@ $F010 label=glyph_a
b $F010 Letter A glyph
N $F010 #UDGTABLE { #UDG$F010(glyph_a) } TABLE#
B $F010,8
B $F018,8
@ $F020 label=test_buffer
u $F020 Unused bytes
S $F020,16
@ $F030 label=unused_f030
u $F030 Unused bytes
S $F030,16
c $F040 Return
