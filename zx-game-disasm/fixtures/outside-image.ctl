# Fixture for validate_ctl_publication.py OUTSIDE.
#
# Reproduces the class: generated
# render-only data (sprite masks a build script produced) declared as blocks
# outside the program image, which skool2html publishes as pages and memory-map
# rows for RAM the program never occupies - here $1000, which is ROM on real
# hardware.
#
# Expected, with the image this fixture describes ($4000, 256 bytes):
#
#   validate_ctl_publication.py fixtures/outside-image.ctl --org 0x4000 --size 256
#   -> 2 OUTSIDE findings (`b $1000`, `b $1020`), exit 1
#
# The two in-image entries and the terminator must not be reported: `i` publishes
# no page, and the terminator sits at ORG+SIZE by construction.
b $1000 Generated mask for the player sprite
  $1000 Produced by build_masks.py, not present in the program image.
B $1000,32,8
b $1020 Generated mask for the enemy sprite
B $1020,32,8
c $4000 Program entry
b $4080 Player sprite bitmap
B $4080,128,8
i $4100
