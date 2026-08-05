# Fixture for validate_ctl_publication.py FRAGMENTED.
#
# Reproduces the class: one structure cut into pages. A loading screen
# published as one entry per screen address the front-end writes to gives as
# many pages and memory-map rows as it has entries, none of them a structure,
# and no page anywhere says "this is the loading screen". The fixture is the
# regression case: six rows of one screen, then three attribute runs that share
# a head.
#
# Expected, with the image this fixture describes ($4000, 6912 bytes):
#
#   validate_ctl_publication.py fixtures/fragmented-structure.ctl \
#       --org 0x4000 --size 6912
#   -> 2 FRAGMENTED findings, at `b $4000` (6 entries) and `b $4800`
#      (3 entries), exit 1
#
# The $4800 run is the shape the check has to catch and the earlier one does not
# prove: the titles are not identical, they share a head and each adds a note
# about its own start cell. Comparing whole titles calls those three distinct.
#
# Everything from $4700 down is the control and must not be reported: three
# tables that each carry a sub-directive and a distinct title; three `g`
# variables, three `t` messages and three `s` spaces, for which a
# sub-directive-free run is the normal form rather than a structure cut up.
b $4000 Loading screen row 0
b $4100 Loading screen row 1
b $4200 Loading screen row 2
b $4300 Loading screen row 3
b $4400 Loading screen row 4
b $4500 Loading screen row 5
c $4600 Program entry
b $4700 Bounce angle table
B $4700,32,8
b $4720 Per-level enemy scripts
B $4720,32,8
b $4740 Tile attribute byte per tile code
B $4740,32,8
b $4800 Loading-screen attributes; start cell reused for the score readout
b $4830 Loading-screen attributes; start cell reused for the high-score heading
b $4840 Loading-screen attributes; start cell reused for the options line
g $4900 Player 1 score
g $4903 Player 2 score
g $4906 Player 3 score
t $4910 Level 1 name
t $4920 Level 2 name
t $4930 Level 3 name
s $4940 Unused space
s $4950 Unused space
s $4960 Unused space
i $5B00
