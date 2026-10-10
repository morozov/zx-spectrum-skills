#!/usr/bin/env python3
"""Report every listing comment that runs longer than the code rows it explains.

An entry page lays each comment group out as its own grid: one fixed track per
instruction row and a trailing auto track. A comment that fits its rows leaves
the auto track empty; one that does not opens space under the group's last
instruction. Only a browser knows how many lines a comment wraps to, so this
loads every built entry page in headless Chrome and, for each tbody.group,
compares the group's rendered height with the sum of its fixed tracks.

It is a report, not a gate: an overflowing note keeps its place beside the code,
and the list is the to-do list for the notes worth shortening. It always exits 0.
Without a Chrome binary, or on a site whose listing is not laid out in groups,
it says that it skipped and why.

Usage: report_comment_fit.py <html-dir>

Chrome is looked up as $CHROME, then on PATH (google-chrome, google-chrome-stable,
chromium, chromium-browser, chrome), then at the stock macOS install path.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CANDIDATES = ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome')
MAC_CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

# The harness loads each page into one iframe in turn, at the desktop width the
# site is designed for, and writes what it measured into its own DOM, which
# --dump-dom prints. Measuring after document.fonts.ready keeps a late webfont
# from changing the line count after the fact.
HARNESS = '''<!doctype html><meta charset="utf-8">
<iframe id="f" style="width:1280px;height:900px;border:0"></iframe>
<pre id="out"></pre>
<script>
const pages = %s;
const out = [];
const f = document.getElementById('f');
function px(v) { return parseFloat(v) || 0; }
function next(i) {
  if (i >= pages.length) {
    document.getElementById('out').textContent = 'RESULT ' + JSON.stringify(out);
    return;
  }
  f.onload = function () {
    const doc = f.contentDocument;
    doc.fonts.ready.then(function () {
      const groups = doc.querySelectorAll('table.disassembly > tbody.group');
      const rec = {page: pages[i][1], groups: groups.length, over: []};
      groups.forEach(function (tb) {
        const rows = parseInt(tb.style.getPropertyValue('--rows'), 10) || 0;
        const tracks = getComputedStyle(tb).gridTemplateRows.split(' ').map(px);
        let fixed = 0;
        for (let k = 0; k < rows && k < tracks.length; k++) fixed += tracks[k];
        const excess = tb.getBoundingClientRect().height - fixed;
        if (excess > 0.5) {
          const a = tb.querySelector('td[class^="address-"]');
          rec.over.push([a ? a.textContent.trim() : '?', rows, Math.round(excess)]);
        }
      });
      out.push(rec);
      next(i + 1);
    });
  };
  f.src = pages[i][0];
}
next(0);
</script>
'''


def find_chrome():
    env = os.environ.get('CHROME')
    if env:
        return env if (os.path.isfile(env) or shutil.which(env)) else None
    for name in CANDIDATES:
        path = shutil.which(name)
        if path:
            return path
    return MAC_CHROME if os.path.isfile(MAC_CHROME) else None


def main():
    if len(sys.argv) != 2:
        sys.exit('usage: report_comment_fit.py <html-dir>')
    root = Path(sys.argv[1]).resolve()
    pages = sorted(p for p in root.rglob('*.html') if p.parent.name == 'asm')
    if not pages:
        print('comment fit: skipped - no entry pages under %s.' % root)
        return
    chrome = find_chrome()
    if chrome is None:
        print('comment fit: skipped - no Chrome binary found ($CHROME, PATH, or the macOS '
              'install path), and only a browser can measure how a comment wraps.')
        return

    listing = [[p.as_uri(), str(p.relative_to(root))] for p in pages]
    with tempfile.TemporaryDirectory() as tmp:
        harness = Path(tmp, 'harness.html')
        harness.write_text(HARNESS % json.dumps(listing), encoding='utf-8')
        cmd = [chrome, '--headless=new', '--disable-gpu', '--allow-file-access-from-files',
               '--user-data-dir=' + str(Path(tmp, 'profile')), '--window-size=1400,1000',
               '--virtual-time-budget=%d' % (len(pages) * 2000), '--dump-dom', harness.as_uri()]
        try:
            run = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except (OSError, subprocess.TimeoutExpired) as e:
            print('comment fit: skipped - Chrome did not finish (%s).' % e)
            return
    m = re.search(r'RESULT (\[.*\])', run.stdout)
    if not m:
        print('comment fit: skipped - Chrome returned no measurement (exit %d).' % run.returncode)
        return
    import html
    records = json.loads(html.unescape(m.group(1)))
    if len(records) != len(pages):
        print('comment fit: skipped - measured %d of %d pages.' % (len(records), len(pages)))
        return
    if not any(r['groups'] for r in records):
        print('comment fit: skipped - no page lays its listing out in tbody.group blocks.')
        return

    total = 0
    pages_over = 0
    for r in records:
        if not r['over']:
            continue
        pages_over += 1
        for address, rows, excess in r['over']:
            total += 1
            print('  %s  %s  rows=%d  +%dpx' % (r['page'], address, rows, excess))
    groups = sum(r['groups'] for r in records)
    print('comment fit: %d of %d comment group(s) run past their rows, on %d of %d page(s). '
          'Report only - the gate does not fail on it.' % (total, groups, pages_over, len(pages)))


if __name__ == '__main__':
    main()
