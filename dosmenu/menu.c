/* MENU.EXE - graphical game installer for the exo486 discs.
 * Copyright (c) 2026 Ariel Juszczyk. MIT License, see LICENSE.
 *
 * VGA 320x200 (mode 13h), runs on any PC with VGA (8086 code, DOS 3.3+).
 * Reads _MENU\MENU.DAT next to the program, shows the game list with a
 * screenshot (_MENU\<GAME>.PIC) and copies the chosen game's folder from
 * the disc to a directory the user types.  F1 shows a help screen, F10
 * switches the screens between English and Spanish.
 *
 * Build (OpenWatcom 2): wcl -q -w4 -bt=dos -ml -0 -os -k12288 -fe=MENU.EXE menu.c
 *
 * Test hook: MENU /T:<file> reads the keys from <file> instead of the
 * keyboard (UP DOWN PGUP PGDN HOME END ENTER ESC BKSP F1 F10 SHOT TEXT:<chars>);
 * SHOT dumps palette + screen to SHOTnn.BIN.  Exits at the end of the file.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <dos.h>
#include <i86.h>
#include <conio.h>
#include <io.h>
#include <fcntl.h>
#include <direct.h>
#include <sys/stat.h>

#define MAXGAMES  400
#define MAXRUN    12
#define SHOT_W    192
#define SHOT_H    120
#define SHOT_X    126
#define SHOT_Y    13
#define LIST_X    2
#define LIST_Y    13
#define ROW_H     9
#define LIST_ROWS 19
#define LIST_W    15            /* characters */

/* UI colours 0-15; the screenshot uses 16-255 */
enum { C_BG, C_PANEL, C_TEXT, C_DIM, C_HILITE, C_HITEXT, C_TITLE, C_BAR,
       C_BARTEXT, C_BORDER, C_OK, C_ERR, C_FIELD, C_FIELDTX, C_PROG, C_BLACK };
static const unsigned char ui_pal[16][3] = {
    { 2,  4, 14}, { 5,  8, 22}, {58, 58, 58}, {38, 40, 46}, {14, 28, 50}, {63, 63, 63},
    {63, 52, 20}, {10, 18, 38}, {50, 54, 63}, {28, 36, 56}, {20, 56, 24}, {60, 18, 16},
    { 0,  0,  0}, {63, 63, 40}, {24, 44, 63}, { 0,  0,  0} };

typedef struct {
    char dir[9], shot[9];
    char far *title, far *shrt, far *year, far *genre, far *genre_es, far *lang;
    unsigned long size;
    int nrun;
    char far *run[MAXRUN];
} Game;

