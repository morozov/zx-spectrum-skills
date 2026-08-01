#!/bin/bash
# Drive z88dk-gdb against FuseX's gdbserver in one non-interactive batch.
#
# Each invocation is ONE session: connect -> run the commands you pass (in
# order, sharing state) -> the client reaches stdin EOF and detaches, which
# RESUMES the emulator. Put every command that must observe the same halted
# state in the SAME invocation.
#
# Usage:
#   gdb.sh "break 0x5d93" "cont" "reg" "dis 0x5d93"
#   PORT=1338 gdb.sh "reg"
#
# Requires: z88dk-gdb on PATH (a nightly build, which detaches and exits 0
# cleanly on EOF) and FuseX already launched with --gdbserver-enable.
# The -x map file is mandatory even with no symbols; we point it at an empty file.
#
# A `cont` that never traps blocks until TIMEOUT; `timeout` then kills the client
# and `pipefail` surfaces its exit 124. Set a reset guard (break 0x0000) so a
# missed trap is observable rather than a silent wait.
set -euo pipefail

PORT="${PORT:-1337}"
HOST="${HOST:-127.0.0.1}"
MAP="${MAP:-/tmp/empty.map}"
TIMEOUT="${TIMEOUT:-45}"

touch "$MAP"

for cmd in "$@"; do printf '%s\n' "$cmd"; done \
  | timeout "$TIMEOUT" z88dk-gdb -h "$HOST" -p "$PORT" -x "$MAP" 2>&1
