# Shared SkoolKit-disassembly build framework for the zx-game-disasm skill.
#
# A game Makefile sets GAME, ORG, SIZE, PC, SP (and optionally RELOC_FLOOR), then
# `include`s this file. All build rules live here, so a project's Makefile stays a
# few lines and a fix to the framework reaches every game without re-copying. This
# mirrors how SkoolKit's own disassemblies include `$(SKOOLKIT_HOME)/tools/
# disassembly.mk`. Do NOT copy this into a project — reference it in place.
#
# Targets:
#   make          The gate: round-trip cmp + .ctl linters + HTML build (validates
#                 the .ref catalogs). Build the asm, snapshot, and site.
#   make gate     The same gate, logged, ending in one verdict line that names
#                 the SkoolKit and the gate it ran under, says whether anything
#                 rebuilt, and on a red run says how many checks failed and with
#                 how many findings each
#   make coverage The "is it done?" gauge (documentation/naming/relocatability)
#   make lint-identity        Gate: every entry titled, every sub-block named
#   make lint-data-structure  Gate: every data entry tiles and declares its stride
#   make lint-publication     Gate: every page inside the image, one page per thing,
#                             each entry the type its bytes are
#   make lint-names           Gate: prose names a labeled slot by its label
#   make lint-label-namespace Gate: a label's prefix names something containing it
#   make test-checks          Gate: each .ctl check still reports what its fixture says
#   make lint-byte-counts     Gate: no instruction comment recites a byte count
#   make lint-array-elements  Gate: every array record annotated individually
#   make lint-images          Gate: every image macro put an image under html/
#   make lint-baseline        Re-record the gating checks' findings as the baseline
#                             (it can only shrink the file; it fails on growth) and
#                             stamp the gate it was recorded under into its header
#   make verify-frag FRAG=…  Round-trip one Worker fragment in isolation
#   make tap      A loadable .tap of the fixed build — the disassembly as a
#                 playable rebuild, not only a byte-check
#   make clean    Remove all generated files
#
# The default `make` builds everything — the disassembly, the verified round-trip,
# and the HTML site — so one command produces the whole deliverable. HTML degrades
# gracefully: with no `.ref` files yet it is a basic site from the skool alone, and
# it gains the catalog/reference pages as the `.ref` files appear. `make` is
# incremental — run it while iterating; avoid `make clean && make`.
#
# The build refuses to start when any of its tools is missing from PATH, whether
# or not the tree is up to date — see "The toolchain" below.

# Locate the skill's scripts relative to this file: .../tools/disassembly.mk lives
# beside .../scripts, so the project never has to point at them.
SCRIPTS := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../scripts)
FIXTURES := $(abspath $(SCRIPTS)/../fixtures)

# --- The toolchain -----------------------------------------------------------
#
# The build runs its tools from PATH.
TAP2SNA    := tap2sna.py
SNA2SKOOL  := sna2skool.py
SKOOL2ASM  := skool2asm.py
SKOOL2HTML := skool2html.py
BIN2SNA    := bin2sna.py
BIN2TAP    := bin2tap.py
PASMO      := pasmo

# The executables each stage of the build shells out to.
TOOLS_SNAPSHOT := tap2sna.py
TOOLS_SKOOL    := $(TOOLS_SNAPSHOT) sna2skool.py
TOOLS_ASM      := $(TOOLS_SKOOL) skool2asm.py
TOOLS_BIN      := $(TOOLS_ASM) pasmo

# What each goal can reach, so a goal is held to the tools it actually invokes.
# `coverage` and the .ctl linters run on SkoolKit alone and build on a machine
# with no assembler at all; `bin2tap.py` belongs to `tap` and to nothing else.
TOOLS_all                 := $(TOOLS_BIN) bin2sna.py skool2html.py
TOOLS_test                := $(TOOLS_BIN)
TOOLS_tap                 := $(TOOLS_BIN) bin2tap.py
TOOLS_verify-frag         := $(TOOLS_BIN)
TOOLS_html                := $(TOOLS_SKOOL) skool2html.py
TOOLS_coverage            := $(TOOLS_SKOOL)
TOOLS_lint-comments       := $(TOOLS_SKOOL)
TOOLS_test-checks         := $(TOOLS_SKOOL)
TOOLS_lint                := $(TOOLS_SKOOL)
TOOLS_lint-data-structure := $(TOOLS_SNAPSHOT)
TOOLS_lint-publication    := $(TOOLS_SKOOL)
TOOLS_lint-label-namespace := $(TOOLS_SKOOL)
TOOLS_lint-images         := $(TOOLS_html)
TOOLS_lint-baseline       := $(TOOLS_html)

# Goals that shell out to no tool at all: `clean` deletes, the .ctl-only linters
# read one text file, and `gate` re-enters make for the build — the sub-make is
# preflighted and the gate turns its failure into the verdict line. A goal named
# neither here nor above — a file target, or one a project added — is held to the
# default build's set. `lint-publication` is not among them: it reads the
# generated .skool for the addresses the code stores to, so it can need the
# disassembler to produce one.
TOOLS_FREE_GOALS := clean gate lint-address-order lint-instruction-order \
                    lint-lengths lint-label-length lint-identity \
                    lint-names lint-byte-counts lint-array-elements

# Preflight. An absent toolchain is not a state in which "every target is up to
# date" carries any meaning: with nothing installed and nothing stale, make runs
# no recipe, invokes no missing tool, and exits 0 — and that 0 reads as
# proof of a round-trip that never ran. So the check happens while the makefile is
# read: before make compares a single timestamp, and out of reach of whatever `-j`
# does to recipe order.
TOOLCHAIN_GOALS := $(if $(MAKECMDGOALS),$(MAKECMDGOALS),all)
REQUIRED_TOOLS := $(sort $(foreach g,$(filter-out $(TOOLS_FREE_GOALS),$(TOOLCHAIN_GOALS)),\
    $(if $(TOOLS_$(g)),$(TOOLS_$(g)),$(TOOLS_all))))
ifneq ($(REQUIRED_TOOLS),)
MISSING_TOOLS := $(strip $(foreach t,$(REQUIRED_TOOLS),\
    $(if $(shell command -v '$(t)' 2>/dev/null),,$(t))))
