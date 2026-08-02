#!/usr/bin/env python3
"""Minimal libfusex driver: boot a ZX Spectrum program, send keystrokes, step
frames, read the 256x192 screen, peek/poke RAM. The play/input/screen half of the
zx-fuse-driver skill (the gdbserver half is gdb.sh / gdb-session.py).

FuseX supplies the library and the ROMs. Both resolve from its install:
FuseX.app in ~/Applications or /Applications on macOS. On Linux, set FUSEX_LIB
and FUSEX_ROMS to a --with-null-ui build (/usr/lib/libfusex.so and
/usr/share/fusex are tried when unset). Both override the defaults anywhere.

As a library:
    from fuse_drive import Fuse
    f = Fuse().boot_media("/abs/game.tap")   # boots + steps past the tape load
    f.tap('p'); scr = f.screen()             # press P, read the screen
    f.save_png("/tmp/frame.png")

CLI smoke test:
    fuse_drive.py MEDIA [frames]   # boot, step, save /tmp/fuse_screen.png, report

Headless gdbserver, running at the Spectrum's speed until killed:
    fuse_drive.py gdbserver PORT [FUSEX ARGS...]
    fuse_drive.py gdbserver 1337 --tape=/abs/game.tzx --auto-load

The C emulator allows one boot per process.
"""
import ctypes
import os
import sys
import time
from pathlib import Path

W, H = 256, 192


_MACOS_PREFIXES = (Path.home() / "Applications", Path("/Applications"))

# Fuse's keyboard_key_name: printable keys are their ASCII codes.
KEY_ENTER, KEY_CAPS, KEY_SYMBOL = 0x100, 0x101, 0x102


class _DisplayInfo(ctypes.Structure):
    _fields_ = [("width", ctypes.c_int), ("height", ctypes.c_int),
                ("border_width", ctypes.c_int), ("border_height", ctypes.c_int)]


class _DisplayFrame(ctypes.Structure):
    _fields_ = [("pixels", ctypes.POINTER(ctypes.c_uint8)),
                ("generation", ctypes.c_uint64)]


def _installed(macos, linux):
    if sys.platform == "darwin":
        candidates = [prefix / macos for prefix in _MACOS_PREFIXES]
    elif sys.platform == "linux":
        candidates = [Path(linux)]
    else:
        candidates = []
    return next((c for c in candidates if c.exists()), None)


def resolve_lib():
    named = os.environ.get("FUSEX_LIB")
    return Path(named) if named else _installed(
        "FuseX.app/Contents/Frameworks/libfusex.dylib", "/usr/lib/libfusex.so")


def resolve_roms():
    named = os.environ.get("FUSEX_ROMS")
    return Path(named) if named else _installed(
        "FuseX.app/Contents/Resources", "/usr/share/fusex")


