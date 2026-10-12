#!/usr/bin/env python3
r"""Copy the DOS files of eXoDOS-installed games into folders for burning to CD.

For each game, keeps only what a real DOS PC needs: the files DOSBox mounted
as C:\ for it, minus eXo/DOSBox-only extras (menus, network scripts, DOSBox
GUS drivers, CD/floppy images, cracks). No launchers or installers are added.

Output (OUT is rebuilt on every run, files are hardlinks into eXoDOS):
  DISCn/<GAME>/...      one folder per game: copy it to C:\<GAME> (DISCn.TXT says how to start it)
  DISCn.TXT             per game: where it goes on C:, how to start it (not on the CD)
  DOSGAMESn.ISO         ISO9660 image of DISCn (only discs chosen with --iso)
If a game's Spanish version is downloaded (!spanish/<game>), it is used instead of English.
Games are packed alphabetically: disc 1 from A until the next game doesn't fit.
Games that need their own CD (eXo mounts a CD image) are left out entirely.
Games listed in G have hand-checked notes; any other game folder is converted
automatically from its eXo dosbox.conf/run.bat (listed under WARNINGS).
After burning a disc, pass its list with --burned DISC1.TXT on later runs so
new games don't reshuffle what's already burned.
"""
import os, re, sys, shutil, base64

SRC = OUT = None   # set in main()
LANG = {}          # game -> 'es' when the Spanish version is used (set in main)

def game_src(g):
    """Folder with the game's files: the Spanish version if downloaded, else English."""
    return os.path.join(SRC, '!spanish', g) if LANG.get(g) == 'es' else os.path.join(SRC, g)

def game_conf(g):
    return os.path.join(SRC, '!dos', '!spanish', g, 'dosbox.conf') if LANG.get(g) == 'es' \
        else os.path.join(SRC, '!dos', g, 'dosbox.conf')
DISC_BUDGET = 720 * 1000 * 1000   # bytes; an 80-min CD-R holds ~737 MB, leaves headroom for ISO overhead

# --- per-game definitions --------------------------------------------------
# kind: 'root'  -> DOSBox C:\ was the eXoDOS dir, so the game lives in C:\<G>
#       'self'  -> DOSBox C:\ was the game dir, all files at its root;
#                  we place them in C:\<G> (none of these use absolute paths)
#       'drive' -> DOSBox C:\ was the game dir, with real subfolders that
#                  the game expects at C:\<SUB> (absolute paths inside)
# subs:  for 'drive', subfolders that go to C:\ root
# loose: for 'drive', where loose root files go (dir name) or None to drop
# cd:    True if the game needs its own CD in drive D: (images -> CD-IMAGES)
# opts:  launcher menu entries: (label, [DOS commands])

def snd(dirn, exe, presets, pre=None):
    """eXo-style 'play with sound X' options: copy preset configs, run."""
    names = {'SB16': 'Sound Blaster', 'MT32': 'Roland MT-32',
             'SC55': 'General MIDI (Sound Canvas)', 'GUS': 'Gravis Ultrasound',
             'ADLIB': 'AdLib', 'TANDY': 'Tandy', 'GB': 'Game Blaster'}
    out = []
    for p in presets:
        cmds = ['CD \\' + dirn]
        cmds += (pre or [])
        cmds += ['COPY %s\\*.* . >NUL' % p, exe]
        out.append(('with ' + names[p], cmds))
    return out

def preset_menu(dirs, play, presets, setup=None):
    """For games eXo remembered a sound choice for: play + one-time presets."""
    names = {'SB16': 'Sound Blaster', 'SC55': 'General MIDI (Sound Canvas)',
             'GUS': 'Gravis Ultrasound', 'CDA': 'CD audio music'}
    out = list(play)
    for p in presets:
        cmds = []
        for d in dirs:
            cmds += ['CD \\' + d, 'COPY %s\\*.* . >NUL' % p]
        cmds += ['ECHO %s settings applied.' % names[p], 'PAUSE']
        out.append(('Set sound to ' + names[p] + ' (do once)', cmds))
    if setup:
        out.append(('Run SETUP (sound / controls)', setup))
    return out

GUSMID = ['IF EXIST C:\\ULTRASND\\ULTRAMID.EXE C:\\ULTRASND\\ULTRAMID']