ifneq ($(MISSING_TOOLS),)
$(error toolchain incomplete — not executable on PATH: $(MISSING_TOOLS). \
The SkoolKit tools come from the packages in requirements.txt)
endif
endif

# Game floor: a raw operand at/above this address is the game's own and must be a
# label (below is ROM/screen, fixed). Per-game; override in the game Makefile.
RELOC_FLOOR ?= 0x5B00

# Source files (hand-edited)
CTL = $(GAME).ctl
T2S = $(GAME).t2s
INI = skoolkit.ini
REF = $(GAME).ref

# Further .ctl files the disassembly is built from, if the project generates any
# (a build script's sprite masks, say). Set it in the game Makefile as a plain
# list of paths. They reach sna2skool as extra `--ctl` arguments and are held to
# the same publication rules as the main one: a page is a page whichever file
# declared it.
CTL_EXTRA ?=

# Generated files
SKOOL         = $(GAME).skool
Z80_PRISTINE  = $(GAME).pristine.z80
Z80_FIXED     = $(GAME).fixed.z80
BIN_PRISTINE  = $(GAME).pristine.bin
BIN_NON_FIXED = $(GAME).non-fixed.bin
BIN_FIXED     = $(GAME).fixed.bin
ASM_NON_FIXED = $(GAME).non-fixed.asm
ASM_FIXED     = $(GAME).asm

.PHONY: all gate tap clean verify-frag test test-checks lint lint-address-order lint-instruction-order lint-lengths lint-label-length lint-label-namespace lint-identity lint-data-structure lint-publication lint-names lint-byte-counts lint-images lint-baseline lint-array-elements lint-comments coverage html

# A recipe that redirects into its own target has already created that target by
# the time it fails: `sna2skool.py … > $(SKOOL)` that dies mid-write leaves a
# truncated .skool newer than the .ctl, which make then calls current and every
# downstream target agrees with. Delete the target instead, so the next make
# rebuilds it and a failure cannot be laundered into an up-to-date tree. Every
# failing target that must survive here is phony, and `lint-baseline` writes
# $(BASELINE), not $@.
.DELETE_ON_ERROR:

# Findings a project has accepted as its starting point, one per line. The gating
# checks below hold this line: a finding it does not list fails the build, and a
# line it lists that the check no longer reports fails the build too, so a fix
# takes its baseline entry with it. See `scripts/ctl_baseline.py`.
BASELINE ?= lint-baseline.txt

# `make` (the default) is the one verification gate: it drives the round-trip cmp,
# the .ctl linters, and the HTML build (the only step that validates the .ref
# catalogs). It is not slow, so there is no separate "verify" — use `make`.
# `lint-images` is listed after `html` because it reads what the build produced:
# it is the one check whose subject is a directory of files rather than a text
# file. Its own prerequisite is html/.stamp, so the order holds under `-j` too.
all: $(ASM_FIXED) $(Z80_FIXED) test test-checks lint html lint-images

# The same gate, with a result that cannot be misread. Under `-j` the HTML branch
# can print `touch html/.stamp` while the asm branch is failing, so the tail of a
# parallel build shows a success line for a red build; and a piped `make | tail`
# hands the reader the pipeline's status, not make's. This runs the gate into a
# log and ends with one verdict line, then exits with make's own status. Judge a
# build by that status — never by what the output looks like.
GATE_LOG = build/make.log

# The generated files the gate would rebuild. `all` also depends on the phony
# `test`, `lint` and `html`, whose recipes run on every invocation, so asking make
# whether `all` is current always answers "no". Asking about these answers the
# question the verdict has to distinguish: did this build regenerate anything, or
# did it find every file current and only re-run the phony checks over them?
#
# That is the whole of what `-q` knows — one bit, over the set as a whole. It does
# not say which of them rebuilt, so REBUILT claims no more than "at least one",
# and the log is where a reader finds out which. Deleting one leaf artifact
# rebuilds that leaf and nothing else, and REBUILT covers that case too.
GATE_ARTIFACTS = $(Z80_PRISTINE) $(BIN_PRISTINE) $(SKOOL) $(ASM_NON_FIXED) \
                 $(BIN_NON_FIXED) $(ASM_FIXED) $(BIN_FIXED) $(Z80_FIXED) html/.stamp

# --- Which gate produced the verdict ------------------------------------------
#
# PASS and FAIL are relative to a gate that moves independently of the project, so
# a verdict that does not name its gate stops meaning anything the moment either
# side moves. An old commit rebuilt under a newer skill can FAIL on a check the
# commit predates rather than on a defect in it, and nothing in an unmarked
# verdict says which it is. The verdict names the gate in two halves:
#
#   gate 1       the generation the skill declares, in SKILL.md's frontmatter,
#                raised by hand in the commit that changes what the gate accepts
#   /e70342a     a digest over the skill files the build runs and reads
#
# The declared half is the one a human chose, and the only half that says a
# changed verdict was *meant* to change. The digest is what catches a gate that
# moved without being declared: one version over two digests says the bytes moved
# and nobody declared it, which is how a lagging declaration becomes visible
# instead of being trusted. Neither half needs the skill to keep its old checks
# alive — the marker labels a verdict, it does not re-run one.
#
# The digest is over file contents, never `git rev-parse`: the skill is consumed
# through a symlink, a copy or a checkout, and only the files are guaranteed to be
# there. A copy has no revision to read, while a digest reads the same there as in
# the checkout it came from — and it does not move when only prose moves, because
# it covers tools/, scripts/ and assets/, which is what the build runs and reads,
# and not references/.
#
# Every part of it degrades to a word rather than to a failure, because a project
# whose marker cannot be read must still build: an unreadable SKILL.md gives
# `gate undeclared/…`, and a machine with no SHA tool gives `…/unknown`.
#
# $(BASELINE) carries the marker too, and a baseline recorded under another gate
# is reported on a pass and on a failure both. A tree with no baseline at all is
# reported only on a failure — that is the shape of an old commit rebuilt under a
# newer gate, and on a pass the absence is the right default for a new
# disassembly rather than something to say.
SKILL_HOME := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)