class Fuse:
    def __init__(self, libpath=None, rom_dir=None):
        libpath = libpath or resolve_lib()
        self.rom_dir = rom_dir or resolve_roms()
        if libpath is None or self.rom_dir is None:
            raise RuntimeError("FuseX is not installed; set FUSEX_LIB and FUSEX_ROMS")
        lib = ctypes.CDLL(str(libpath))
        lib.fuse_init.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_char_p)]
        lib.fuse_init.restype = ctypes.c_int
        lib.spectrum_do_frame.argtypes = []
        lib.keyboard_press.argtypes = [ctypes.c_int]
        lib.keyboard_release.argtypes = [ctypes.c_int]
        lib.fusex_display_info.restype = ctypes.POINTER(_DisplayInfo)
        lib.fusex_display_frame.restype = ctypes.POINTER(_DisplayFrame)
        lib.fusex_peek.argtypes = [ctypes.c_int]; lib.fusex_peek.restype = ctypes.c_int
        lib.writebyte_internal.argtypes = [ctypes.c_uint16, ctypes.c_uint8]
        lib.snapshot_write.argtypes = [ctypes.c_char_p]; lib.snapshot_write.restype = ctypes.c_int
        lib.snapshot_read.argtypes = [ctypes.c_char_p]; lib.snapshot_read.restype = ctypes.c_int
        self.lib = lib
        self._argv = None

    # --- boot ---------------------------------------------------------------
    def boot(self, *args):
        """Boot with raw FuseX CLI args (program name is prepended)."""
        argv = [b"fusex", b"--no-banner", b"--rom-dir", str(self.rom_dir).encode()]
        argv += [a.encode() if isinstance(a, str) else a for a in args]
        # fuse_init keeps argv, so it must outlive the call.
        self._argv = (ctypes.c_char_p * len(argv))(*argv)
        rc = self.lib.fuse_init(len(argv), self._argv)
        if rc != 0:
            raise RuntimeError(f"fuse_init failed (rc={rc}) for {argv}")
        return self

    def boot_media(self, path, autoload=True, load_frames=2500):
        """Boot a tape/snapshot and step past the load. Tapes need autoload."""
        args = ["--auto-load", path] if autoload else [path]
        self.boot(*args)
        self.step(load_frames)
        return self

    # --- control ------------------------------------------------------------
    def step(self, n_frames):
        for _ in range(int(n_frames)):
            self.lib.spectrum_do_frame()

    def key_down(self, ch):
        self.lib.keyboard_press(ord(ch) if isinstance(ch, str) else int(ch))

    def key_up(self, ch):
        self.lib.keyboard_release(ord(ch) if isinstance(ch, str) else int(ch))

    def tap(self, ch, hold=4, after=4):
        """Hold a key for `hold` frames, release, then `after` frames."""
        self.key_down(ch); self.step(hold)
        self.key_up(ch); self.step(after)

    # --- observation --------------------------------------------------------
    def screen(self):
        """256x192 palette indices (0-15) as an ndarray (192,256); numpy required."""
        import numpy as np
        info = self.lib.fusex_display_info().contents
        frame = self.lib.fusex_display_frame().contents
        pixels = np.ctypeslib.as_array(frame.pixels, shape=(info.width * info.height,))
        display = pixels.reshape(info.height, info.width)
        top, left = info.border_height, info.border_width
        return display[top:top + H, left:left + W].copy()

    @staticmethod
    def to_rgb(scr):
        import numpy as np
        lut = np.array([[(255 if i & 8 else 192) if i & b else 0
                         for b in (2, 4, 1)] for i in range(16)], np.uint8)
        return lut[scr & 15]

    def save_png(self, path, scale=2):
        from PIL import Image
        img = Image.fromarray(self.to_rgb(self.screen()), "RGB")
        if scale != 1:
            img = img.resize((W * scale, H * scale), Image.NEAREST)
        img.save(path)
        return path

    # --- memory / state -----------------------------------------------------
    def peek(self, addr):
        return self.lib.fusex_peek(int(addr))

    def poke(self, addr, val):
        self.lib.writebyte_internal(int(addr), int(val) & 0xFF)

    def save(self, path):
        self.lib.snapshot_write(path.encode() if isinstance(path, str) else path)

    def reset(self, snapshot):
        self.lib.snapshot_read(snapshot.encode() if isinstance(snapshot, str) else snapshot)


def _serve_gdb(port, args):
    f = Fuse().boot("--gdbserver-enable", f"--gdbserver-port={port}", *args)
    frame = 1 / 50
    deadline = time.monotonic()
    while True:
        f.lib.spectrum_do_frame()
        # A frame held at a breakpoint is not made up afterwards.
        now = time.monotonic()
        deadline = max(deadline + frame, now)
        time.sleep(deadline - now)


def _main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "gdbserver":
        if len(sys.argv) < 3:
            sys.exit(__doc__)
        _serve_gdb(int(sys.argv[2]), sys.argv[3:])
    media = sys.argv[1]
    frames = int(sys.argv[2]) if len(sys.argv) > 2 else 2500
    f = Fuse().boot_media(media, load_frames=frames)
    scr = f.screen()
    lit = int((scr != scr[0, 0]).sum())          # pixels differing from the corner (bg)
    out = "/tmp/fuse_screen.png"
    f.save_png(out)
    print(f"booted {media}: stepped {frames} frames, {lit} non-background pixels")
    print(f"screen {W}x{H}, saved {out}")


if __name__ == "__main__":
    _main()