G = {
 'ACF91':   dict(title='All-American College Football (1991)', kind='drive', subs=['COLLEGE'], floppy=['floppy/AACF.IMA'],
                 opts=[('Game mode', ['CD \\COLLEGE', 'CLP']), ('GM mode', ['CD \\COLLEGE', 'GM'])]),
 'ActionSo':dict(title='Action Soccer (1995)', kind='drive', subs=['ACTION'], loose='ACTION', cd=True,
                 opts=[('Play', ['CD \\ACTION', 'FAKEHMA', 'CALL AS'])]),
 'Actua95': dict(title='Actua Soccer (1995)', kind='drive', subs=['ASOCCER'], cd=True,
                 opts=snd('ASOCCER', 'SOCCER', ['SB16', 'MT32', 'SC55'])),
 'adark1':  dict(title='Alone in the Dark (1992)', kind='drive', subs=['DARK', 'INDARKF'], cd=True,
                 floppy=['floppy/Disk1.ima', 'floppy/Disk2.ima', 'floppy/Disk3.ima', 'floppy/Disk4.ima'],
                 opts=[('Floppy version (no CD needed)', ['CD \\INDARKF', 'ALONE']),
                       ('CD version (needs the CD)', ['CD \\DARK\\INDARK', 'INDARK']),
                       ('Jack in the Dark (needs the CD)', ['CD \\DARK\\JACK', 'JACK'])]),
 'adark2':  dict(title='Alone in the Dark 2 (1993)', kind='root', cd=True,
                 opts=[('Floppy version (no CD needed)', ['CD \\ADARK2\\FLOPPY', 'CALL ALONE']),
                       ('CD version (needs the CD)', ['CD \\ADARK2', 'AITD2'])]),
 'AmerGlad':dict(title='American Gladiators (1992)', kind='root',
                 opts=snd('AMERGLAD', 'GLAD', ['SB16', 'MT32'])),
 'bchess':  dict(title='Battle Chess (1988)', kind='drive', subs=['CHESS'], floppydir='floppy',
                 opts=[('with PC speaker', ['CD \\CHESS', 'CHESS']), ('with AdLib', ['CD \\CHESS', 'CHESS /ADLIB'])]),
 'bioforge':dict(title='Bioforge (1995)', kind='root', cd=True,
                 opts=snd('BIOFORGE', 'BIOFORGE', ['SB16', 'SC55'],
                          pre=['IF EXIST AILXMI.DLL DEL AILXMI.DLL', 'IF EXIST INSTALL.OPT DEL INSTALL.OPT'])),
 'Blacktho':dict(title='Blackthorne (1994)', kind='drive', subs=['BTHORNE'], cd=True,
                 opts=snd('BTHORNE', 'BTHORNE', ['SB16', 'SC55']) +
                      [('with Gravis Ultrasound', ['CD \\BTHORNE', 'COPY GUS\\*.* . >NUL', 'CALL BTHORNEG'])]),
 'Blood':   dict(title='Blood (1997) + Cryptic Passage + Plasma Pak', kind='drive',
                 subs=['BLOOD', 'BLOODcp', 'BloodPak', 'Blood3D'], loose='BLOOD', cd=True,
                 drop=['_BLOOD.EXE'],
                 opts=preset_menu(['BLOOD', 'BLOODCP', 'BLOODPAK', 'BLOOD3D'],
                          [('Blood', ['CD \\BLOOD', 'BLOOD']),
                           ('Blood: Cryptic Passage', ['CD \\BLOODCP', 'CRYPTIC']),
                           ('Blood: Plasma Pak', ['CD \\BLOODPAK', 'BLOOD']),
                           ('Blood: Plasma Pak 3Dfx (needs a Voodoo card)', ['CD \\BLOOD3D', 'CALL 3DFX'])],
                          ['SB16', 'GUS', 'SC55', 'CDA'],
                          setup=['CD \\BLOODPAK', 'SETUP'])),
 'BubbBobb':dict(title='Bubble Bobble (1988)', kind='self',
                 opts=[('AdLib, 1 player', ['CD \\BUBBBOBB', 'COPY ADLIB\\*.* . >NUL', 'BUBBLE']),
                       ('AdLib, 2 players', ['CD \\BUBBBOBB', 'COPY ADLIB\\*.* . >NUL', 'BUBBLE R']),
                       ('Tandy, 1 player', ['CD \\BUBBBOBB', 'COPY TANDY\\*.* . >NUL', 'BUBBLE']),
                       ('Game Blaster, 1 player', ['CD \\BUBBBOBB', 'COPY GB\\*.* . >NUL', 'BUBBLE'])]),
 'caesar':  dict(title='Caesar (1992)', kind='root',
                 opts=[('Caesar', ['CD \\CAESAR', 'CALL CAESAR']),
                       ('Caesar + Cohort II battles', ['CD \\CAESAR\\COMBINED', 'CALL CAESAR'])]),
 'CalGam':  dict(title='California Games (1988)', kind='self', opts=[('Play', ['CD \\CALGAM', 'LOADFIX CALGAMES'])]),
 'CalGam2': dict(title='California Games II (1990)', kind='self', opts=[('Play', ['CD \\CALGAM2', 'CGII'])]),
 'castles': dict(title='Castles (1991)', kind='root',
                 opts=[('with Sound Blaster/AdLib', ['CD \\CASTLES', 'CASINT /VGA /ADLIB', 'CASTLES1 87670918 /VGA /ADLIB /NOSTICK /NOTITLE']),
                       ('with Roland MT-32', ['CD \\CASTLES', 'CASINT /VGA /ROLAND', 'CASTLES1 87670918 /VGA /ROLAND /NOSTICK /NOTITLE']),
                       ('with Tandy', ['CD \\CASTLES', 'CASINT /VGA /TANDY', 'CASTLES1 87670918 /VGA /TANDY /NOSTICK /NOTITLE'])]),
 'CastleWo':dict(title='Castle Wolfenstein (1984)', kind='self', opts=[('Play', ['CD \\CASTLEWO', 'CW'])]),
 'CKeen1':  dict(title='Commander Keen 1 - Marooned on Mars (1990)', kind='self', opts=[('Play', ['CD \\CKEEN1', 'KEEN1'])]),
 'CKeen2':  dict(title='Commander Keen 2 - The Earth Explodes (1990)', kind='self', opts=[('Play', ['CD \\CKEEN2', 'KEEN2'])]),
 'CKeen3':  dict(title='Commander Keen 3 - Keen Must Die! (1990)', kind='self', opts=[('Play', ['CD \\CKEEN3', 'KEEN3'])]),
 'CKeen4':  dict(title='Commander Keen 4 - Secret of the Oracle (1991)', kind='self', opts=[('Play', ['CD \\CKEEN4', 'KEEN4'])]),
 'CKeen5':  dict(title='Commander Keen 5 - The Armageddon Machine (1991)', kind='self', opts=[('Play', ['CD \\CKEEN5', 'KEEN5'])]),
 'CKeen6':  dict(title='Commander Keen 6 - Aliens Ate My Baby Sitter! (1991)', kind='drive', subs=['KEEN'],
                 floppy=['floppy/ALIENS_D1.IMA', 'floppy/ALIENS_D2.IMA', 'floppy/ALIENS_D3.IMA'],
                 opts=[('Play', ['CD \\KEEN', 'POGO6'])]),
 'comcon':  dict(title='Command & Conquer (1995)', kind='root', cd=True,
                 opts=[('GDI campaign (insert CD 1)', ['CD \\COMCON', 'C&C']),
                       ('NOD campaign (insert CD 2)', ['CD \\COMCON', 'C&C']),
                       ('Covert Operations (insert Covert Ops CD)', ['CD \\COMCON', 'C&C']),
                       ('Hidden dinosaur campaign (insert CD 1)', ['CD \\COMCON', 'C&C FUNPARK'])]),
 'CrusRegr':dict(title='Crusader - No Regret (1996)', kind='drive', subs=['REGRET'], cd=True,
                 opts=snd('REGRET', 'REGRET', ['SB16']) + snd('REGRET', 'REGRET', ['GUS'], pre=GUSMID)),
 'CrusRemo':dict(title='Crusader - No Remorse (1995)', kind='drive', subs=['CRUSADER'], cd=True,
                 opts=snd('CRUSADER', 'CRUSADER', ['SB16', 'GUS'])),
 'cyberia': dict(title='Cyberia (1994)', kind='root', cd=True, opts=[('Play', ['CD \\CYBERIA', 'CALL CYBERIA'])]),
 'DeDerby': dict(title='Destruction Derby (1995)', kind='drive', subs=['DERBY'], cd=True,
                 opts=[('Play', ['CD \\DERBY', 'DD']), ('Setup', ['CD \\DERBY', 'SETUP'])]),
 'DeDerby2':dict(title='Destruction Derby 2 (1996)', kind='drive', subs=['dd2'], cd=True, drop=['DD2DOSXP.bat'],
                 opts=[('Play', ['CD \\DD2', 'DD2']), ('Play hi-res (SVGA)', ['CD \\DD2', 'DD2HIRES'])]),
 'Descent': dict(title='Descent (1995)', kind='drive', subs=['DESCENT'], cd=True,
                 opts=[(l, c) for p, h in [('SB16', ''), ('SB16', ' -640x480'), ('SC55', ''), ('SC55', ' -640x480')]
                       for l, c in [(('with %s%s' % ({'SB16': 'Sound Blaster', 'SC55': 'General MIDI'}[p], ' hi-res' if h else '')),
                                     ['CD \\DESCENT', 'IF EXIST DESCENT.CFG DEL DESCENT.CFG', 'COPY %s\\*.* . >NUL' % p, 'DESCENT' + h])]]),
 'DesStr':  dict(title='Desert Strike - Return to the Gulf (1994)', kind='drive', subs=['DESERT'], cd=True,
                 opts=[(l, ['CD \\DESERT', 'IF EXIST DESERT.CFG DEL DESERT.CFG', 'COPY %s\\*.* . >NUL' % p, 'CALL DESERT'])
                       for l, p in [('with Sound Blaster', 'SB16'), ('with Roland MT-32', 'MT32'), ('with General MIDI', 'SC55')]]),
 'Dlair2':  dict(title="Dragon's Lair II - Time Warp (1990)", kind='self',
                 opts=[('Play (press 0 on the numpad to start, numpad to play)', ['CD \\DLAIR2', 'TIMEWARP'])]),
 'Dlair89': dict(title="Dragon's Lair (1989)", kind='self', opts=[('Play', ['CD \\DLAIR89', 'GAME'])]),
 'DOOM':    dict(title='DOOM (1993)', kind='self',
                 opts=preset_menu(['DOOM'], [('Play DOOM', ['CD \\DOOM', 'DOOM'])], ['SB16', 'GUS', 'SC55'],
                                  setup=['CD \\DOOM', 'SETUP'])),
 'DOOMII':  dict(title='DOOM II (1994)', kind='root',
                 opts=preset_menu(['DOOMII'], [('Play DOOM II', ['CD \\DOOMII', 'DOOM2'])], ['SB16', 'SC55'],
                                  setup=['CD \\DOOMII', 'SETUP'])),
 'Duke3D':  dict(title='Duke Nukem 3D (1996)', kind='drive', subs=['DUKE3D'], drop=['DUKE3D.BAT', 'DMO'],
                 opts=preset_menu(['DUKE3D'], [('Play Duke Nukem 3D', ['CD \\DUKE3D', 'DUKE3D'])], ['SB16', 'GUS', 'SC55'],
                                  setup=['CD \\DUKE3D', 'SETUP'])),
 'dune':    dict(title='Dune (1992)', kind='drive', subs=['DUNECD'], loose='DUNE', cd=True, drop=['DUNE.vlp', 'DUNE.BAT'],
                 opts=[('Floppy version, Sound Blaster', ['CD \\DUNE', 'LOGO', 'DUNEPRG ENG VGA SDB2207 HIM 386']),
                       ('Floppy version, Roland MT-32', ['CD \\DUNE', 'LOGO', 'DUNEPRG ENG VGA MID330 HIM 386']),
                       ('Floppy version, AdLib Gold', ['CD \\DUNE', 'LOGO', 'DUNEPRG ENG VGA AGD388 HIM 386']),
                       ('CD version, Sound Blaster (needs the CD)', ['D:', 'CD \\', 'DNCDPRG AMR ADP220 SBP2227 EMS 386 SAF WRIC:\\DUNECD\\']),
                       ('CD version, Roland MT-32 (needs the CD)', ['D:', 'CD \\', 'DNCDPRG AMR MID330 SBP2227 EMS 386 SAF WRIC:\\DUNECD\\']),
                       ('CD version, AdLib Gold (needs the CD)', ['D:', 'CD \\', 'DNCDPRG AMR ADG388 SBP2227 EMS 386 SAF WRIC:\\DUNECD\\'])]),
 'enchant': dict(title='Curse of Enchantia (1992)', kind='root', cd=True,
                 opts=snd('ENCHANT', 'CURSE', ['SB16', 'MT32'])),
 'IntSSoc': dict(title='International Sensible Soccer (1994)', kind='drive', subs=['SOCCER'],
                 floppy=['cd/International Sensible Soccer.ima'],
                 opts=snd('SOCCER', 'SOC_K', ['SB16', 'MT32'])),
 'Ppersia': dict(title='Prince of Persia (1990)', kind='self', drop=['runH.bat'],
                 opts=[('v1.3 with Sound Blaster', ['CD \\PPERSIA', 'COPY SB16\\*.* . >NUL', 'PRINCE SBLAST']),
                       ('v1.3 with Roland MT-32', ['CD \\PPERSIA', 'COPY MT32\\*.* . >NUL', 'PRINCE']),
                       ('v1.3 with Sound Blaster + cheats', ['CD \\PPERSIA', 'COPY SB16\\*.* . >NUL', 'PRINCE SBLAST IMPROVED']),
                       ('v1.1 with Game Blaster', ['CD \\PPERSIA\\PRINCE11', 'PRINCE1 GBLAST'])]),
 # lang='es': entry describes the Spanish pack's layout, only used for that version
 'KQ5':     dict(title="King's Quest V - Absence Makes the Heart Go Yonder! (1990)", kind='drive', lang='es',
                 subs=['floppy', 'ega'], loose='-',   # root = English CD-talkie data eXo's DOS menu never uses
                 opts=[('VGA version', ['CD \\FLOPPY', 'SIERRA']), ('EGA version', ['CD \\EGA', 'SIERRA']),
                       ('Sound setup', ['CD \\FLOPPY', 'INSTALL'])]),
 'KQ6CD':   dict(title="King's Quest VI - Heir Today Gone Tomorrow (1992)", kind='drive', lang='es',
                 subs=['floppy'], loose='-',   # KQ6CD\\ (420 MB CD data) is unused by eXo's Spanish menu
                 opts=[('Play', ['CD \\FLOPPY', 'SIERRA']), ('Sound setup', ['CD \\FLOPPY', 'INSTALL'])]),
 # Spanish packs that ship a floppy version next to the CD one: the floppy version
 # goes on the data disc, so these don't need their own CD
 'Darkseed':dict(title='Dark Seed (1992)', kind='drive', lang='es', subs=['DARKSEED'], loose='-',
                 opts=[('Play (floppy version)', ['CD \\DARKSEED', 'CALL DS'])]),
 'dune:es': dict(title='Dune (1992)', kind='self', lang='es', drop=['DUNECD', 'DUNE.BAT', 'DUNE.vlp'],
                 opts=[('Sound Blaster (floppy version)', ['CD \\DUNE', 'LOGO', 'DUNECRK SPA VGA SDB2207 HIM 386']),
                       ('Roland MT-32 (floppy version)', ['CD \\DUNE', 'LOGO', 'DUNECRK SPA VGA MID330 HIM 386']),
                       ('AdLib Gold (floppy version)', ['CD \\DUNE', 'LOGO', 'DUNECRK SPA VGA AGD388 HIM 386'])]),
 'gob1':    dict(title='Gobliiins (1991)', kind='drive', lang='es', subs=['GOB'], loose='-',
                 opts=[('Play (floppy version)', ['CD \\GOB', 'CALL GO'])]),
 'gob2':    dict(title='Gobliins 2 - The Prince Buffoon (1992)', kind='drive', lang='es', subs=['GOB2'], loose='-',
                 opts=[('Play (floppy version)', ['CD \\GOB2', 'CALL GO'])]),
 'gob3':    dict(title='Goblins Quest 3 (1993)', kind='drive', lang='es', subs=['f'], loose='-',
                 opts=[('Play (floppy version)', ['CD \\F\\COKTEL\\GOB3', 'GOB3'])]),
 'loom':    dict(title='Loom (1990)', kind='root', lang='es',    # cd\\ = the CD talkie, root kind skips it
                 opts=[('EGA, AdLib (floppy version)', ['CD \\LOOM\\FLOPPY', 'LOOM V A']),
                       ('EGA, Roland MT-32', ['CD \\LOOM\\FLOPPY', 'LOOM R']),
                       ('EGA, PC speaker', ['CD \\LOOM\\FLOPPY', 'LOOM V I'])]),
 'SQ4':     dict(title='Space Quest IV - Roger Wilco and the Time Rippers (1991)', kind='drive', lang='es',
                 subs=['EGA'], loose='-',
                 opts=[('EGA floppy version, Sound Blaster', ['CD \\EGA', 'SIERRA SESOURCE.CFG']),
                       ('EGA floppy version, Roland MT-32', ['CD \\EGA', 'SIERRA RESOURCE.CFG'])]),
 'mi1':     dict(title='The Secret of Monkey Island (1990)', kind='root', lang='es',
                 drop=['CD-ROM', 'Voces'],    # CD-version image + fan talkie (195 MB): not the original floppy game
                 opts=[('VGA, Sound Blaster/AdLib', ['CD \\MI1\\VGA', 'MONKEY A']),
                       ('VGA, Roland MT-32', ['CD \\MI1\\VGA', 'MONKEY R']),
                       ('VGA, PC speaker', ['CD \\MI1\\VGA', 'MONKEY']),
                       ('EGA version', ['CD \\MI1\\EGA', 'MONKEY'])]),
 'mi2':     dict(title="Monkey Island 2 - LeChuck's Revenge (1991)", kind='root', lang='es',
                 drop=['talkie', 'sb16', 'mt32'],   # fan talkie (265 MB) + unused duplicate copies
                 opts=[('Sound Blaster/AdLib', ['CD \\MI2\\MI2', 'MONKEY2 S']),
                       ('Roland MT-32', ['CD \\MI2\\MI2', 'MONKEY2 R'])]),
 'TranTDLX':dict(title='Transport Tycoon Deluxe (1995)', kind='drive', subs=['TTDLX'], cd=True,
                 opts=[(l, ['CD \\TTDLX'] + ['IF EXIST %s DEL %s' % (f, f) for f in ('MUSIC.COM', 'SOUND.CFG', 'SOUND.COM', 'SOUNDRV.COM')]
                        + ['COPY %s\\*.* . >NUL' % p, 'TYCOON'])
                       for l, p in [('with Sound Blaster', 'SB16'), ('with Roland MT-32', 'MT32'), ('with General MIDI', 'SC55')]]),
}

