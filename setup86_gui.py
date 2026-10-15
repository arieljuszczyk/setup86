#!/usr/bin/env python3
# SPDX-License-Identifier: MIT  (Copyright (c) 2026 Ariel Juszczyk, see LICENSE)
"""Setup86 Disc Builder: pick games from your eXoDOS install and build one CD at a time.

Left: the games installed in eXoDOS. Right: the disc being built, with its capacity.
Add games with the arrow buttons, a double click or by dragging them across, then
Build ISO: setup86.py makes the disc (game folders, MENU.EXE, text menu) and its ISO.
Runs on Windows and Linux (Python 3 with Tkinter, pycdlib and Pillow), or as Setup86.exe.
"""
import contextlib, json, os, queue, re, subprocess, sys, tempfile, threading, webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import setup86

APP = 'Setup86 Disc Builder'
MB = 1000 * 1000
CAPACITY = setup86.DISC_BUDGET
STATUS = {'ok': '', 'nocd': 'no CD needed', 'music': 'CD music', 'cd': 'needs its own CD',
          'fan': 'fan-made', 'port': 'modern port', 'error': 'error'}
USABLE = ('ok', 'nocd', 'music')
GITHUB = 'https://github.com/arieljuszczyk/setup86'
KOFI = 'https://ko-fi.com/setup86'

