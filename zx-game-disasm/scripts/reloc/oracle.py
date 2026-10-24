#!/usr/bin/env python3
"""
Dump a per-frame state trace of a snapshot run under libfusex.

The relocation proof's oracle. It loads the snapshot, checks that memory holds
the image it was made from, plays a key script from the project's TOML config,
and records the config's `regions` and a SHA-256 of the screen every frame.
Two builds that behave alike give identical dumps; compare.py diffs them.

A script is a list of [key, frames held] under [scripts]; "" holds no key. The
library comes from $FUSEX_LIB, else FuseX's installed copy, and the ROMs from
$FUSEX_ROMS, else FuseX's. The emulator initializes once per process, so run
each image in its own process.

Usage:
    oracle.py SNAPSHOT IMAGE OUT --config TOML --script NAME --org ORG [--png PATH]
"""

import argparse
import ctypes
import hashlib
import os
import sys
import tomllib


def installed(macos, linux):
    if sys.platform == 'darwin':
        candidates = [os.path.join(prefix, macos) for prefix in
                      (os.path.expanduser('~/Applications'), '/Applications')]
    elif sys.platform == 'linux':
        candidates = [linux]
    else:
        candidates = []
    return next((c for c in candidates if os.path.exists(c)), candidates[0] if candidates else '')


LIB = os.environ.get('FUSEX_LIB') or installed(
    'FuseX.app/Contents/Frameworks/libfusex.dylib', '/usr/lib/libfusex.so')
ROMS = os.environ.get('FUSEX_ROMS') or installed(
    'FuseX.app/Contents/Resources', '/usr/share/fusex')


class DisplayInfo(ctypes.Structure):
    _fields_ = [('width', ctypes.c_int), ('height', ctypes.c_int),
                ('border_width', ctypes.c_int), ('border_height', ctypes.c_int)]


class DisplayFrame(ctypes.Structure):
    _fields_ = [('pixels', ctypes.POINTER(ctypes.c_uint8)),
                ('generation', ctypes.c_uint64)]


def load_library():
    lib = ctypes.CDLL(LIB)
    c_int, c_char_p = ctypes.c_int, ctypes.c_char_p
    lib.fuse_init.argtypes = [c_int, ctypes.POINTER(c_char_p)]
    lib.fuse_init.restype = c_int
    lib.spectrum_do_frame.argtypes = []
    lib.keyboard_press.argtypes = [c_int]
    lib.keyboard_release.argtypes = [c_int]
    lib.snapshot_read.argtypes = [c_char_p]
    lib.snapshot_read.restype = c_int
    lib.fusex_peek.argtypes = [ctypes.c_uint16]
    lib.fusex_peek.restype = ctypes.c_uint8
    lib.fusex_display_info.restype = ctypes.POINTER(DisplayInfo)
    lib.fusex_display_frame.restype = ctypes.POINTER(DisplayFrame)
    return lib


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split('\n')[0])
    parser.add_argument('snapshot', help='the snapshot to run')
    parser.add_argument('image', help='the image the snapshot was made from')
    parser.add_argument('out', help='the dump to write')
    parser.add_argument('--config', required=True, help='the project\'s relocation TOML')
    parser.add_argument('--script', required=True, help='the [scripts] entry to play')
    parser.add_argument('--org', required=True, type=lambda s: int(s, 0),
                        help='the address of the image\'s first byte')
    parser.add_argument('--png', help='also save the last frame\'s screen here')
    args = parser.parse_args()

    config = tomllib.load(open(args.config, 'rb'))
    regions = config['regions']
    script = config['scripts'][args.script]

    lib = load_library()
    argv = [b'fusex', b'--no-banner', b'--rom-dir', ROMS.encode()]
    cargv = (ctypes.c_char_p * len(argv))(*argv)
    if lib.fuse_init(len(argv), cargv) != 0:
        raise SystemExit('oracle: fuse_init failed')
    if lib.snapshot_read(args.snapshot.encode()) != 0:
        raise SystemExit(f'oracle: cannot read {args.snapshot}')

    def mem(addr, n):
        return bytes(lib.fusex_peek(a) for a in range(addr, addr + n))

    def screen():
        info = lib.fusex_display_info().contents
        frame = lib.fusex_display_frame().contents
        base = ctypes.addressof(frame.pixels.contents)
        return b''.join(
            ctypes.string_at(base + (info.border_height + y) * info.width
                             + info.border_width, 256)
            for y in range(192))

    img = open(args.image, 'rb').read()
    if mem(args.org, len(img)) != img:
        raise SystemExit(f'oracle: memory does not hold {args.image}')

    dump = bytearray()
    frames = 0
    for key, n in script:
        if key:
            lib.keyboard_press(ord(key))
        for _ in range(n):
            lib.spectrum_do_frame()
            frames += 1
            for base, size in regions:
                dump += mem(base, size)
            dump += hashlib.sha256(screen()).digest()
        if key:
            lib.keyboard_release(ord(key))

    open(args.out, 'wb').write(bytes(dump))
    print(f'{args.snapshot}: {frames} frames, {len(dump)} sampled bytes')

    if args.png:
        import numpy as np
        from PIL import Image
        scr = np.frombuffer(screen(), np.uint8).reshape(192, 256)
        lut = np.array([[(255 if i & 8 else 192) if i & b else 0 for b in (2, 4, 1)]
                        for i in range(16)], np.uint8)
        Image.fromarray(lut[scr & 15]).save(args.png)


if __name__ == '__main__':
    main()