# eXo/DOSBox-only files dropped everywhere (case-insensitive)
DROP_NAMES = {'run.bat', 'network.bat', 'askecho.com', 'setip.bat',
    # helpers eXo adds for DOSBox / Windows, not part of the original games
    'doomatic.exe', 'doomatic.cfg', 'doomatic.txt', 'doomargs.tmp', 'dm$$$.tmp', 'launch.tmp', 'tmp.txt',
    'doom_patch.exe', 'apogee_patch.exe', 'fakehma.com', 'bmouse.exe', 'bmouse.txt', 'gamer.ini',
    'midi_fix.ips', 'glide2x_emu.ovl', 'mtr.exe', 'd3dx9_43.dll', 'glide.dll', 'glide2x.dll', 'glide3x.dll',
    '3dfxspl.dll', '3dfxspl2.dll', '3dfxspl3.dll', 'cheats.bat', 'controls.txt', 'runh.bat',
    # fan-made add-ons eXo bundles: LSL3 mouse mod, Plutonia MIDI pack
    'ls3pp', 'plutmid'}

# Original releases only. Fan-made games are left out; for fan translations
# (eXo's Spanish pack) the English original is used instead.
FAN_GAMES = {'ckeen7', 'ckeen8', 'ckeen9'}                       # Keen 7-9: 2006-2011 fan games
FAN_TRANSLATIONS = {'kq1', 'lsl1', 'lsl2', 'lsl3', 'sq3', 'sq5',   # Spanish = fan translation
                    'xcomuf'}                                     # (SQ5: + fan voice dub)
DROP_RE = re.compile(r'(\.exo$|^extip.*|\.sel$|\.bak$|\.pdf$|\.chm$|\.vlp$)', re.I)
# eXo's per-sound-card / video config presets: a folder with one of these names
# whose files all also exist in its parent folder (eXo copies them over on launch)
PRESET_NAMES = {'sb16', 'sc55', 'mt32', 'gus', 'adlib', 'tandy', 'gb', 'cda', 'herc', 'network'}

IMAGE_RE = re.compile(r'\.(ima|img|vfd|dsk|imz|360|720|144|cue|bin|iso|ccd|sub|mds|mdf)$', re.I)

def images_only(path):
    """True if a folder holds only disk/CD images (a 'floppy' folder can also be a real game version)."""
    return all(e.is_file() and IMAGE_RE.search(e.name) for e in os.scandir(path))

def is_windows_only(path):
    """Folder whose programs are all Windows GUI .EXEs (fan remakes etc.), no DOS .COM/.BAT."""
    exes, other = [], False
    for e in os.scandir(path):
        n = e.name.lower()
        if e.is_file() and n.endswith(('.com', '.bat')):
            other = True
        elif e.is_file() and n.endswith('.exe'):
            exes.append(e.path)
    if not exes or other:
        return False
    for x in exes:
        with open(x, 'rb') as f:
            h = f.read(64)
            if h[:2] != b'MZ':
                return False
            f.seek(int.from_bytes(h[60:64], 'little'))
            pe = f.read(96)
            if pe[:4] != b'PE\0\0' or int.from_bytes(pe[92:94], 'little') != 2:   # 2 = Windows GUI
                return False
    return True

def is_preset(path, parent_names):
    ents = list(os.scandir(path))
    return (os.path.basename(path).lower() in PRESET_NAMES and ents and not any(e.is_dir() for e in ents)
            and {e.name.upper() for e in ents} <= parent_names)
