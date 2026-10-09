#!/usr/bin/env python3
"""
Infer, for every routine in a .skool, the registers it takes as inputs and the
registers its callers read back as outputs, and compare them with the `R` rows of
the .ctl.

  INPUT   a register the routine reads on some path before it writes it. A PUSH
          that is later popped into the same register pair only saves the value
          and does not read it.
  OUTPUT  a register the routine changes (it does not hold the caller's value at
          every RET) and that some caller reads after the CALL before writing it.

The analysis is a dataflow over the instruction graph, one node per instruction
and shadow-register state. It follows jumps, conditional jumps, tail jumps and
fall-through into the next entry, so a routine is whatever its entry reaches. A
CALL is replaced by the callee's summary: what the callee reads, what it always
writes, and what it may change. PUSH/POP pairs are matched on a symbolic stack, so
a register saved and restored counts as untouched. EXX and EX AF,AF' swap the
names of the registers that follow, and the report names a shadow register with a
trailing quote.

What it cannot see, it reports as a note instead of guessing: computed jumps,
RST, a POP with nothing pushed, stack pointer arithmetic, a return with a
non-empty stack, flow into data, and a RET reached with the shadow set swapped.
Self-modified operands are read as the bytes the listing shows.

Usage: register_usage.py SKOOL [--ctl CTL] [--all] [--notes]
  --ctl    compare against the R rows and list only the routines that differ
  --all    list every routine, differing or not
  --notes  also print the notes each routine collected
"""

import argparse
import re
import sys
from collections import defaultdict

PAIR = {'BC': ('B', 'C'), 'DE': ('D', 'E'), 'HL': ('H', 'L'), 'AF': ('A', 'F'),
        'IX': ('IX',), 'IY': ('IY',)}
R8 = {'A', 'B', 'C', 'D', 'E', 'H', 'L'}
MAIN_SET = {'B', 'C', 'D', 'E', 'H', 'L'}
ACC_SET = {'A', 'F'}
BASE = ['A', 'F', 'B', 'C', 'D', 'E', 'H', 'L', 'IX', 'IY']
ALL = frozenset(BASE + [r + "'" for r in BASE if r not in ('IX', 'IY')])
FLAG_TOKENS = {'F', 'Z', 'NZ', 'NC', 'CF', 'FLAGS', 'CARRY'}

LINE_RE = re.compile(r'^[ *a-z]\$([0-9A-F]{4}) (\S+)(?: +([^;]*?))?\s*(?:;.*)?$')
ENTRY_RE = re.compile(r'^c\$([0-9A-F]{4}) ')
ROW_RE = re.compile(r'^R \$([0-9A-F]{4}) ([IO]):(\S+)')
DATA_OPS = {'DEFB', 'DEFW', 'DEFM', 'DEFS'}
CONDS = {'NZ', 'Z', 'NC', 'C', 'PO', 'PE', 'P', 'M'}


def halves(token):
    token = token.strip()
    if token in R8:
        return (token,)
    return PAIR.get(token, ())


INDIRECT_RE = re.compile(r'\((HL|BC|DE|IX|IY)(?:[+-][^)]*)?\)')


def mem_regs(operand):
    """Registers an indirect operand needs: (HL), (BC), (DE), (IX+d), (IY+d)."""
    m = INDIRECT_RE.fullmatch(operand.strip())
    return set(PAIR[m.group(1)]) if m else set()


def value_regs(operand):
    """Registers a source operand reads."""
    operand = operand.strip()
    if operand.startswith('('):
        return mem_regs(operand)
    return set(halves(operand))


def is_mem(operand):
    return operand.strip().startswith('(')


class Effect:
    __slots__ = ('use', 'dfn', 'kind', 'target', 'cond', 'push', 'pop', 'note', 'store', 'swap')

    def __init__(self):
        self.use, self.dfn = set(), set()
        self.kind = 'seq'      # seq jp jr call ret jpind exx exaf data
        self.target = None
        self.cond = False
        self.push = self.pop = None
        self.note = None
        self.store = False
        self.swap = False


NOT_PURE = {'IN', 'OUT', 'LDI', 'LDD', 'LDIR', 'LDDR', 'CPIR', 'CPDR', 'DJNZ', 'EX'}