/* ---------- screen texts: English / Spanish (CP437, the VGA font's own accents) ---------- */
enum { S_HEADER, S_FOOTER, S_NOPIC, S_SPANISH, S_ENGLISH, S_PRESS, S_WHERE, S_OKCANCEL, S_BADPATH, S_NODRIVE, S_NEEDS, S_NOSPACE, S_NOMKDIR, S_HASFILES, S_OVERWRITE, S_NOMEM, S_COPYING, S_BUFFER, S_FILES, S_ERRREAD, S_ERRCREATE, S_ERRWRITE, S_STOPPED, S_INCOMPLETE, S_INSTALLED, S_INFILES, S_TOPLAY, S_BYE, S_HELP, S_H_MOVE, S_H_PAGE, S_H_ENDS, S_H_JUMP, S_H_INST, S_H_HELP, S_H_LANG, S_H_QUIT, S_H_NOTE, S_COUNT };
static const char *msgs[2][S_COUNT] = {
    { "DOS GAMES",
      "ENTER Install  F1 Help  ESC Quit",
      "(no picture)",
      "Spanish",
      "English",
      "Press a key",
      "Install to which folder?",
      "ENTER OK   ESC Cancel",
      "Not a valid DOS folder name",
      "That drive is not available",
      "Needs %lu KB, %lu KB free",
      "Not enough free space",
      "Cannot create the folder",
      "The folder already has files.",
      "Copy over them? (Y/N)",
      "Not enough memory to copy",
      "Copying...  (ESC stops)",
      "%u KB buffer",
      "%u / %u files",
      "Cannot read from the disc",
      "Cannot create a file",
      "Disk full or write error",
      "Stopped",
      "The copy is incomplete.",
      "Installed!",
      "%u files in %s",
      "To play it:",
      "Bye!  Run MENU again from the CD to install another game.\n",
      "Help",
      "Move through the list",
      "Page up / down",
      "First / last game",
      "Jump to a game",
      "Install the game",
      "This help",
      "Espa\244ol",
      "Quit",
      "The game is copied to the folder you choose (C:\\JUEGOS\\<GAME> if you just press ENTER). The last screen shows how to start it." },
    { "DOS GAMES",
      "ENTER Instalar  F1 Ayuda  ESC Salir",
      "(sin imagen)",
      "Espa\244ol",
      "Ingl\202s",
      "Pulse una tecla",
      "\250En qu\202 carpeta instalar?",
      "ENTER Aceptar   ESC Cancelar",
      "Nombre de carpeta DOS no v\240lido",
      "Esa unidad no est\240 disponible",
      "Necesita %lu KB, hay %lu KB",
      "No hay espacio suficiente",
      "No se pudo crear la carpeta",
      "La carpeta ya tiene archivos.",
      "\250Copiar encima? (S/N)",
      "Falta memoria para copiar",
      "Copiando...  (ESC detiene)",
      "b\243fer %u KB",
      "%u / %u archivos",
      "No se pudo leer el disco",
      "No se pudo crear un archivo",
      "Disco lleno o error al escribir",
      "Detenido",
      "La copia qued\242 incompleta.",
      "\255Instalado!",
      "%u archivos en %s",
      "Para jugar:",
      "\255Chau! Ejecute MENU desde el CD para instalar otro juego.\n",
      "Ayuda",
      "Moverse por la lista",
      "P\240gina arriba / abajo",
      "Primer / \243ltimo juego",
      "Saltar a un juego",
      "Instalar el juego",
      "Esta ayuda",
      "English",
      "Salir",
      "El juego se copia a la carpeta que elija (C:\\JUEGOS\\<JUEGO> si s\242lo pulsa ENTER). La \243ltima pantalla muestra c\242mo iniciarlo." } };
static int lang;                      /* 0 English, 1 Spanish (F10) */
#define L(id) msgs[lang][id]

/* exit screen, DOOM "ENDOOM" style: a red band with centred yellow text, then the
 * MIT notice (kept in English, see LICENSE). Written straight to text-mode memory. */
static const char *exit_band[] = {
    0,                                    /* the goodbye line, in the screen language */
    "Copyright (c) 2026 Ariel Juszczyk (ariel.juszczyk@gmail.com) - MIT License",
    "exo486 - https://github.com/arieljuszczyk/exo486" };
static const char *license_body[] = {
    "Permission is hereby granted, free of charge, to any person obtaining a copy",
    "of this software and associated documentation files (the \"Software\"), to deal",
    "in the Software without restriction, including without limitation the rights",
    "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell",
    "copies of the Software, and to permit persons to whom the Software is",
    "furnished to do so, subject to the following conditions:",
    "",
    "The above copyright notice and this permission notice shall be included in all",
    "copies or substantial portions of the Software.",
    "",
    "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR",
    "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,",
    "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE",
    "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER",
    "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,",
    "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE",
    "SOFTWARE.",
};

static Game far *games;
static int ngames;
static char label[40], base[80];
static unsigned char far *vga;
static unsigned char far *font;
static unsigned char far *shotbuf;
static FILE *keyfile;
static int shotno;

/* ---------- low level graphics ---------- */

static void set_mode(int m) { union REGS r; r.x.ax = m; int86(0x10, &r, &r); }

static void exit_screen(void)
{
    unsigned short far *t = MK_FP(0xB800, 0);
    union REGS r;
    int i, row;
    for (i = 0; i < 80 * 25; i++) t[i] = 0x0720;              /* grey on black, blank */
    for (i = 0; i < 80 * 5; i++) t[i] = 0x4E20;               /* rows 0-4: yellow on red */
    for (row = 0; row < 3; row++) {
        const char *sp = row ? exit_band[row] : L(S_BYE);
        int n = strcspn(sp, "\n"), x = (80 - n) / 2;
        for (i = 0; i < n; i++) t[(row + 1) * 80 + x + i] = 0x4E00 | (unsigned char)sp[i];
    }
    for (row = 0; row < 17; row++)                            /* rows 6-22 */
        for (i = 0; license_body[row][i]; i++) t[(row + 6) * 80 + i] = 0x0700 | (unsigned char)license_body[row][i];
    r.h.ah = 2; r.h.bh = 0; r.h.dh = 23; r.h.dl = 0;          /* DOS prompt goes below */
    int86(0x10, &r, &r);
    if (keyfile) {                                            /* test hook: dump the text screen */
        FILE *f = fopen("ENDSCR.BIN", "wb");
        if (f) { fwrite(t, 2, 80 * 25, f); fclose(f); }
    }
}

