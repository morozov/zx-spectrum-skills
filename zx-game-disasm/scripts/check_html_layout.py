#!/usr/bin/env python3
"""Gate the built site on two layout defects only a browser can see.

HEADING_WRAP   An h1-h4 whose rendered text runs past 1.5 lines at a 1280 px
               viewport. A heading is a name, and a name that wraps is a
               sentence in a heading's place.
INLINE_RENDER  An <img> whose nearest block-level ancestor holds more than 3
               words of inline text outside the image's own table cell, the
               text that shares the image's line boxes. Text in a nested block,
               such as a caption div under the image, does not count. A render
               belongs in its own block, such as a #UDGTABLE cell, and an image
               set into running text breaks the line it sits in.

Every page under the site directory loads in one headless Chrome, one iframe at
a time, through the same harness shape as `report_comment_fit.py`. Findings are
held against the project baseline like every other gating check, keyed by page
and heading text or image source.

Usage: check_html_layout.py <html-dir> [--baseline FILE] [--write-baseline]
       check_html_layout.py --fixture <page.html>...   (pages named directly)
       check_html_layout.py <html-dir> --screenshot <outdir>

`--screenshot` takes one 1280 px screenshot of each page kind (index, a code
entry, a data entry, a map, a reference page, a buffer page, and each custom
top-level page) for the Challenger's review record, and checks nothing.

Exit 0 when clean, 1 on findings, 2 when the check could not run: no Chrome, or
Chrome returned no measurement. A check that could not run is never clean.
"""
import argparse
import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ctl_baseline  # noqa: E402
from report_comment_fit import find_chrome  # noqa: E402

CHECK = 'html-layout'
WIDTH = 1280
WRAP_LIMIT = 1.5
WORD_LIMIT = 3

