# GETLINE.COM - read a line from the keyboard into a batch variable (MS-DOS 6.x
# batch files have no SET /P).
#   GETLINE <file> <VAR>   writes "SET <VAR>=<typed text>" to <file>; then CALL <file>
# Input is uppercased, a trailing backslash is dropped, Esc gives an empty value.
# Build: as --32 getline.s -o g.o && ld -m elf_i386 -Ttext 0x100 --oformat binary g.o -o GETLINE.COM
        .intel_syntax noprefix
        .code16
        .arch i8086,jumps
        .global _start
_start:
        cld
        mov     si, 0x81            # command tail
        call    skipsp
        mov     [fname], si         # <file>
1:      lodsb
        cmp     al, 13
        je      usage               # no <VAR> given
        cmp     al, ' '
        jne     1b
        mov     byte ptr [si-1], 0  # NUL-terminate file name
        call    skipsp
        mov     di, offset outbuf + 4   # after "SET "
2:      lodsb                       # copy <VAR>
        cmp     al, 13
        je      3f
        cmp     al, ' '
        je      3f
        stosb
        cmp     di, offset outbuf + 40
        jb      2b
3:      cmp     di, offset outbuf + 4
        je      usage
        mov     al, '='
        stosb
        mov     [start], di
key:    xor     ah, ah              # BIOS: wait for key -> AL
        int     0x16
        cmp     al, 13
        je      enter
        cmp     al, 27
        je      escape
        cmp     al, 8
        je      bksp
        cmp     al, ' '
        jb      key
        cmp     di, offset outbuf + 200
        jae     key
        cmp     al, 'a'
        jb      4f
        cmp     al, 'z'
        ja      4f
        sub     al, 32              # uppercase
4:      stosb
        call    putc
        jmp     key
bksp:   cmp     di, [start]
        je      key
        dec     di
        mov     al, 8
        call    putc
        mov     al, ' '
        call    putc
        mov     al, 8
        call    putc
        jmp     key
escape: mov     di, [start]
enter:  cmp     di, [start]         # drop a trailing backslash
        je      5f
        cmp     byte ptr [di-1], '\\'
        jne     5f
        dec     di
5:      mov     al, 13
        call    putc
        mov     al, 10
        call    putc
        mov     ax, 0x0A0D          # CR LF
        stosw
        mov     ah, 0x3C            # DOS: create file
        xor     cx, cx
        mov     dx, [fname]
        int     0x21
        jc      fail
        mov     bx, ax
        mov     ah, 0x40            # DOS: write
        mov     cx, di
        sub     cx, offset outbuf
        mov     dx, offset outbuf
        int     0x21
        mov     ah, 0x3E            # DOS: close
        int     0x21
        mov     ax, 0x4C00
        int     0x21
fail:   mov     dx, offset msgfail
        jmp     6f
usage:  mov     dx, offset msgusage
6:      mov     ah, 9
        int     0x21
        mov     ax, 0x4C01
        int     0x21

putc:   push    bx                  # BIOS teletype (not redirectable)
        mov     ah, 0x0E
        xor     bx, bx
        int     0x10
        pop     bx
        ret

skipsp: lodsb
        cmp     al, ' '
        je      skipsp
        cmp     al, 9
        je      skipsp
        dec     si
        ret

msgusage: .ascii "Usage: GETLINE <file> <VAR>\r\n$"
msgfail:  .ascii "GETLINE: cannot write the temp file\r\n$"
fname:  .word   0
start:  .word   0
outbuf: .ascii  "SET "