static void vsync(void) { while (inp(0x3DA) & 8); while (!(inp(0x3DA) & 8)); }

static void set_pal(int first, int n, const unsigned char far *rgb)
{
    int i;
    outp(0x3C8, first);
    for (i = 0; i < n * 3; i++) outp(0x3C9, rgb[i]);
}

static void get_font(void)
{
    /* in mode 13h the VGA BIOS points INT 43h at its 8x8 font (all 256 characters) */
    font = (unsigned char far *)_dos_getvect(0x43);
}

static void fill(int x, int y, int w, int h, int c)
{
    int j;
    for (j = 0; j < h; j++) _fmemset(vga + (unsigned)(y + j) * 320 + x, c, w);
}

static void frame(int x, int y, int w, int h, int c)
{
    fill(x, y, w, 1, c); fill(x, y + h - 1, w, 1, c);
    fill(x, y, 1, h, c); fill(x + w - 1, y, 1, h, c);
}

static void text(int x, int y, const char far *s, int fg, int bg, int max)
{
    int n = 0;
    for (; *s && n < max; s++, n++, x += 8) {
        unsigned char ch = (unsigned char)*s;
        const unsigned char far *g;
        int r, b;
        g = font + ch * 8;
        for (r = 0; r < 8; r++) {
            unsigned char far *p = vga + (unsigned)(y + r) * 320 + x;
            for (b = 0; b < 8; b++)
                if (g[r] & (0x80 >> b)) p[b] = fg;
                else if (bg >= 0) p[b] = bg;
        }
    }
}

static void text_c(int y, const char far *s, int fg)   /* centred */
{
    int n = _fstrlen(s); if (n > 40) n = 40;
    text((320 - n * 8) / 2, y, s, fg, -1, 40);
}

/* ---------- keyboard (or test script) ---------- */

enum { K_UP = 0x148, K_DOWN = 0x150, K_PGUP = 0x149, K_PGDN = 0x151,
       K_HOME = 0x147, K_END = 0x14F, K_F1 = 0x13B, K_F10 = 0x144,
       K_ENTER = 13, K_ESC = 27, K_BKSP = 8 };

static char pending[64];
static int npend;

static void dump_screen(void)
{
    char fn[16]; FILE *f; int i;
    sprintf(fn, "SHOT%02d.BIN", shotno++);
    f = fopen(fn, "wb");
    if (!f) return;
    outp(0x3C7, 0);
    for (i = 0; i < 768; i++) fputc(inp(0x3C9), f);
    for (i = 0; i < 200; i++) fwrite(vga + i * 320, 1, 320, f);
    fclose(f);
}

static int getkey(void)
{
    if (keyfile) {
        char tok[80];
        for (;;) {
            if (npend) { int c = (unsigned char)pending[0]; memmove(pending, pending + 1, npend--); return c; }
            if (fscanf(keyfile, "%79s", tok) != 1) return -1;       /* end of script */
            if (!strcmp(tok, "UP")) return K_UP;
            if (!strcmp(tok, "DOWN")) return K_DOWN;
            if (!strcmp(tok, "PGUP")) return K_PGUP;
            if (!strcmp(tok, "PGDN")) return K_PGDN;
            if (!strcmp(tok, "HOME")) return K_HOME;
            if (!strcmp(tok, "END")) return K_END;
            if (!strcmp(tok, "ENTER")) return K_ENTER;
            if (!strcmp(tok, "ESC")) return K_ESC;
            if (!strcmp(tok, "BKSP")) return K_BKSP;
            if (!strcmp(tok, "F1")) return K_F1;
            if (!strcmp(tok, "F10")) return K_F10;
            if (!strcmp(tok, "SHOT")) { dump_screen(); continue; }
            if (!strncmp(tok, "TEXT:", 5)) { strcpy(pending, tok + 5); npend = strlen(pending); continue; }
        }
    } else {
        union REGS r;
        r.h.ah = 0; int86(0x16, &r, &r);
        return r.h.al ? r.h.al : 0x100 + r.h.ah;
    }
}