HARNESS = '''<!doctype html><meta charset="utf-8">
<iframe id="f" style="width:%(width)dpx;height:900px;border:0"></iframe>
<pre id="out"></pre>
<script>
const pages = %(pages)s;
const out = [];
const f = document.getElementById('f');
const INLINE = /^inline/;
function px(v) { return parseFloat(v) || 0; }
function words(t) { return (t.match(/[A-Za-z0-9][\\w'’-]*/g) || []).length; }
// The text that shares the image's line boxes: inline content of the block,
// leaving out nested blocks and the image's own table cell.
function textOutside(node, skip, win, root) {
  if (node === skip) return '';
  if (node.nodeType === 3) return node.nodeValue;
  if (node.nodeType !== 1) return '';
  const tag = node.tagName;
  if (tag === 'SCRIPT' || tag === 'STYLE') return '';
  if (node !== root && !INLINE.test(win.getComputedStyle(node).display)) return '';
  let s = '';
  for (const c of node.childNodes) s += ' ' + textOutside(c, skip, win, root);
  return s;
}
function next(i) {
  if (i >= pages.length) {
    document.getElementById('out').textContent = 'RESULT ' + JSON.stringify(out);
    return;
  }
  f.onload = function () {
    const doc = f.contentDocument;
    const win = f.contentWindow;
    doc.fonts.ready.then(function () {
      const rec = {page: pages[i][1], wrap: [], inline: []};
      doc.querySelectorAll('h1, h2, h3, h4').forEach(function (h) {
        const cs = win.getComputedStyle(h);
        if (cs.display === 'none' || cs.visibility === 'hidden') return;
        const r = h.getBoundingClientRect();
        if (r.height === 0) return;
        const content = r.height - px(cs.paddingTop) - px(cs.paddingBottom)
                        - px(cs.borderTopWidth) - px(cs.borderBottomWidth);
        let lh = px(cs.lineHeight);
        if (!lh) lh = px(cs.fontSize) * 1.2;
        const lines = content / lh;
        if (!isFinite(lines)) return;
        if (lines > %(limit)s) rec.wrap.push([h.tagName.toLowerCase(), h.textContent.trim().replace(/\\s+/g, ' '), Math.round(lines * 10) / 10]);
      });
      doc.querySelectorAll('img').forEach(function (img) {
        let block = img.parentElement;
        while (block && INLINE.test(win.getComputedStyle(block).display)) block = block.parentElement;
        if (!block) return;
        const cell = img.closest('td, th');
        const skip = (cell && block.contains(cell)) ? cell : null;
        const text = textOutside(block, skip, win, block);
        const n = words(text);
        if (n > %(words)d) rec.inline.push([img.getAttribute('src') || '?', n, text.trim().replace(/\\s+/g, ' ').slice(0, 80)]);
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


def measure(pages, root):
    """Return the per-page records, or an error string when Chrome cannot measure."""
    chrome = find_chrome()
    if chrome is None:
        return 'no Chrome binary found ($CHROME, PATH, or the macOS install path)'
    listing = [[p.as_uri(), str(p.relative_to(root)) if root else p.name] for p in pages]
    with tempfile.TemporaryDirectory() as tmp:
        harness = Path(tmp, 'harness.html')
        harness.write_text(HARNESS % {'width': WIDTH, 'pages': json.dumps(listing),
                                      'limit': WRAP_LIMIT, 'words': WORD_LIMIT}, encoding='utf-8')
        cmd = [chrome, '--headless=new', '--disable-gpu', '--allow-file-access-from-files',
               '--user-data-dir=' + str(Path(tmp, 'profile')), '--window-size=1400,1000',
               '--virtual-time-budget=%d' % (len(pages) * 2000), '--dump-dom', harness.as_uri()]
        try:
            run = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        except (OSError, subprocess.TimeoutExpired) as e:
            return 'Chrome did not finish (%s)' % e
    m = re.search(r'RESULT (\[.*\])', run.stdout)
    if not m:
        return 'Chrome returned no measurement (exit %d)' % run.returncode
    records = json.loads(html.unescape(m.group(1)))
    if len(records) != len(pages):
        return 'Chrome measured %d of %d pages' % (len(records), len(pages))
    return records


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')[:60] or '?'


def findings_of(records):
    out = []
    for r in records:
        for tag, text, lines in r['wrap']:
            out.append((0, 'HEADING_WRAP',
                        '%s "%s" renders on %.1f lines at %d px; a heading holds one line'
                        % (tag, text[:100], lines, WIDTH), r['page'], '%s#%s' % (r['page'], slug(text))))
        for src, n, text in r['inline']:
            out.append((0, 'INLINE_RENDER',
                        'image %s sits in a block with %d words outside its own table cell ("%s"); '
                        'a render takes a block of its own' % (src, n, text), r['page'],
                        '%s#%s' % (r['page'], slug(Path(src).name))))
    return out


def first_link(page, root):
    """The first entry page a map page links to."""
    try:
        text = page.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None
    for href in re.findall(r'href="([^"#]*asm/[^"#]+\.html)', text):
        target = (page.parent / href).resolve()
        if target.is_file():
            return target
    return None


def kinds_of(root):
    """One page of each kind: (name, page)."""
    game = next((d for d in sorted(root.iterdir()) if (d / 'index.html').is_file()), root) \
        if not (root / 'index.html').is_file() else root
    out = [('index', game / 'index.html')]
    for name, mp in (('code-entry', 'routines'), ('data-entry', 'data')):
        page = first_link(game / 'maps' / ('%s.html' % mp), game)
        if page:
            out.append((name, page))
    for sub in ('maps', 'reference', 'buffers'):
        pages = sorted((game / sub).glob('*.html'))
        if pages:
            out.append((sub, pages[0]))
    for page in sorted(game.glob('*.html')):
        if page.name != 'index.html':
            out.append((page.stem.lower(), page))
    return [(n, p) for n, p in out if p.is_file()]


def screenshots(root, outdir):
    chrome = find_chrome()
    if chrome is None:
        print('visual review: COULD NOT RUN – no Chrome binary found.')
        return 2
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    shot = 0
    with tempfile.TemporaryDirectory() as tmp:
        for name, page in kinds_of(root):
            target = outdir / ('%s.png' % name)
            cmd = [chrome, '--headless=new', '--disable-gpu', '--hide-scrollbars',
                   '--allow-file-access-from-files', '--user-data-dir=' + str(Path(tmp, name)),
                   '--window-size=%d,2400' % WIDTH, '--virtual-time-budget=3000',
                   '--screenshot=' + str(target), page.as_uri()]
            try:
                subprocess.run(cmd, capture_output=True, timeout=120)
            except (OSError, subprocess.TimeoutExpired):
                pass
            if target.is_file():
                shot += 1
                print('  %s  %s' % (target, page.relative_to(root)))
            else:
                print('  %s  NOT TAKEN (%s)' % (target, page.relative_to(root)))
    print('visual review: %d screenshot(s) at %d px in %s. List them in the review record\'s '
          'screenshots field.' % (shot, WIDTH, outdir))
    return 0 if shot else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('html', nargs='*', help='the built site directory, or pages with --fixture')
    parser.add_argument('--fixture', action='store_true', help='treat the arguments as pages')
    parser.add_argument('--screenshot', metavar='OUTDIR',
                        help='screenshot one page of each kind into OUTDIR instead of checking')
    ctl_baseline.add_arguments(parser)
    args = parser.parse_args()

    if args.screenshot:
        if len(args.html) != 1 or not Path(args.html[0]).is_dir():
            print('Error: --screenshot needs the built site directory.')
            return 2
        return screenshots(Path(args.html[0]).resolve(), args.screenshot)
    if args.fixture:
        pages = [Path(p).resolve() for p in args.html]
        root = None
    else:
        if len(args.html) != 1 or not Path(args.html[0]).is_dir():
            print('Error: no built site at %s; this check reads the pages the build produced.'
                  % (args.html or ['?'])[0])
            return 2
        root = Path(args.html[0]).resolve()
        pages = sorted(root.rglob('*.html'))
    if not pages:
        print('Error: no pages to measure.')
        return 2

    records = measure(pages, root)
    if isinstance(records, str):
        print('html layout: COULD NOT RUN – %s. Only a browser measures a wrap, so no finding '
              'count exists, and that is not a count of zero.' % records)
        return 2
    findings = findings_of(records)
    token = lambda f: f[4]  # noqa: E731

    if args.write_baseline:
        if not args.baseline:
            print('Error: --write-baseline needs --baseline', file=sys.stderr)
            return 2
        ctl_baseline.report_write(args.baseline, CHECK,
                                  *ctl_baseline.write(args.baseline, CHECK, findings, [], token_of=token))
        return 0

    new, held, stale = ctl_baseline.partition(args.baseline, CHECK, findings, [],
                                              report_stale=not args.ignore_stale, token_of=token)
    if new:
        print('Found %d layout defect(s) in the built pages:' % len(new))
        print()
        for _, kind, message, page, _ in new:
            print('  %s: %s – %s' % (page, kind, message))
        print()
    elif not held and not stale:
        print('html layout: %d page(s) measured at %d px; no heading wraps and no image sits '
              'in running text.' % (len(pages), WIDTH))
    ctl_baseline.report(args.baseline, CHECK, held, stale)
    return 1 if new or stale else 0


if __name__ == '__main__':
    sys.exit(main())
