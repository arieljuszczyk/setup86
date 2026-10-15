/* MENU.EXE - graphical game installer for the Setup86 discs.
 * Copyright (c) 2026 Ariel Juszczyk. MIT License, see LICENSE.
 *
 * VGA 320x200 (mode 13h), runs on any PC with VGA (8086 code, DOS 3.3+).
 * Two modes, picked by what is next to the program:
 *  - disc: _MENU\MENU.DAT (+ _MENU\<GAME>.PIC) lists the games on this disc.
 *    F2, or starting the copy named INSTALL.EXE, installs the menu on a hard
 *    disk with this disc's list.
 *  - installed: _MENU\VOLS.DAT names the discs it knows; _MENU\Vnnn.DAT and
 *    _MENU\Vnnn\<GAME>.PIC are each disc's list. It shows all of them and asks
 *    for the right disc (found by its \SETUP86.ID) before copying. F2 (or a new
 *    disc found at start) adds the disc in the CD drive to the list.
 * Installing a game copies its directory from the disc to a directory the user
 * types.  F3 (or SPACE) shows the game's info screen: what it supports (MT-32,
 * Sound Canvas, Gravis Ultrasound, 3dfx) and a short description
 * (_MENU\<GAME>.TXT).  F1 shows a help screen, F10 switches English / Spanish,
 * F12 shows the About screen.
 *
 * Build (OpenWatcom 2): wcl -q -w4 -bt=dos -ml -0 -os -k12288 -fe=MENU.EXE menu.c
 *
 * Test hook: MENU /T:<file> reads the keys from <file> instead of the
 * keyboard (UP DOWN PGUP PGDN HOME END ENTER ESC BKSP SPACE F1 F2 F3 F10 F12 SHOT
 * TEXT:<chars>);
 * SHOT dumps palette + screen to SHOTnn.BIN.  Exits at the end of the file.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <dos.h>
#include <i86.h>
#include <conio.h>
#include <bios.h>
#include <io.h>
#include <fcntl.h>
#include <direct.h>
#include <sys/stat.h>

#define VERSION   "v1.3.0"      /* shown at the right of the top bar; the release tag */
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
    unsigned char vi;           /* installed mode: index in vols[] */
    unsigned char hw;           /* HW_*: what the game supports */
    unsigned char desc;         /* has _MENU\<GAME>.TXT */
    int nrun;
    char far *run[MAXRUN];
} Game;
/* what a game supports (MENU.DAT's SUPPORTS line): the tag there, a short name for the
 * chips on the screenshot (tiny font), the full one for the info screen */
#define NHW 4
static const struct { const char *tag, *chip, *name; int col; } hw_list[NHW] = {
    { "MT-32", "MT-32", "MT-32", C_OK }, { "SC-55", "SOUND CANVAS", "Sound Canvas", C_OK },
    { "GUS", "GUS", "GUS", C_OK }, { "3DFX", "3DFX", "3dfx", C_HILITE } };     /* sound green, video blue */

/* ---------- screen texts: English / Spanish (CP437, the VGA font's own accents) ---------- */
enum { S_HEADER, S_FOOTER, S_NOPIC, S_SPANISH, S_ENGLISH, S_PRESS, S_WHERE, S_OKCANCEL, S_BADPATH, S_NODRIVE, S_NEEDS, S_NOSPACE, S_NOMKDIR, S_HASFILES, S_OVERWRITE, S_NOMEM, S_COPYING, S_BUFFER, S_FILES, S_ERRREAD, S_ERRCREATE, S_ERRWRITE, S_STOPPED, S_INCOMPLETE, S_INSTALLED, S_INFILES, S_TOPLAY, S_HELP, S_H_MOVE, S_H_PAGE, S_H_ENDS, S_H_JUMP, S_H_INST, S_H_HELP, S_H_LANG, S_H_QUIT, S_H_NOTE,
       S_FOOTER_C, S_H_F2D, S_H_F2C, S_MWHERE, S_MDONE, S_MRUN, S_INSERT, S_READY, S_NEWDISC, S_ADDQ,
       S_NEWBUILD, S_UPDQ, S_NODISC, S_ADDED, S_NOTONDISC, S_MCOPYFAIL, S_DISCLINE, S_TOOMANY,
       S_H_ABOUT, S_ABOUT, S_A_BY, S_A_MADE1, S_A_MADE2, S_A_FREE, S_A_DONATE, S_A_VER,
       S_H_INFO, S_INFOKEYS, S_NODESC, S_COUNT };
