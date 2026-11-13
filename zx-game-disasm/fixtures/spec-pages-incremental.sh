#!/usr/bin/env bash
# Fixture for site/site.mk: does an incremental build follow spec/*.md away?
#
# The behavior pages reach the site through $(SPEC_REF), which joins HTML_REFS
# and the stamp's prerequisites only while spec/*.md has a file. So deleting the
# last one took the ref out of both, nothing else the stamp depends on changed,
# and an incremental build kept the old Spec links and pages. The set of pages
# is a prerequisite of its own, so a page added or removed, the last one
# included, makes the site out of date.
#
# Nothing is built: `make -q` asks whether the site is current, and the skool is
# held old (`-o`), so only the spec set decides.
#
# Expected:
#
#   one page, site built:            up to date
#   the last page deleted:           out of date, and HTML_REFS names no spec.ref
#   the stamp rebuilt:               up to date
#   -> `spec-pages-incremental: OK`, exit 0
set -uo pipefail

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mk=$(command -v gmake || command -v make)

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cd "$work" || exit 2

cat > Makefile <<'MK'
GAME = x
ORG = 0x8000
SIZE = 1
PC = 0x8000
SP = 0xFF00
include $(SITE)/site.mk
show-refs:
	@echo '$(HTML_REFS)'
MK
mkdir -p src spec build/html
touch src/x.ref src/x.ctl spec/index.md build/x.skool

fail=0
q() { "$mk" --no-print-directory -s -q "SITE=$SKILL/site" -o build/x.skool html; }
built() { sleep 1; touch build/spec.ref; sleep 1; touch build/html/.stamp; }
want() { # <what> <0 up to date | 1 out of date>
    q; local s=$?
    if [ "$s" = "$2" ]; then echo "PASS  $1"
    else echo "FAIL  $1: make -q exited $s, wanted $2"; fail=1; fi
}

q; built
want "one page, site built" 0
rm spec/index.md
want "the last page deleted" 1
refs=$("$mk" --no-print-directory -s "SITE=$SKILL/site" show-refs)
case "$refs" in
    *spec.ref*) echo "FAIL  the last page deleted: HTML_REFS still names spec.ref"; fail=1 ;;
    *) echo "PASS  the last page deleted: HTML_REFS names no spec.ref" ;;
esac
built
want "the stamp rebuilt" 0

[ $fail -eq 0 ] || { echo "spec-pages-incremental: FAILED"; exit 1; }
echo "spec-pages-incremental: OK"