# Prints `<declared>/<digest>` — the verdict adds the word `gate`, the baseline
# header writes it as `# gate: `. The digest hashes the list of per-file hashes,
# taken from inside $(SKILL_HOME) so the paths that go into it are relative and a
# copy elsewhere on disk digests identically.
#
# The file list travels NUL-separated end to end. A skill file whose name holds a
# space splits into two arguments under a newline-separated `xargs`, both of them
# unreadable, and `2>/dev/null` swallows the error — so the digest reads the same
# before and after that file lands, which is the one thing it exists not to do.
GATE_ID = { \
      v=$$(awk '/^metadata:/{m=1;next} m&&/^[^ ]/{m=0} m&&$$1=="gate:"{print $$2;exit}' \
          '$(SKILL_HOME)/SKILL.md' 2>/dev/null); \
      sha=$$(command -v shasum >/dev/null 2>&1 && echo 'shasum -a 256' || echo 'sha256sum'); \
      d=$$(cd '$(SKILL_HOME)' 2>/dev/null && find tools scripts assets -type f ! -name '*.pyc' -print0 2>/dev/null \
          | LC_ALL=C sort -z | xargs -0 $$sha 2>/dev/null | $$sha 2>/dev/null | cut -c1-7); \
      echo "$${v:-undeclared}/$${d:-unknown}"; }

# Record the gate a baseline was written under, in the baseline's own header,
# beside the `# adopted:` declarations a reviewer already reads. That is what
# makes an inherited baseline detectably stale instead of silently wrong: the gate
# compares this line against the gate running now, and the verdict says so. The
# line goes in ahead of the first finding, and a rewrite replaces it rather than
# accumulating; a baseline that lists nothing yet gets it at the end.
#
# Every `#` in the awk program is escaped: an unescaped one in a variable
# definition opens a make comment, and the program is then truncated mid-quote.
stamp_baseline_gate = [ -f $(BASELINE) ] || exit 0; id=$$($(GATE_ID)); \
      awk -v id="$$id" '/^\# gate: /{next} !stamped && !/^\#/{print "\# gate: " id; stamped=1} {print} END{if (!stamped) print "\# gate: " id}' \
        $(BASELINE) > $(BASELINE).tmp && mv $(BASELINE).tmp $(BASELINE)

# --- What a red verdict leads with --------------------------------------------
#
# Two things can be red at once, and only one of them is the headline. `all`
# names `test`, `lint` and `html` as siblings, so under `-j` — including an
# inherited `MAKEFLAGS=-j4` nobody typed — the checks run beside the round-trip
# and finish even though `cmp` has already failed. The log then holds a build
# failure and a full sweep of findings, and a verdict built from the findings
# alone reports a count of failed checks for a tree whose bytes do not
# round-trip. Sequentially the same state cannot arise.
#
# So the gate reads which targets make reported as failed and separates the
# non-lint ones. `buildfail` non-empty means the build itself broke, and that
# branch comes first: it prints the build's own log lines ahead of the check
# blocks and leads the verdict with the failing target, keeping the finding
# counts after it rather than dropping them. `named` counts the failure lines the
# gate could parse at all — none, on a red run with findings, means the failure
# cannot be attributed to lint, and an unattributable failure is reported as a
# build failure rather than silently read as a clean build with findings.
#
# The remaining branches are unreachable while `buildfail` is set, so their
# wording still holds: lint alone red, build red with every check clean, build
# red before any check ran.
gate:
	@mkdir -p $(dir $(GATE_LOG))
	@$(MAKE) --no-print-directory -q $(GATE_ARTIFACTS) >/dev/null 2>&1; q=$$?; \
	  $(MAKE) --no-print-directory all > $(GATE_LOG) 2>&1; s=$$?; \
	  v=$$($(SNA2SKOOL) --version 2>/dev/null); \
	  id=$$($(GATE_ID)); \
	  stamp="[$${v:-SkoolKit version unknown}, gate $$id]"; \
	  lintfail=$$(awk -v tot=$(LINT_TOTAL) '/^LINT FAIL: /{f+=$$3; n+=$$8; \
	      sub(/^LINT FAIL: [^:]*: /,""); sub(/\.$$/,""); l=(l?l ", " $$0:$$0)} \
	      END{if (f) printf "%d of %d checks failed, %d finding(s): %s.", f, tot, n, l}' $(GATE_LOG)); \
	  lintran=$$(grep -c '^LINT ' $(GATE_LOG)); \
	  lintseen=$$(awk '/^LINT (PASS|FAIL): /{t+=$$5} END{print t+0}' $(GATE_LOG)); \
	  buildfail=$$(awk '/: \*\*\* \[/{t=$$0; sub(/^.*\*\*\* \[/,"",t); sub(/\].*$$/,"",t); \
	      sub(/^.*: /,"",t); if (t!="lint" && t!="lint-images" && !seen[t]++) \
	      l=(l?l ", " t:t)} END{print l}' $(GATE_LOG)); \
	  named=$$(grep -c ': \*\*\* \[' $(GATE_LOG)); \
	  if [ $$s -ne 0 ] && [ -n "$$lintfail" ] && [ $$named -eq 0 ]; then \
	    buildfail='target unknown — make named none'; \
	  fi; \
	  case "$$lintfail" in \
	    *'could not run'*|*'count unread'*|*'crashed'*) \
	      lintfail="$$lintfail A check with no count is not a check with no findings, so that total is short by whatever it would have reported."; ;; \
	  esac; \
	  if [ -n "$$lintfail" ] && [ $$lintseen -lt $(LINT_TOTAL) ]; then \
	    lintfail="$$lintfail The log accounts for $$lintseen of the gate's $(LINT_TOTAL) checks — no sweep reports the other $$(($(LINT_TOTAL)-lintseen)), so they did not run. That count is a floor, not the distance to green."; \
	  fi; \
	  was=$$(sed -n 's/^# gate: *//p' $(BASELINE) 2>/dev/null | head -1); \
	  drift=''; absent=''; \
	  if [ ! -f $(BASELINE) ]; then \
	    absent=" There is no $(BASELINE) in this tree, so this run accepted nothing — a commit that predates the project's baseline fails a gating check the way a regression does; see the gate-boundary rule in references/build-verify.md."; \
	  elif [ "$$was" = "$$id" ]; then :; \
	  elif [ -z "$$was" ]; then \
	    drift=" $(BASELINE) records no gate; make lint-baseline stamps the one it was recorded under."; \
	  else \
	    drift=" $(BASELINE) was recorded under gate $$was, so a finding this gate reports and that one did not is the gate moving, not this commit regressing — see the gate-boundary rule in references/build-verify.md."; \
	  fi; \
	  if [ $$s -ne 0 ] && [ -n "$$buildfail" ] && [ -n "$$lintfail" ]; then \
	    awk '/^--- lint-/{b=1} !b{print} /^LINT /{b=0}' $(GATE_LOG) | tail -40; \
	    sed -n '/^--- lint-/,/^LINT /p' $(GATE_LOG); \
	    echo; echo "GATE FAIL (make exit $$s) $$stamp — the build itself failed ($$buildfail), which is what to fix first: a finding count is a distance to green only over a tree that builds. $$lintfail The build's last 40 log lines are above, then every finding in full. Full log: $(GATE_LOG).$$drift$$absent"; \
	  elif [ $$s -ne 0 ] && [ -n "$$lintfail" ]; then \
	    sed -n '/^--- lint-/,/^LINT /p' $(GATE_LOG); \
	    echo; echo "GATE FAIL (make exit $$s) $$stamp — $$lintfail Every finding is above in full, not tailed. Full log: $(GATE_LOG).$$drift$$absent"; \
	  elif [ $$s -ne 0 ] && [ $$lintran -gt 0 ]; then \
	    tail -40 $(GATE_LOG); \
	    echo; echo "GATE FAIL (make exit $$s) $$stamp — every check that ran was clean, so this is the build failing rather than a finding; its last 40 log lines are above. Full log: $(GATE_LOG).$$drift$$absent"; \
	  elif [ $$s -ne 0 ]; then \
	    tail -40 $(GATE_LOG); \
	    echo; echo "GATE FAIL (make exit $$s) $$stamp — the build failed before any check ran, so no check has a finding count and none of them is what failed; the build's last 40 log lines are above. Full log: $(GATE_LOG).$$drift$$absent"; \
	  elif [ $$q -eq 0 ]; then \
	    echo "GATE PASS, NOTHING REBUILT $$stamp — every generated file was already current; the round-trip cmp and the linters re-ran over the existing build, nothing was regenerated from source (log: $(GATE_LOG)).$$drift"; \
	  else \
	    echo "GATE PASS, REBUILT $$stamp — at least one generated file was regenerated from source; the round-trip cmp and the linters passed. Which files rebuilt is in the log: $(GATE_LOG).$$drift"; \
	  fi; exit $$s