static const char *msgs[2][S_COUNT] = {
    { "SETUP86 COLLECTION",
      "ENTER Install F1 Help F2 HD F3 Info",
      "(no picture)",
      "Spanish",
      "English",
      "Press a key",
      "Install to which directory?",
      "ENTER OK   ESC Cancel",
      "Not a valid DOS directory name",
      "That drive is not available",
      "Needs %lu KB, %lu KB free",
      "Not enough free space",
      "Cannot create the directory",
      "The directory already has files.",
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
      "Help",
      "Move through the list",
      "Page up / down",
      "First / last game",
      "Jump to a game",
      "Install the game",
      "This help",
      "Espa\244ol",
      "Quit",
      "The game is copied to the directory you choose (C:\\GAMES\\<GAME> if you just press ENTER). The last screen shows how to start it.",
      "ENTER Install F1 Help F2 +CD F3 Info",
      "Install menu to hard disk",
      "Add the CD in the drive",
      "Install the menu in which directory?",
      "Menu installed",
      "Start it with  %s\\MENU",
      "Insert Setup86 %s %d",
      "ENTER Ready   ESC Cancel",
      "New disc: %s %d",
      "Add it to the list? (Y/N)",
      "Other version of %s %d",
      "Update the list? (Y/N)",
      "No Setup86 disc in the CD drive",
      "Added: %s %d, %d games",
      "Not on this version of the disc",
      "Cannot copy the menu files",
      "Disc %s %d",
      "Too many discs in the list",
      "About Setup86",
      "About Setup86",
      "Created by Ariel Juszczyk",
      "Made for the eXoDOS collection,",
      "to run on real x86 hardware.",
      "Free & open source - MIT License",
      "Please donate to support it:",
      "Version %s",
      "Game info and description",
      "ENTER Install   ESC Back",
      "(no description)" },
    { "SETUP86 COLLECTION",
      "ENTER Inst. F1 Ayuda F2 HD F3 Info",
      "(sin imagen)",
      "Espa\244ol",
      "Ingl\202s",
      "Pulse una tecla",
      "\250En qu\202 directorio instalar?",
      "ENTER Aceptar   ESC Cancelar",
      "Nombre de directorio no v\240lido",
      "Esa unidad no est\240 disponible",
      "Necesita %lu KB, hay %lu KB",
      "No hay espacio suficiente",
      "No se pudo crear el directorio",
      "El directorio ya tiene archivos.",
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
      "Ayuda",
      "Moverse por la lista",
      "P\240gina arriba / abajo",
      "Primer / \243ltimo juego",
      "Saltar a un juego",
      "Instalar el juego",
      "Esta ayuda",
      "English",
      "Salir",
      "El juego se copia al directorio que elija (C:\\JUEGOS\\<JUEGO> si s\242lo pulsa ENTER). La \243ltima pantalla muestra c\242mo iniciarlo.",
      "ENTER Inst. F1 Ayuda F2 +CD F3 Info",
      "Instalar men\243 al disco duro",
      "Agregar el CD de la unidad",
      "\250En qu\202 directorio instalar el men\243?",
      "Men\243 instalado",
      "Para iniciarlo:  %s\\MENU",
      "Inserte Setup86 %s %d",
      "ENTER Listo   ESC Cancelar",
      "Disco nuevo: %s %d",
      "\250Agregarlo a la lista? (S/N)",
      "Otra versi\242n de %s %d",
      "\250Actualizar la lista? (S/N)",
      "No hay un disco Setup86 en el CD",
      "Agregado: %s %d, %d juegos",
      "No est\240 en esta versi\242n del disco",
      "No se pudo copiar el men\243",
      "Disco %s %d",
      "Demasiados discos en la lista",
      "Acerca de Setup86",
      "Acerca de Setup86",
      "Creado por Ariel Juszczyk",
      "Hecho para la colecci\242n eXoDOS,",
      "para usar en PCs x86 reales.",
      "Libre y gratuito - Licencia MIT",
      "Si quiere apoyar su desarrollo:",
      "Versi\242n %s",
      "Datos y descripci\242n",
      "ENTER Instalar   ESC Volver",
      "(sin descripci\242n)" } };
static int lang;                      /* 0 English, 1 Spanish (F10) */
#define L(id) msgs[lang][id]

/* exit screen, DOOM "ENDOOM" style: a red band with centred yellow text, then the
 * MIT notice (kept in English, see LICENSE). 10 + 14 rows; the DOS prompt gets row 25. */
static const char *exit_band[] = {           /* centred, yellow on red, max 80 columns */
    "Setup86",
    "",
    "Created by Ariel Juszczyk",
    "Copyright (c) 2026 - ariel.juszczyk@gmail.com",
    "",
    "https://github.com/arieljuszczyk/setup86 - MIT License",
    "",
    "Made for the eXoDOS collection, to run on real x86 hardware.",
    "Free & open source.",
    "Please donate to support its development: ko-fi.com/setup86" };
#define BAND_ROWS 10
static const char *license_body[] = {         /* LICENSE re-wrapped to 80 columns, 14 rows */
    "Permission is hereby granted, free of charge, to any person obtaining a copy of",
    "this software and associated documentation files (the \"Software\"), to deal in",
    "the Software without restriction, including without limitation the rights to",
    "use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of",
    "the Software, and to permit persons to whom the Software is furnished to do so,",
    "subject to the following conditions:",
    "The above copyright notice and this permission notice shall be included in all",
    "copies or substantial portions of the Software.",
    "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR",
    "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS",
    "FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR",
    "COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER",
    "IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN",
    "CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE." };
#define LIC_ROWS 14

static Game far *games;
static int ngames;
static char label[40], base[80], exe[80];

/* the discs: in disc mode only this one (vols[0]); installed, all known ones */
#define MAXVOLS 40
typedef struct { char set[10]; int vol; char build[16]; } Vol;
static Vol vols[MAXVOLS];
static int nvols, coll;                 /* coll: running from an install (_MENU\VOLS.DAT) */
static unsigned char far *vga;
static unsigned char far *font;
static unsigned char far *shotbuf;
static FILE *keyfile;
static int install_only;                /* started as INSTALL.EXE */
static int shotno;

/* ---------- low level graphics ---------- */