# top-level dirs never copied as game files (CD/floppy images, cracks, DOSBox GUS drivers)
TOP_SKIP = {'cd', 'floppy', 'crack', 'ultrasnd'}

DOSCH = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$%&'()-@^_`{}~")

def dosname(n):
    """Return the uppercase 8.3 name, or None if n isn't a valid 8.3 name."""
    u = n.upper()
    base, dot, ext = u.partition('.')
    if not base or len(base) > 8 or len(ext) > 3 or '.' in ext:
        return None
    if not set(base + ext) <= DOSCH:
        return None
    return u

def short83(n, taken):
    """Make a valid unique 8.3 name for a non-8.3 file (docs/extras only)."""
    base, _, ext = n.rpartition('.') if '.' in n else (n, '', '')
    clean = lambda s: ''.join(c for c in s.upper() if c in DOSCH)
    b, e = clean(base)[:8] or 'FILE', clean(ext)[:3]
    for i in range(1, 100):
        cand = b if i == 1 else b[:8 - len(str(i)) - 1] + '~' + str(i)
        full = cand + ('.' + e if e else '')
        if full not in taken:
            return full
    raise RuntimeError(n)

renamed, dropped_junk, extracted, long_dirs = [], [], [], []
DOS_SYSTEM = {'io.sys', 'msdos.sys', 'ibmbio.com', 'ibmdos.com', 'command.com', 'drvspace.bin', 'dblspace.bin'}

def link_tree(src, dst, rel, drop_extra, skip_dirs=frozenset(), names=DROP_NAMES, top=True):
    """Hardlink src tree into dst with uppercase 8.3 names; return byte size."""
    os.makedirs(dst, exist_ok=True)
    taken, size = set(), 0
    parent_names = {e.name.upper() for e in os.scandir(src) if e.is_file()}
    # names that are already valid 8.3 first, so a shortened name never takes theirs
    for ent in sorted(os.scandir(src), key=lambda e: (dosname(e.name) is None, e.name)):
        nm = ent.name
        if ent.is_dir() and (nm.lower() in skip_dirs or is_preset(ent.path, parent_names)
                             or is_windows_only(ent.path)):
            dropped_junk.append(rel + '/' + nm + '/')
            continue
        if ent.is_file() and top and ent.stat().st_size == 0:     # eXo's empty marker files
            dropped_junk.append(rel + '/' + nm)
            continue
        if nm.lower() in names or DROP_RE.search(nm) or nm.lower() in drop_extra:
            dropped_junk.append(rel + '/' + nm)
            continue
        dn = dosname(nm)
        if dn is None or dn in taken:
            if ent.is_dir():      # DOS could never open it by this name: an eXo/ScummVM extra
                dropped_junk.append(rel + '/' + nm + '/ (not 8.3)')
                long_dirs.append(rel + '/' + nm)
                continue
            dn = short83(nm, taken)
            renamed.append('%s/%s -> %s' % (rel, nm, dn))
        taken.add(dn)
        if ent.is_dir(follow_symlinks=False):
            size += link_tree(ent.path, os.path.join(dst, dn), rel + '/' + nm, drop_extra, frozenset(), names, False)
        else:
            os.link(ent.path, os.path.join(dst, dn))
            size += ent.stat().st_size
    return size


# --- automatic mode for games not in G ---------------------------------------
# Reads eXo's !dos/<game>/dosbox.conf [autoexec] (+ the game's run.bat) and
# turns it into a plain-DOS launcher. Good enough for most games; check the
# warnings and add a hand-written entry to G when a game needs it.

DOSBOX_ONLY = re.compile(r'^\s*@?\s*(config\s+-|imgmount\b|mount\b|ipxnet\b|serial\d\b|viewport\b|'
                         r'askecho\b|mixer\b|rescan\b|keyb\s+\S+\s+\d|exit\b)', re.I)
NETCALL = re.compile(r'^\s*@?\s*(call\s+)?network(\.bat)?\s*$', re.I)

def sanitize_bat(text):
    """Strip DOSBox-only commands from a batch file; return (text, changed)."""
    out, changed = [], False
    for ln in text.replace('\r\n', '\n').split('\n'):
        if DOSBOX_ONLY.match(ln):
            changed = True
            continue
        if NETCALL.match(ln):
            out += ['ECHO Network play was a DOSBox feature, not available here.', 'PAUSE']
            changed = True
            continue
        out.append(ln)
    while out and not out[-1].strip():
        out.pop()
    return '\r\n'.join(out) + '\r\n', changed

def read_autoexec(g):
    p = game_conf(g)
    txt = open(p, encoding='latin-1').read()
    return [l.strip() for l in txt.split('[autoexec]', 1)[1].splitlines() if l.strip()]

def auto_def(g, warn):
    src = game_src(g)
    ae = read_autoexec(g)
    d = dict(title=next((os.path.splitext(f)[0] for f in os.listdir(src) if f.endswith('.exo')), g), auto=True)
    if any(re.match(r'@?boot\b', l, re.I) for l in ae):
        raise RuntimeError('self-booting disk game (eXo uses BOOT), cannot run from DOS: write its disk image to a floppy')
    mount = next((l for l in ae if re.match(r'@?mount\s+c\s', l, re.I)), None)
    if not mount:
        raise RuntimeError('no "mount c" in dosbox.conf')
    path = mount.split(None, 2)[2].strip().strip('"').rstrip('\\').split('\\')[-1]
    # a CD mounted from the game's own cd\ folder in eXo's menu: the game needs its CD
    if any(re.match(r'@?(img)?mount\s+\w\s+.*\\%s\\cd\\.*-t\s+(cdrom|iso)' % re.escape(g), l, re.I)
           for l in read_runbat(src)):
        d['cd'] = True
    for l in ae:
        m = re.match(r'@?(?:img)?mount\s+(\w)\s+(.*?)\s+-t\s+(\w+)', l, re.I)
        if m and m.group(3).lower() in ('cdrom', 'iso'):
            d['cd'] = True
        elif m and m.group(3).lower() == 'floppy':
            d['floppy'] = [os.path.relpath(os.path.join(SRC, '..', f.replace('\\', '/')), src)
                           for f in re.findall(r'"([^"]+)"|(\S+)', m.group(2)) for f in f if f]
            d['floppy'] = [f for f in d['floppy'] if os.path.isfile(os.path.join(src, f))]
        m = re.match(r'@?mount\s+a\s+"?([^"]+?)"?\s+-t\s+floppy', l, re.I)
        if m:
            d['floppydir'] = m.group(1).replace('\\', '/').split('/')[-1]
    # commands after the mounts = what eXo runs
    body = [l for l in ae if not re.match(r'@?\s*(echo off|cls|exit|cd\s*\.\.|[a-z]:)\s*$', l, re.I)
            and not DOSBOX_ONLY.match(l) and not l.startswith('#')]
    dirs = [e.name for e in os.scandir(src) if e.is_dir() and e.name.lower() not in TOP_SKIP]
    if path.lower() in ('exodos', '!spanish'):
        d['kind'] = 'root'
        d['opts'] = [('Play', body)]
    else:
        # game dir was C:\ ; does eXo cd into a subfolder to run it?
        cds = set()
        for l in body + read_runbat(src):
            m = re.match(r'@?cd\s+\\?([^\\\s]+)', l, re.I)
            if m:
                cds.add(m.group(1).lower())
        subs = [x for x in dirs if x.lower() in cds]
        if subs:
            d['kind'] = 'drive'
            # every real subfolder goes to C:\ ; a non-8.3 one DOS could never open is an eXo extra
            d['subs'] = [x for x in dirs if dosname(x) and x.lower() not in DROP_NAMES]
            long_dirs.extend(g + '/' + x for x in dirs if not dosname(x))
            d['loose'] = g             # loose files (incl. run.bat) -> C:\<G>
            d['opts'] = [('Play', ['CD \\'] + [re.sub(r'^@?call\s+run\b', 'CALL \\\\%s\\\\RUN' % g.upper(), l, flags=re.I)
                                                for l in body])]
        else:
            d['kind'] = 'self'
            d['opts'] = [('Play', ['CD \\' + g.upper()] + body)]
    if d.get('cd') and not any(e.name.lower() == 'cd' for e in os.scandir(src) if e.is_dir()):
        warn.append('%s: mounts a CD but has no cd/ folder - find its image by hand' % g)
    return d

def read_runbat(src):
    p = os.path.join(src, 'run.bat')
    return [l.replace('\xef\xbb\xbf', '').strip() for l in open(p, encoding='latin-1')] if os.path.isfile(p) else []

def fix_bats(root):
    """Auto mode: replace hardlinked .BATs that use DOSBox commands with clean copies."""
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith('.BAT'):
                p = os.path.join(dp, f)
                txt, changed = sanitize_bat(open(p, encoding='latin-1').read())
                if changed:
                    os.unlink(p)          # break the hardlink, never touch the original
                    open(p, 'w', encoding='latin-1', newline='').write(txt)