# Round-trip a parallel Worker's range-fragment in isolation (splice into a
# throwaway .ctl, reassemble, lint — all under a temp dir, touching no shared file)
# so a Worker can self-check before reporting; the Manager still proves the
# integrated result with the full `make`. The multi-step logic lives in the script
# so this recipe stays one line. Usage: make verify-frag FRAG=build/frags/my.ctl
#
# $(ASM_FIXED_FLAGS) goes last and unquoted: it is the same flag list the
# fixed-asm rule below passes, so the fragment check gates on exactly what the
# Manager's `make` will, and a project that has opted out (empty) expands to no
# argument here just as it does there.
verify-frag: $(Z80_PRISTINE) $(BIN_PRISTINE)
	@$(SCRIPTS)/verify_fragment.sh "$(CTL)" "$(FRAG)" "$(Z80_PRISTINE)" "$(BIN_PRISTINE)" "$(SCRIPTS)" "$(BASELINE)" "$(ORG)" "$(RELOC_FLOOR)" "$(SIZE)" $(ASM_FIXED_FLAGS)

# Download and convert the original tape to the pristine snapshot.
$(Z80_PRISTINE): $(T2S)
	$(TAP2SNA) @$(T2S) --reg pc=$(PC) --reg sp=$(SP) $(Z80_PRISTINE)

# Extract the program bytes from the pristine snapshot (the ground truth).
$(BIN_PRISTINE): $(Z80_PRISTINE)
	$(SCRIPTS)/extract_bytes.py $(Z80_PRISTINE) $(ORG) $(SIZE) $@

# Disassemble the snapshot into skool, applying the control file.
$(SKOOL): $(Z80_PRISTINE) $(CTL) $(CTL_EXTRA)
	$(SNA2SKOOL) --hex $(Z80_PRISTINE) --ctl $(CTL) $(addprefix --ctl ,$(CTL_EXTRA)) > $@

# The round-trip: reassembled non-fixed bytes must equal the pristine bytes.
test: $(BIN_PRISTINE) $(BIN_NON_FIXED)
	cmp $(BIN_PRISTINE) $(BIN_NON_FIXED)