static void set_mode(int m) { union REGS r; r.x.ax = m; int86(0x10, &r, &r); }

static void exit_screen(void)
{
    unsigned short far *t = MK_FP(0xB800, 0);
    union REGS r;
    int i, row;
    for (i = 0; i < 80 * 25; i++) t[i] = 0x0720;              /* grey on black, blank */
    for (i = 0; i < 80 * BAND_ROWS; i++) t[i] = 0x4E20;       /* the band: yellow on red */
    for (row = 0; row < BAND_ROWS; row++) {                   /* centred */
        int n = strlen(exit_band[row]), x = (80 - n) / 2;
        for (i = 0; i < n; i++) t[row * 80 + x + i] = 0x4E00 | (unsigned char)exit_band[row][i];
    }
    for (row = 0; row < LIC_ROWS; row++)                      /* the MIT notice below it */
        for (i = 0; license_body[row][i]; i++) t[(row + BAND_ROWS) * 80 + i] = 0x0700 | (unsigned char)license_body[row][i];
    r.h.ah = 2; r.h.bh = 0; r.h.dh = 24; r.h.dl = 0;          /* DOS prompt on the last row */
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

/* tiny 3x5 font: the version number at the top right ("v1.2.3"), the chips ("MT-32") */
static const char tiny_chars[] = "0123456789.vMTSC-AODFGNUVX";
static const unsigned char tiny[26][5] = {       /* 3 bits per row, MSB = left */
    {7,5,5,5,7}, {2,6,2,2,7}, {7,1,7,4,7}, {7,1,7,1,7}, {5,5,7,1,1},
    {7,4,7,1,7}, {7,4,7,5,7}, {7,1,1,1,1}, {7,5,7,5,7}, {7,5,7,1,7},
    {0,0,0,0,2}, {0,5,5,5,2}, {5,7,7,5,5}, {7,2,2,2,2}, {7,4,7,1,7},
    {7,4,4,4,7}, {0,0,7,0,0}, {2,5,7,5,5}, {7,5,5,5,7}, {6,5,5,5,6},
    {7,4,6,4,4}, {7,4,5,5,7}, {6,5,5,5,5}, {5,5,5,5,7}, {5,5,5,5,2},
    {5,5,2,5,5} };

static int tiny_width(const char *s)
{
    int w = 0;
    for (; *s; s++) w += *s == '.' ? 2 : 4;
    return w - 1;
}

static void tiny_text(int x, int y, const char *s, int fg)
{
    int r, b;
    for (; *s; s++) {
        const char *c = strchr(tiny_chars, *s);
        int i = c ? c - tiny_chars : -1;
        if (i < 0) { x += 4; continue; }
        for (r = 0; r < 5; r++)
            for (b = 0; b < 3; b++)
                if (tiny[i][r] & (4 >> b)) vga[(unsigned)(y + r) * 320 + x + b - (i == 10)] = fg;
        x += i == 10 ? 2 : 4;
    }
}

static void text_c(int y, const char far *s, int fg)   /* centred */
{
    int n = _fstrlen(s); if (n > 40) n = 40;
    text((320 - n * 8) / 2, y, s, fg, -1, 40);
}

/* ---------- keyboard (or test script) ---------- */

enum { K_UP = 0x148, K_DOWN = 0x150, K_PGUP = 0x149, K_PGDN = 0x151,
       K_HOME = 0x147, K_END = 0x14F, K_F1 = 0x13B, K_F2 = 0x13C, K_F3 = 0x13D, K_F10 = 0x144, K_F12 = 0x186,
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

/* the BIOS reports a 101-key keyboard (and so supports int 16h function 10h) */
static int enhanced_kbd(void)
{
    return *(unsigned char far *)MK_FP(0x40, 0x96) & 0x10;
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
            if (!strcmp(tok, "F2")) return K_F2;
            if (!strcmp(tok, "F3")) return K_F3;
            if (!strcmp(tok, "SPACE")) return ' ';
            if (!strcmp(tok, "F12")) return K_F12;
            if (!strncmp(tok, "KEY:", 4)) return (unsigned char)tok[4];
            if (!strcmp(tok, "SHOT")) { dump_screen(); continue; }
            if (!strncmp(tok, "TEXT:", 5)) { strcpy(pending, tok + 5); npend = strlen(pending); continue; }
        }
    } else {
        union REGS r;
        r.h.ah = enhanced_kbd() ? 0x10 : 0; int86(0x16, &r, &r);   /* only 10h returns F11/F12 */
        return r.h.al && !(r.h.al == 0xE0 && r.h.ah) ? r.h.al : 0x100 + r.h.ah;
    }
}

/* a key is waiting (int 16h 01h/11h set ZF when there is none; REGS has no ZF, only cflag) */
static int key_waiting(void)
{
    if (keyfile) return 0;
    return _bios_keybrd(enhanced_kbd() ? _NKEYBRD_READY : _KEYBRD_READY) != 0;
}

/* ---------- data ---------- */

static char far *fdup(const char *s)
{
    char far *p = malloc(strlen(s) + 1);
    if (p) _fstrcpy(p, s);
    return p;
}

/* read a disc's MENU.DAT (or an installed copy of it): the header lines SET,
 * VOL and BUILD describe the disc, then one GAME block per game */
