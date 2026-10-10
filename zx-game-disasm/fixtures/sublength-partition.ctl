# Fixture for the sublength-partition rule shared by validate_ctl_data_structure.py
# DIVISIBILITY and validate_ctl_array_elements.py UNINDEXED.
#
# SkoolKit repeats a sublength list until it covers the span, so a list is a
# record size only when it repeats. A list of two or more sizes that sums to the
# span's whole length is laid out once: it marks statement boundaries. The shape
# this protects is a mostly-zero buffer holding stray bytes from the capture, cut
# into `DEFB` islands and `DEFS` runs so the listing does not print a row per
# eight zeros.
#
# Expected:
#
#   validate_ctl_data_structure.py fixtures/sublength-partition.ctl
#   -> 1 DIVISIBILITY finding, at `B $F0C0,10,4` (2 left over). Exit 1.
#
#   validate_ctl_array_elements.py fixtures/sublength-partition.ctl
#   -> 1 UNINDEXED finding, at `B $F200,480,2,22`: a two-size list that repeats
#      is a 24-byte record, twenty of them, none annotated. Exit 1. The same
#      span raises no DIVISIBILITY: 480 is a whole number of 24-byte records,
#      whatever 480 % 22 is.
#
# Controls that must not be reported:
#
#   `S $F000,128,2,30,2,94` sums to its length: two islands and two zero runs.
#   `B $F080,64,16,48` sums to its length too, under `B`.
s $F000 Canvas with stray bytes
S $F000,128,2,30,2,94 Leftover bytes the capture caught.
b $F080 Split table
B $F080,64,16,48 Header, then body.
b $F0C0 Ragged table
B $F0C0,10,4 Records.
b $F0CA Pad
B $F0CA,310,310 Filler.
b $F200 Repeating pair
D $F200 Twenty 24-byte records.
B $F200,480,2,22