static int key_waiting(void)
{
    union REGS r;
    if (keyfile) return 0;
    r.h.ah = 1; int86(0x16, &r, &r);
    return !(r.x.cflag & INTR_ZF);
}

/* ---------- data ---------- */

static char far *fdup(const char *s)
{
    char far *p = malloc(strlen(s) + 1);
    if (p) _fstrcpy(p, s);
    return p;
}

static int load_data(void)
{
    char fn[100], line[200];
    FILE *f;
    Game far *g = 0;
    sprintf(fn, "%s_MENU\\MENU.DAT", base);
    f = fopen(fn, "r");
    if (!f) return 0;
    games = malloc(sizeof(Game) * MAXGAMES);
    if (!games) { fclose(f); return 0; }
    while (fgets(line, sizeof line, f)) {
        char *v;
        line[strcspn(line, "\r\n")] = 0;
        v = strchr(line, ' ');
        if (v) *v++ = 0; else v = line + strlen(line);
        if (!strcmp(line, "LABEL")) { strncpy(label, v, 39); }
        else if (!strcmp(line, "GAME") && ngames < MAXGAMES) {
            g = &games[ngames++];
            _fmemset(g, 0, sizeof(Game));
            _fstrncpy(g->dir, v, 8);
        }
        else if (!g) continue;
        else if (!strcmp(line, "TITLE")) g->title = fdup(v);
        else if (!strcmp(line, "SHORT")) g->shrt = fdup(v);
        else if (!strcmp(line, "YEAR")) g->year = fdup(v);
        else if (!strcmp(line, "GENRE")) g->genre = fdup(v);
        else if (!strcmp(line, "GENRE_ES")) g->genre_es = fdup(v);
        else if (!strcmp(line, "LANG")) g->lang = fdup(v);
        else if (!strcmp(line, "SIZE")) g->size = strtoul(v, 0, 10);
        else if (!strcmp(line, "SHOT")) _fstrncpy(g->shot, v, 8);
        else if (!strcmp(line, "RUN") && g->nrun < MAXRUN) g->run[g->nrun++] = fdup(v);
    }
    fclose(f);
    return ngames;
}

/* ---------- screens ---------- */

static void draw_shot(Game far *g)
{
    char fn[100];
    int h, j;
    fill(SHOT_X, SHOT_Y, SHOT_W, SHOT_H, C_BLACK);
    if (!g->shot[0]) { text(SHOT_X + (SHOT_W - 8 * strlen(L(S_NOPIC))) / 2, SHOT_Y + 56, L(S_NOPIC), C_DIM, -1, 20); return; }
    sprintf(fn, "%s_MENU\\%Fs.PIC", base, (char far *)g->shot);
    if (_dos_open(fn, O_RDONLY, &h)) return;
    {
        unsigned got;
        _dos_read(h, shotbuf, 720 + SHOT_W * SHOT_H, &got);
        _dos_close(h);
        if (got != 720 + SHOT_W * SHOT_H) return;
    }
    vsync();
    set_pal(16, 240, shotbuf);
    for (j = 0; j < SHOT_H; j++)
        _fmemcpy(vga + (unsigned)(SHOT_Y + j) * 320 + SHOT_X, shotbuf + 720 + j * SHOT_W, SHOT_W);
}

/* word-wrap s into lines of at most w chars; returns line count */
static int wrap(const char far *s, int w, char out[][41], int maxl)
{
    int n = 0;
    while (*s && n < maxl) {
        int len = _fstrlen(s), cut = len;
        if (len > w) {
            cut = w;
            while (cut > 0 && s[cut] != ' ') cut--;
            if (cut == 0) cut = w;
        }
        _fmemcpy(out[n], s, cut); out[n][cut] = 0;
        n++;
        s += cut;
        while (*s == ' ') s++;
    }
    return n;
}

static void draw_info(Game far *g)
{
    char lines[3][41], buf[60];
    int n, i, y = SHOT_Y + SHOT_H + 4;
    fill(SHOT_X, y, SHOT_W, 200 - 11 - y, C_BG);
    n = wrap(g->title ? g->title : (char far *)"", 24, lines, 3);
    for (i = 0; i < n; i++, y += 9) text(SHOT_X, y, lines[i], C_TITLE, -1, 24);
    y += 2;
    {
        char far *genre = (lang && g->genre_es) ? g->genre_es : g->genre;
        sprintf(buf, "%Fs  %Fs", g->year ? g->year : (char far *)"", genre ? genre : (char far *)"");
    }
    text(SHOT_X, y, buf, C_TEXT, -1, 24); y += 9;
    sprintf(buf, "%s, %lu.%lu MB", (g->lang && g->lang[0] == 'S') ? L(S_SPANISH) : L(S_ENGLISH),
            g->size / 1000000UL, (g->size / 100000UL) % 10);
    text(SHOT_X, y, buf, C_DIM, -1, 24);
}

