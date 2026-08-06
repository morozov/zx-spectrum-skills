# Fixture for validate_ctl_array_elements.py UNINDEXED: one line comment stating
# a wide length, standing in for every record under it.
#
# Covers a bypass on the check's own remediation path. The finding tells the
# author to annotate each record; if a single `  $F000,120` comment counted as
# annotating all thirty, the cheapest way to clear the finding would be to
# defeat the check. What SkoolKit renders from that comment is one braced comment
# opening on the first `DEFB` row and closing on the last, naming no record at
# all - the shape the check exists to catch.
#
# Expected:
#
#   validate_ctl_array_elements.py fixtures/wide-comment-array.ctl
#   -> 1 UNINDEXED finding at `B $F000,120,4`: 30 records, 29 of them
#      unannotated - the comment names the one record at its own address. Exit 1.
#
# Four controls must not be reported:
#
#   `B $F100,120,4` is the fix the finding asks for - one comment per record, and
#     each names its own record.
#   `B $F300,48,4` is that same fix indented four spaces. SkoolKit renders a
#     two-, four- or six-space line comment identically, so the check must read
#     them identically too.
#   `B $F078,8` is not an array: no stride, and eight bytes is under `--min-span`.
#   `B $F200,64,1` has a one-byte stride: a scalar has no record layout to state.
b $F000 Enemy table
D $F000 30 enemy records, 4 bytes each: type, x, y, flags.
B $F000,120,4
  $F000,120 The thirty enemy records.
B $F078,8 Trailer
b $F100 Enemy table, annotated
D $F100 30 enemy records, 4 bytes each: type, x, y, flags.
B $F100,120,4
  $F100 Enemy 1
  $F104 Enemy 2
  $F108 Enemy 3
  $F10C Enemy 4
  $F110 Enemy 5
  $F114 Enemy 6
  $F118 Enemy 7
  $F11C Enemy 8
  $F120 Enemy 9
  $F124 Enemy 10
  $F128 Enemy 11
  $F12C Enemy 12
  $F130 Enemy 13
  $F134 Enemy 14
  $F138 Enemy 15
  $F13C Enemy 16
  $F140 Enemy 17
  $F144 Enemy 18
  $F148 Enemy 19
  $F14C Enemy 20
  $F150 Enemy 21
  $F154 Enemy 22
  $F158 Enemy 23
  $F15C Enemy 24
  $F160 Enemy 25
  $F164 Enemy 26
  $F168 Enemy 27
  $F16C Enemy 28
  $F170 Enemy 29
  $F174 Enemy 30
b $F200 Per-type starting speed
D $F200 Indexed by object type.
B $F200,64,1
b $F300 Wave script, annotated at a four-space indent
D $F300 12 wave records, 4 bytes each: delay, count, type, flags.
B $F300,48,4
    $F300 Wave 1
    $F304 Wave 2
    $F308 Wave 3
    $F30C Wave 4
    $F310 Wave 5
    $F314 Wave 6
    $F318 Wave 7
    $F31C Wave 8
    $F320 Wave 9
    $F324 Wave 10
    $F328 Wave 11
    $F32C Wave 12
i $F330