def address(operand):
    m = re.fullmatch(r'\$([0-9A-F]{4})', operand.strip())
    return int(m.group(1), 16) if m else None


def effect(op, args):
    e = Effect()
    p = [a.strip() for a in args.split(',')] if args else []
    if op in DATA_OPS:
        e.kind = 'data'
    elif op == 'LD' and len(p) == 2:
        dst, src = p
        e.use |= value_regs(src)
        if is_mem(dst):
            e.store = True
            e.use |= mem_regs(dst)
        elif dst in ('SP',):
            e.note = 'stack pointer load'
            e.use |= value_regs(src)
        else:
            e.dfn |= set(halves(dst))
            if dst in ('A',) and src in ('I', 'R'):
                e.dfn.add('F')
    elif op in ('INC', 'DEC') and p:
        if is_mem(p[0]):
            e.store = True
            e.use |= mem_regs(p[0])
            e.dfn.add('F')
        elif p[0] == 'SP':
            e.note = 'stack pointer arithmetic'
        else:
            h = set(halves(p[0]))
            e.use |= h
            e.dfn |= h
            if p[0] in R8:
                e.dfn.add('F')
    elif op in ('ADD', 'ADC', 'SBC') and len(p) == 2:
        dst, src = p
        e.use |= set(halves(dst)) | value_regs(src)
        e.dfn |= set(halves(dst)) | {'F'}
        if op != 'ADD':
            e.use.add('F')
        if src == 'SP':
            e.note = 'stack pointer arithmetic'
    elif op in ('SUB', 'AND', 'OR', 'XOR', 'CP') and p:
        src = p[-1]
        if op in ('XOR', 'SUB') and src == 'A':
            e.dfn |= {'A', 'F'}
        elif op == 'AND' and src == 'A':
            e.dfn.add('F')      # the clear-carry idiom: it does not read A's value
        else:
            e.use |= {'A'} | value_regs(src)
            e.dfn.add('F')
            if op != 'CP':
                e.dfn.add('A')
    elif op in ('RLCA', 'RRCA'):
        e.use.add('A')
        e.dfn |= {'A', 'F'}
    elif op in ('RLA', 'RRA'):
        e.use |= {'A', 'F'}
        e.dfn |= {'A', 'F'}
    elif op in ('CPL', 'NEG'):
        e.use.add('A')
        e.dfn |= {'A', 'F'}
    elif op == 'DAA':
        e.use |= {'A', 'F'}
        e.dfn |= {'A', 'F'}
    elif op == 'SCF':
        e.dfn.add('F')
    elif op == 'CCF':
        e.use.add('F')
        e.dfn.add('F')
    elif op in ('RL', 'RR') and p:
        e.use.add('F')
        _shift(e, p[0])
    elif op in ('RLC', 'RRC', 'SLA', 'SRA', 'SRL', 'SLL') and p:
        _shift(e, p[0])
    elif op == 'BIT' and len(p) == 2:
        e.use |= value_regs(p[1])
        e.dfn.add('F')
    elif op in ('SET', 'RES') and len(p) == 2:
        if is_mem(p[1]):
            e.store = True
            e.use |= mem_regs(p[1])
        else:
            e.use |= set(halves(p[1]))
            e.dfn |= set(halves(p[1]))
    elif op == 'PUSH' and p:
        e.push = p[0]
        e.use |= set(halves(p[0]))
    elif op == 'POP' and p:
        e.pop = p[0]
        e.dfn |= set(halves(p[0]))
    elif op == 'EX' and p == ['DE', 'HL']:
        e.use |= {'D', 'E', 'H', 'L'}
        e.dfn |= {'D', 'E', 'H', 'L'}
        e.swap = True
    elif op == 'EX' and p == ['AF', "AF'"]:
        e.kind = 'exaf'
    elif op == 'EX' and p and p[0] == '(SP)':
        e.use |= set(halves(p[1]))
        e.dfn |= set(halves(p[1]))
        e.note = 'EX (SP) stack exchange'
    elif op == 'EXX':
        e.kind = 'exx'
    elif op in ('LDI', 'LDD', 'LDIR', 'LDDR'):
        regs = {'H', 'L', 'D', 'E', 'B', 'C'}
        e.use |= regs
        e.dfn |= regs | {'F'}
        e.store = True
    elif op in ('CPI', 'CPD', 'CPIR', 'CPDR'):
        e.use |= {'A', 'H', 'L', 'B', 'C'}
        e.dfn |= {'H', 'L', 'B', 'C', 'F'}
    elif op == 'DJNZ':
        e.use.add('B')
        e.dfn.add('B')
        e.kind, e.cond, e.target = 'jr', True, address(p[0]) if p else None
    elif op == 'IN' and len(p) == 2:
        e.dfn |= set(halves(p[0])) | {'F'}
        e.use |= {'B', 'C'} if p[1] == '(C)' else {'A'} if p[0] == 'A' else set()
    elif op == 'OUT' and len(p) == 2:
        e.use |= value_regs(p[1])
        if p[0] == '(C)':
            e.use |= {'B', 'C'}
        elif p[1] == 'A':
            pass
    elif op in ('JP', 'JR', 'CALL', 'RET'):
        _flow(e, op, p)
    elif op == 'RST':
        e.note = 'RST'
    elif op in ('RETI', 'RETN'):
        e.kind = 'ret'
    elif op in ('NOP', 'DI', 'EI', 'HALT', 'IM'):
        pass
    elif op in ('LDIR', 'OTIR', 'INIR'):
        e.note = 'block I/O'
    else:
        e.note = f'unmodeled {op}'
    return e


