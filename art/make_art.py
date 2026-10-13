#!/usr/bin/env python3
# SPDX-License-Identifier: MIT  (Copyright (c) 2026 Ariel Juszczyk, see LICENSE)
"""Setup86 artwork: pixel-art floppy icon, avatar and GitHub social preview.
Drawn pixel by pixel at 64x64 (the icon) and scaled with nearest-neighbour, so every
size stays crisp. Colours are MENU.EXE's palette. Run: python3 make_art.py"""
from PIL import Image, ImageDraw
import os
OUT = os.path.dirname(os.path.abspath(__file__))
V = lambda r, g, b: (r * 4 + r // 16, g * 4 + g // 16, b * 4 + b // 16, 255)   # VGA 6-bit -> 8-bit
BG, PANEL, BAR, BARTX, BORDER, PROG, TITLE = (V(2, 4, 14), V(5, 8, 22), V(10, 18, 38), V(50, 54, 63),
                                              V(28, 36, 56), V(24, 44, 63), V(63, 52, 20))
OUTL = (10, 10, 18, 255)
BODY, BODY_HI, BODY_LO = (38, 42, 60, 255), (66, 72, 98, 255), (24, 26, 38, 255)
MET, MET_HI, MET_LO = (178, 184, 198, 255), (222, 226, 236, 255), (120, 126, 142, 255)
LABEL, LABEL_LO = (240, 236, 218, 255), (206, 200, 178, 255)
RED, RED_LO = (214, 40, 40, 255), (130, 20, 24, 255)

FONT = {  # 5x7
 'A': "01110 10001 10001 11111 10001 10001 10001", 'B': "11110 10001 10001 11110 10001 10001 11110",
 'C': "01110 10001 10000 10000 10000 10001 01110", 'D': "11110 10001 10001 10001 10001 10001 11110",
 'E': "11111 10000 10000 11110 10000 10000 11111", 'F': "11111 10000 10000 11110 10000 10000 10000",
 'G': "01110 10001 10000 10111 10001 10001 01111", 'H': "10001 10001 10001 11111 10001 10001 10001",
 'I': "01110 00100 00100 00100 00100 00100 01110", 'J': "00111 00010 00010 00010 00010 10010 01100",
 'K': "10001 10010 10100 11000 10100 10010 10001", 'L': "10000 10000 10000 10000 10000 10000 11111",
 'M': "10001 11011 10101 10101 10001 10001 10001", 'N': "10001 10001 11001 10101 10011 10001 10001",
 'O': "01110 10001 10001 10001 10001 10001 01110", 'P': "11110 10001 10001 11110 10000 10000 10000",
 'Q': "01110 10001 10001 10001 10101 10010 01101", 'R': "11110 10001 10001 11110 10100 10010 10001",
 'S': "01111 10000 10000 01110 00001 00001 11110", 'T': "11111 00100 00100 00100 00100 00100 00100",
 'U': "10001 10001 10001 10001 10001 10001 01110", 'V': "10001 10001 10001 10001 10001 01010 00100",
 'W': "10001 10001 10001 10101 10101 10101 01010", 'X': "10001 10001 01010 00100 01010 10001 10001",
 'Y': "10001 10001 01010 00100 00100 00100 00100", 'Z': "11111 00001 00010 00100 01000 10000 11111",
 '0': "01110 10001 10011 10101 11001 10001 01110", '1': "00100 01100 00100 00100 00100 00100 01110",
 '2': "01110 10001 00001 00010 00100 01000 11111", '3': "11110 00001 00001 01110 00001 00001 11110",
 '4': "00010 00110 01010 10010 11111 00010 00010", '5': "11111 10000 11110 00001 00001 10001 01110",
 '6': "00110 01000 10000 11110 10001 10001 01110", '7': "11111 00001 00010 00100 01000 01000 01000",
 '8': "01110 10001 10001 01110 10001 10001 01110", '9': "01110 10001 10001 01111 00001 00010 01100",
 ',': "00000 00000 00000 00000 00110 00100 01000", '.': "00000 00000 00000 00000 00000 01100 01100",
 '&': "01100 10010 10100 01000 10101 10010 01101", '-': "00000 00000 00000 11111 00000 00000 00000",
 ':': "00000 01100 01100 00000 01100 01100 00000", '/': "00001 00010 00010 00100 01000 01000 10000",
 ' ': "00000 00000 00000 00000 00000 00000 00000"}

def text(px, x, y, s, col, k=1, shadow=None, off=None):
    off = k if off is None else off
    for ch in s:
        rows = FONT[ch].split()
        for r, row in enumerate(rows):
            for c, b in enumerate(row):
                if b == '1':
                    for dy in range(k):
                        for dx in range(k):
                            if shadow: px[x + c * k + dx + off, y + r * k + dy + off] = shadow
                    for dy in range(k):
                        for dx in range(k): px[x + c * k + dx, y + r * k + dy] = col
        x += 6 * k
    return x

def rect(d, x0, y0, x1, y1, c): d.rectangle([x0, y0, x1, y1], fill=c)

def floppy():
    """64x64, transparent background."""
    im = Image.new('RGBA', (64, 64), (0, 0, 0, 0)); d = ImageDraw.Draw(im); px = im.load()
    # outline + body, top-right corner cut like a real 3.5" disk
    body = [(5, 4), (54, 4), (59, 9), (59, 59), (5, 59)]
    d.polygon([(4, 3), (55, 3), (60, 8), (60, 60), (4, 60)], fill=OUTL)
    d.polygon(body, fill=BODY)
    rect(d, 5, 4, 53, 4, BODY_HI); rect(d, 5, 4, 5, 59, BODY_HI)              # light top/left edge
    d.line([(54, 4), (59, 9)], fill=BODY_HI)
    rect(d, 6, 59, 59, 59, BODY_LO); rect(d, 59, 9, 59, 59, BODY_LO)          # dark bottom/right edge
    # metal shutter
    rect(d, 17, 4, 47, 22, OUTL)
    rect(d, 18, 4, 46, 21, MET); rect(d, 18, 4, 46, 5, MET_HI); rect(d, 18, 4, 19, 21, MET_HI)
    rect(d, 18, 21, 46, 21, MET_LO); rect(d, 45, 4, 46, 21, MET_LO)
    rect(d, 35, 7, 41, 18, OUTL); rect(d, 36, 8, 40, 17, BODY_LO)             # slot window
    rect(d, 36, 8, 40, 8, BODY)                                               # its inner edge
    rect(d, 13, 6, 15, 20, BODY_LO)                                           # groove left of the shutter
    # label
    rect(d, 10, 24, 54, 58, OUTL)
    rect(d, 11, 25, 53, 57, LABEL)
    rect(d, 11, 25, 53, 28, PROG); rect(d, 11, 29, 53, 29, BORDER)            # blue stripe
    rect(d, 52, 30, 53, 57, LABEL_LO); rect(d, 11, 57, 53, 57, LABEL_LO)      # label shade
    text(px, 18, 32, 'SETUP', BAR)
    # big "86" (2x font) with a dark drop shadow
    text(px, 21, 41, '86', RED_LO, 2); text(px, 20, 40, '86', RED, 2)
    return im

def on_bg(icon, size, bg=BG, frac=0.82):
    """Square image: the icon centred on the menu's background colour."""
    img = Image.new('RGBA', (size, size), bg)
    k = int(size * frac) // 64 * 64 or 64
    ic = icon.resize((k, k), Image.NEAREST)
    img.alpha_composite(ic, ((size - k) // 2, (size - k) // 2))
    return img

def preview(icon):
    """1280x640 GitHub social preview."""
    W, H = 1280, 640
    img = Image.new('RGBA', (W, H), BG); d = ImageDraw.Draw(img)
    rect(d, 0, 0, W - 1, 47, BAR); rect(d, 0, H - 48, W - 1, H - 1, BAR)     # menu-style bars
    img.alpha_composite(icon.resize((448, 448), Image.NEAREST), (64, 96))
    small = Image.new('RGBA', (W, H), (0, 0, 0, 0)); px = small.load()
    # wordmark 5x7 font at 14x, tagline at 5x (drawn on a separate layer)
    text(px, 560, 150, 'SETUP86', TITLE, 14, shadow=BAR, off=6)
    text(px, 564, 330, 'DISC BUILDER, INSTALLER', BARTX, 4)
    text(px, 564, 372, 'AND MENU FOR REAL X86 PCS', BARTX, 4)
    text(px, 564, 450, 'FREE & OPEN SOURCE', PROG, 4)
    img.alpha_composite(small)
    return img

if __name__ == '__main__':
    ic = floppy()
    ic.resize((512, 512), Image.NEAREST).save(os.path.join(OUT, 'setup86-icon-512.png'))
    for s in (256, 128, 64):
        ic.resize((s, s), Image.NEAREST).save(os.path.join(OUT, 'setup86-icon-%d.png' % s))
    on_bg(ic, 500).convert('RGB').save(os.path.join(OUT, 'setup86-avatar-500.png'))
    preview(ic).convert('RGB').save(os.path.join(OUT, 'setup86-social-1280x640.png'))
    print('written to', OUT)