static void draw_list(int top, int sel)
{
    int i;
    fill(0, LIST_Y - 1, SHOT_X - 3, LIST_ROWS * ROW_H + 2, C_PANEL);
    for (i = 0; i < LIST_ROWS && top + i < ngames; i++) {
        Game far *g = &games[top + i];
        int y = LIST_Y + i * ROW_H;
        if (top + i == sel) {
            fill(0, y - 1, SHOT_X - 3, ROW_H, C_HILITE);
            text(LIST_X, y, g->shrt, C_HITEXT, -1, LIST_W);
        } else
            text(LIST_X, y, g->shrt, C_TEXT, -1, LIST_W);
    }
    /* more games above / below: arrows in the top and bottom bars */
    text(4, 1, top > 0 ? "\x18" : " ", C_TITLE, C_BAR, 1);
    text(4, 191, top + LIST_ROWS < ngames ? "\x19" : " ", C_TITLE, C_BAR, 1);
}

static void draw_frame(void)
{
    fill(0, 0, 320, 200, C_BG);
    fill(0, 0, 320, 10, C_BAR);
    text_c(1, L(S_HEADER), C_BARTEXT);
    fill(0, 190, 320, 10, C_BAR);
    text_c(191, L(S_FOOTER), C_BARTEXT);
}

static void dialog(int x, int y, int w, int h)
{
    fill(x, y, w, h, C_PANEL);
    frame(x, y, w, h, C_BORDER);
    frame(x + 2, y + 2, w - 4, h - 4, C_BORDER);
}

static void message(const char *l1, const char far *l2, int col)
{
    dialog(24, 70, 272, 60);
    text_c(82, l1, col);
    if (l2) text_c(96, l2, C_TEXT);
    text_c(114, L(S_PRESS), C_DIM);
    getkey();
}

static void help(void)
{
    static const struct { const char *key; int id; } rows[] = {
        { "\x18 \x19", S_H_MOVE }, { "PgUp PgDn", S_H_PAGE }, { "Home End", S_H_ENDS },
        { "A-Z", S_H_JUMP }, { "ENTER", S_H_INST }, { "F1", S_H_HELP }, { "F10", S_H_LANG },
        { "ESC", S_H_QUIT } };
    char lines[5][41];
    int i, n, y = 40;
    fill(0, 10, 320, 180, C_BG);
    dialog(4, 14, 312, 172);
    text_c(22, L(S_HELP), C_TITLE);
    for (i = 0; i < 8; i++, y += 10) {
        text(16, y, rows[i].key, C_FIELDTX, -1, 10);
        text(104, y, L(rows[i].id), C_TEXT, -1, 25);
    }
    y += 6;
    n = wrap(L(S_H_NOTE), 36, lines, 5);
    for (i = 0; i < n; i++, y += 9) text(16, y, lines[i], C_DIM, -1, 36);
    text_c(172, L(S_PRESS), C_DIM);
    getkey();
}

/* ---------- install ---------- */

/* X:\DIR\DIR... with 8.3 names */
static int valid_path(const char *p)
{
    int name = 0, ext = -1;          /* chars in the name / extension (-1: no dot yet) */
    if (strlen(p) < 4 || !isalpha((unsigned char)p[0]) || p[1] != ':' || p[2] != '\\') return 0;
    for (p += 3; ; p++) {
        if (*p == '\\' || !*p) {
            if (name == 0 || ext == 0) return 0;
            if (!*p) return 1;
            name = 0; ext = -1;
        } else if (*p == '.') {
            if (ext >= 0 || name == 0) return 0;
            ext = 0;
        } else {
            if (!isalnum((unsigned char)*p) && !strchr("_-!#$%&'()@^`{}~", *p)) return 0;
            if (ext >= 0) { if (++ext > 3) return 0; }
            else if (++name > 8) return 0;
        }
    }
}