# --- floppy images ---------------------------------------------------------
# Some games run straight from a floppy image that eXo mounts as A: (e.g. Italy 90).
# Real DOS can't use the image, so its files are extracted into the game folder.

def fat_extract(img, dst):
    """Extract every file of a FAT12/FAT16 disk image into dst; return file count."""
    data = open(img, 'rb').read()
    u16 = lambda o: int.from_bytes(data[o:o + 2], 'little')
    u32 = lambda o: int.from_bytes(data[o:o + 4], 'little')
    bps, spc, rsv, nfat, nroot = u16(11), data[13], u16(14), data[16], u16(17)
    total, spf = u16(19) or u32(32), u16(22)
    if bps not in (512, 1024, 2048) or spc == 0 or nfat == 0 or spf == 0:
        raise RuntimeError('%s is not a FAT disk image' % os.path.basename(img))
    root = (rsv + nfat * spf) * bps
    first_data = root + -(-nroot * 32 // bps) * bps
    nclus = (total * bps - first_data) // (spc * bps)
    fat = data[rsv * bps:(rsv + spf) * bps]
    fat12 = nclus < 4085
    def nxt(c):
        if fat12:
            v = int.from_bytes(fat[c * 3 // 2:c * 3 // 2 + 2], 'little')
            return v >> 4 if c & 1 else v & 0xFFF
        return int.from_bytes(fat[c * 2:c * 2 + 2], 'little')
    end = 0xFF8 if fat12 else 0xFFF8
    def chain(c):
        out, seen = bytearray(), set()
        while 2 <= c < end and c not in seen:
            seen.add(c)
            o = first_data + (c - 2) * spc * bps
            out += data[o:o + spc * bps]
            c = nxt(c)
        return bytes(out)
    count = 0
    def walk(raw, path):
        nonlocal count
        os.makedirs(path, exist_ok=True)
        for i in range(0, len(raw) - 31, 32):
            e = raw[i:i + 32]
            if e[0] == 0:
                break
            if e[0] == 0xE5 or e[11] == 0x0F or e[11] & 0x08:      # deleted, LFN, volume label
                continue
            name = e[0:8].replace(b'\x05', b'\xe5', 1).decode('latin-1').rstrip()
            ext = e[8:11].decode('latin-1').rstrip()
            if name in ('.', '..'):
                continue
            nm = name + ('.' + ext if ext else '')
            clus, size = int.from_bytes(e[26:28], 'little'), int.from_bytes(e[28:32], 'little')
            if e[11] & 0x10:
                walk(chain(clus), os.path.join(path, nm))
            else:
                with open(os.path.join(path, nm), 'wb') as f:
                    f.write(chain(clus)[:size])
                count += 1
    walk(data[root:root + nroot * 32], dst)
    return count

def runs_from_floppy(ae):
    """Images eXo mounts as A: when the game is then started from A:."""
    if not any(re.fullmatch(r'@?a:', l, re.I) for l in ae):
        return []
    for l in ae:
        m = re.match(r'@?imgmount\s+a\s+(.*?)\s+-t\s+floppy', l, re.I)
        if m:
            return [f for pair in re.findall(r'"([^"]+)"|(\S+)', m.group(1)) for f in pair if f]
    return []

# --- staging ---------------------------------------------------------------

def stage_game(g, d, dst_games):
    """Hardlink the game's DOS files into dst_games/<G>/<C:\\ entries>."""
    src = game_src(g)
    GU = g.upper()
    if not dosname(GU) or len(GU) > 8:
        raise RuntimeError('folder name is not 8.3')
    gdst = os.path.join(dst_games, GU)
    drop_extra = {x.lower() for x in d.get('drop', [])}
    imgs = [os.path.normpath(os.path.join(SRC, '..', f.replace('\\', '/'))) for f in runs_from_floppy(read_autoexec(g))]
    drop_extra |= {os.path.basename(f).lower() for f in imgs}
    tops, size = [], 0
    if d['kind'] in ('root', 'self'):
        skipdirs = {e.name.lower() for e in os.scandir(src) if e.is_dir() and e.name.lower() in TOP_SKIP
                    and not (e.name.lower() == 'floppy' and not images_only(e.path))}
        size += link_tree(src, os.path.join(gdst, GU), g, drop_extra, skipdirs)
        tops.append(GU)
    else:
        for sub in d['subs']:
            size += link_tree(os.path.join(src, sub), os.path.join(gdst, sub.upper()), g + '/' + sub, drop_extra, top=False)
            tops.append(sub.upper())
        for ent in os.scandir(src):
            nm = ent.name
            if not ent.is_file() or ent.stat().st_size == 0 or nm.lower() in DROP_NAMES or DROP_RE.search(nm) or nm.lower() in drop_extra:
                continue
            tgt = d.get('loose')
            if tgt == '-':
                continue
            if not tgt:
                raise RuntimeError('unplaced loose file %s' % nm)
            tdir = os.path.join(gdst, tgt.upper())
            os.makedirs(tdir, exist_ok=True)
            dn = dosname(nm) or short83(nm, set(os.listdir(tdir)))
            if not os.path.exists(os.path.join(tdir, dn)):
                os.link(ent.path, os.path.join(tdir, dn))
                size += ent.stat().st_size
                if tgt.upper() not in tops:
                    tops.append(tgt.upper())
    for img in imgs:      # files the game runs from A: go into its main folder
        tgt = os.path.join(gdst, tops[0]) if tops else os.path.join(gdst, GU)
        if not tops:
            tops.append(GU)
        before = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(tgt) for f in fs) if os.path.isdir(tgt) else 0
        n = fat_extract(img, tgt)
        for f in os.listdir(tgt):          # the floppy's own DOS boot files aren't part of the game
            if f.lower() in DOS_SYSTEM:
                os.remove(os.path.join(tgt, f)); n -= 1
        size += sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(tgt) for f in fs) - before
        extracted.append('%s: %d files from %s' % (g, n, os.path.basename(img)))
    fix_bats(gdst)
    return dict(g=g, GU=GU, d=d, tops=tops, size=size)

def howto(g, d):
    """Human-readable 'how to run' lines (not put on the disc)."""
    if not d.get('auto'):
        out, seen = [], set()
        for lab, cmds in d['opts']:
            if lab.startswith('Set sound'):
                continue
            cmds = tuple(c for c in cmds if not re.match(r'(COPY |IF EXIST|ECHO|PAUSE|FAKEHMA)', c))
            if cmds in seen:
                continue
            seen.add(cmds)
            out.append((lab, cmds))
        if len(out) == 1 or all(l.startswith('with ') for l, _ in out):
            out = [('Run' if len(out) == 1 else l, c) for l, c in out]
        return ['%s: %s' % (l, ' / '.join(c)) for l, c in out]
    cmds = []
    for l in d['opts'][0][1] + read_runbat(game_src(g)):
        l = l.strip().lstrip('@')
        if not l or DOSBOX_ONLY.match(l) or re.match(r'(echo|if |goto|cls|choice|rem\b|:|call run\b|set )', l, re.I) \
                or re.fullmatch(r'cd\s+\\?' + re.escape(g), l, re.I):
            continue
        l = re.sub(r'(\s+%\d)+\s*$', '', l)          # batch-file argument placeholders
        if l not in cmds:
            cmds.append(l)
    return ['commands from the eXo menu: ' + ' / '.join(cmds)] if cmds else ['(no launch command found)']

def remap(line, gm):
    """Rewrite CD \\<C:-folder> paths in the run notes to the \\<GAME> layout."""
    GU, tops = gm['GU'], gm['tops']
    def sub(m):
        first, rest = m.group(1), m.group(2) or ''
        if first.upper() not in tops:
            return m.group(0)
        base = GU if len(tops) == 1 else GU + '\\' + first.upper()
        return 'CD \\' + base + rest
    return re.sub(r'CD \\([^\\\s/]+)((?:\\[^\s/]+)*)', sub, line, flags=re.I)

# GETLINE.COM (8086, 311 bytes) assembled from getline.s next to this script:
# reads a typed line into a batch variable, since DOS 6 batch files have no SET /P.
GETLINE_COM = base64.b64decode(
    '/L6BAOjZAIk2LwKsPA11A+m4ADwgdfTGRP8A6MIAvzcCrDwNdAs8IHQHqoH/WwJy8IH/NwJ1A+mRALA9qok+MQIw5M0WPA10PjwbdDY8CHQaPCBy7IH/+wJz5jxhcgY8encCLCCq6G4A69Y7PjECdNBPsAjoYACwIOhbALAI6FYA676LPjECOz4xAnQHgH3/XHUBT7AN6D4AsAroOQC4DQqrtDwxyYsWLwLNIXIYicO0QIn5gekzArozAs0htD7NIbgATM0hugkC6wO66wG0Cc0huAFMzSFTtA4x280QW8OsPCB0+zwJdPdOw1VzYWdlOiBHRVRMSU5FIDxmaWxlPiA8VkFSPg0KJEdFVExJTkU6IGNhbm5vdCB3cml0ZSB0aGUgdGVtcCBmaWxlDQokAAAAAFNFVCA=')

def bat(lines):
    """DOS batch file bytes: CRLF line endings, plain ASCII."""
    return ('\r\n'.join(lines) + '\r\n').encode('ascii', 'replace')

def dos_echo(text):
    """Make text safe for ECHO in a DOS batch file."""
    text = re.sub(r'\s*[<>]+\s*[^\s,]+', '', text)  # drop redirections like >tmp.txt
    return text.replace('|', '/').replace('%', '%%').encode('ascii', 'replace').decode()

def play_lines(gm):
    """'label: CD \\GAME\\SUB / CMD / CMD' -> 'label: cd SUB, CMD, CMD'."""
    out = []
    for h in howto(gm['g'], gm['d']):
        h = remap(h, gm)
        label, _, cmds = h.rpartition(': ') if ': CD ' in h or ': ' in h else ('', '', h)
        parts = [c.strip() for c in cmds.split(' / ') if c.strip()]
        steps = []
        for c in parts:
            m = re.match(r'CD \\%s(\\.*)?$' % re.escape(gm['GU']), c, re.I)
            if m:
                if m.group(1):
                    steps.append('cd ' + m.group(1).lstrip('\\'))
                continue
            steps.append(dos_echo(c))
        label = label.replace('commands from the eXo menu', 'one of')
        line = (label + ': ' if label else '') + ', '.join(steps)
        while len(line) > 74:                       # wrap long lines
            cut = line.rfind(' ', 0, 74)
            cut = cut if cut > 20 else 74
            out.append(line[:cut].rstrip()); line = '  ' + line[cut:].lstrip()
        out.append(line)
    return out

def short_title(t, w):
    """Menu title: drop the year first if it doesn't fit, then cut."""
    es = ' (ES)' if t.endswith(' [ESPANOL]') else ''
    t = dos_echo(t.replace(' [ESPANOL]', ''))
    if len(t) + len(es) > w:
        t = re.sub(r' \(\d{4}[^)]*\)', '', t)
    w -= len(es)
    return (t if len(t) <= w else t[:w - 1].rstrip() + '~') + es

def write_menu(root, n, dk):
    """MENU.BAT: pick a game by number, type a destination, copy it there."""
    with open(os.path.join(root, 'GETLINE.COM'), 'wb') as f:
        f.write(GETLINE_COM)
    per = 36                                        # 2 columns x 18 rows per screen
    pages = [dk[i:i + per] for i in range(0, len(dk), per)]
    L = ['@ECHO OFF',
         'IF NOT EXIST \\GETLINE.COM GOTO WRONG',
         'SET _P=1',
         'GOTO P1']
    num = 0
    for pi, pg in enumerate(pages, 1):
        L += [':P%d' % pi, 'SET _P=%d' % pi, 'CLS',
              'ECHO  DOS GAMES - DISC %d%s' % (n, ('   (page %d of %d)' % (pi, len(pages))) if len(pages) > 1 else ''),
              'ECHO  ' + '-' * 74]
        items = ['%3d %s' % (num + i + 1, short_title(g['d']['title'], 34))
                 for i, g in enumerate(pg)]
        num += len(pg)
        rows = (len(items) + 1) // 2
        for r in range(rows):
            left = items[r]
            right = items[r + rows] if r + rows < len(items) else ''
            L.append('ECHO %-39s%s' % (left, right))
        L += ['ECHO.',
              ('ECHO  Game number + Enter.   N = next page, P = previous, Enter alone = quit'
               if len(pages) > 1 else 'ECHO  Type a game number and press Enter.  Enter alone = quit.'),
              '\\GETLINE C:\\_M.BAT _K', 'CALL C:\\_M.BAT',
              'IF "%_K%"=="" GOTO END',
              'IF "%_K%"=="N" GOTO P' + str(pi % len(pages) + 1),
              'IF "%_K%"=="P" GOTO P' + str((pi - 2) % len(pages) + 1),
              'GOTO PICK']
    L.append(':PICK')
    L += ['IF "%_K%"=="' + str(i) + '" GOTO G' + str(i) for i in range(1, len(dk) + 1)]
    L += ['ECHO  There is no game number %_K%.', 'PAUSE', 'GOTO P%_P%']
    for i, gm in enumerate(dk, 1):
        # few, short variables: DOS's default environment is only 256 bytes
        L += [':G%d' % i, 'SET _G=%s' % gm['GU'], 'CLS', 'ECHO.',
              'ECHO  ' + dos_echo(gm['d']['title']), 'GOTO ASK']
    L += [':ASK', 'ECHO.',
          'ECHO  Copy to which folder?  (Enter = C:\\JUEGOS\\%_G%)',
          '\\GETLINE C:\\_M.BAT _D', 'CALL C:\\_M.BAT',
          'IF "%_D%"=="" SET _D=C:\\JUEGOS\\%_G%',
          'ECHO.', 'ECHO  Copy \\%_G% to %_D% ?  (Y/N)',
          'CHOICE /C:YN /N',
          'IF ERRORLEVEL 2 GOTO P%_P%',
          'XCOPY \\%_G%\\*.* %_D%\\ /S /E /V',
          'IF ERRORLEVEL 1 GOTO CFAIL',
          'ATTRIB -R %_D%\\*.* /S',
          'ECHO.', 'ECHO  Done. To play: go to that drive, CD %_D%  and run:',
          'GOTO H%_K%']
    for i, gm in enumerate(dk, 1):
        L += [':H%d' % i] + ['ECHO    ' + dos_echo(x) for x in play_lines(gm)] + ['GOTO DONE']
    L += [':DONE', 'ECHO.', 'PAUSE', 'GOTO P%_P%',
          ':CFAIL', 'ECHO.', 'ECHO  The copy failed. Check the folder name and the free space.',
          'PAUSE', 'GOTO P%_P%',
          ':WRONG', 'ECHO Run TXTMENU from the CD drive: type D:  (your CD letter), then TXTMENU',
          'GOTO QUIT',
          ':END', 'IF EXIST C:\\_M.BAT DEL C:\\_M.BAT',
          'SET _P=', 'SET _K=', 'SET _G=', 'SET _D=',
          ':QUIT']
    with open(os.path.join(root, 'TXTMENU.BAT'), 'wb') as f:
        f.write(bat(L))

def make_iso(root, iso_path, label):
    import pycdlib
    iso = pycdlib.PyCdlib()
    iso.new(interchange_level=4, vol_ident=label)   # level 4: keeps DOS chars like & - ! ~
    for dp, dns, fns in os.walk(root):
        rel = os.path.relpath(dp, root)
        isodir = '' if rel == '.' else '/' + rel.replace(os.sep, '/')
        for dn in sorted(dns):
            iso.add_directory(isodir + '/' + dn)
        for fn in sorted(fns):
            iso.add_file(os.path.join(dp, fn), isodir + '/' + fn + ';1')
    iso.write(iso_path)
    iso.close()

EXODIUM_DB = os.path.expanduser('~/.local/share/com.redfox.exodium/exodium.db')

_INFO = None

def exodium_info():
    """shortcode (lowercase) -> dict(name, year, genre, thumb) from Exodium's database (read-only).
    name = eXo's file name for the game, e.g. 'Secret of Monkey Island, The (1990)'."""
    global _INFO
    if _INFO is None:
        import sqlite3
        _INFO = {}
        if os.path.isfile(EXODIUM_DB):
            db = sqlite3.connect('file:%s?mode=ro' % EXODIUM_DB, uri=True)
            try:
                for sc, app, year, genre, thumb in db.execute(
                        "SELECT shortcode, application_path, year, genre, thumbnail_key FROM games "
                        "WHERE language = 'EN' AND shortcode IS NOT NULL"):
                    name = os.path.splitext((app or '').replace('\\', '/').split('/')[-1])[0]
                    _INFO[sc.lower()] = dict(name=name, year=year, genre=genre or '', thumb=thumb)
            finally:
                db.close()
    return _INFO

def exodium_genres():
    return {k: v['genre'] for k, v in exodium_info().items()}


# --- graphical menu (MENU.EXE) ----------------------------------------------
# MENU.EXE (dosmenu/menu.c) shows the list with a screenshot and copies the
# game. Screenshots: a frame of eXo's gameplay video (Content/GameData zip),
# with eXo's logo painted out; else the box art from Exodium's posters pack.

SHOT_W, SHOT_H = 192, 120
CACHE = os.path.expanduser('~/eXoDOS/.exo2cd-cache/shots')
POSTERS = os.path.expanduser('~/content/posters/eXoDOS')
MENU_EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dosmenu', 'MENU.EXE')

def _frame_score(im):
    from PIL import ImageStat
    lum = im.convert('L')
    hist = lum.histogram()
    dark = sum(hist[:24]) / float(SHOT_W * SHOT_H)
    colors = len(im.getcolors(SHOT_W * SHOT_H) or [])
    return ImageStat.Stat(lum).stddev[0] * (1 - dark) + min(colors, 4000) / 100.0

def video_frame(name):
    """Best-looking frame of eXo's gameplay video for this game, or None."""
    import subprocess, tempfile, zipfile, io
    from PIL import Image
    z = os.path.join(SRC, '..', '..', 'Content', 'GameData', 'eXoDOS', name + '.zip')
    if not name or not os.path.isfile(z) or os.path.getsize(z) == 0:
        return None
    with zipfile.ZipFile(z) as zf:
        vids = [m for m in zf.namelist() if m.startswith('Videos/') and m.lower().endswith('.mp4')]
        main = [m for m in vids if os.path.basename(m)[:-4] == name]
        if not vids:
            return None
        with tempfile.TemporaryDirectory() as tmp:
            vid = os.path.join(tmp, 'v.mp4')
            with zf.open((main or vids)[0]) as src, open(vid, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                  'stream=width,height:format=duration', '-of', 'default=nw=1', vid],
                                 capture_output=True, text=True).stdout
            info = dict(l.split('=', 1) for l in out.split() if '=' in l)
            w, h, dur = int(info['width']), int(info['height']), float(info.get('duration', 0) or 0)
            lx, lh = int(w * 0.765), int(h * 0.14)          # eXo's logo, top right
            vf = 'delogo=x=%d:y=1:w=%d:h=%d,scale=%d:%d:flags=area' % (lx, w - lx - 2, lh, SHOT_W, SHOT_H)
            best = None
            for frac in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
                png = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.2f' % (dur * frac), '-i', vid,
                                      '-frames:v', '1', '-vf', vf, '-f', 'image2pipe', '-vcodec', 'png', '-'],
                                     capture_output=True).stdout
                if not png:
                    continue
                im = Image.open(io.BytesIO(png)).convert('RGB')
                sc = _frame_score(im)
                if best is None or sc > best[0]:
                    best = (sc, im)
            return best and best[1]