def _shift(e, operand):
    if is_mem(operand):
        e.store = True
        e.use |= mem_regs(operand)
        e.dfn.add('F')
    else:
        e.use |= set(halves(operand))
        e.dfn |= set(halves(operand)) | {'F'}


def _flow(e, op, p):
    if op == 'RET':
        e.kind = 'ret'
        e.cond = bool(p)
        if p:
            e.use.add('F')
        return
    cond = bool(p) and p[0] in CONDS and len(p) == 2
    dest = p[-1] if p else ''
    e.cond = cond
    if cond:
        e.use.add('F')
    if op == 'JP' and is_mem(dest):
        e.kind = 'jpind'
        e.use |= mem_regs(dest)
        e.note = 'computed jump'
        return
    e.kind = {'JP': 'jp', 'JR': 'jr', 'CALL': 'call'}[op]
    e.target = address(dest)


def parse(skool):
    instrs, order, entries = {}, [], []
    with open(skool, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            m = ENTRY_RE.match(line)
            if m:
                entries.append(int(m.group(1), 16))
            m = LINE_RE.match(line)
            if not m:
                continue
            addr = int(m.group(1), 16)
            instrs[addr] = (m.group(2), (m.group(3) or '').strip())
            order.append(addr)
    nxt = {a: order[i + 1] for i, a in enumerate(order[:-1])}
    return instrs, nxt, entries


def ren(name, exx, exaf):
    """Physical name of a register named in the frame of a code position."""
    if exx and name in MAIN_SET:
        return name + "'"
    if exaf and name in ACC_SET:
        return name + "'"
    return name


def ren_set(names, exx, exaf):
    return {ren(n, exx, exaf) for n in names}


def ret_addrs_of(g, eff):
    return {n[0] for n in g['order'] if eff[n[0]].kind == 'ret'}


class Program:
    def __init__(self, skool):
        self.instr, self.nxt, c_entries = parse(skool)
        self.eff = {a: effect(op, args) for a, (op, args) in self.instr.items()}
        targets = {e.target for e in self.eff.values() if e.kind == 'call' and e.target}
        # An entry that begins in data (a table in front of the code) is attributed to
        # the first code address after it, which is where the routine starts.
        self.entries = sorted({self.first_code(a) for a in set(c_entries) | targets
                               if a in self.instr})
        self.summary = {a: {'use': frozenset(), 'must': ALL, 'may': frozenset()}
                        for a in self.entries}
        self.graph = {}
        self.notes = defaultdict(set)

    def first_code(self, addr):
        """The first address at or after `addr` that holds an instruction, not data."""
        while addr in self.eff and self.eff[addr].kind == 'data' and addr in self.nxt:
            addr = self.nxt[addr]
        return addr

    def succ(self, node):
        addr, exx, exaf = node
        e = self.eff[addr]
        nxt = self.nxt.get(addr)
        out = []
        if e.kind in ('ret', 'jpind'):
            if e.kind == 'ret' and e.cond and nxt:
                out.append((nxt, exx, exaf))
            return out
        if e.kind == 'data':
            return out
        if e.kind in ('jp', 'jr'):
            if e.target in self.instr:
                out.append((e.target, exx, exaf))
            if e.cond and nxt:
                out.append((nxt, exx, exaf))
            return out
        if nxt:
            if e.kind == 'exx':
                out.append((nxt, 1 - exx, exaf))
            elif e.kind == 'exaf':
                out.append((nxt, exx, 1 - exaf))
            else:
                out.append((nxt, exx, exaf))
        return out

    def build(self, entry):
        """Nodes reachable from an entry, their successors and exit kinds."""
        start = (entry, 0, 0)
        seen, order, edges = {start}, [start], {}
        stack = [start]
        while stack:
            node = stack.pop()
            edges[node] = self.succ(node)
            for s in edges[node]:
                if s not in seen:
                    seen.add(s)
                    order.append(s)
                    stack.append(s)
        return {'start': start, 'order': order, 'edges': edges}

    def node_effect(self, node):
        """Return (use, kill, def, may_change) of a node, as physical names."""
        addr, exx, exaf = node
        e = self.eff[addr]
        if e.kind == 'call' and e.target in self.summary:
            s = self.summary[e.target]
            use = ren_set(s['use'], exx, exaf)
            return use, ren_set(s['must'], exx, exaf), ren_set(s['must'], exx, exaf), \
                ren_set(s['may'], exx, exaf)
        use = ren_set(e.use, exx, exaf)
        dfn = ren_set(e.dfn, exx, exaf)
        if e.kind == 'call':
            e_note = 'call to code outside the entries'
            self.notes[addr].add(e_note)
        return use, dfn, dfn, dfn

    # forward: defined, intact, symbolic stack, pairing of pushes with pops
    def forward(self, entry, g):
        start = g['start']
        init = (frozenset(), ALL, ())
        state = {start: init}
        work = [start]
        exits = []
        pairs = defaultdict(set)        # push address -> pops feeding on it
        feeders = defaultdict(set)      # pop address -> pushes it may pop
        notes = set()
        while work:
            node = work.pop()
            addr, exx, exaf = node
            e = self.eff[addr]
            defined, intact, stack = state[node]
            if e.note:
                notes.add(e.note)
            if e.kind == 'data':
                notes.add('flow into data')
            use, kill, dfn, may = self.node_effect(node)
            if e.push:
                h = frozenset(ren_set(halves(e.push), exx, exaf))
                stack = stack + ((e.push, h, defined & h, intact & h, addr),)
            elif e.pop:
                h = frozenset(ren_set(halves(e.pop), exx, exaf))
                if stack:
                    pushed, ph, td, ti, paddr = stack[-1]
                    stack = stack[:-1]
                    same = (pushed == e.pop and ph == h)
                    pairs[paddr].add(same)
                    feeders[addr].add((paddr, same))
                    if same:
                        defined = (defined - h) | td
                        intact = (intact - h) | ti
                    else:
                        defined = defined | h
                        intact = intact - h
                else:
                    notes.add('POP with nothing pushed')
                    defined = defined | h
                    intact = intact - h
            else:
                defined = defined | dfn
                intact = intact - may
            if e.kind == 'ret':
                exits.append((node, defined, intact, stack))
                if e.cond:
                    pass
            for s in g['edges'][node]:
                new = (defined, intact, stack)
                old = state.get(s)
                if old is None:
                    state[s] = new
                    work.append(s)
                    continue
                od, oi, ostack = old
                if len(ostack) != len(stack):
                    notes.add('stack depth differs at a join')
                    k = min(len(ostack), len(stack))
                    merged_stack = ostack[:k]
                else:
                    merged_stack = tuple(
                        (a[0], a[1], a[2] & b[2], a[3] & b[3], a[4])
                        if a[4] == b[4] else (a[0], a[1], frozenset(), frozenset(), a[4])
                        for a, b in zip(ostack, stack))
                merged = (od & defined, oi & intact, merged_stack)
                if merged != old:
                    state[s] = merged
                    work.append(s)
        # Exit states can have been refined after being recorded; recompute them.
        final = []
        for node in g['order']:
            addr, exx, exaf = node
            e = self.eff[addr]
            if e.kind == 'ret' and node in state:
                defined, intact, stack = state[node]
                final.append((node, defined, intact, stack))
        for node, defined, intact, stack in final:
            if stack:
                notes.add('return with a non-empty stack')
            if node[1] or node[2]:
                notes.add('return with the shadow registers swapped')
        return final, pairs, feeders, notes

    def analyze_entry(self, entry, exit_live):
        g = self.graph[entry]
        final, pairs, feeders, notes = self.forward(entry, g)
        feeders = dict(feeders)
        if final:
            must = frozenset.intersection(*[d for _, d, _, _ in final])
            may = ALL - frozenset.intersection(*[i for _, _, i, _ in final])
        else:
            must, may = ALL, frozenset()
        # Backward liveness twice: with no live registers at the exits, which gives the
        # routine's own reads, and with the callers' live registers, which gives what is
        # live after each of its calls.
        def liveness(exits, dead):
            live_in = {n: frozenset() for n in g['order']}
            live_out = {n: frozenset() for n in g['order']}
            changed = True
            while changed:
                changed = False
                for node in reversed(g['order']):
                    addr, exx, exaf = node
                    e = self.eff[addr]
                    out = set()
                    for s in g['edges'][node]:
                        out |= live_in[s]
                    if e.kind == 'ret':
                        out |= exits.get(addr, frozenset())
                    if e.push:
                        # A push copies each half into a stack slot named by the push.
                        h = [ren(x, exx, exaf) for x in halves(e.push)]
                        new = {x for x in out if not (isinstance(x, tuple) and x[0] == addr)}
                        new |= {h[i] for i in range(len(h)) if (addr, i) in out}
                        new_in = frozenset(new)
                    elif e.pop and feeders.get(addr):
                        h = [ren(x, exx, exaf) for x in halves(e.pop)]
                        new = set(out)
                        for i, reg in enumerate(h):
                            if reg in out:
                                new.discard(reg)
                                new |= {(pa, i) for pa, _ in feeders[addr]}
                        new_in = frozenset(new)
                    elif e.swap:
                        new = set(out) - {'D', 'E', 'H', 'L'}
                        for a, b in (('D', 'H'), ('E', 'L'), ('H', 'D'), ('L', 'E')):
                            if ren(a, exx, exaf) in out:
                                new.add(ren(b, exx, exaf))
                        new_in = frozenset(new)
                    else:
                        use, kill, _, _ = self.node_effect(node)
                        if node in dead and not (kill & out):
                            new_in = frozenset(out)     # its result is never read
                        else:
                            new_in = frozenset(use | (out - kill))
                    out = frozenset(out)
                    if new_in != live_in[node] or out != live_out[node]:
                        live_in[node], live_out[node] = new_in, out
                        changed = True
            return live_in, live_out

        # Instructions whose results are read by nothing, even with every register live at
        # the exits, do not make their operands live. Dropping one can strand another.
        candidates = set()
        for node in g['order']:
            e = self.eff[node[0]]
            if (e.kind == 'seq' and not e.store and e.dfn and not e.note and not e.swap
                    and not e.push and not e.pop and self.instr[node[0]][0] not in NOT_PURE):
                candidates.add(node)
        everything = {a: ALL for a in ret_addrs_of(g, self.eff)}
        dead = set()
        for _ in range(6):
            _, all_out = liveness(everything, dead)
            now = {n for n in candidates if not (self.node_effect(n)[1] & all_out[n])}
            if now == dead:
                break
            dead = now
        own_in, _ = liveness({}, dead)
        _, ctx_out = liveness(exit_live, dead)
        return {'use': own_in[g['start']], 'must': must, 'may': may,
                'live_out': ctx_out, 'notes': notes}

    def solve(self):
        for a in self.entries:
            self.graph[a] = self.build(a)
        exit_live = {}
        ret_addrs = {a: {n[0] for n in g['order'] if self.eff[n[0]].kind == 'ret'}
                     for a, g in self.graph.items()}
        results = {}
        for _ in range(40):
            results = {a: self.analyze_entry(a, exit_live) for a in self.entries}
            summary = {a: {'use': r['use'], 'must': r['must'], 'may': r['may']}
                       for a, r in results.items()}
            new_exit = defaultdict(set)
            after = defaultdict(set)
            for caller, r in results.items():
                for node in self.graph[caller]['order']:
                    addr, exx, exaf = node
                    e = self.eff[addr]
                    if e.kind == 'call' and e.target in self.summary:
                        live = ren_set(r['live_out'][node], exx, exaf)
                        after[e.target] |= live
                        for ra in ret_addrs[e.target]:
                            new_exit[ra] |= live
            new_exit = {k: frozenset(v) for k, v in new_exit.items()}
            if summary == self.summary and new_exit == exit_live:
                break
            self.summary, exit_live = summary, new_exit
        self.results = results
        self.after = {a: frozenset(v) for a, v in after.items()}
        return results


def fold(regs):
    """Show H+L as HL, D+E as DE, B+C as BC, A+F as AF; leave the rest."""
    left, out = set(regs), []
    for pair, (hi, lo) in (('HL', ('H', 'L')), ('DE', ('D', 'E')), ('BC', ('B', 'C'))):
        if hi in left and lo in left:
            out.append(pair)
            left -= {hi, lo}
        elif hi + "'" in left and lo + "'" in left:
            out.append(pair + "'")
            left -= {hi + "'", lo + "'"}
    return out + sorted(left)


def ctl_rows(path, prog):
    rows = defaultdict(lambda: {'I': [], 'O': []})
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = ROW_RE.match(line)
            if m and not re.match(r'^R \S+ \S+ unchanged\b', line):
                rows[prog.first_code(int(m.group(1), 16))][m.group(2)].append(m.group(3))
    return rows


def expand_row(tokens):
    out = set()
    for t in tokens:
        if t.upper() in FLAG_TOKENS and t != 'C':
            out.add('F')
        elif t in PAIR:
            out |= set(PAIR[t])
        elif t.rstrip("'") in PAIR:
            out |= {h + "'" for h in PAIR[t.rstrip("'")]}
        else:
            out.add(t)
    return out


def main():
    ap = argparse.ArgumentParser(usage='register_usage.py SKOOL [--ctl CTL] [--all] [--notes]',
                                 description=__doc__.split('\n\n')[0])
    ap.add_argument('skool', help='the .skool to analyze')
    ap.add_argument('--ctl', help='compare against the R rows of this .ctl and list only '
                                  'the routines that differ')
    ap.add_argument('--all', action='store_true',
                    help='list every routine, differing or not')
    ap.add_argument('--notes', action='store_true',
                    help='also print the notes each routine collected')
    args = ap.parse_args()

    prog = Program(args.skool)
    results = prog.solve()
    rows = ctl_rows(args.ctl, prog) if args.ctl else {}
    for a in prog.entries:
        r = results[a]
        ins = set(r['use'])
        outs = set(prog.after.get(a, frozenset())) & set(r['may'])
        have_in = expand_row(rows[a]['I']) if a in rows else set()
        have_out = expand_row(rows[a]['O']) if a in rows else set()
        differs = args.ctl and (ins != have_in or outs != have_out)
        if not (args.all or (differs if args.ctl else (ins or outs))):
            continue
        tag = ''
        if args.ctl:
            tag = ' DIFF' if differs else ' ok'
        print(f'${a:04X}  in: {" ".join(fold(ins)) or "-"}  out: {" ".join(fold(outs)) or "-"}'
              f'   rows: in {" ".join(rows[a]["I"]) if a in rows and rows[a]["I"] else "-"}'
              f' / out {" ".join(rows[a]["O"]) if a in rows and rows[a]["O"] else "-"}{tag}')
        if args.notes and r['notes']:
            print(f'        notes: {"; ".join(sorted(r["notes"]))}')


if __name__ == '__main__':
    sys.exit(main())
