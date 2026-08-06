# Fixture for the rendered-asset exemption at span granularity: a block a render
# macro covers in part.
#
# The exemption discharges over the bytes a macro reads, not over the block a
# macro appears in. A block drawn whole cannot tell the whole-block form of the
# exemption from the span form, since both discharge every byte of it. This is
# the constructed case where they differ, and
# it must be read the same way by both checks: the drawn spans are declared, the
# rest is asked about.
#
# Expected:
#
#   scripts/validate_ctl_data_structure.py fixtures/partial-render.ctl
#   -> 2 UNTYPED findings, exit 1:
#      `B $F1F0,80`  - 80 bytes with no sublength, outside every macro's extent
#      `b $F340`     - 192 of 256 bytes fall outside every render's extent
#
#   scripts/validate_ctl_array_elements.py fixtures/partial-render.ctl
#   -> 2 findings, exit 1:
#      UNINDEXED at `B $F100,240,10` - 24 records, none annotated
#      UNDECLARED at `b $F340`       - 192 bytes, the part no macro draws
#
# What must NOT be reported, in either check:
#
#   `B $F000,256,8` - 32 records of 8 bytes, every one of them drawn by the
#     #UDGARRAY above it. Indexing them by hand adds nothing a render has not
#     already proved, and demanding it is the "nobody should index 6144 screen
#     pixels to satisfy a linter" false finding wearing a partial block.
#   `b $F240` - the same bank drawn whole, which is the case that already passed.
#
# The two numbers that carry the span form: `B $F1F0,80` is reported while
# `B $F000,256,8` is not, in one block, under one macro; and `b $F340` is
# reported over 192 bytes rather than its full 256, because the macro's 64 are
# discharged.
b $F000 Sprite bank drawn in part, with two undescribed tails
D $F000 The first 32 records are the sprite bitmaps, eight rows each. #UDGARRAY8($F000-$F0F8-8)(sprites_partial)
B $F000,256,8
B $F100,240,10
B $F1F0,80
b $F240 Sprite bank drawn whole
D $F240 #UDGARRAY8($F240-$F338-8)(sprites_whole)
B $F240,256,8
b $F340 Drawn head, undeclared tail
D $F340 The eight glyphs at the head are drawn; nothing states what follows them. #UDGARRAY8($F340-$F378-8)(glyphs_head)
i $F440