# --- Running every check, and reporting every one that failed -----------------
#
# Each check is a target of its own, so `make lint-publication` runs one in
# isolation. `lint` does NOT list them as prerequisites, because make stops at the
# first prerequisite that fails: the reader gets the first check's findings and
# nothing about the checks after it. A gate shaped that way answers "is it
# green" and cannot answer "how far from green": the count it reports is a
# prefix of the real one, and nothing labels it as one.
#
# So `lint` runs the checks itself, in one shell, and each one runs whatever the
# last one did. The command the gate runs a check with is stated once, in
# `CHECK_<name>`, and both the standalone target and the sweep use it. That is the
# gate's copy only: `lint-baseline` invokes the baselined checks with
# `--write-baseline`, `scripts/verify_fragment.sh` invokes its own set over a
# spliced fragment, and both spell out their own argument lists — the same check
# takes a different file and a different baseline mode in each.
#
# The loop is not theirs to restate. It lives in `scripts/lint_sweep.sh`, sourced
# here and by `verify_fragment.sh`, so a fix to how a count is read or an
# unreadable one reported reaches every sweep at once.
#
# This is deliberately narrower than `make -k`. `-k` keeps going after *any*
# failed target, which changes what a red build means everywhere: a broken
# round-trip would stop stopping the build. It also gives up the ordering that
# keeps `lint-images` after `html`, and what it continues past differs between
# make versions. What has to survive a first failure is the set of independent
# checks, not the build, so the aggregation lives where the checks are and the
# build keeps halting.
#
# Halting is not enough on its own to keep a `cmp` from arriving buried in
# findings: `-j` starts `lint` beside `test`, so a sweep can complete after the
# round-trip has already failed. What keeps the build failure the headline is the
# verdict, which reads the failing targets out of the log and leads with the
# non-lint ones — see "What a red verdict leads with" above.
#
# A check that needs a built prerequisite is held by the prerequisites of the
# target it runs under, never by anything inside the loop: if the .skool or the
# pristine image cannot be built the recipe never starts, and make reports the
# build failure. That is the one thing this must not get wrong — a check that
# never ran must never be reported as a check with no findings.
#
# `lint-images` runs its own one-element sweep, because it reads what the HTML
# build wrote and so cannot run beside the rest. Both of the gate's sweeps end in
# one `LINT PASS:`/`LINT FAIL:` line in the same format, and the gate adds up
# every such line it finds — so a verdict counts every check even though they ran
# in two places.
LINT_CHECKS = address-order instruction-order lengths label-length identity \
              data-structure publication names byte-counts array-elements \
              comments label-namespace

# Every check the gate holds a project to: the sweep's, plus the one that runs
# after the site is built. The gate compares this against the number of checks the log
# accounts for, so a run that could not reach one of them says so instead of
# letting its count read as the whole of the distance to green.
LINT_TOTAL := $(words $(LINT_CHECKS) images)

# The sweep the gate runs its checks under: `lint_begin`, `lint_run <name>
# <command…>`, `lint_report <checks swept>`, all in one shell. See
# `scripts/lint_sweep.sh` for what each outcome is reported as and why.
#
# `lint_report`'s argument is what this sweep ran, not what the gate holds a
# project to, and the two differ whenever a sweep did not happen: with
# `lint-images` unreached that line counts fewer than $(LINT_TOTAL). The verdict's
# denominator is $(LINT_TOTAL) so that two runs of the same tree are comparable —
# which sweeps got to run depends on the scheduler, and a column of stored verdict
# lines whose denominator moved with `-j` compares nothing. The shortfall is
# reported as its own clause.
LINT_SWEEP = . $(SCRIPTS)/lint_sweep.sh

lint: $(CTL) $(CTL_EXTRA) $(BIN_PRISTINE) $(SKOOL)
	@$(LINT_SWEEP); lint_begin; \
	$(foreach c,$(LINT_CHECKS),lint_run $(c) $(CHECK_$(c));) \
	lint_report $(words $(LINT_CHECKS))

# Label naming is a gauge metric, not a build gate. Early on the map is mostly
# auto-labels and you cannot name a block before you have disassembled it, so a hard
# per-commit gate would block the breadth phase. `make coverage` reports label-naming
# progress (% named, auto-labels remaining); the goal is 100% before "done", not
# before the first commit. See `scripts/coverage_report.py`.

# The checks the gate trusts, held to their own fixtures. A fixture that is only
# run says a check still produces findings; it does not say the check still
# produces *these* findings. A check that loses a finding kind still prints the
# others, and its falling count reads as progress. Each fixture carries a
# recorded expectation and this diffs against it, so a rule that
# stops firing is a red build rather than a quieter one. See
# `fixtures/check-findings.sh` for why the whole output is the assertion.
test-checks:
	@$(FIXTURES)/check-findings.sh

CHECK_address-order = $(SCRIPTS)/validate_ctl_address_order.py $(CTL)
lint-address-order: $(CTL)
	$(CHECK_address-order)

CHECK_instruction-order = $(SCRIPTS)/validate_ctl_instruction_order.py $(CTL)
lint-instruction-order: $(CTL)
	$(CHECK_instruction-order)

CHECK_lengths = $(SCRIPTS)/validate_ctl_lengths.py $(CTL)
lint-lengths: $(CTL)
	$(CHECK_lengths)

# Labels never wrap in the HTML listing, so an over-long label opens a wide
# gutter on its page. Cap length at the source (24 chars); a violation is fixed
# by renaming the label, never by clipping the column.
CHECK_label-length = $(SCRIPTS)/validate_ctl_label_length.py $(CTL)
lint-label-length: $(CTL)
	$(CHECK_label-length)

# Every published block must say what it is: an entry with no title publishes
# under SkoolKit's default heading for its type ("Data at 5B08"), and a
# sub-directive with neither a description nor a label
# on its address leaves a run of DEFB that nothing in the listing explains and
# nothing outside it can refer to. Both forms round-trip, tile, and count as
# documented under `coverage`, so this is the only check that sees them.
CHECK_identity = $(SCRIPTS)/validate_ctl_identity.py $(CTL) --baseline $(BASELINE)
lint-identity: $(CTL)
	$(CHECK_identity)

# An underscore in a label claims that these bytes are part of the thing the
# prefix names, and a reader who follows a false claim lands in a routine that
# does not contain them. Containment for a routine is dominance, so this reads the
# generated .skool for the control flow — which is why it is not a .ctl-only
# check and why the disassembler is among its tools.
#
# It gates what is decidable: a helper called from one entry wearing another's
# name, a narrated behavior filed under someone else's prefix, a prefix that
# reaches past the behavior the bytes actually sit in. What a suffix set *encodes*
# is a judgment no check makes — `--report-families` prints the families for a
# reviewer instead. See `references/ctl-authoring.md`.
CHECK_label-namespace = $(SCRIPTS)/validate_ctl_label_namespace.py $(CTL) \
    --skool $(SKOOL) --baseline $(BASELINE)
lint-label-namespace: $(CTL) $(SKOOL)
	$(CHECK_label-namespace)

