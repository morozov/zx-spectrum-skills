#!/usr/bin/env bash
# Fixture for validate_renames.py: does a rename that retires a word fail until
# the registry row that retires it lands, and stay silent once it does?
#
# The repo is built here, in two commits:
#
#   1. `enemy_spark` labels $EC4B, the entry title reads "Enemy spark update",
#      `spr_shot` labels $ED00, and the registry has no row for `enemy`.
#   2. The label becomes `guard_spark`, the title "Guard spark
#      update", and `spr_shot` moves family to `slot_shot`. `test_state`
#      becomes the generated `unused_ee00` under the title "Unused bytes",
#      and the title "Shot speed lookup table" is rewritten as "How fast the
#      shot moves on each level". The registry is unchanged.
#
# Expected:
#
#   against HEAD~1, registry without the row: the label and the title each
#     drop 'enemy' and fail; the split at $F000 moves `menu_text` and its title
#     to $F00C and retypes $F000, which renames nothing, so it is silent; the
#     half-finished retitle at $F100 (its twin at $F200 keeps "Enemy sprites")
#     and the label merged onto `saw_update`, a name that stood at $F400
#     before, each drop 'enemy' and fail; so do the retype plus rename at
#     $F500 and the split plus rename at $F610, since neither old name moved; the family move drops only a declared prefix, the
#     reclassification as unused renames no term, and the rewrite drops three
#     words, so all three are silent; exit 1
#   against HEAD~1, the row added to the working registry: silent, exit 0
#   against HEAD (the default), no .ctl change since: silent, exit 0
set -uo pipefail

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECK="$SKILL/scripts/validate_renames.py"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cd "$work" || exit 2

git init -q .
git config user.email fixture@example.invalid
git config user.name fixture
git config commit.gpgsign false

cat > AGENTS.md <<'AGENTS'
<!-- label-families
spr_ $FA00-$FAFF
slot_ $FC00-$FCFF
-->
AGENTS

cat > glossary.ref <<'REF'
[Term:spelling:One spelling per word]
#TABLE(default)
{ =h Write | =h Not }
{ afterward | afterwards }
TABLE#
REF

cat > game.ctl <<'CTL'
@ $EC4B label=enemy_spark
c $EC4B Enemy spark update
@ $ED00 label=spr_shot
c $ED00 Draw the shot
@ $EE00 label=test_state
b $EE00 Range-test operands
@ $EF00 label=shot_speeds
b $EF00 Shot speed lookup table
@ $F000 label=menu_text
t $F000 Menu lines
@ $F100 label=drone_sprites
b $F100 Enemy sprites
@ $F200 label=crate_sprites
b $F200 Enemy sprites
@ $F300 label=enemy_saw
c $F300 Saw update
@ $F400 label=saw_update
c $F400 Saw helper
@ $F500 label=enemy_ptrs
b $F500 Enemy handler addresses
@ $F600 label=enemy_door
b $F600 Door frames
@ $F610 label=enemy_door_2
CTL
git add -A && git commit -qm one

cat > game.ctl <<'CTL'
@ $EC4B label=guard_spark
c $EC4B Guard spark update
@ $ED00 label=slot_shot
c $ED00 Draw the shot
@ $EE00 label=unused_ee00
u $EE00 Unused bytes
@ $EF00 label=shot_speeds
b $EF00 How fast the shot moves on each level
@ $F000 label=menu_row_addrs
w $F000 Menu-row screen addresses
@ $F00C label=menu_text
t $F00C Menu lines
@ $F100 label=drone_sprites
b $F100 Guard sprites
@ $F200 label=crate_sprites
b $F200 Enemy sprites
@ $F300 label=saw_update
c $F300 Saw update
@ $F500 label=guard_ptrs
w $F500 Guard handler addresses
@ $F600 label=enemy_door
b $F600 Door frames
@ $F610 label=guard_door_2
b $F610 Door frame 2
CTL
git add -A && git commit -qm two

run() {
    echo "\$ validate_renames.py $*"
    "$CHECK" "$@"
    echo "exit $?"
    echo
}

run game.ctl --base HEAD~1 --agents AGENTS.md

cat > glossary.ref <<'REF'
[Term:spelling:One spelling per word]
#TABLE(default)
{ =h Write | =h Not }
{ afterward | afterwards }
{ guard | enemy }
TABLE#
REF

run game.ctl --base HEAD~1 --agents AGENTS.md
run game.ctl --agents AGENTS.md