static int edit_path(Game far *g, char *path)
{
    int k;
    sprintf(path, "C:\\JUEGOS\\%Fs", (char far *)g->dir);
    for (;;) {
        dialog(8, 60, 304, 80);
        text_c(70, L(S_WHERE), C_TITLE);
        text(16, 84, g->title, C_TEXT, -1, 36);
        fill(16, 100, 288, 12, C_FIELD);
        text(20, 102, path, C_FIELDTX, -1, 35);
        fill(20 + strlen(path) * 8, 109, 8, 2, C_FIELDTX);      /* cursor */
        text_c(122, L(S_OKCANCEL), C_DIM);
        k = getkey();
        if (k == -1 || k == K_ESC) return 0;
        if (k == K_ENTER) {
            int n = strlen(path);
            while (n > 3 && path[n - 1] == '\\') path[--n] = 0;
            if (valid_path(path)) return 1;
            message(L(S_BADPATH), path, C_ERR);
        } else if (k == K_BKSP) {
            if (*path) path[strlen(path) - 1] = 0;
        } else if (k > 32 && k < 127 && strlen(path) < 34) {
            int n = strlen(path);
            path[n] = toupper(k); path[n + 1] = 0;
        }
    }
}

static unsigned long done_bytes, total_bytes, cluster;
static unsigned nfiles, total_files;
static int copy_err;

static void scan(const char *src, unsigned long *bytes, unsigned *files)
{
    struct find_t f;
    char pat[128], sub[128];
    unsigned rc;
    sprintf(pat, "%s\\*.*", src);
    for (rc = _dos_findfirst(pat, _A_SUBDIR | _A_HIDDEN | _A_SYSTEM | _A_RDONLY | _A_ARCH, &f); !rc;
         rc = _dos_findnext(&f)) {
        if (f.name[0] == '.') continue;
        if (f.attrib & _A_SUBDIR) {
            sprintf(sub, "%s\\%s", src, f.name);
            scan(sub, bytes, files);
            *bytes += cluster;
        } else {
            *bytes += (f.size + cluster - 1) / cluster * cluster;
            (*files)++;
        }
    }
    _dos_findclose(&f);
}

static void progress(const char *name)
{
    unsigned long w = total_bytes ? (done_bytes / 1024) * 268 / (total_bytes / 1024 + 1) : 0;
    char buf[44];
    if (w > 268) w = 268;
    fill(26, 104, 268, 8, C_FIELD);
    fill(26, 104, (int)w, 8, C_PROG);
    sprintf(buf, "%-34.34s", name);
    text(26, 88, buf, C_TEXT, C_PANEL, 34);
    sprintf(buf, L(S_FILES), nfiles, total_files);
    text(26, 118, buf, C_DIM, C_PANEL, 34);
}

/* Copy buffer: as much DOS memory as is free (up to 512 KB), in 32 KB chunks.
 * The file is read with back-to-back reads until the buffer is full, then
 * written out: a CD drive streams instead of stopping and seeking again
 * after every small read (what made the first version slow on real hardware). */
#define CHUNK      0x8000u              /* bytes per DOS read/write call */
#define CHUNK_PARA 0x0800u              /* the same in 16-byte paragraphs */
static unsigned bufseg, nchunks;

static int alloc_copybuf(void)
{
    unsigned maxp, want;
    if (_dos_allocmem(0xFFFF, &maxp) == 0) { _dos_freemem(maxp); return 0; }   /* can't happen */
    want = maxp > 0x0400 ? maxp - 0x0400 : 0;      /* leave 16 KB free for DOS */
    if (want > 0x8000) want = 0x8000;               /* 512 KB is plenty */
    want -= want % CHUNK_PARA;
    if (want < CHUNK_PARA || _dos_allocmem(want, &bufseg)) return 0;
    nchunks = want / CHUNK_PARA;
    return 1;
}

static int copy_file(const char *src, const char *dst, const char *name)
{
    int in, out;
    unsigned d, t, got, wrote, k, n, last = CHUNK;
    if (_dos_open(src, O_RDONLY, &in)) { copy_err = 1; return 0; }
    _dos_setfileattr(dst, _A_NORMAL);
    if (_dos_creat(dst, _A_NORMAL, &out)) { _dos_close(in); copy_err = 2; return 0; }
    progress(name);
    while (last == CHUNK && !copy_err) {
        for (n = 0; n < nchunks; ) {                   /* fill the buffer */
            if (_dos_read(in, MK_FP(bufseg + n * CHUNK_PARA, 0), CHUNK, &got)) { copy_err = 1; break; }
            last = got;
            if (got) n++;
            if (got < CHUNK) break;
        }
        for (k = 0; k < n && !copy_err; k++) {         /* then write it all */
            unsigned len = (k == n - 1) ? last : CHUNK;
            if (_dos_write(out, MK_FP(bufseg + k * CHUNK_PARA, 0), len, &wrote) || wrote != len) copy_err = 3;
            done_bytes += len;
        }
        progress(name);
        if (!copy_err && key_waiting() && getkey() == K_ESC) copy_err = 4;
    }
    _dos_getftime(in, &d, &t);
    _dos_setftime(out, d, t);
    _dos_close(in); _dos_close(out);
    if (copy_err) { remove(dst); return 0; }
    nfiles++;
    return 1;
}

