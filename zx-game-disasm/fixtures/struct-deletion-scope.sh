#!/usr/bin/env bash
# Fixture for validate_deletion_scope.py: does a staged diff that removes more
# than three items fail until the review record for that exact diff names each
# of them in its scope?
#
# Expected:
#
#   one labeled entry removed (2 items): under the threshold, exit 0
#   two labeled entries and a glossary term removed (5 items), no record:
#     all five named as out of scope, exit 1
#   the same, with a record whose scope names one entry and the term:
#     the other entry's label and directive named, exit 1
#   the same, with a record whose scope names everything: exit 0
#   five labels renamed in place: nothing removed, exit 0
set -uo pipefail

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECK="$SKILL/scripts/validate_deletion_scope.py"
RECORD="$SKILL/scripts/review_record.py"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cd "$work" || exit 2

git init -q .
git config user.email fixture@example.invalid
git config user.name fixture
git config commit.gpgsign false
printf 'build/\n' > .gitignore

cat > glossary.ref <<'REF'
[Term:guard:Guard]
A hostile figure that patrols the level.

[Term:workbuf:Work buffer]
The frame's work buffer.
REF

write_ctl() {
    : > game.ctl
    for entry in "$@"; do
        address=${entry%%:*}
        label=${entry#*:}
        printf '@ $%s label=%s\nb $%s %s\nB $%s,1 One byte\n' \
            "$address" "$label" "$address" "$label" "$address" >> game.ctl
    done
}

write_ctl F000:player_x F001:player_y F002:enemy_x F003:enemy_y F004:lives
git add -A && git commit -qm base

run() {
    echo "\$ validate_deletion_scope.py  # $1"
    "$CHECK" | sed -E 's/[0-9a-f]{64}/<diffhash>/g'
    echo "exit ${PIPESTATUS[0]}"
    echo
}

record() {
    mkdir -p build/review
    hash=$("$RECORD" hash --cached)
    printf '{"diffhash": "%s", "verdict": "COMMIT", "reviewer": "fixture", "rules": [], "scope": %s}\n' \
        "$hash" "$1" > "build/review/$hash.json"
}

write_ctl F000:player_x F001:player_y F002:enemy_x F003:enemy_y
git add -A
run 'one labeled entry removed'

write_ctl F000:player_x F001:player_y F002:enemy_x
cat > glossary.ref <<'REF'
[Term:guard:Guard]
A hostile figure that patrols the level.
REF
git add -A
run 'two labeled entries and a term removed, no record'

record '["b $F004 lives", "[Term:workbuf]"]'
run 'record names one entry and the term'

record '["b $F004 lives", "enemy_y at $F003", "[Term:workbuf]"]'
run 'record names everything'

git reset -q --hard
rm -rf build
write_ctl F000:player_a_x F001:player_a_y F002:enemy_a_x F003:enemy_a_y F004:lives_left
git add -A
run 'five labels renamed in place'
