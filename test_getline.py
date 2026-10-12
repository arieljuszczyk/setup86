# SPDX-License-Identifier: MIT  (Copyright (c) 2026 Ariel Juszczyk, see LICENSE)
# Emulates GETLINE.COM (unicorn CPU emulator, fake BIOS/DOS calls) with typed keys.
# Usage: python test_getline.py GETLINE.COM   (pip install unicorn)
import sys
from unicorn import *
from unicorn.x86_const import *
COM = open(sys.argv[1], 'rb').read()
def run(tail, keys):
    mu = Uc(UC_ARCH_X86, UC_MODE_16)
    SEG = 0x1000; base = SEG * 16
    mu.mem_map(0, 0x100000)
    t = tail.encode()
    mu.mem_write(base + 0x80, bytes([len(t)]) + t + b'\r')
    mu.mem_write(base + 0x100, COM)
    for r in (UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS):
        mu.reg_write(r, SEG)
    mu.reg_write(UC_X86_REG_SP, 0xFFFE)
    keys = list(keys); screen = []; files = {}; st = {'exit': None, 'h': {}}
    def intr(mu, no, ud):
        ah = mu.reg_read(UC_X86_REG_AH)
        if no == 0x16:
            mu.reg_write(UC_X86_REG_AX, ord(keys.pop(0)))
        elif no == 0x10:
            screen.append(chr(mu.reg_read(UC_X86_REG_AL)))
        elif no == 0x21:
            dx = mu.reg_read(UC_X86_REG_DX)
            if ah == 0x3C:
                name = bytes(mu.mem_read(base + dx, 80)).split(b'\0')[0].decode()
                files[name] = b''; st['h'][5] = name
                mu.reg_write(UC_X86_REG_AX, 5)
                mu.reg_write(UC_X86_REG_EFLAGS, mu.reg_read(UC_X86_REG_EFLAGS) & ~1)
            elif ah == 0x40:
                n = mu.reg_read(UC_X86_REG_CX)
                files[st['h'][mu.reg_read(UC_X86_REG_BX)]] += bytes(mu.mem_read(base + dx, n))
                mu.reg_write(UC_X86_REG_AX, n)
            elif ah == 0x3E:
                pass
            elif ah == 0x09:
                screen.append(bytes(mu.mem_read(base + dx, 80)).split(b'$')[0].decode())
            elif ah == 0x4C:
                st['exit'] = mu.reg_read(UC_X86_REG_AL); mu.emu_stop()
    mu.hook_add(UC_HOOK_INTR, intr)
    mu.emu_start(base + 0x100, base + 0x10000, count=100000)
    return st['exit'], files, ''.join(screen)
tests = [
  ('C:\\_GL.BAT N', '12\r', b'SET N=12\r\n'),
  ('C:\\_GL.BAT D', 'c:\\juegos\\ckeen1\\\r', b'SET D=C:\\JUEGOS\\CKEEN1\r\n'),
  ('C:\\_GL.BAT D', 'c:\\jux\x08egos\r', b'SET D=C:\\JUEGOS\r\n'),
  ('C:\\_GL.BAT D', '\x08\x08abc\x1b', b'SET D=\r\n'),
  ('C:\\_GL.BAT D', '\r', b'SET D=\r\n'),
  ('  C:\\_GL.BAT   DEST  ', 'x\r', b'SET DEST=X\r\n'),
]
ok = True
for tail, keys, want in tests:
    code, files, scr = run(tail, keys)
    got = files.get('C:\\_GL.BAT')
    good = code == 0 and got == want
    ok &= good
    print('OK ' if good else 'BAD', repr(tail), repr(keys), '->', code, got, repr(scr))
code, files, scr = run('C:\\_GL.BAT', '')
print('usage test:', code, files, repr(scr)); ok &= code == 1 and not files
print('ALL OK' if ok else 'FAILURES')