def poster(thumb):
    """Box art fitted into the screenshot box (mode 13h pixels are 1.2x taller than wide)."""
    from PIL import Image
    p = os.path.join(POSTERS, '%s.jpg' % thumb)
    if not thumb or not os.path.isfile(p):
        return None
    im = Image.open(p).convert('RGB')
    a = im.width / float(im.height)
    w, h = (round(SHOT_H * 1.2 * a), SHOT_H) if SHOT_H * 1.2 * a <= SHOT_W else (SHOT_W, round(SHOT_W / a / 1.2))
    box = Image.new('RGB', (SHOT_W, SHOT_H))
    box.paste(im.resize((w, h), Image.LANCZOS), ((SHOT_W - w) // 2, (SHOT_H - h) // 2))
    return box

def screenshot(g):
    """192x120 picture for game g (cached), or None."""
    from PIL import Image
    info = exodium_info().get(g.lower(), {})
    cached = os.path.join(CACHE, g.lower() + '.png')
    if os.path.isfile(cached):
        return Image.open(cached).convert('RGB')
    try:
        im = video_frame(info.get('name')) or poster(info.get('thumb'))
    except Exception:
        im = poster(info.get('thumb'))
    if im is not None:
        os.makedirs(CACHE, exist_ok=True)
        im.save(cached)
    return im

def pic_bytes(im):
    """MENU.EXE picture: 240-colour VGA palette (6-bit RGB) + 192x120 pixels using colours 16-255."""
    from PIL import Image
    q = im.quantize(colors=240, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
    pal = (q.getpalette() + [0] * 720)[:720]
    return bytes(v >> 2 for v in pal) + bytes(p + 16 for p in q.tobytes())

LIST_ABBREV = [('Leisure Suit Larry', 'Larry'), ('Indiana Jones and the ', 'Indy '), ('Indiana Jones', 'Indy'),
               ('Commander Keen', 'Keen'), ('Secret of Monkey Island', 'Monkey Island'), (' and the ', ' & ')]

# genre names shortened to fit the info line, and in Spanish for MENU.EXE's F10
GENRE_EN = {'Construction and Management Simulation': 'Management', 'Racing & Driving': 'Racing',
            'First Person Shooter': 'FPS', 'Cards & Tiles': 'Cards', 'Paddle & Pong': 'Pong',
            'Board Game': 'Board'}
GENRE_ES = {'Action': 'Acción', 'Adult': 'Adultos', 'Adventure': 'Aventura', 'App': 'Aplicación',
            'Application': 'Aplicación', 'Arcade': 'Arcade', "Beat 'em Up": "Beat 'em up", 'Board': 'De mesa',
            'Board Game': 'De mesa', 'Cards': 'Cartas', 'Cards & Tiles': 'Cartas', 'Casino': 'Casino',
            'Construction and Management Simulation': 'Gestión', 'Creativity': 'Creatividad', 'Demo': 'Demo',
            'Detective': 'Detectives', 'Education': 'Educativo', 'Fighting': 'Lucha',
            'First Person Shooter': 'FPS', 'Flight Simulator': 'Simulador de vuelo', 'Game Show': 'Concurso',
            'Hidden Object': 'Objetos ocultos', 'Horror': 'Terror', 'Interactive Fiction': 'Ficción interact.',
            'Interactive Movie': 'Cine interactivo', 'Life Simulation': 'Simulación de vida', 'Paddle': 'Pong',
            'Paddle & Pong': 'Pong', 'Pinball': 'Pinball', 'Platform': 'Plataformas', 'Puzzle': 'Puzzle',
            'Quiz': 'Preguntas', 'Racing': 'Carreras', 'Racing & Driving': 'Carreras', 'Reference': 'Referencia',
            'Role-Playing': 'Rol', 'Screensaver': 'Salvapantallas', 'Shooter': 'Disparos',
            'Simulation': 'Simulación', 'Sports': 'Deportes', 'Strategy': 'Estrategia', 'Text-Based': 'Texto',
            'Vehicle Simulation': 'Sim. de vehículos', 'Visual Novel': 'Novela visual'}

def genre_line(genre, names, w=18):
    """'Action; Platform' -> 'Action, Platform', keeping only what fits in w characters."""
    out = ''
    for part in genre.split(';'):
        part = part.strip().split(' / ')[0]
        part = names.get(part, part) if part else ''
        if part and part not in out and len(out) + len(part) + (2 if out else 0) <= w:
            out += (', ' if out else '') + part
    return out

def list_name(title, w=15):
    """Short, distinct-looking name for MENU.EXE's 15-character list."""
    t = re.sub(r' \(\d{4}[^)]*\)', '', title).strip()
    t = re.sub(r'^The ', '', t)
    if len(t) > w:
        t = re.split(r' - |: ', t)[0]                  # drop the subtitle
    for a, b in LIST_ABBREV:
        if len(t) > w:
            t = re.sub(re.escape(a), b, t, flags=re.I)
    return t if len(t) <= w else t[:w - 1].rstrip() + '~'

def write_gui(root, label, dk):
    """MENU.EXE + _MENU\\MENU.DAT + one _MENU\\<GAME>.PIC per game."""
    if not os.path.isfile(MENU_EXE):
        return 'MENU.EXE not built (see dosmenu/menu.c) - text menu only'
    shutil.copyfile(MENU_EXE, os.path.join(root, 'MENU.EXE'))
    mdir = os.path.join(root, '_MENU')
    os.makedirs(mdir, exist_ok=True)
    asc = lambda t: t.encode('ascii', 'replace').decode()
    lines, nopic = ['LABEL ' + label], []
    names = {gm['GU']: list_name(asc(gm['d']['title'].replace(' [ESPANOL]', ''))) for gm in dk}
    for gm in sorted(dk, key=lambda x: names[x['GU']].lower()):
        g, GU = gm['g'], gm['GU']
        info = exodium_info().get(g.lower(), {})
        title = gm['d']['title'].replace(' [ESPANOL]', '')
        m = re.search(r' \((\d{4})[^)]*\)', title)
        year = m.group(1) if m else (info.get('year') or '')
        genre = info.get('genre', '')                      # fits next to the year (24 chars)
        lines += ['GAME ' + GU, 'TITLE ' + asc(re.sub(r' \(\d{4}[^)]*\)', '', title)),
                  'SHORT ' + names[GU], 'YEAR %s' % year,
                  'GENRE ' + genre_line(genre, GENRE_EN), 'GENRE_ES ' + genre_line(genre, GENRE_ES),
                  'LANG ' + ('Spanish' if LANG.get(g) == 'es' else 'English'),
                  'SIZE %d' % gm['size']]
        im = screenshot(g)
        if im is not None:
            with open(os.path.join(mdir, GU + '.PIC'), 'wb') as f:
                f.write(pic_bytes(im))
            lines.append('SHOT ' + GU)
        else:
            nopic.append(g)
        run = []
        for l in play_lines(gm):                      # undo play_lines' wrapping
            if l.startswith('  ') and run:
                run[-1] += ' ' + l.strip()
            else:
                run.append(l)
        lines += ['RUN ' + asc(r).replace('%%', '%') for r in run[:12]]
    with open(os.path.join(mdir, 'MENU.DAT'), 'wb') as f:
        f.write(('\r\n'.join(lines) + '\r\n').encode('cp437', 'replace'))   # the VGA font's charset
    return ('no picture: ' + ' '.join(nopic)) if nopic else None

def main():
    global SRC, OUT
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src', help='the eXo/eXoDOS folder with the installed games')
    ap.add_argument('out', help='output folder (rebuilt on every run)')
    ap.add_argument('--iso', default='1', help='which discs get an .ISO: e.g. "1", "2,3", "all", "none" (default 1)')
    ap.add_argument('--burned', nargs='*', default=[], metavar='DISCn.TXT',
                    help='game lists of discs already burned: those games are left out')
    ap.add_argument('--genre', metavar='GENRE',
                    help='only games of this genre, from Exodium\'s database (e.g. "adventure": genre has '
                         'Adventure but not Action, so no action-adventures or interactive movies)')
    ap.add_argument('--label', default='DOSGAMES', help='ISO file name / volume label prefix (default DOSGAMES)')
    a = ap.parse_args()
    SRC, OUT = os.path.abspath(a.src), os.path.abspath(a.out)
    skip = set()
    for f in a.burned:
        for l in open(f):
            if l.strip() and not l.startswith(('#', ' ', '\t')):
                skip.add(l.split()[0].lower())
    if os.path.exists(OUT):
        if not os.path.exists(os.path.join(OUT, '.exo2cd')):
            sys.exit('refusing: %s exists but was not made by this script' % OUT)
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    open(os.path.join(OUT, '.exo2cd'), 'w').close()
    stage = os.path.join(OUT, '_stage')
    warn, games, cdgames = [], [], []
    # Spanish first: a game whose Spanish version is downloaded (!spanish/<game> +
    # !dos/!spanish/<game>/dosbox.conf) is taken in Spanish, otherwise English.
    es_dir = os.path.join(SRC, '!spanish')
    spanish = {e.name for e in os.scandir(es_dir) if e.is_dir() and not e.name.startswith('!')
               and os.path.isfile(os.path.join(SRC, '!dos', '!spanish', e.name, 'dosbox.conf'))} \
        if os.path.isdir(es_dir) else set()
    english = {e.name for e in os.scandir(SRC) if e.is_dir() and not e.name.startswith('!')}
    es_scummvm = sorted((e.name for e in os.scandir(es_dir) if e.is_dir() and not e.name.startswith('!')
                         and e.name not in spanish and e.name not in english), key=str.lower) \
        if os.path.isdir(es_dir) else []
    es_missing = []
    fan_tr = sorted((g for g in spanish if g.lower() in FAN_TRANSLATIONS), key=str.lower)
    spanish -= set(fan_tr)
    en_missing = [g for g in fan_tr if g not in english]     # English original not downloaded yet
    fan_games = sorted((g for g in english | spanish if g.lower() in FAN_GAMES), key=str.lower)
    for g in spanish:
        LANG[g] = 'es'
    names = sorted((english | spanish) - set(fan_games), key=str.lower)
    if a.genre:
        genres = exodium_genres()
        want_g = a.genre.lower()
        names = [g for g in names if want_g in genres.get(g.lower(), '').lower()
                 and (want_g == 'action' or 'action' not in genres.get(g.lower(), '').lower())]
    for g in names:
        if g.upper() in {s.upper() for s in skip}:
            continue
        if not os.path.isfile(game_conf(g)):
            warn.append('%s: no dosbox.conf - skipped' % g); continue
        if g not in spanish and g not in fan_tr and os.path.isfile(os.path.join(SRC, '!dos', '!spanish', g, 'dosbox.conf')):
            es_missing.append(g)
        try:
            d = (LANG.get(g) == 'es' and G.get(g + ':es')) or G.get(g)
            if d and d.get('lang', LANG.get(g)) != LANG.get(g):
                d = None
            d = d or auto_def(g, warn)
            if LANG.get(g) == 'es':
                d = dict(d, title=d['title'] + ' [ESPANOL]')
            if d.get('cd') is True:          # needs its own CD: user burns those separately
                cdgames.append(g); continue
            games.append(stage_game(g, d, stage))
            if d.get('auto'):
                warn.append('%s: auto-converted, test it on the DOS PC' % g)
        except Exception as e:
            warn.append('%s: SKIPPED (%s)' % (g, e))
            shutil.rmtree(os.path.join(stage, g.upper()), ignore_errors=True)
    # alphabetical: fill disc 1 from A until the next game doesn't fit, then disc 2...
    # (a game that doesn't fit waits, and the following games are tried first)
    discs, cur, size, waiting = [], [], 0, []
    queue = list(games)
    while queue or waiting:
        if not queue:
            discs.append(cur); cur, size, queue, waiting = [], 0, waiting, []
            continue
        gm = queue.pop(0)
        if gm['size'] > DISC_BUDGET:
            warn.append('%s: %.0f MB, bigger than one CD - left out' % (gm['g'], gm['size'] / 1e6)); continue
        if gm['GU'] in {x['GU'] for x in cur}:   # one folder per game at the disc root
            waiting.append(gm); continue
        if size + gm['size'] > DISC_BUDGET:     # doesn't fit: try the next games first
            waiting.append(gm); continue
        cur.append(gm); size += gm['size']
    if cur:
        discs.append(cur)
    want = (set(range(1, len(discs) + 1)) if a.iso == 'all' else set() if a.iso == 'none'
            else {int(x) for x in a.iso.split(',')})
    for n, dk in enumerate(discs, 1):
        root = os.path.join(OUT, 'DISC%d' % n)
        os.makedirs(root)
        lines = ['# DISC%d - game folder, where it goes on C:, how to run it (this file is not on the CD)' % n, '']
        for gm in dk:
            # one folder per game at the disc root: a single C:\ folder becomes
            # \<GAME> itself, several become subfolders of \<GAME>
            if len(gm['tops']) == 1:
                os.rename(os.path.join(stage, gm['GU'], gm['tops'][0]), os.path.join(root, gm['GU']))
            else:
                os.rename(os.path.join(stage, gm['GU']), os.path.join(root, gm['GU']))
            lines.append('%-9s %s  [%.1f MB]' % (gm['g'], gm['d']['title'].encode('ascii', 'replace').decode(),
                                                 gm['size'] / 1e6))
            lines.append('    copy \\%s to C:\\%s' % (gm['GU'], gm['GU']))
            lines += ['    ' + remap(h, gm) for h in howto(gm['g'], gm['d'])]
        write_menu(root, n, dk)
        note = write_gui(root, '%s%d' % (a.label, n), dk)
        if note:
            warn.append('DISC%d menu: %s' % (n, note))
        with open(os.path.join(OUT, 'DISC%d.TXT' % n), 'w') as f:
            f.write('\n'.join(lines) + '\n')
        if n in want:
            make_iso(root, os.path.join(OUT, '%s%d.ISO' % (a.label, n)), '%s%d' % (a.label, n))
    shutil.rmtree(stage, ignore_errors=True)
    for n, dk in enumerate(discs, 1):
        print('DISC%d: %.0f MB, %s .. %s (%d games)%s' % (n, sum(g['size'] for g in dk) / 1e6, dk[0]['GU'],
              dk[-1]['GU'], len(dk), '  -> %s%d.ISO' % (a.label, n) if n in want else ''))
    print('\nLeft out, need their own CD (%d): %s' % (len(cdgames), ' '.join(cdgames)))
    es_used = sorted(set(spanish) & set(names), key=str.lower)
    print('\nIn Spanish (%d): %s' % (len(es_used), ' '.join(es_used)))
    if es_missing:
        print('Spanish version exists in eXo but is not downloaded, used English (%d): %s'
              % (len(es_missing), ' '.join(es_missing)))
        print('  -> download the Spanish version in Exodium and rerun to switch them.')
    if fan_tr:
        print('\nSpanish version is a fan translation, English original used instead (%d): %s'
              % (len(fan_tr), ' '.join(fan_tr)))
    if en_missing:
        print('  English original not downloaded, left out (%d): %s  -> download it in Exodium'
              % (len(en_missing), ' '.join(en_missing)))
    if fan_games:
        print('\nFan-made games, left out (%d): %s' % (len(fan_games), ' '.join(fan_games)))
    if es_scummvm:
        print('\nSpanish version runs only in ScummVM (no DOS version), English not downloaded, left out (%d): %s'
              % (len(es_scummvm), ' '.join(es_scummvm)))
    if long_dirs:
        print('\nFolders left out, name is not 8.3 (eXo/ScummVM extras):'); print('\n'.join('  ' + x for x in long_dirs))
    if extracted:
        print('\nRan from a floppy image, files extracted:'); print('\n'.join('  ' + x for x in extracted))
    if renamed:
        print('\nRenamed to 8.3:'); print('\n'.join('  ' + r for r in renamed))
    if warn:
        print('\nWARNINGS:'); print('\n'.join('  ' + w for w in warn))

if __name__ == '__main__':
    main()