# Data-block schema check: every data entry — every block type but `c` and `i` —
# must tile: its sub-directives cover every byte exactly once. Code modeled as an
# undifferentiated byte span reads as clean under every other check while
# relocating nothing, and a byte inside an entry that no sub-directive covers is
# that defect at one-byte scale. Under `s` it publishes as unused space (`DEFS`);
# under every other type it publishes as data — `DEFB`, `DEFM`, `DEFW` — that the
# .ctl never declared, on a page whose title implies it did.
#
# It is in `lint` and lands red on a mature .ctl. That is what the baseline is for:
# the project records the gaps it starts with, the gate fails on a new one, and the
# baseline shrinks as they are closed. Left advisory instead, it is never run and
# the gaps go out the door.
#
# The image is passed, not optional: the ZEROFILL and POINTER checks need to read
# the bytes, and a linter that silently skips half its checks is worse than one
# that is not wired up at all.
CHECK_data-structure = $(SCRIPTS)/validate_ctl_data_structure.py $(CTL) \
    --bin $(BIN_PRISTINE) --org $(ORG) --reloc-floor $(RELOC_FLOOR) \
    --baseline $(BASELINE)
lint-data-structure: $(CTL) $(BIN_PRISTINE)
	$(CHECK_data-structure)

# What the .ctl publishes as pages, rather than what any one entry declares.
# An entry outside the program image publishes a page for RAM the program never
# occupies, and a memory-map row for it. A run of same-titled,
# sub-directive-free entries is one structure cut into pages, none of which says
# what it is. Neither is visible to a check that reads one entry at a time,
# which is every other check here. $(CTL_EXTRA) is swept alongside $(CTL)
# because a generated second .ctl is where render-only data goes.
#
# It also holds each entry to being the type its bytes are, which is the other
# way a page stands for the wrong thing: a `t` entry that swallows `B`
# sub-directives files runtime counters under a text title, and bytes the game
# writes as it plays — a level number, a lives count — publish as load-time data
# on a `b` page. The second of those is settled from the code, so the .skool is
# passed and is not optional: the whole point of reading it is that a store
# instruction is a fact where a description saying "while the timer runs" is a
# reading of English.
CHECK_publication = $(SCRIPTS)/validate_ctl_publication.py $(CTL) $(CTL_EXTRA) \
    --org $(ORG) --size $(SIZE) --skool $(SKOOL) --baseline $(BASELINE)
lint-publication: $(CTL) $(CTL_EXTRA) $(SKOOL)
	$(CHECK_publication)

# One name per entity, in the only form arithmetic can settle: a slot family the
# labels declare (`door_a`/`door_b`) must not be named by position in prose ("the
# second door"). The .ctl and every reader-facing file beside it are swept, since
# a term settles wherever nothing looks. See `references/ctl-authoring.md`.
CHECK_names = $(SCRIPTS)/validate_prose_names.py $(CTL) $(PROSE) --baseline $(BASELINE)
lint-names: $(CTL)
	$(CHECK_names)

# A length the listing already carries, copied into an instruction comment:
# "Clear 163 bytes of the tile map" over the `LD BC` that says 163. It
# buys the reader nothing and rots on the next resize or split. A rate — "9
# bytes per slot", "22-byte record stride" — is the arithmetic a reader would
# otherwise do by hand and is exempt; the author declares a rate by writing it
# as one. See `references/comment-style.md`.
CHECK_byte-counts = $(SCRIPTS)/validate_ctl_byte_counts.py $(CTL) --baseline $(BASELINE)
lint-byte-counts: $(CTL)
	$(CHECK_byte-counts)

# The outcome check: every image macro named a file, and every named file is on
# the site. `make` proved the HTML *builds*; nothing proved it contains anything.
# A rewrite of every `(name)` into the frame-only `(*name)` — which defines a
# frame and writes no file — leaves those images off the site, while the macro
# count in the source, which is what `coverage` reports, does not move. This
# reads html/, so it runs after the site is built.
#
# It sweeps the .ctl and the .ref catalogs, not $(PROSE): a `spec/*.md` page is
# not SkoolKit input, so a macro written there renders nothing and is not
# supposed to.
#
# It runs through the same sweep as the other checks, so its findings reach the
# verdict the way theirs do. Reporting it as "the build failed" would put the
# one check whose subject is an outcome back behind a truncated tail.
CHECK_images = $(SCRIPTS)/validate_rendered_images.py $(CTL) $(REFS) --html html \
    --baseline $(BASELINE)
lint-images: html/.stamp
	@$(LINT_SWEEP); lint_begin; lint_run images $(CHECK_images); lint_report 1

# Re-record the gating checks' findings as the project's accepted baseline. Run it
# when a fix clears a finding — the shrunk file is the evidence. It cannot do the
# opposite: a check whose rewrite would add a key writes nothing, names the keys
# and exits with BASELINE_REFUSED, so this target has no route to burying a
# finding you introduced. Adopting a check for the first time — or a finding kind
# the check has gained since — is the one growth that is legitimate, and it is
# deliberately not reachable from here — see `references/build-verify.md`.
#
# They run in one shell so that a refusal by one does not stop the rest: each
# check rewrites only its own lines, so a check that shrinks must still be able to
# record that while another check is red. The refuser leaves its own section as it
# found it, so every section the file ends with is one its check would write, and
# the accumulated status fails the target. The leading `@` hides the command, not
# the exit status.
#
# A check that exits any other way did not refuse — it crashed, or was called with
# an argument it does not take — so the run stops there rather than reporting a
# refusal that did not happen and letting the checks after it rewrite the file
# from a state nobody has read.
#
# It depends on the built site because one of the checks it re-records reads the
# images the build produced: an outcome cannot be baselined without the outcome.

# The status `ctl_baseline.write` refuses with: see REFUSED_EXIT in
# `scripts/ctl_baseline.py`. Anything else non-zero is a check that failed to run.
BASELINE_REFUSED = 3
sift_baseline_status = s=$$?; \
    if [ $$s -eq $(BASELINE_REFUSED) ]; then refused=1; \
    elif [ $$s -ne 0 ]; then \
        echo "make lint-baseline: the check above exited $$s without recording anything — that is not a refusal, it is a check that could not run."; \
        exit $$s; fi

