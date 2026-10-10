# The data-structure checks, each over a bad block, a padded block and a good one.
#
# ROW_WIDTH reports one-byte rows that are no record of their own:
#   $F000  a sublength-1 span with no record (bad)
#   $F010  a run of one-byte rows, three of them commented (bad)
#   $F0C0  a run with every row commented (padding: a comment is no record)
#   $F058  one-byte fields the code at $F0D0 reads by address (good)
#   $F0C4  a table whose description says it is indexed one byte per type (good)
#   $F0B0, $F0B8  one-byte rows a render draws (good)
# STRIDE_APPEASE lists a narrow sublength over a render or a bitmap family, and
# never gates:
#   $F020  over a render (listed)
#   $F028  over a render, with a record length stated in prose (padding: listed)
#   $F090  inside the slot_ range, a family whose range holds a copy of a render
#          (listed)
b $F000 Attribute ramp
B $F000,16,1 Rising attribute ramp
b $F010 Loose bytes
B $F010,1
B $F011,1
B $F012,1
B $F013,1
B $F014,1 Enemy speed
B $F015,1 Shot speed
B $F016,1 Lives
B $F017,1
B $F018,8,8 Padding row
b $F020 Letter glyph
N $F020 #UDGTABLE { #UDG$F020(glyph) } TABLE#
B $F020,8,2
b $F028 Pair glyph
D $F028 Four 2-byte records, one per frame.
N $F028 #UDGTABLE { #UDG$F028(pair) } TABLE#
B $F028,8,2
b $F030 Scores
B $F030,40,8 Score rows
b $F058 Player state
B $F058,1 Player X
B $F059,1 Player Y
B $F05A,1
B $F05B,1 Shot speed
B $F05C,4,4 Player colors
b $F060 Source glyphs
N $F060 #UDGTABLE { #UDG$F060(src1) } { #UDG$F068(src2) } TABLE#
B $F060,16,8 The two glyphs
b $F070 Copied glyphs
D $F070 The two glyphs, copied from #R$F060.
B $F070,16
b $F080 Bad copy
D $F080 The two glyphs, copied from #R$F060.
B $F080,16
b $F090 Copy slot
D $F090 The letter glyph's slot, copied from #R$F020.
B $F090,16,2
b $F0A0 Mystery
b $F0B0 Rendered glyph
N $F0B0 #UDGTABLE { #UDG$F0B0(rows) } TABLE#
B $F0B0,8,1
b $F0B8 Rendered glyph, one directive per byte
N $F0B8 #UDGTABLE { #UDG$F0B8(rows2) } TABLE#
B $F0B8,1
B $F0B9,1
B $F0BA,1
B $F0BB,1
B $F0BC,1
B $F0BD,1
B $F0BE,1
B $F0BF,1
b $F0C0 Padded bytes
B $F0C0,1 First byte
B $F0C1,1 Second byte
B $F0C2,1 Third byte
B $F0C3,1 Fourth byte
b $F0C4 Object speeds
D $F0C4 One movement speed per object type, indexed by object type.
B $F0C4,12,1
c $F0D0 Read the player state
t $F0E0 Row addresses typed as text
T $F0E0,8,2 One address per row
t $F0E8 Player tags
T $F0E8,6,2 Two characters per player
