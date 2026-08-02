#!/usr/bin/env python3
"""Persistent z88dk-gdb session driver for FuseX's gdbserver.

Unlike a batch wrapper (connect -> run -> detach every call), this keeps ONE
z88dk-gdb alive via a small background daemon. The emulator stays
stopped at its current state between commands, so a break / cont / read / cont /
read cycle all happens in a single halted session. Only `stop` detaches (which
is what resumes the emulator).

Subcommands:
  start [--port P] [--host H] [--map M]   launch the session; connect halted
  cmd "<gdb command>" [--timeout S]       send one command, print its output
  stop                                    detach and tear down

State lives under $GDB_SESSION_DIR (default /tmp/gdb-session).
"""
import argparse, os, re, select, signal, subprocess, sys, time

DIR = os.environ.get("GDB_SESSION_DIR", "/tmp/gdb-session")
CMD = os.path.join(DIR, "cmd.fifo")
RESP = os.path.join(DIR, "resp.fifo")
LOG = os.path.join(DIR, "session.log")
PID = os.path.join(DIR, "daemon.pid")
GDBPID = os.path.join(DIR, "gdb.pid")
PROMPT = b"()>"   # z88dk-gdb prompt tail, e.g. " 5cd0 ()>"
ANSI = re.compile(rb'\x1b(\[[0-9;?]*[ -/]*[@-~]|[=>NOM]|\][^\x07]*\x07)')


def _strip(b):
    return ANSI.sub(b"", b).replace(b"\r", b"")


def _clean(b):
    """ANSI-strip and drop prompt-only lines, leaving the command's output."""
    lines = [ln for ln in _strip(b).split(b"\n")
             if not ln.strip().endswith(PROMPT)]
    return b"\n".join(lines).strip(b"\n").decode(errors="replace")


def _read_until_prompt(master, timeout):
    buf = b""
    end = time.time() + timeout
    while time.time() < end:
        r, _, _ = select.select([master], [], [], 0.3)
        if master in r:
            try:
                chunk = os.read(master, 65536)
            except OSError:
                break
            if not chunk:  # EOF: gdb exited / FuseX disconnected (e.g. crash)
                buf += b"\n[session ended: gdb exited or FuseX disconnected]\n"
                return buf
            buf += chunk
            if _strip(buf).rstrip().endswith(PROMPT):
                r2, _, _ = select.select([master], [], [], 0.05)
                if master not in r2:
                    return buf
    # The loop ran out of time without returning to a prompt: the command never
    # completed. For `cont` this means no breakpoint trapped (a missed bp or a
    # reset). Surface it loudly rather than returning silent partial output.
    buf += (b"\n[timed out after %ds with no prompt: a 'cont' that never trapped?"
            b" set a reset guard (break 0x0000) and raise --timeout]\n" % int(timeout))
    return buf


def _daemon(port, host, mapfile):
    proc = subprocess.Popen(
        ["z88dk-gdb", "-h", host, "-p", str(port), "-x", mapfile],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=dict(os.environ, TERM="dumb", NO_COLOR="1"))
    master = proc.stdout.fileno()
    gdb_in = proc.stdin.fileno()
    pid = proc.pid
    with open(GDBPID, "w") as f:
        f.write(str(pid))
    log = open(LOG, "ab", buffering=0)
    log.write(b"=== connect ===\n" + _read_until_prompt(master, 30))
    while True:
        with open(CMD, "r") as cf:
            req = cf.readline()
        if not req:
            continue
        timeout_s, _, command = req.partition("\x00")
        command = command.rstrip("\n")
        try:
            timeout = float(timeout_s)
        except ValueError:
            timeout = 30.0
        if command == "__QUIT__":
            for b in (b"detach\n", b"quit\n"):
                try:
                    os.write(gdb_in, b); time.sleep(0.2)
                except OSError:
                    break
            with open(RESP, "w") as rf:
                rf.write("[stopped]\n")
            break
        log.write(b"\n=== cmd: " + command.encode() + b" ===\n")
        try:
            os.write(gdb_in, command.encode() + b"\n")
        except OSError:
            with open(RESP, "w") as rf:
                rf.write("[error: gdb not writable]\n")
            break
        out = _read_until_prompt(master, timeout)
        log.write(out)
        with open(RESP, "w") as rf:
            rf.write(_clean(out) + "\n")
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


def start(a):
    if os.path.exists(PID):
        try:
            os.kill(int(open(PID).read()), 0)
            print("[session already running; run stop first]")
            return 1
        except (ProcessLookupError, ValueError):
            pass
    os.makedirs(DIR, exist_ok=True)
    open(a.map, "a").close()  # gdb needs the (possibly empty) map file
    for f in (CMD, RESP):
        try:
            os.unlink(f)
        except FileNotFoundError:
            pass
        os.mkfifo(f)
    open(LOG, "wb").close()
    if os.fork() > 0:
        time.sleep(2)
        try:
            sys.stdout.write(_clean(open(LOG, "rb").read()) + "\n")
        except OSError:
            pass
        print("[session ready]")
        return 0
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    with open(PID, "w") as f:
        f.write(str(os.getpid()))
    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, 0); os.dup2(devnull, 1); os.dup2(devnull, 2)
    _daemon(a.port, a.host, a.map)
    os._exit(0)


def _send(command, timeout):
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError()))
    signal.alarm(int(timeout) + 15)
    try:
        fd = os.open(CMD, os.O_WRONLY)
        os.write(fd, f"{timeout}\x00{command}\n".encode())
        os.close(fd)
        with open(RESP, "r") as rf:
            return rf.read()
    finally:
        signal.alarm(0)


def cmd(a):
    if not os.path.exists(PID):
        print("[no session: run start]")
        return 1
    try:
        sys.stdout.write(_send(a.command, a.timeout))
    except TimeoutError:
        print("[timeout waiting for daemon; session may be wedged]")
        return 1
    return 0


def stop(a):
    try:
        _send("__QUIT__", 5)
    except Exception:
        pass
    for pf in (GDBPID, PID):
        try:
            os.kill(int(open(pf).read()), signal.SIGTERM)
        except Exception:
            pass
    for f in (CMD, RESP, PID, GDBPID):
        try:
            os.unlink(f)
        except FileNotFoundError:
            pass
    print("[session stopped]")
    return 0


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="sub", required=True)
    s = sub.add_parser("start")
    s.add_argument("--port", type=int, default=1337)
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--map", default="/tmp/empty.map")
    s.set_defaults(fn=start)
    c = sub.add_parser("cmd")
    c.add_argument("command")
    c.add_argument("--timeout", type=float, default=30.0)
    c.set_defaults(fn=cmd)
    t = sub.add_parser("stop")
    t.set_defaults(fn=stop)
    a = p.parse_args()
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