lint-baseline: $(CTL) $(CTL_EXTRA) $(BIN_PRISTINE) $(SKOOL) html/.stamp
	@refused=0; \
	$(SCRIPTS)/validate_ctl_identity.py $(CTL) \
	    --baseline $(BASELINE) --write-baseline; $(sift_baseline_status); \
	$(SCRIPTS)/validate_ctl_data_structure.py $(CTL) --bin $(BIN_PRISTINE) \
	    --org $(ORG) --reloc-floor $(RELOC_FLOOR) \
	    --baseline $(BASELINE) --write-baseline; $(sift_baseline_status); \
	$(SCRIPTS)/validate_ctl_publication.py $(CTL) $(CTL_EXTRA) \
	    --org $(ORG) --size $(SIZE) --skool $(SKOOL) \
	    --baseline $(BASELINE) --write-baseline; $(sift_baseline_status); \
	$(SCRIPTS)/validate_prose_names.py $(CTL) $(PROSE) \
	    --baseline $(BASELINE) --write-baseline; $(sift_baseline_status); \
	$(SCRIPTS)/validate_ctl_byte_counts.py $(CTL) \
	    --baseline $(BASELINE) --write-baseline; $(sift_baseline_status); \
	$(SCRIPTS)/validate_ctl_array_elements.py $(CTL) \
	    --baseline $(BASELINE) --write-baseline; $(sift_baseline_status); \
	$(SCRIPTS)/validate_rendered_images.py $(CTL) $(REFS) --html html \
	    --baseline $(BASELINE) --write-baseline; $(sift_baseline_status); \
	$(SCRIPTS)/lint_comments.py $(SKOOL) $(PROSE) \
	    --baseline $(BASELINE) --write-baseline; $(sift_baseline_status); \
	$(SCRIPTS)/validate_ctl_label_namespace.py $(CTL) --skool $(SKOOL) \
	    --baseline $(BASELINE) --write-baseline; $(sift_baseline_status); \
	[ $$refused -eq 0 ] || { echo "make lint-baseline: a check refused to record a key $(BASELINE) does not list, so it keeps what it said — the gate still fails on the finding."; exit $(BASELINE_REFUSED); }
	@$(stamp_baseline_gate)

# Every element of an array of records must be annotated individually. An array
# laid out as one directive - or as none at all, with the record size stated only
# in prose - documents the span, not the contents: the reader gets "64 bytes per
# level" and no way to find level 12. Catches both forms (UNINDEXED: one directive
# standing in for >= 10 records; UNDECLARED: an array-sized span with no
# sub-directive), and both are fixed the same way, one annotated line per record
# naming it.
#
# What is not a record array is exempt, because this check gates: baselining a
# bitmap span or a cell grid would use the baseline to bury a false finding,
# which is the one thing it must never do. A render macro, a `w` entry, a
# one-byte stride and a page-sized region cut at a power-of-two width all
# disqualify a span - see the script and `references/ctl-authoring.md`.
CHECK_array-elements = $(SCRIPTS)/validate_ctl_array_elements.py $(CTL) --baseline $(BASELINE)
lint-array-elements: $(CTL)
	$(CHECK_array-elements)