static int copy_tree(const char *src, const char *dst)
{
    struct find_t f;
    char pat[128], s[128], d[128];
    unsigned rc;
    int ok = 1;
    sprintf(pat, "%s\\*.*", src);
    for (rc = _dos_findfirst(pat, _A_SUBDIR | _A_HIDDEN | _A_SYSTEM | _A_RDONLY | _A_ARCH, &f); !rc && ok;
         rc = _dos_findnext(&f)) {
        if (f.name[0] == '.') continue;
        sprintf(s, "%s\\%s", src, f.name);
        sprintf(d, "%s\\%s", dst, f.name);
        if (f.attrib & _A_SUBDIR) {
            mkdir(d);
            ok = copy_tree(s, d);
        } else
            ok = copy_file(s, d, f.name);
    }
    _dos_findclose(&f);
    return ok;
}

static int make_dirs(const char *path)
{
    char p[80];
    int i;
    strcpy(p, path);
    for (i = 3; ; i++) {
        if (p[i] == '\\' || p[i] == 0) {
            char c = p[i];
            struct find_t f;
            p[i] = 0;
            if (mkdir(p) && _dos_findfirst(p, _A_SUBDIR, &f)) return 0;
            p[i] = c;
            if (!c) return 1;
        }
    }
}

static int not_empty(const char *path)
{
    struct find_t f;
    char pat[90];
    unsigned rc;
    sprintf(pat, "%s\\*.*", path);
    for (rc = _dos_findfirst(pat, _A_SUBDIR | _A_HIDDEN | _A_SYSTEM | _A_RDONLY | _A_ARCH, &f); !rc;
         rc = _dos_findnext(&f))
        if (f.name[0] != '.') { _dos_findclose(&f); return 1; }
    return 0;
}

static void install(Game far *g)
{
    char path[80], src[100], buf[60], lines[MAXRUN * 2][41];
    struct diskfree_t df;
    unsigned long avail;
    int i, j, y, n;

    if (!edit_path(g, path)) return;
    if (_dos_getdiskfree(toupper(path[0]) - 'A' + 1, &df)) {
        message(L(S_NODRIVE), path, C_ERR); return;
    }
    cluster = (unsigned long)df.sectors_per_cluster * df.bytes_per_sector;
    avail = (unsigned long)df.avail_clusters * cluster;
    sprintf(src, "%s%Fs", base, (char far *)g->dir);
    if (src[strlen(src) - 1] == '\\') src[strlen(src) - 1] = 0;
    total_bytes = 0; total_files = 0;
    scan(src, &total_bytes, &total_files);
    if (total_bytes > avail) {
        sprintf(buf, L(S_NEEDS), total_bytes / 1024, avail / 1024);
        message(L(S_NOSPACE), buf, C_ERR); return;
    }
    if (!make_dirs(path)) { message(L(S_NOMKDIR), path, C_ERR); return; }
    if (not_empty(path)) {
        int k;
        dialog(24, 70, 272, 60);
        text_c(82, L(S_HASFILES), C_TITLE);
        text_c(96, L(S_OVERWRITE), C_TEXT);
        do k = toupper(getkey()); while (k != 'Y' && k != 'S' && k != 'N' && k != K_ESC && k != -1);
        if (k != 'Y' && k != 'S') return;           /* Y (yes) or S (si) */
    }
    if (!alloc_copybuf()) { message(L(S_NOMEM), 0, C_ERR); return; }
    dialog(16, 66, 288, 68);
    text_c(74, L(S_COPYING), C_TITLE);
    sprintf(buf, L(S_BUFFER), nchunks * 32);
    text(206, 118, buf, C_DIM, -1, 11);
    done_bytes = 0; nfiles = 0; copy_err = 0;
    copy_tree(src, path);
    _dos_freemem(bufseg);
    if (copy_err) {
        static const int why[] = { 0, S_ERRREAD, S_ERRCREATE, S_ERRWRITE, S_STOPPED };
        message(L(why[copy_err]), L(S_INCOMPLETE), C_ERR);
        return;
    }

    /* done: how to play */
    fill(0, 10, 320, 180, C_BG);
    dialog(4, 14, 312, 172);
    text_c(22, L(S_INSTALLED), C_OK);
    sprintf(buf, L(S_INFILES), nfiles, path);
    text_c(34, buf, C_TEXT);
    text(14, 50, L(S_TOPLAY), C_TITLE, -1, 36);
    sprintf(buf, "%c:", toupper(path[0]));
    text(22, 62, buf, C_FIELDTX, -1, 36);
    sprintf(buf, "CD %s", path + 2);
    text(22, 71, buf, C_FIELDTX, -1, 36);
    /* each RUN entry is "label: commands": label, then the commands highlighted */
    y = 84;
    for (i = 0; i < g->nrun && y < 166; i++) {
        char tmp[200], *cmd;
        _fstrncpy(tmp, g->run[i], sizeof tmp - 1); tmp[sizeof tmp - 1] = 0;
        cmd = strstr(tmp, ": ");
        if (cmd) {
            cmd[1] = 0; cmd += 2;
            n = wrap(tmp, 36, lines, 2);
            for (j = 0; j < n && y < 166; j++, y += 9) text(14, y, lines[j], C_TEXT, -1, 36);
        } else
            cmd = tmp;
        n = wrap(cmd, 35, lines, 4);
        for (j = 0; j < n && y < 166; j++, y += 9) text(22, y, lines[j], C_FIELDTX, -1, 35);
    }
    text_c(172, L(S_PRESS), C_DIM);
    getkey();
}

