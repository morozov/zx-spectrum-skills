#!/usr/bin/env bash
# Assert what the review machinery reports on its fixtures: the review record,
# the commit hook and the HTML layout check.
#
# Same contract as check-findings.sh: each case's whole output, exit status
# included, is diffed against fixtures/<name>.expected, and `--record`
# regenerates them.
#
# Usage:  fixtures/review-checks.sh [--record]

set -u
# The cases build their own repos; nothing from a calling gate may steer them.
unset REVIEW_RECORD_DIR
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 2
SKILL=$PWD
record=0
[ "${1-}" = '--record' ] && record=1
failed=0
ran=0
WORK=$(mktemp -d "${TMPDIR:-/tmp}/review-checks.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

run() {
    local name=$1
    shift
    local actual s
    actual=$("$@" 2>&1) && s=0 || s=$?
    actual=$(printf '%s\nexit=%s\n' "$actual" "$s" | sed -e "s|$WORK|<work>|g" -e "s|$SKILL/||g")
    local expected="fixtures/$name.expected"
    ran=$((ran + 1))
    if [ "$record" = 1 ]; then
        printf '%s\n' "$actual" > "$expected"
        echo "recorded  $name"
        return
    fi
    if [ ! -f "$expected" ]; then
        echo "MISSING   $name – no $expected; record it and review the diff"
        failed=$((failed + 1))
        return
    fi
    if ! diff -u "$expected" <(printf '%s\n' "$actual") > "$WORK/diff"; then
        echo "FAIL      $name"
        sed 's/^/    /' "$WORK/diff"
        failed=$((failed + 1))
    else
        echo "ok        $name"
    fi
}

# A throwaway repo whose HEAD holds the corrected text and whose working tree
# holds the bad text.
repo() {
    local d="$WORK/$1"
    mkdir -p "$d" && cd "$d" || exit 2
    git init -q . && printf 'build/\n' > .gitignore
    cp "$SKILL/fixtures/review-base.ref" glossary.ref
    git add . && git -c user.email=f@x -c user.name=f -c commit.gpgsign=false commit -qm base
    cp "$SKILL/fixtures/review-callouts.ref" glossary.ref
    cd "$SKILL" || exit 2
}

in_repo() { (cd "$WORK/$1" && shift && "$@"); }

RR="$SKILL/scripts/review_record.py"
export REVIEW_RULES_MD="$SKILL/fixtures/review-record-rules.md"

# --- The review record and the pre-commit hook --------------------------------
record_flow() {
    "$RR" status
    mkdir -p build
    echo '[{"id": "AUD-3", "result": "fail", "quote": "is not a counter", "location": "glossary.ref:5"}]' > build/rules-fail.json
    echo '[{"id": "AUD-3", "result": "pass"}, {"id": "DEF-4", "result": "pass"}]' > build/rules-pass.json
    echo '[{"id": "AUD-3", "result": "pass"}]' > build/rules-partial.json
    "$RR" write --verdict COMMIT --reviewer fixture --rules build/rules-partial.json
    "$RR" write --verdict COMMIT --reviewer fixture --rules build/rules-fail.json
    "$RR" write --verdict REJECT --reviewer fixture --rules build/rules-fail.json
    "$RR" status
    "$RR" write --verdict COMMIT --reviewer fixture --rules build/rules-pass.json
    "$RR" status
    git add glossary.ref
    "$SKILL/tools/hooks/pre-commit" && echo "hook: commit allowed"
    echo 'one more line' >> glossary.ref
    "$RR" status
    git add glossary.ref
    "$SKILL/tools/hooks/pre-commit" || echo "hook: commit refused"
    echo 'a { color: red }' > site.css
    "$RR" write --verdict COMMIT --reviewer fixture --rules build/rules-pass.json
    "$RR" verdict --checks PASS --rules-file "$SKILL/fixtures/review-rules.md"
}
repo record
run review-record in_repo record record_flow

# --- The HTML layout check -----------------------------------------------------
run review-html-layout scripts/check_html_layout.py --fixture \
    fixtures/review-layout-bad.html fixtures/review-layout-good.html

if [ "$record" = 1 ]; then
    echo "review-checks: recorded $ran expectation(s) – review the diff before committing"
    exit 0
fi
if [ "$failed" -gt 0 ]; then
    echo "review-checks: FAIL, $failed of $ran fixture(s) report something other than their expectation."
    exit 1
fi
echo "review-checks: $ran fixture(s), every review check reports what its fixture says it must."
