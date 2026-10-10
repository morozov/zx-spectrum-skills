#!/usr/bin/env bash
# Fixture for diff_entries.py: does it list every entry a diff touches, and
# mark the deleted ones?
#
# Expected, for the working tree against HEAD:
#
#   game.ctl  $F001 modified (a row comment changed), $F002 deleted together
#             with its `@` label line, $F004 added; $F000 untouched and absent
#   glossary.ref  [Term:workbuf] deleted, [Page:Glossary] modified
#   notes.txt  listed whole
#
# and with --cached, only what was staged: the notes.txt change.
set -uo pipefail

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECK="$SKILL/scripts/diff_entries.py"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cd "$work" || exit 2

git init -q .
git config user.email fixture@example.invalid
git config user.name fixture
git config commit.gpgsign false

cat > game.ctl <<'CTL'
@ $F000 label=player_x
b $F000 Player X
B $F000,1 Player X position
@ $F001 label=player_y
b $F001 Player Y
B $F001,1 Player Y position
@ $F002 label=enemy_x
b $F002 Enemy X
B $F002,1 Enemy X position
c $F003 Return
CTL
cat > glossary.ref <<'REF'
[Page:Glossary]
The game's terms.

[Term:guard:Guard]
A hostile figure that patrols the level.

[Term:workbuf:Work buffer]
The frame's work buffer.
REF
echo one > notes.txt
git add -A && git commit -qm base

cat > game.ctl <<'CTL'
@ $F000 label=player_x
b $F000 Player X
B $F000,1 Player X position
@ $F001 label=player_y
b $F001 Player Y
B $F001,1 Player Y position, in pixels
c $F003 Return
@ $F004 label=lives
g $F004 Lives
B $F004,1 Lives left
CTL
cat > glossary.ref <<'REF'
[Page:Glossary]
The game's own terms.

[Term:guard:Guard]
A hostile figure that patrols the level.
REF
echo two > notes.txt
git add notes.txt

echo '$ diff_entries.py'
"$CHECK"
echo
echo '$ diff_entries.py --cached'
"$CHECK" --cached