static int load_file(const char *fn, int vi, Vol *hdr)
{
    char line[200];
    FILE *f;
    Game far *g = 0;
    f = fopen(fn, "r");
    if (!f) return 0;
    while (fgets(line, sizeof line, f)) {
        char *v;
        line[strcspn(line, "\r\n")] = 0;
        v = strchr(line, ' ');
        if (v) *v++ = 0; else v = line + strlen(line);
        if (!strcmp(line, "LABEL")) { strncpy(label, v, 39); }
        else if (!strcmp(line, "SET") && hdr) { strncpy(hdr->set, v, 9); hdr->set[9] = 0; }
        else if (!strcmp(line, "VOL") && hdr) hdr->vol = atoi(v);
        else if (!strcmp(line, "BUILD") && hdr) { strncpy(hdr->build, v, 15); hdr->build[15] = 0; }
        else if (!strcmp(line, "GAME")) {
            if (ngames >= MAXGAMES) { g = 0; continue; }
            g = &games[ngames++];
            _fmemset(g, 0, sizeof(Game));
            _fstrncpy(g->dir, v, 8);
            g->vi = (unsigned char)vi;
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
        else if (!strcmp(line, "SUPPORTS") || !strcmp(line, "SOUND")) {   /* SOUND: v1.3.0 discs */
            int i;
            for (i = 0; i < NHW; i++) if (strstr(v, hw_list[i].tag)) g->hw |= 1 << i;
        }
        else if (!strcmp(line, "DESC")) g->desc = 1;
        else if (!strcmp(line, "RUN") && g->nrun < MAXRUN) g->run[g->nrun++] = fdup(v);
    }
    fclose(f);
    return 1;
}

static void free_games(void)
{
    int i, j;
    for (i = 0; i < ngames; i++) {
        Game far *g = &games[i];
        free(g->title); free(g->shrt); free(g->year); free(g->genre); free(g->genre_es); free(g->lang);
        for (j = 0; j < g->nrun; j++) free(g->run[j]);
    }
    ngames = 0;
}

static int cmp_games(const void *a, const void *b)
{
    const Game far *x = a, far *y = b;
    return _fstricmp(x->shrt ? x->shrt : (char far *)"", y->shrt ? y->shrt : (char far *)"");
}

/* VOLS.DAT: one line per known disc, "<set> <vol> <build>"; line n is Vnnn.DAT */
static int read_vols(const char *dir)
{
    char fn[100], line[80];
    FILE *f;
    nvols = 0;
    sprintf(fn, "%s_MENU\\VOLS.DAT", dir);
    f = fopen(fn, "r");
    if (!f) return 0;
    while (nvols < MAXVOLS && fgets(line, sizeof line, f)) {
        Vol *v = &vols[nvols];
        memset(v, 0, sizeof *v);
        if (sscanf(line, "%9s %d %15s", v->set, &v->vol, v->build) >= 2) nvols++;
    }
    fclose(f);
    return 1;
}

static int write_vols(const char *dir)
{
    char fn[100];
    FILE *f;
    int i;
    sprintf(fn, "%s_MENU\\VOLS.DAT", dir);
    f = fopen(fn, "w");
    if (!f) return 0;
    for (i = 0; i < nvols; i++) fprintf(f, "%s %d %s\n", vols[i].set, vols[i].vol, vols[i].build);
    return fclose(f) == 0;
}

static int load_data(void)
{
    char fn[100];
    int i;
    free_games();
    if (!games) {
        games = malloc(sizeof(Game) * MAXGAMES);
        if (!games) return 0;
    }
    if (coll) {
        if (!read_vols(base)) return 0;
        for (i = 0; i < nvols; i++) {
            sprintf(fn, "%s_MENU\\V%03d.DAT", base, i + 1);
            load_file(fn, i, 0);
        }
        qsort(games, ngames, sizeof(Game), cmp_games);
    } else {
        nvols = 1;
        memset(&vols[0], 0, sizeof vols[0]);
        sprintf(fn, "%s_MENU\\MENU.DAT", base);
        if (!load_file(fn, 0, &vols[0])) return 0;
    }
    return ngames;
}

/* ---------- screens ---------- */

static void draw_shot(Game far *g)
{
    char fn[100];
    int h, j;
    fill(SHOT_X, SHOT_Y, SHOT_W, SHOT_H, C_BLACK);
    if (!g->shot[0]) { text(SHOT_X + (SHOT_W - 8 * strlen(L(S_NOPIC))) / 2, SHOT_Y + 56, L(S_NOPIC), C_DIM, -1, 20); return; }
    if (coll) sprintf(fn, "%s_MENU\\V%03d\\%Fs.PIC", base, g->vi + 1, (char far *)g->shot);
    else sprintf(fn, "%s_MENU\\%Fs.PIC", base, (char far *)g->shot);
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

/* what the game supports: chips in the tiny font along the bottom of the screenshot */
static void draw_chips(Game far *g)
{
    int i, x = SHOT_X + SHOT_W - 1, y = SHOT_Y + SHOT_H - 9;
    for (i = NHW - 1; i >= 0; i--)
        if (g->hw & (1 << i)) {
            int w = tiny_width(hw_list[i].chip) + 4;
            x -= w;
            fill(x, y, w, 8, hw_list[i].col);
            tiny_text(x + 2, y + 1, hw_list[i].chip, C_HITEXT);
            x -= 2;
        }
}

static void draw_info(Game far *g)
{
    char lines[3][41], buf[60];
    int n, i, y = SHOT_Y + SHOT_H + 4;
    fill(SHOT_X, y, SHOT_W, 200 - 11 - y, C_BG);
    n = wrap(g->title ? g->title : (char far *)"", 24, lines, coll ? 2 : 3);   /* installed: + disc line */
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
    draw_chips(g);
    if (coll) {
        sprintf(buf, L(S_DISCLINE), vols[g->vi].set, vols[g->vi].vol);
        text(SHOT_X, y + 9, buf, C_TITLE, -1, 24);
    }
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
    if (coll || !vols[0].set[0]) text_c(1, L(S_HEADER), C_BARTEXT);
    else {                                       /* "SETUP86 - ADVENTURE 1" */
        char h[40];
        sprintf(h, "SETUP86 \372 %s %d", vols[0].set, vols[0].vol);
        strupr(h);
        text_c(1, h, C_BARTEXT);
    }
    tiny_text(318 - tiny_width(VERSION), 3, VERSION, C_DIM);
    fill(0, 190, 320, 10, C_BAR);
    text_c(191, L(coll ? S_FOOTER_C : S_FOOTER), C_BARTEXT);
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
        { "A-Z", S_H_JUMP }, { "ENTER", S_H_INST }, { "F3 SPACE", S_H_INFO }, { "F2", -1 },
        { "F10", S_H_LANG }, { "F12", S_H_ABOUT }, { "ESC", S_H_QUIT } };
    char lines[5][41];
    int i, n, y = 36;
    fill(0, 10, 320, 180, C_BG);
    dialog(4, 14, 312, 172);
    text_c(22, L(S_HELP), C_TITLE);
    for (i = 0; i < 10; i++, y += 9) {
        int id = rows[i].id >= 0 ? rows[i].id : coll ? S_H_F2C : S_H_F2D;
        text(16, y, rows[i].key, C_FIELDTX, -1, 10);
        text(96, y, L(id), C_TEXT, -1, 27);
    }
    y += 6;
    n = wrap(L(S_H_NOTE), 36, lines, 4);
    for (i = 0; i < n; i++, y += 9) text(16, y, lines[i], C_DIM, -1, 36);
    text_c(172, L(S_PRESS), C_DIM);
    getkey();
}

static void about(void)
{
    char ver[24];
    fill(0, 10, 320, 180, C_BG);
    dialog(4, 14, 312, 172);
    sprintf(ver, L(S_A_VER), VERSION + 1);        /* "1.1.0" without the v */
    text_c(22, L(S_ABOUT), C_TITLE);
    text_c(33, ver, C_DIM);
    text_c(48, L(S_A_BY), C_TEXT);
    text_c(58, "(c) 2026 ariel.juszczyk@gmail.com", C_DIM);
    text_c(76, L(S_A_MADE1), C_TEXT);
    text_c(85, L(S_A_MADE2), C_TEXT);
    text_c(103, L(S_A_FREE), C_TEXT);
    text_c(113, "github.com/arieljuszczyk/setup86", C_FIELDTX);
    text_c(131, L(S_A_DONATE), C_TEXT);
    text_c(141, "ko-fi.com/setup86", C_FIELDTX);
    text_c(172, L(S_PRESS), C_DIM);
    getkey();
}

/* the game's info screen (F3): title, year, genre, what it supports and its description
 * (_MENU\<GAME>.TXT, one line that setup86.py already cut to DESC_LINES x DESC_W);
 * returns 1 when ENTER asks to install it */
#define DESC_W     37
#define DESC_LINES 10
static int info(Game far *g)
{
    char lines[DESC_LINES][41], buf[80], desc[512];
    char far *genre = (lang && g->genre_es) ? g->genre_es : g->genre;
    int i, n, k;
    FILE *f;
    fill(0, 10, 320, 180, C_BG);
    dialog(4, 14, 312, 172);
    n = wrap(g->title ? g->title : (char far *)"", 36, lines, 2);
    for (i = 0; i < n; i++) text_c(22 + 9 * i, lines[i], C_TITLE);
    sprintf(buf, "%Fs  %Fs", g->year ? g->year : (char far *)"", genre ? genre : (char far *)"");
    text(12, 43, buf, C_TEXT, -1, DESC_W);
    sprintf(buf, "%s, %lu.%lu MB", (g->lang && g->lang[0] == 'S') ? L(S_SPANISH) : L(S_ENGLISH),
            g->size / 1000000UL, (g->size / 100000UL) % 10);
    if (coll) {
        strcat(buf, "  ");
        sprintf(buf + strlen(buf), L(S_DISCLINE), vols[g->vi].set, vols[g->vi].vol);
    }
    text(12, 52, buf, C_DIM, -1, DESC_W);
    for (i = 0, k = 12; i < NHW; i++)                     /* what it supports: chips */
        if (g->hw & (1 << i)) {
            int w = 8 * strlen(hw_list[i].name) + 6;
            fill(k, 60, w, 10, hw_list[i].col);
            text(k + 3, 61, hw_list[i].name, C_HITEXT, -1, 20);
            k += w + 4;
        }
    desc[0] = 0;
    if (g->desc) {
        if (coll) sprintf(buf, "%s_MENU\\V%03d\\%Fs.TXT", base, g->vi + 1, (char far *)g->dir);
        else sprintf(buf, "%s_MENU\\%Fs.TXT", base, (char far *)g->dir);
        f = fopen(buf, "r");
        if (f) {
            if (!fgets(desc, sizeof desc, f)) desc[0] = 0;
            fclose(f);
            desc[strcspn(desc, "\r\n")] = 0;
        }
    }
    if (desc[0]) {
        n = wrap(desc, DESC_W, lines, DESC_LINES);
        for (i = 0; i < n; i++) text(12, 74 + 9 * i, lines[i], C_TEXT, -1, DESC_W);
    } else
        text(12, 74, L(S_NODESC), C_DIM, -1, DESC_W);
    text_c(172, L(S_INFOKEYS), C_DIM);
    for (;;) {
        k = getkey();
        if (k == K_ENTER) return 1;
        if (k == -1 || k == K_ESC || k == K_F3 || k == ' ') return 0;
    }
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

/* edit the directory in path (holds the default); prompt + title line above it */
static int edit_path(int prompt, const char far *title, char *path)
{
    int k;
    for (;;) {
        dialog(8, 60, 304, 80);
        text_c(70, L(prompt), C_TITLE);
        text(16, 84, title, C_TEXT, -1, 36);
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
 * after every small read (what made the first version slow on real hardware).
 * The chunks start on a 32 KB boundary, so no read crosses a 64 KB DMA page:
 * CD-ROM drivers that use DMA can't transfer across one, and retry forever. */
#define CHUNK      0x8000u              /* bytes per DOS read/write call */
#define CHUNK_PARA 0x0800u              /* the same in 16-byte paragraphs */
static unsigned rawseg, bufseg, nchunks;

static int alloc_copybuf(void)
{
    unsigned maxp, want;
    if (_dos_allocmem(0xFFFF, &maxp) == 0) { _dos_freemem(maxp); return 0; }   /* can't happen */
    want = maxp > 0x0400 ? maxp - 0x0400 : 0;      /* leave 16 KB free for DOS */
    if (want > 0x8000 + CHUNK_PARA) want = 0x8000 + CHUNK_PARA;   /* 512 KB + room to align */
    if (want < 2 * CHUNK_PARA || _dos_allocmem(want, &rawseg)) return 0;
    bufseg = (rawseg + CHUNK_PARA - 1) & ~(CHUNK_PARA - 1);
    nchunks = (unsigned)(((unsigned long)rawseg + want - bufseg) / CHUNK_PARA);
    if (!nchunks) { _dos_freemem(rawseg); return 0; }
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

/* ---------- discs ---------- */

/* a disk error (empty CD drive, disc being changed) must not print DOS's
 * "Abort, Retry, Fail?" over the VGA screen: fail the call and carry on */
static int __far crit_handler(unsigned deverr, unsigned errcode, unsigned __far *devhdr)
{
    (void)deverr; (void)errcode; (void)devhdr;
    return _HARDERR_FAIL;
}

/* CD-ROM drive letters from MSCDEX (0 = A:); returns how many */
static int cd_drives(unsigned char *d, int max)
{
    union REGS r; struct SREGS s;
    unsigned char list[26];
    int n, i;
    r.x.ax = 0x1500; r.x.bx = 0; int86(0x2F, &r, &r);
    n = r.x.bx;
    if (n <= 0) return 0;
    if (n > 26) n = 26;
    segread(&s);
    r.x.ax = 0x150D; s.es = FP_SEG((void far *)list); r.x.bx = FP_OFF((void far *)list);
    int86x(0x2F, &r, &r, &s);                       /* MSCDEX 2.0+: the drive list */
    for (i = 0; i < n && i < max; i++) d[i] = list[i];
    if (list[0] > 25) for (i = 0; i < n && i < max; i++) d[i] = r.x.cx + i;   /* old MSCDEX */
    return i < max ? i : max;
}

/* root ("D:\") holds a Setup86 disc: read its \SETUP86.ID ("SET x", "VOL n", "BUILD b") */
static int read_id(const char *root, Vol *v)
{
    char fn[40], line[80];
    FILE *f;
    memset(v, 0, sizeof *v);
    sprintf(fn, "%sSETUP86.ID", root);
    f = fopen(fn, "r");
    if (!f) return 0;
    while (fgets(line, sizeof line, f)) {
        char *val;
        line[strcspn(line, "\r\n")] = 0;
        val = strchr(line, ' ');
        if (!val) continue;
        *val++ = 0;
        if (!strcmp(line, "SET")) { strncpy(v->set, val, 9); v->set[9] = 0; }
        else if (!strcmp(line, "VOL")) v->vol = atoi(val);
        else if (!strcmp(line, "BUILD")) { strncpy(v->build, val, 15); v->build[15] = 0; }
    }
    fclose(f);
    return v->set[0] && v->vol;
}

static int find_vol(const Vol *v)
{
    int i;
    for (i = 0; i < nvols; i++)
        if (!strcmp(vols[i].set, v->set) && vols[i].vol == v->vol) return i;
    return -1;
}

/* small files (lists, screenshots, the program): through the screenshot buffer */
static int small_copy(const char *src, const char *dst)
{
    int in, out, ok = 1;
    unsigned got, wrote;
    if (_dos_open(src, O_RDONLY, &in)) return 0;
    _dos_setfileattr(dst, _A_NORMAL);
    if (_dos_creat(dst, _A_NORMAL, &out)) { _dos_close(in); return 0; }
    for (;;) {
        if (_dos_read(in, shotbuf, 720 + SHOT_W * SHOT_H, &got)) { ok = 0; break; }
        if (!got) break;
        if (_dos_write(out, shotbuf, got, &wrote) || wrote != got) { ok = 0; break; }
    }
    _dos_close(in);
    if (_dos_close(out)) ok = 0;
    if (!ok) remove(dst);
    return ok;
}

/* add (or refresh) the disc in root to the installed list in dir: its MENU.DAT
 * becomes _MENU\Vnnn.DAT, its pictures and descriptions go to _MENU\Vnnn\; -1 on error */
static int import_volume(const char *root, const char *dir, const Vol *v)
{
    static const char *kinds[] = { "*.PIC", "*.TXT" };
    char src[100], dst[100], pat[100];
    struct find_t f;
    unsigned rc;
    int k, vi = find_vol(v);
    if (vi < 0) {
        if (nvols >= MAXVOLS) { message(L(S_TOOMANY), 0, C_ERR); return -1; }
        vi = nvols++;
    }
    vols[vi] = *v;
    sprintf(src, "%s_MENU\\MENU.DAT", root);
    sprintf(dst, "%s_MENU\\V%03d.DAT", dir, vi + 1);
    if (!small_copy(src, dst)) return -1;
    sprintf(dst, "%s_MENU\\V%03d", dir, vi + 1);
    mkdir(dst);
    for (k = 0; k < 2; k++) {                           /* files of an older build */
        sprintf(pat, "%s\\%s", dst, kinds[k]);
        for (rc = _dos_findfirst(pat, _A_NORMAL, &f); !rc; rc = _dos_findnext(&f)) {
            sprintf(src, "%s\\%s", dst, f.name);
            remove(src);
        }
        _dos_findclose(&f);
    }
    for (k = 0; k < 2; k++) {
        sprintf(pat, "%s_MENU\\%s", root, kinds[k]);
        for (rc = _dos_findfirst(pat, _A_NORMAL | _A_RDONLY, &f); !rc; rc = _dos_findnext(&f)) {
            sprintf(src, "%s_MENU\\%s", root, f.name);
            sprintf(dst, "%s_MENU\\V%03d\\%s", dir, vi + 1, f.name);
            if (!small_copy(src, dst)) { _dos_findclose(&f); return -1; }
        }
        _dos_findclose(&f);
    }
    if (!write_vols(dir)) return -1;
    return vi;
}

static int ask_yn(const char *l1, const char *l2)
{
    int k;
    dialog(24, 70, 272, 60);
    text_c(82, l1, C_TITLE);
    text_c(96, l2, C_TEXT);
    do k = toupper(getkey()); while (k != 'Y' && k != 'S' && k != 'N' && k != K_ESC && k != -1);
    return k == 'Y' || k == 'S';                    /* Y (yes) or S (si) */
}

/* installed mode: look at the CD drives for a Setup86 disc that is new, or a
 * different build of a known one, and offer to add it. quiet: no message if none */
static int add_disc(int quiet)
{
    unsigned char d[8];
    int n = cd_drives(d, 8), i, found = 0, added = -1;
    char buf[60];
    for (i = 0; i < n; i++) {
        char root[4];
        Vol v;
        int vi;
        sprintf(root, "%c:\\", 'A' + d[i]);
        if (!read_id(root, &v)) continue;
        found = 1;
        vi = find_vol(&v);
        if (vi >= 0 && !strcmp(vols[vi].build, v.build)) continue;   /* already up to date */
        sprintf(buf, L(vi < 0 ? S_NEWDISC : S_NEWBUILD), v.set, v.vol);
        if (!ask_yn(buf, L(vi < 0 ? S_ADDQ : S_UPDQ))) continue;
        if ((vi = import_volume(root, base, &v)) < 0) { message(L(S_MCOPYFAIL), 0, C_ERR); continue; }
        added = vi;
    }
    if (added >= 0) {
        int c = 0, j;
        load_data();
        for (j = 0; j < ngames; j++) if (games[j].vi == added) c++;
        sprintf(buf, L(S_ADDED), vols[added].set, vols[added].vol, c);
        message(buf, 0, C_OK);
        return 1;
    }
    if (!quiet && !found) message(L(S_NODISC), 0, C_ERR);
    return 0;
}

/* disc mode: install the program + this disc's list on a hard disk */
static void install_menu(void)
{
    char path[80], dir[84], dst[100], buf[60];
    Vol self = vols[0];                             /* this disc */
    int i;
    strcpy(path, "C:\\SETUP86");
    if (!edit_path(S_MWHERE, (char far *)"Setup86", path)) return;
    if (!make_dirs(path)) { message(L(S_NOMKDIR), path, C_ERR); return; }
    sprintf(dir, "%s\\", path);
    sprintf(dst, "%s_MENU", dir);
    mkdir(dst);
    sprintf(dst, "%sMENU.EXE", dir);
    if (!small_copy(exe, dst)) { message(L(S_MCOPYFAIL), path, C_ERR); return; }
    if (!read_vols(dir)) nvols = 0;                 /* an earlier install: add to it */
    i = import_volume(base, dir, &self);
    nvols = 1; vols[0] = self;                      /* back to disc mode's own entry */
    if (i < 0) { message(L(S_MCOPYFAIL), path, C_ERR); return; }
    sprintf(buf, L(S_MRUN), path);
    message(L(S_MDONE), buf, C_OK);
}

/* installed mode: the CD drive that holds disc vols[vi]; 0 if the user gives up.
 * *reload is set when the list was refreshed from a different build of that disc */
static int ask_disc(int vi, int *reload)
{
    *reload = 0;
    for (;;) {
        unsigned char d[8];
        int n = cd_drives(d, 8), i, k;
        char buf[60];
        for (i = 0; i < n; i++) {
            char root[4];
            Vol v;
            sprintf(root, "%c:\\", 'A' + d[i]);
            if (!read_id(root, &v) || strcmp(v.set, vols[vi].set) || v.vol != vols[vi].vol) continue;
            if (strcmp(v.build, vols[vi].build)) {        /* re-burned: its list may differ */
                sprintf(buf, L(S_NEWBUILD), v.set, v.vol);
                if (!ask_yn(buf, L(S_UPDQ))) return 0;
                if (import_volume(root, base, &v) < 0) { message(L(S_MCOPYFAIL), 0, C_ERR); return 0; }
                *reload = 1;
            }
            return 'A' + d[i];
        }
        dialog(24, 70, 272, 60);
        sprintf(buf, L(S_INSERT), vols[vi].set, vols[vi].vol);
        text_c(82, buf, C_TITLE);
        text_c(110, L(S_READY), C_DIM);
        do k = getkey(); while (k != K_ENTER && k != K_ESC && k != -1);
        if (k != K_ENTER) return 0;
    }
}

static void install(Game far *g)
{
    char path[80], src[100], buf[60], lines[MAXRUN * 2][41], srcroot[80];
    struct diskfree_t df;
    unsigned long avail;
    int i, j, y, n;

    if (coll) {                                  /* find the disc it is on */
        char dirname[9], set[10];
        int vol = vols[g->vi].vol, reload, drv, j;
        _fstrcpy(dirname, g->dir); strcpy(set, vols[g->vi].set);
        drv = ask_disc(g->vi, &reload);
        if (!drv) return;
        if (reload) {                            /* list refreshed: find the game again */
            load_data();
            for (j = 0; j < ngames; j++)
                if (!_fstricmp(games[j].dir, dirname) && !strcmp(vols[games[j].vi].set, set)
                    && vols[games[j].vi].vol == vol) break;
            if (j == ngames) { message(L(S_NOTONDISC), 0, C_ERR); return; }
            g = &games[j];
        }
        sprintf(srcroot, "%c:\\", drv);
    } else
        strcpy(srcroot, base);
    sprintf(path, lang ? "C:\\JUEGOS\\%Fs" : "C:\\GAMES\\%Fs", (char far *)g->dir);   /* default follows F10 */
    if (!edit_path(S_WHERE, g->title, path)) return;
    if (_dos_getdiskfree(toupper(path[0]) - 'A' + 1, &df)) {
        message(L(S_NODRIVE), path, C_ERR); return;
    }
    cluster = (unsigned long)df.sectors_per_cluster * df.bytes_per_sector;
    avail = (unsigned long)df.avail_clusters * cluster;
    sprintf(src, "%s%Fs", srcroot, (char far *)g->dir);
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
    _dos_freemem(rawseg);
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

    strcpy(exe, argv[0]);
    strcpy(base, argv[0]);                       /* data lives next to MENU.EXE */
    p = strrchr(base, '\\');
    install_only = !stricmp(p ? p + 1 : base, "INSTALL.EXE");
    if (p) p[1] = 0; else base[0] = 0;
    _harderr(crit_handler);

    {
        char fn[100];
        struct find_t f;
        sprintf(fn, "%s_MENU\\VOLS.DAT", base);
        coll = !_dos_findfirst(fn, _A_NORMAL, &f);
    }
    if (!load_data()) {
        printf("MENU: cannot read %s_MENU\\%s\n", base, coll ? "VOLS.DAT" : "MENU.DAT");
        return 1;
    }
    {   /* the screenshot buffer is read from the CD too: keep it inside one 64 KB DMA page */
        unsigned char far *b = malloc(2 * (720 + SHOT_W * SHOT_H));
        unsigned long lin;
        if (!b) { printf("MENU: not enough memory\n"); return 1; }
        lin = (unsigned long)FP_SEG(b) * 16 + FP_OFF(b);
        if ((lin & 0xFFFFUL) + 720 + SHOT_W * SHOT_H > 0x10000UL) lin = (lin | 0xFFFFUL) + 1;
        shotbuf = MK_FP((unsigned)(lin >> 4), (unsigned)(lin & 15));
    }

    vga = MK_FP(0xA000, 0);
    set_mode(0x13);
    get_font();
    set_pal(0, 16, &ui_pal[0][0]);
    if (install_only && !coll) {                 /* INSTALL.EXE: just put the menu on the hard disk */
        draw_frame();
        install_menu();
        set_mode(0x03);
        exit_screen();
        return 0;
    }
    draw_frame();
    if (coll) add_disc(1);                       /* a new disc in the drive? */
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
        case K_F12: about(); redraw(top, sel); continue;
        case K_F10: lang = !lang; redraw(top, sel); continue;
        case K_F2:
            if (coll) { if (add_disc(0)) { sel = top = 0; } }
            else install_menu();
            redraw(top, sel);
            continue;
        case K_ENTER:
            install(&games[sel]);
            redraw(top, sel);
            continue;
        case K_F3: case ' ':
            if (info(&games[sel])) install(&games[sel]);
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