# MENU.EXE's palette (dosmenu/menu.c ui_pal, 6-bit VGA values x 4)
def _rgb(r, g, b):
    return '#%02x%02x%02x' % (r * 4 + r // 16, g * 4 + g // 16, b * 4 + b // 16)
C = dict(bg=_rgb(2, 4, 14), panel=_rgb(5, 8, 22), text=_rgb(58, 58, 58), dim=_rgb(38, 40, 46),
         hilite=_rgb(14, 28, 50), white=_rgb(63, 63, 63), title=_rgb(63, 52, 20), bar=_rgb(10, 18, 38),
         bartext=_rgb(50, 54, 63), border=_rgb(28, 36, 56), ok=_rgb(20, 56, 24), err=_rgb(60, 18, 16),
         field=_rgb(0, 0, 0), fieldtx=_rgb(63, 63, 40), prog=_rgb(24, 44, 63))
# the app's own accents instead of the menu's yellow: the red of the floppy's "86", and white text in fields
C.update(title='#ff5a5a', fieldtx=C['white'])


def apply_theme(root):
    """ttk 'clam' recoloured with the DOS menu's blues and yellows."""
    st = ttk.Style(root)
    if 'clam' in st.theme_names():
        st.theme_use('clam')
    root.configure(bg=C['bg'])
    st.configure('.', background=C['bg'], foreground=C['text'], fieldbackground=C['field'],
                 bordercolor=C['border'], lightcolor=C['border'], darkcolor=C['bg'],
                 troughcolor=C['field'], focuscolor=C['title'], insertcolor=C['fieldtx'],
                 selectbackground=C['hilite'], selectforeground=C['white'])
    st.configure('TLabel', background=C['bg'], foreground=C['text'])
    st.configure('Title.TLabel', foreground=C['title'], font=('TkDefaultFont', 10, 'bold'))
    st.configure('Dim.TLabel', foreground=C['dim'])
    st.configure('TFrame', background=C['bg'])
    st.configure('TButton', background=C['bar'], foreground=C['white'], padding=(10, 4))
    st.map('TButton', background=[('disabled', C['panel']), ('pressed', C['hilite']), ('active', C['hilite'])],
           foreground=[('disabled', C['dim'])])
    st.configure('Accent.TButton', background=C['hilite'], foreground=C['white'], font=('TkDefaultFont', 10, 'bold'))
    st.map('Accent.TButton', background=[('disabled', C['panel']), ('active', C['prog'])],
           foreground=[('disabled', C['dim']), ('active', C['white'])])
    for w in ('TEntry', 'TCombobox', 'TSpinbox'):
        st.configure(w, fieldbackground=C['field'], foreground=C['fieldtx'], arrowcolor=C['text'],
                     background=C['bar'], insertcolor=C['fieldtx'])
    st.map('TCombobox', fieldbackground=[('readonly', C['field'])], foreground=[('readonly', C['fieldtx'])],
           selectbackground=[('readonly', C['field'])], selectforeground=[('readonly', C['fieldtx'])])
    root.option_add('*TCombobox*Listbox.background', C['panel'])
    root.option_add('*TCombobox*Listbox.foreground', C['text'])
    root.option_add('*TCombobox*Listbox.selectBackground', C['hilite'])
    root.option_add('*TCombobox*Listbox.selectForeground', C['white'])
    st.configure('TCheckbutton', background=C['bg'], foreground=C['text'], indicatorbackground=C['field'],
                 indicatorforeground=C['fieldtx'])
    st.map('TCheckbutton', background=[('active', C['bg'])])
    st.configure('Treeview', background=C['panel'], fieldbackground=C['panel'], foreground=C['text'],
                 bordercolor=C['border'], rowheight=22)
    st.map('Treeview', background=[('selected', C['hilite'])], foreground=[('selected', C['white'])])
    st.configure('Treeview.Heading', background=C['bar'], foreground=C['bartext'], relief='flat',
                 font=('TkDefaultFont', 9, 'bold'))
    st.map('Treeview.Heading', background=[('active', C['hilite'])])
    st.configure('Vertical.TScrollbar', background=C['bar'], troughcolor=C['bg'], arrowcolor=C['text'],
                 bordercolor=C['bg'])
    st.map('Vertical.TScrollbar', background=[('active', C['hilite'])])
    st.configure('Horizontal.TProgressbar', background=C['prog'], troughcolor=C['field'], bordercolor=C['border'])
    st.configure('Over.Horizontal.TProgressbar', background=C['err'], troughcolor=C['field'])
    st.configure('TPanedwindow', background=C['bg'])
    st.configure('Sash', sashthickness=6, gripcount=0, background=C['bg'])


def asset(name):
    """A file shipped with Setup86 (inside Setup86.exe too)."""
    return os.path.join(setup86.HERE, name)


def config_path():
    base = os.environ.get('APPDATA') if sys.platform.startswith('win') else \
        (os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config'))
    return os.path.join(base or os.path.expanduser('~'), 'setup86', 'app.json')


def load_config():
    try:
        with open(config_path(), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    try:
        os.makedirs(os.path.dirname(config_path()), exist_ok=True)
        with open(config_path(), 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=1)
    except OSError:
        pass


def find_exodos(path):
    """The eXo/eXoDOS games folder for a path that is that folder or the eXoDOS install above it."""
    for p in (path, os.path.join(path, 'eXo', 'eXoDOS'), os.path.join(path, 'eXoDOS')):
        if os.path.isdir(os.path.join(p, '!dos')):
            return os.path.abspath(p)
    return None


def default_exodos():
    for p in ('~/eXoDOS', '~/Games/eXoDOS', 'C:/eXoDOS', 'D:/eXoDOS', '~/Exodium'):
        hit = find_exodos(os.path.expanduser(p))
        if hit:
            return hit
    return ''


def burned_discs(outdir):
    """Games already on discs built into outdir: folder name (lowercase) -> 'Volume 1'."""
    on = {}
    if not os.path.isdir(outdir):
        return on
    for e in sorted(os.scandir(outdir), key=lambda e: e.name):
        if not e.is_dir():
            continue
        for f in os.listdir(e.path):
            m = re.fullmatch(r'DISC(\d+)\.TXT', f, re.I)
            if not m:
                continue
            series = re.match(r'SETUP86-([A-Z]+)-', e.name)
            label = '%s %s' % (series.group(1).capitalize() if series else 'Disc', m.group(1))
            for line in open(os.path.join(e.path, f), encoding='utf-8', errors='replace'):
                if line.strip() and not line.startswith(('#', ' ', '\t')):
                    on[line.split()[0].lower()] = label
    return on


class QueueWriter:
    """stdout/stderr of a build -> the log, through a queue (Tk is only touched by the main thread)."""
    def __init__(self, q):
        self.q = q
    def write(self, s):
        if s:
            self.q.put(('log', s))
    def flush(self):
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__(className='setup86')   # WM_CLASS: Linux docks match it to setup86.desktop
        self.title('%s %s' % (APP, setup86.VERSION))
        self.geometry('1180x720')
        self.minsize(900, 560)
        self.cfg = load_config()
        self.games = {}            # folder -> catalog row
        self.chosen = []           # folders on the disc, in the order added
        self.on_disc = {}
        self.q = queue.Queue()
        self.busy = False
        self.drag = None
        apply_theme(self)
        try:
            self.icon = tk.PhotoImage(file=asset('art/setup86-icon-128.png'))
            self.iconphoto(True, self.icon)
        except tk.TclError:
            self.icon = None
        self.build_ui()
        self.bind('<F1>', lambda e: self.about())
        self.after(100, self.poll)
        if self.src.get():
            self.after(200, self.load)

    # ---------- layout ----------
    def build_ui(self):
        head = tk.Frame(self, bg=C['bar'])
        head.pack(fill='x')
        tk.Label(head, text='SETUP86 \u00b7 DISC BUILDER', bg=C['bar'], fg=C['bartext'],
                 font=('TkFixedFont', 13, 'bold'), pady=5).pack(side='left', expand=True)
        tk.Label(head, text='v' + setup86.VERSION, bg=C['bar'], fg=C['dim'], font=('TkFixedFont', 8)).place(
            relx=1.0, x=-8, rely=0.5, anchor='e')
        foot = tk.Frame(self, bg=C['bar'])
        foot.pack(side='bottom', fill='x')
        tk.Label(foot, text='Add \u25ba  Double click  Drag across  \u00b7  F1 About', bg=C['bar'], fg=C['bartext'],
                 font=('TkFixedFont', 9, 'bold'), pady=3).pack(side='left', expand=True)
        about = tk.Label(foot, text='About', bg=C['bar'], fg=C['title'], font=('TkFixedFont', 9, 'bold', 'underline'),
                         cursor='hand2', padx=8)
        about.place(relx=1.0, rely=0.5, anchor='e')
        about.bind('<Button-1>', lambda e: self.about())
        top = ttk.Frame(self, padding=(8, 8, 8, 4))
        top.pack(fill='x')
        ttk.Label(top, text='eXoDOS:').pack(side='left')
        self.src = tk.StringVar(value=self.cfg.get('exodos') or default_exodos())
        ttk.Entry(top, textvariable=self.src).pack(side='left', fill='x', expand=True, padx=4)
        ttk.Button(top, text='Browse...', command=self.browse_src).pack(side='left')
        ttk.Button(top, text='Load', command=self.load).pack(side='left', padx=(4, 0))

        panes = ttk.PanedWindow(self, orient='horizontal')
        panes.pack(fill='both', expand=True, padx=8)

        # left: the eXoDOS games
        left = ttk.Frame(panes)
        panes.add(left, weight=3)
        bar = ttk.Frame(left)
        bar.pack(fill='x', pady=(0, 4))
        self.left_title = ttk.Label(bar, text='Your eXoDOS games', style='Title.TLabel')
        self.left_title.pack(side='left')
        self.show_all = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Show games that can't go on a disc", variable=self.show_all,
                        command=self.refresh_left).pack(side='right')
        bar2 = ttk.Frame(left)
        bar2.pack(fill='x', pady=(0, 4))
        ttk.Label(bar2, text='Search:').pack(side='left')
        self.search = tk.StringVar()
        self.search.trace_add('write', lambda *a: self.refresh_left())
        ttk.Entry(bar2, textvariable=self.search, width=24).pack(side='left', padx=4)
        ttk.Label(bar2, text='Genre:').pack(side='left', padx=(8, 0))
        self.genre = tk.StringVar(value='All')
        self.genre_box = ttk.Combobox(bar2, textvariable=self.genre, state='readonly', width=18, values=['All'])
        self.genre_box.pack(side='left', padx=4)
        self.genre_box.bind('<<ComboboxSelected>>', lambda e: self.refresh_left())
        self.left = self.make_tree(left, (('year', 'Year', 50), ('genre', 'Genre', 150), ('lang', 'Lang', 45),
                                          ('sound', 'MIDI', 85), ('size', 'MB', 60), ('status', 'Note', 150)))
        self.left.tag_configure('off', foreground=C['dim'])
        self.left.tag_configure('used', foreground=C['prog'])
        self.left.bind('<Double-1>', lambda e: self.add())

        # middle: the buttons
        mid = ttk.Frame(panes, padding=6)
        panes.add(mid, weight=0)
        ttk.Frame(mid).pack(expand=True)
        ttk.Button(mid, text='Add \u25ba', width=10, command=self.add).pack(pady=4)
        ttk.Button(mid, text='\u25c4 Remove', width=10, command=self.remove).pack(pady=4)
        ttk.Button(mid, text='Clear', width=10, command=self.clear).pack(pady=(16, 4))
        ttk.Frame(mid).pack(expand=True)

        # right: the disc
        right = ttk.Frame(panes)
        panes.add(right, weight=2)
        hdr = ttk.Frame(right)
        hdr.pack(fill='x', pady=(0, 4))
        ttk.Label(hdr, text='Disc:', style='Title.TLabel').pack(side='left')
        ttk.Label(hdr, text='Setup86').pack(side='left', padx=(6, 2))
        self.series = tk.StringVar(value=self.cfg.get('series', 'Volume'))
        ttk.Entry(hdr, textvariable=self.series, width=10).pack(side='left')
        self.number = tk.IntVar(value=1)
        ttk.Spinbox(hdr, from_=1, to=99, textvariable=self.number, width=4).pack(side='left', padx=4)
        self.right = self.make_tree(right, (('size', 'MB', 60),))
        self.right.bind('<Double-1>', lambda e: self.remove())
        cap = ttk.Frame(right)
        cap.pack(fill='x', pady=(6, 2))
        self.capbar = ttk.Progressbar(cap, maximum=CAPACITY / MB, length=200)
        self.capbar.pack(side='left', fill='x', expand=True)
        self.caplabel = ttk.Label(cap, text='', width=24, anchor='e')
        self.caplabel.pack(side='left', padx=(6, 0))
        outf = ttk.Frame(right)
        outf.pack(fill='x', pady=(4, 0))
        ttk.Label(outf, text='Output:').pack(side='left')
        self.out = tk.StringVar(value=self.cfg.get('output') or os.path.join(os.path.expanduser('~'), 'Setup86 ISOs'))
        ttk.Entry(outf, textvariable=self.out).pack(side='left', fill='x', expand=True, padx=4)
        ttk.Button(outf, text='Browse...', command=self.browse_out).pack(side='left')
        btns = ttk.Frame(right)
        btns.pack(fill='x', pady=6)
        self.build_btn = ttk.Button(btns, text='Build ISO', style='Accent.TButton', command=self.build)
        self.build_btn.pack(side='right')
        ttk.Button(btns, text='Open output folder', command=self.open_out).pack(side='right', padx=6)

        # bottom: progress and the build log
        bottom = ttk.Frame(self, padding=(8, 2, 8, 8))
        bottom.pack(fill='x')
        self.status = ttk.Label(bottom, text='')
        self.status.pack(fill='x')
        self.progress = ttk.Progressbar(bottom, mode='determinate')
        self.progress.pack(fill='x', pady=2)
        self.log = tk.Text(bottom, height=7, wrap='word', state='disabled', font=('TkFixedFont', 9),
                           bg=C['field'], fg=C['text'], insertbackground=C['fieldtx'], relief='flat',
                           highlightthickness=1, highlightbackground=C['border'], highlightcolor=C['border'])
        self.log.pack(fill='x')
        self.update_capacity()

    def make_tree(self, parent, cols):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True)
        tree = ttk.Treeview(frame, columns=[c[0] for c in cols], selectmode='extended')
        tree.heading('#0', text='Game', command=lambda: self.sort(tree, '#0'))
        tree.column('#0', width=260, stretch=True)
        for key, title, width in cols:
            tree.heading(key, text=title, command=lambda k=key: self.sort(tree, k))
            tree.column(key, width=width, stretch=key in ('genre', 'status'),
                        anchor='e' if key == 'size' else 'w')
        sb = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='left', fill='y')
        tree.bind('<ButtonPress-1>', self.drag_start, add='+')
        tree.bind('<ButtonRelease-1>', self.drag_end, add='+')
        return tree

    # ---------- loading ----------
    def browse_src(self):
        d = filedialog.askdirectory(title='Your eXoDOS folder (the one with eXo inside)',
                                    initialdir=self.src.get() or os.path.expanduser('~'))
        if d:
            self.src.set(d)
            self.load()

    def browse_out(self):
        d = filedialog.askdirectory(title='Where to put the ISOs', initialdir=self.out.get())
        if d:
            self.out.set(d)
            self.mark_burned()

    def load(self):
        if self.busy:
            return
        src = find_exodos(self.src.get().strip())
        if not src:
            messagebox.showerror(APP, 'No eXoDOS games found in:\n%s\n\nChoose your eXoDOS folder: the one '
                                      'with eXo\\eXoDOS inside (where Exodium or eXoDOS put the games).'
                                 % self.src.get())
            return
        self.src.set(src)
        self.cfg['exodos'] = src
        save_config(self.cfg)
        self.set_busy(True, 'Reading your eXoDOS games...')

        def work():
            try:
                rows = setup86.catalog(src, progress=lambda i, n, g: self.q.put(('progress', i, n, g)))
                self.q.put(('loaded', rows))
            except BaseException as e:
                self.q.put(('error', 'Could not read the games: %s' % e))
        threading.Thread(target=work, daemon=True).start()

    def loaded(self, rows):
        self.games = {r['g']: r for r in rows}
        self.chosen = [g for g in self.chosen if g in self.games]
        genres = sorted({x.strip() for r in rows for x in r['genre'].split(';') if x.strip()})
        self.genre_box['values'] = ['All'] + genres
        usable = sum(r['status'] in USABLE for r in rows)
        self.status['text'] = '%d games installed, %d can go on a disc' % (len(rows), usable)
        self.mark_burned()

    def mark_burned(self):
        self.on_disc = burned_discs(self.out.get())
        nums = [int(v.split()[-1]) for v in self.on_disc.values() if v.split()[-1].isdigit()
                and v.split()[0].lower() == self.series.get().lower()]
        if nums and not self.busy:
            self.number.set(max(nums) + 1)
        self.refresh_left()
        self.refresh_right()

    # ---------- lists ----------
    def row_values(self, r, right=False):
        size = '%.1f' % (r['size'] / MB) if r['size'] else ''
        if right:
            return (size,)
        note = STATUS.get(r['status'], r['status'])
        if r['status'] == 'error':
            note = r['note']
        if r['g'].lower() in self.on_disc:
            note = ('on ' + self.on_disc[r['g'].lower()] + ('; ' + note if note else ''))
        return (r['year'], r['genre'].replace(';', ','), r['lang'].upper(), r.get('sound', ''), size, note)

    def game_title(self, r):
        return r['title'] + (' (ES)' if r['lang'] == 'es' else '')

    def refresh_left(self):
        if not hasattr(self, 'left'):
            return
        self.left.delete(*self.left.get_children())
        q = self.search.get().strip().lower()
        genre = self.genre.get()
        shown = 0
        for r in sorted(self.games.values(), key=lambda r: r['title'].lower()):
            if r['g'] in self.chosen:
                continue
            if r['status'] not in USABLE and not self.show_all.get():
                continue
            if q and q not in r['title'].lower() and q not in r['g'].lower():
                continue
            if genre != 'All' and genre not in r['genre']:
                continue
            tags = ('off',) if r['status'] not in USABLE else ('used',) if r['g'].lower() in self.on_disc else ()
            self.left.insert('', 'end', iid=r['g'], text=self.game_title(r), values=self.row_values(r), tags=tags)
            shown += 1
        self.left_title['text'] = 'Your eXoDOS games (%d shown)' % shown

    def refresh_right(self):
        self.right.delete(*self.right.get_children())
        for g in self.chosen:
            r = self.games[g]
            self.right.insert('', 'end', iid=g, text=self.game_title(r), values=self.row_values(r, right=True))
        self.update_capacity()

    def update_capacity(self):
        used = sum(self.games[g]['size'] for g in self.chosen)
        over = used > CAPACITY
        self.capbar.configure(value=min(used, CAPACITY) / MB,
                              style='Over.Horizontal.TProgressbar' if over else 'Horizontal.TProgressbar')
        self.caplabel['text'] = '%s%.0f / %d MB  (%d games)' % ('TOO BIG: ' if over else '', used / MB,
                                                               CAPACITY // MB, len(self.chosen))
        if hasattr(self, 'build_btn'):
            self.build_btn.state(['disabled'] if over or not self.chosen or self.busy else ['!disabled'])

    def sort(self, tree, key):
        rows = [(tree.item(i, 'text') if key == '#0' else tree.set(i, key), i) for i in tree.get_children()]
        num = key in ('size', 'year')
        rev = getattr(tree, '_rev', {}).get(key, False)
        rows.sort(key=lambda x: (float(x[0]) if num and x[0] else 0) if num else x[0].lower(), reverse=rev)
        for n, (_, i) in enumerate(rows):
            tree.move(i, '', n)
        tree._rev = dict(getattr(tree, '_rev', {}), **{key: not rev})

    def add(self, items=None):
        items = items or self.left.selection()
        skipped = []
        for g in items:
            if self.games[g]['status'] not in USABLE:
                skipped.append('%s: %s' % (self.games[g]['title'], self.games[g]['note'] or STATUS[self.games[g]['status']]))
            elif g not in self.chosen:
                self.chosen.append(g)
        self.refresh_left()
        self.refresh_right()
        if skipped:
            messagebox.showinfo(APP, "These can't go on a disc:\n\n" + '\n'.join(skipped[:15]))

    def remove(self, items=None):
        items = items or self.right.selection()
        self.chosen = [g for g in self.chosen if g not in items]
        self.refresh_left()
        self.refresh_right()

    def clear(self):
        self.chosen = []
        self.refresh_left()
        self.refresh_right()

    # ---------- drag and drop between the two lists ----------
    def drag_start(self, event):
        tree = event.widget
        row = tree.identify_row(event.y)
        self.drag = (tree, row) if row else None

    def drag_end(self, event):
        if not self.drag:
            return
        tree, row = self.drag
        self.drag = None
        target = self.winfo_containing(event.x_root, event.y_root)
        while target is not None and target not in (self.left, self.right):
            target = target.master
        if target is None or target is tree:
            return
        items = tree.selection() if row in tree.selection() else (row,)
        if tree is self.left:
            self.add(items)
        else:
            self.remove(items)

    # ---------- building ----------
    def build(self):
        if self.busy or not self.chosen:
            return
        series = self.series.get().strip()
        if not re.fullmatch(r'[A-Za-z]{1,9}', series):
            messagebox.showerror(APP, 'The disc series is one word, letters only, up to 9 (e.g. Volume, Adventure).')
            return
        n = self.number.get()
        outdir = os.path.abspath(os.path.expanduser(self.out.get().strip()))
        work = os.path.join(outdir, 'SETUP86-%s-%02d' % (series.upper(), n))
        if os.path.exists(work):
            if not messagebox.askyesno(APP, 'Setup86 %s %d was already built in\n%s\n\nBuild it again? The old one '
                                            'is replaced.' % (series, n, work)):
                return
            if not os.path.exists(os.path.join(work, '.setup86')):
                messagebox.showerror(APP, '%s exists and was not made by Setup86: choose another output folder.' % work)
                return
        os.makedirs(outdir, exist_ok=True)
        self.cfg.update(output=outdir, series=series)
        save_config(self.cfg)
        lst = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, encoding='utf-8')
        lst.write('\n'.join(self.chosen) + '\n')
        lst.close()
        argv = [self.src.get(), work, '--games', lst.name, '--series', series, '--first', str(n),
                '--iso', 'all', '--one-disc']
        self.clear_log()
        self.set_busy(True, 'Building Setup86 %s %d (%d games)...' % (series, n, len(self.chosen)))
        self.progress.configure(mode='indeterminate')
        self.progress.start(12)

        def work_thread():
            w = QueueWriter(self.q)
            code = 0
            try:
                with contextlib.redirect_stdout(w), contextlib.redirect_stderr(w):
                    setup86.main(argv)
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 1
                if e.code and not isinstance(e.code, int):
                    w.write('\n%s\n' % e.code)
            except BaseException as e:
                code = 1
                w.write('\nERROR: %s\n' % e)
            finally:
                os.unlink(lst.name)
            iso = os.path.join(work, 'SETUP86-%s-%02d.ISO' % (series.upper(), n))
            self.q.put(('built', code, iso, work))
        threading.Thread(target=work_thread, daemon=True).start()

    def built(self, code, iso, work):
        self.progress.stop()
        self.progress.configure(mode='determinate', value=0)
        self.set_busy(False, '')
        if code == 0 and os.path.isfile(iso):
            mb = os.path.getsize(iso) / MB
            self.status['text'] = 'Done: %s (%s MB)' % (iso, ('%.1f' if mb < 10 else '%.0f') % mb)
            done = len(self.chosen)
            self.chosen = []
            self.mark_burned()
            messagebox.showinfo(APP, 'Setup86 disc ready, %d game%s:\n\n%s\n\nTry it in DOSBox, then burn it to a CD-R '
                                     '(a low speed reads best in old drives). The game list and how to start each '
                                     'game are in DISC*.TXT next to it.' % (done, '' if done == 1 else 's', iso))
        else:
            self.status['text'] = 'The build failed: see the log below.'
            messagebox.showerror(APP, 'The build failed. The log at the bottom of the window says why.')

    def about(self):
        if getattr(self, 'about_win', None) and self.about_win.winfo_exists():
            self.about_win.lift()
            return
        w = self.about_win = tk.Toplevel(self, bg=C['bg'])
        w.title('About Setup86')
        w.resizable(False, False)
        w.transient(self)
        box = tk.Frame(w, bg=C['panel'], highlightthickness=2, highlightbackground=C['border'], padx=34, pady=18)
        box.pack(padx=10, pady=10)

        def line(text, fg=C['text'], size=10, bold=False, pady=(0, 0), link=None):
            lab = tk.Label(box, text=text, bg=C['panel'], fg=fg, font=('TkFixedFont', size, 'bold' if bold else 'normal'),
                           cursor='hand2' if link else '')
            lab.pack(pady=pady)
            if link:
                lab.bind('<Button-1>', lambda e: webbrowser.open(link))
        if self.icon:
            tk.Label(box, image=self.icon, bg=C['panel']).pack(pady=(0, 8))
        line('About Setup86', C['title'], 14, True)
        line('Version ' + setup86.VERSION, C['dim'], 10, pady=(0, 12))
        line('Created by Ariel Juszczyk', C['text'], 11, True)
        line('(c) 2026 ariel.juszczyk@gmail.com', C['dim'], 10, pady=(0, 12))
        line('Made for the eXoDOS collection,')
        line('to run on real x86 hardware.', pady=(0, 12))
        line('Free & open source - MIT License')
        line('github.com/arieljuszczyk/setup86', C['title'], 10, True, pady=(0, 12), link=GITHUB)
        line('Please donate to support it:')
        line('ko-fi.com/setup86', C['title'], 10, True, pady=(0, 16), link=KOFI)
        ttk.Button(box, text='OK', style='Accent.TButton', command=w.destroy).pack()
        w.bind('<Escape>', lambda e: w.destroy())
        w.bind('<Return>', lambda e: w.destroy())
        w.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - w.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - w.winfo_height()) // 3
        w.geometry('+%d+%d' % (max(x, 0), max(y, 0)))
        w.grab_set()

    def open_out(self):
        d = os.path.abspath(os.path.expanduser(self.out.get()))
        if not os.path.isdir(d):
            return
        if sys.platform.startswith('win'):
            os.startfile(d)
        else:
            subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', d])

    # ---------- plumbing ----------
    def set_busy(self, busy, text):
        self.busy = busy
        self.status['text'] = text
        self.config(cursor='watch' if busy else '')
        self.update_capacity()

    def clear_log(self):
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled')

    def append_log(self, s):
        self.log.configure(state='normal')
        self.log.insert('end', s)
        self.log.see('end')
        self.log.configure(state='disabled')

    def poll(self):
        try:
            while True:
                m = self.q.get_nowait()
                if m[0] == 'log':
                    self.append_log(m[1])
                elif m[0] == 'progress':
                    _, i, n, g = m
                    self.progress.configure(maximum=n, value=i + 1)
                    self.status['text'] = 'Reading your eXoDOS games... %d / %d  %s' % (i + 1, n, g)
                elif m[0] == 'loaded':
                    self.set_busy(False, '')
                    self.progress.configure(value=0)
                    self.loaded(m[1])
                elif m[0] == 'built':
                    self.built(*m[1:])
                elif m[0] == 'error':
                    self.set_busy(False, m[1])
                    messagebox.showerror(APP, m[1])
        except queue.Empty:
            pass
        self.after(100, self.poll)


def main():
    for name in ('stdout', 'stderr'):        # a windowed Setup86.exe has no console
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, 'w'))
    App().mainloop()


if __name__ == '__main__':
    main()