# Comment quality. The kinds `scripts/lint_comments.py` lists in GATING_KINDS
# gate, held against $(BASELINE) like every other gating check; the rest print a
# tally and never fail, since a judgment call such as a STAMP can be a
# legitimate formula over a genuinely templated reality.
#
# Advisory is how a defect ships: nothing runs the check, and the claim of
# compliance is made by the gate that never looked. The baseline is what lets it
# gate on day one — a mature project adopts the check, records what it already
# fails, and the gate holds that line while the file shrinks.
#
# GROUP_SPLIT and GROUP_ENTRY are the half of the comment-span question the
# control flow decides: a group may not span an unconditional transfer, and may
# not be entered anywhere but its first row. The half left over — does the
# comment add what the code can't show, and does its sentence account for the
# whole span — is the Challenger's, not scriptable.
#
# The catalogs and the spec pages are passed too: they reach the same reader as
# the .skool, so the DIARY sweep covers them. An unswept .ref is where a claim
# sourced from a run survives.
REFS  = $(wildcard *.ref)
PROSE = $(REFS) $(wildcard spec/*.md)

CHECK_comments = $(SCRIPTS)/lint_comments.py $(SKOOL) $(PROSE) \
    --baseline $(BASELINE)
lint-comments: $(SKOOL)
	$(CHECK_comments) --advisory

# Advisory documentation-coverage report — the "is it done?" gauge. Shows the
# basic blocks that carry no comment (the bar is zero), the comment units per
# block, inline-graphics/naming/relocatability signals, and audio/table/
# placeholder gaps. A green build is breadth; maturity requires this to clear the
# floor.
#
# It also reads the two things the *gate* knows — the baseline it holds and the
# images the build wrote — so the gauge cannot call a project done while the gate
# is passing it on recorded credit. Both are auto-discovered beside the skool,
# along with the .ctl and every *.ref.
coverage: $(SKOOL)
	$(SCRIPTS)/coverage_report.py $(SKOOL) --reloc-floor $(RELOC_FLOOR)

# Non-fixed source: must already match the original (no @ofix applied).
#
# The build treats a skool2asm WARNING as fatal, so its stderr is captured and
# grepped — but an error is not a warning (`ERROR: … file not found`, rc=1), so
# the grep alone lets a failed run's partial stdout reach $@ under a green recipe.
# The exit status decides first; the grep only adds the warnings on top of it.
# Nothing moves onto $@ until both say the run was clean.
$(ASM_NON_FIXED): $(SKOOL)
	@$(SKOOL2ASM) --create-labels $(SKOOL) > $@.tmp 2> $@.stderr; rc=$$?; \
	if grep -q WARNING $@.stderr; then rc=1; fi; \
	if [ $$rc -ne 0 ]; then cat $@.stderr >&2; rm -f $@.tmp $@.stderr; exit $$rc; fi; \
	rm -f $@.stderr; mv $@.tmp $@

$(BIN_NON_FIXED): $(ASM_NON_FIXED)
	$(PASMO) --bin $(ASM_NON_FIXED) $@

# Fixed source: applies @isub/@ofix directives. The fixed asm renders relocatably
# by default — `-s` puts every in-image operand through its @ssub/@equ form and
# strictly gates that no raw in-image reference remains, so `coverage` reports
# RELOCATABLE = 0. This is the standard, not a per-project opt-in. `-s` fails on
# any unresolved in-image operand, so a project still in the breadth/labeling
# sweep opts OUT until the sweep is done by setting `ASM_FIXED_FLAGS =` (empty) in
# its Makefile, then removes that line to restore the standard gate.
#
# This is the one place the flags are stated. `verify-frag` reads the same
# variable, and renders and assembles the fixed source the same way this rule and
# $(BIN_FIXED) do, so a Worker's self-check and the Manager's `make` gate a
# fragment identically — strict where the project is strict, permissive where it
# has opted out.
ASM_FIXED_FLAGS ?= -s
$(ASM_FIXED): $(SKOOL)
	@$(SKOOL2ASM) --create-labels -f 1 $(ASM_FIXED_FLAGS) $(SKOOL) > $@.tmp 2> $@.stderr; rc=$$?; \
	if grep -q WARNING $@.stderr; then rc=1; fi; \
	if [ $$rc -ne 0 ]; then cat $@.stderr >&2; rm -f $@.tmp $@.stderr; exit $$rc; fi; \
	rm -f $@.stderr; mv $@.tmp $@

$(BIN_FIXED): $(ASM_FIXED)
	$(PASMO) --bin $< $@

$(Z80_FIXED): $(BIN_FIXED)
	$(BIN2SNA) --border 0 --org $(ORG) --start $(PC) --stack $(SP) $< $@

# The documented source as a runnable deliverable: wrap the fixed program image
# into a tape anyone can load. Kept out of `all` — it is a shipping artifact,
# not a gate.
TAP_FIXED = $(GAME).fixed.tap

tap: $(TAP_FIXED)

$(TAP_FIXED): $(BIN_FIXED)
	$(BIN2TAP) --org $(ORG) --start $(PC) --stack $(SP) $< $@

# Every site ships the skill's default theme: dark responsive layout, the listing
# in the platform's own monospace face, Z80 syntax highlighting, comment-group
# hover, and a card-grid index (assets/theme.{ref,css,js}). The theme names no
# face it does not load — see `references/html-docs.md`. A project layers its
# identity by appending its own stylesheet to the chain its [Game] declares
# (StyleSheet=skoolkit.css;theme.css;$(GAME).css). `-a` renders operands as
# label names — `CALL draw_sprite`, never `CALL $F0A2`.
#
# The theme ref is parsed LAST, after every project ref, and last wins. Reading
# the ref list is built in skool2html.py:183-196: glob($(GAME)*.ref) in the skool
# file's directory first, with $(GAME).ref forced to the front; then the files
# named in [Config] RefFiles; then the ref files on the command line. Passing
# $(REF) after $(THEME)/theme.ref below changes nothing — parse_ref_files skips a
# path already in the list, and $(GAME).ref entered it in the glob pass.
#
# So restating a parameter does NOT override the theme. refparser.py:30-33: a
# plain [Section] REPLACES what earlier refs built, a [Section+] extends it, and
# within a dictionary section a later `Key=` overwrites an earlier one. A key
# theme.ref states in [Game+] or [Paths+] therefore beats the project's value for
# that key, and a plain [Template:*] in theme.ref cannot be reclaimed at all.
# theme.ref carries only what is genuinely the theme's own; a default a project
# should be able to change lives in assets/game.ref.template, which is the
# project's own file and is parsed first. The one layer that composes rather than
# clobbers is `-c` (skool2html.py:197, applied after every ref), which is why
# HTML_JS below appends to the theme's JavaScript instead of replacing it.
THEME := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../assets)

# `-a` names the *targets* of calls and jumps, and nothing else: skool2html
# builds its parser with no asm_mode, so @isub/@ssub and the @equ label map —
# everything that spells an address as a constant in the ASM — never reach the
# page. `InitModule` loads the skill's parser wrapper, which parses the skool a
# second time in ASM mode and copies the operand text across, so the listing and
# the .asm read alike. A project that needs an InitModule of its own must import
# this one from it: the last [Config] value wins, and this is passed last.
#
# The wrapper parses in the sub mode $(ASM_FIXED_FLAGS) renders the fixed source
# in, so a project that has opted out of `-s` while it labels the map does not
# get @ssub operands on the page and not in the file it ships beside.
# It reads the mode from the environment rather than the command line, so the
# recipe stays a plain command and make 3.81's shell-less fast path cannot lose a
# variable assignment prefixed to it (see "The toolchain" above).
HTML_SUBS := $(SCRIPTS)/html_operand_subs.py
export SKOOL_HTML_SUB_MODE := $(if $(filter -r,$(ASM_FIXED_FLAGS)),3,$(if $(filter -s,$(ASM_FIXED_FLAGS)),2,1))

# [Game] JavaScript is a single key, so a ref file that names theme.js owns the
# whole slot and a project can ship none of its own. Composing it here instead
# leaves the slot open: a project lists its scripts in HTML_JS and they load
# after the theme's.
#
#   HTML_JS = maps.js;search.js
#
# Name each file in [Resources] (or keep it in the -S search path) so skool2html
# copies it onto the site.
HTML_JS ?=
HTML_JAVASCRIPT := theme.js$(if $(HTML_JS),;$(HTML_JS))

html: html/.stamp

html/.stamp: $(SKOOL) $(wildcard *.ref) $(wildcard *.js) $(THEME)/theme.ref $(THEME)/theme.css $(THEME)/theme.js $(HTML_SUBS)
	$(SKOOL2HTML) -d html -H -a -c "Config/InitModule=$(SCRIPTS):html_operand_subs" -c "Game/JavaScript=$(HTML_JAVASCRIPT)" --rebuild-images --rebuild-audio -S $(THEME) $(SKOOL) $(THEME)/theme.ref $(REF)
	touch $@

clean:
	rm -rf html *.asm *.bin *.skool *.z80
