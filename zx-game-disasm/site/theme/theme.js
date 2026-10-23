document.addEventListener('DOMContentLoaded', function () {

  /* ── Disassembly row-group hover ─────────────────────────────── */

  /* :empty skips the cells SkoolKit emits for uncommented rows of an annotated
     entry — highlighting a run that documents nothing claims a comment it has not
     got. The emitted cell holds no whitespace, so :empty matches it. */
  document.querySelectorAll('td.comment-1[rowspan]:not(:empty)').forEach(function (cell) {
    var rowspan = parseInt(cell.getAttribute('rowspan'), 10);

    var rows = [];
    var row = cell.parentElement;
    for (var i = 0; i < rowspan; i++) {
      if (row) { rows.push(row); row = row.nextElementSibling; }
    }

    function on()  { rows.forEach(function (r) { r.classList.add('asm-group-hover'); }); }
    function off() { rows.forEach(function (r) { r.classList.remove('asm-group-hover'); }); }

    rows.forEach(function (r) {
      r.addEventListener('mouseenter', on);
      r.addEventListener('mouseleave', off);
    });
  });

  /* ── Z80 syntax highlighting ─────────────────────────────────── */

  /* The whole tokenizer is here. A built site is a directory of files someone
     opens from disk, so nothing on a page may wait on a fetch: a page whose
     <head> script sits on a host that drops packets does not finish loading at
     all.

     The span class names are highlight.js's — hljs-keyword, hljs-built_in,
     hljs-number, hljs-string, hljs-comment — because that is the vocabulary
     theme.css colors and a project stylesheet may extend. */

  var KEYWORDS = new Set([
    'LD', 'LDD', 'LDI', 'LDIR', 'LDDR',
    'PUSH', 'POP', 'EX', 'EXX',
    'ADD', 'ADC', 'SUB', 'SBC', 'AND', 'OR', 'XOR', 'CP',
    'INC', 'DEC', 'DAA', 'CPL', 'NEG', 'CCF', 'SCF',
    'NOP', 'HALT', 'DI', 'EI', 'IM',
    'RLCA', 'RRCA', 'RLA', 'RRA',
    'RLC', 'RRC', 'RL', 'RR', 'SLA', 'SRA', 'SRL', 'SLL',
    'BIT', 'SET', 'RES',
    'CALL', 'RET', 'RETI', 'RETN', 'JP', 'JR', 'DJNZ', 'RST',
    'CPI', 'CPD', 'CPIR', 'CPDR',
    'INI', 'IND', 'INIR', 'INDR',
    'OUTI', 'OUTD', 'OTIR', 'OTDR',
    'IN', 'OUT',
    'DEFB', 'DEFW', 'DEFM', 'DEFS', 'EQU', 'ORG'
  ]);

  var REGISTERS = new Set([
    'A', 'B', 'C', 'D', 'E', 'H', 'L', 'I', 'R',
    'AF', 'BC', 'DE', 'HL', 'IX', 'IY', 'SP', 'PC',
    'IXH', 'IXL', 'IYH', 'IYL',
    'NZ', 'Z', 'NC', 'PO', 'PE', 'P', 'M'
  ]);

  /* One pass, longest-first: a comment swallows the rest of the line, a quoted
     string its own body, and a $/% prefixed literal is claimed before the bare
     decimal rule can take the digits out of it. A word that is neither mnemonic
     nor register — a label — matches last and is left unwrapped, so it inherits
     td.instruction's own color. */
  var TOKEN = /;[^\n]*|"[^"\n]*"|\$[0-9A-Fa-f]+|%[01]+|[0-9]+|[A-Za-z_][A-Za-z0-9_]*/g;

  function escape(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function tokenClass(text) {
    var c = text.charAt(0);
    if (c === ';') return 'comment';
    if (c === '"') return 'string';
    if (c === '$' || c === '%' || (c >= '0' && c <= '9')) return 'number';
    if (KEYWORDS.has(text)) return 'keyword';
    if (REGISTERS.has(text)) return 'built_in';
    return null;
  }

  function highlight(text) {
    var html = '', last = 0, m;
    TOKEN.lastIndex = 0;
    while ((m = TOKEN.exec(text)) !== null) {
      var cls = tokenClass(m[0]);
      if (cls) {
        html += escape(text.slice(last, m.index));
        html += '<span class="hljs-' + cls + '">' + escape(m[0]) + '</span>';
        last = m.index + m[0].length;
      }
    }
    return html + escape(text.slice(last));
  }

  /* Operands that link are already <a> elements, and the byte values and the
     reference graph were computed before this ran. Only text nodes are
     rewritten, so nothing here can move a link or an address. */
  document.querySelectorAll('td.instruction').forEach(function (cell) {
    var html = '';
    cell.childNodes.forEach(function (node) {
      if (node.nodeType === Node.TEXT_NODE) {
        html += highlight(node.textContent);
      } else {
        html += node.outerHTML;
      }
    });
    cell.innerHTML = html;
  });

  /* ── Previous / next entry keys ──────────────────────────────── */

  /* Left and right arrows follow the navigation row's neighbor links. A key
     pressed with a modifier is left to the browser, where Alt+Left is Back,
     and so is one typed into a form field. */
  var neighbors = {
    ArrowLeft: document.querySelector('table.asm-navigation td.prev a'),
    ArrowRight: document.querySelector('table.asm-navigation td.next a')
  };
  document.addEventListener('keydown', function (event) {
    var link = neighbors[event.key];
    if (!link || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    if (event.target.closest('input, textarea, select, [contenteditable]')) return;
    event.preventDefault();
    window.location.href = link.href;
  });

});