/* ---------- main ---------- */

static void redraw(int top, int sel)
{
    draw_frame();
    draw_list(top, sel);
    draw_shot(&games[sel]);
    draw_info(&games[sel]);
}

int main(int argc, char **argv)
{
    int i, sel = 0, top = 0, k;
    char *p;

    for (i = 1; i < argc; i++)
        if (!strnicmp(argv[i], "/T:", 3)) keyfile = fopen(argv[i] + 3, "r");

    strcpy(base, argv[0]);                       /* data lives next to MENU.EXE */
    p = strrchr(base, '\\');
    if (p) p[1] = 0; else base[0] = 0;

    if (!load_data()) {
        printf("MENU: cannot read %s_MENU\\MENU.DAT\n", base);
        return 1;
    }
    shotbuf = malloc(720 + SHOT_W * SHOT_H);
    if (!shotbuf) { printf("MENU: not enough memory\n"); return 1; }

    vga = MK_FP(0xA000, 0);
    set_mode(0x13);
    get_font();
    set_pal(0, 16, &ui_pal[0][0]);
    redraw(top, sel);

    for (;;) {
        int old = sel;
        k = getkey();
        if (k == -1 || k == K_ESC) break;
        switch (k) {
        case K_UP:   if (sel > 0) sel--; break;
        case K_DOWN: if (sel < ngames - 1) sel++; break;
        case K_PGUP: sel -= LIST_ROWS; if (sel < 0) sel = 0; break;
        case K_PGDN: sel += LIST_ROWS; if (sel > ngames - 1) sel = ngames - 1; break;
        case K_HOME: sel = 0; break;
        case K_END:  sel = ngames - 1; break;
        case K_F1:  help(); redraw(top, sel); continue;
        case K_F10: lang = !lang; redraw(top, sel); continue;
        case K_ENTER:
            install(&games[sel]);
            redraw(top, sel);
            continue;
        default:                                  /* letter: jump to the next game starting with it */
            if (k < 128 && isalnum(k)) {
                for (i = 1; i <= ngames; i++) {
                    int j = (sel + i) % ngames;
                    if (toupper(games[j].shrt[0]) == toupper(k)) { sel = j; break; }
                }
            }
        }
        if (sel < top) top = sel;
        if (sel >= top + LIST_ROWS) top = sel - LIST_ROWS + 1;
        if (sel != old) {
            draw_list(top, sel);
            draw_shot(&games[sel]);
            draw_info(&games[sel]);
        }
    }
    set_mode(0x03);
    exit_screen();
    return 0;
}
