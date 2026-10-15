#!/bin/sh
# SPDX-License-Identifier: MIT  (Copyright (c) 2026 Ariel Juszczyk, see LICENSE)
# Try the discs in DOSBox on this PC: the ISO becomes the CD drive (D:), a folder
# becomes the hard disk (C:), and the menu starts.
#   ./dosbox-test.sh [ISO | disc number] [C-folder]
#   ./dosbox-test.sh 3          (isos/SETUP86-VOLUME-03.ISO)
#   ./dosbox-test.sh ~/eXoDOS/SETUP86-ADVENTURE/SETUP86-ADVENTURE-01.ISO
#   ./dosbox-test.sh all [ISO folder] [C-folder]
#       Every SETUP86-*.ISO in the folder (default: the one named in .isos-dir, else isos/), as if the
#       menu had been installed on the hard disk from each disc: C:\SETUP86 lists all their
#       games. The ISOs are all in D:; when the menu asks for another disc, press Ctrl+F4
#       (DOSBox's next disc) until it finds it.
# .isos-dir (git-ignored, optional): one line, a folder of ISOs, e.g. on a NAS share. "all"
# uses it, and a disc number not in isos/ is taken from it.
# Installed games stay in the C-folder (default ~/eXoDOS/dosbox-c) between runs.
# Needs dosbox-staging (Exodium installs it); "all" also needs Python with pycdlib.
HERE=$(cd "$(dirname "$0")" && pwd)
ALT=$(head -n 1 "$HERE/.isos-dir" 2>/dev/null)

if [ "$1" = all ]; then
    DIR=$2
    [ -n "$DIR" ] || DIR=${ALT:-$HERE/isos}
    C=${3:-$HOME/eXoDOS/dosbox-c}
    ls "$DIR"/SETUP86-*.ISO >/dev/null 2>&1 || { echo "no SETUP86-*.ISO in $DIR"; exit 1; }
    mkdir -p "$C"
    PY=$HOME/.venvs/setup86/bin/python
    [ -x "$PY" ] || PY=python3
    # DOSBox gets short links to the ISOs (the gvfs path has ':' and ',' in it)
    LINKS=$(mktemp -d)
    trap 'rm -rf "$LINKS"' EXIT
    "$PY" - "$DIR" "$C/SETUP86" "$LINKS" <<'EOF' || exit 1
import glob, io, os, sys
import pycdlib
src, dst, links = sys.argv[1:4]
menu = os.path.join(dst, '_MENU')
os.makedirs(menu, exist_ok=True)
vols = []
for n, iso_path in enumerate(sorted(glob.glob(os.path.join(src, 'SETUP86-*.ISO'))), 1):
    os.symlink(iso_path, os.path.join(links, 'D%02d.ISO' % n))
    iso = pycdlib.PyCdlib()
    iso.open(iso_path)
    def get(p):
        b = io.BytesIO()
        iso.get_file_from_iso_fp(b, iso_path=p + ';1')
        return b.getvalue()
    ident = dict(l.split(' ', 1) for l in get('/SETUP86.ID').decode('latin-1').splitlines() if ' ' in l)
    vols.append('%s %s %s' % (ident['SET'], ident['VOL'], ident.get('BUILD', '-')))
    vdir = os.path.join(menu, 'V%03d' % n)
    os.makedirs(vdir, exist_ok=True)
    for f in os.listdir(vdir):
        os.remove(os.path.join(vdir, f))
    open(os.path.join(menu, 'V%03d.DAT' % n), 'wb').write(get('/_MENU/MENU.DAT'))
    for rec in iso.list_children(iso_path='/_MENU'):
        name = rec.file_identifier().decode('latin-1').split(';')[0]
        if name.upper().endswith(('.PIC', '.TXT')):
            open(os.path.join(vdir, name), 'wb').write(get('/_MENU/' + name))
    if n == 1:
        open(os.path.join(dst, 'MENU.EXE'), 'wb').write(get('/MENU.EXE'))
    iso.close()
    print('%s: %s' % (os.path.basename(iso_path), vols[-1]))
open(os.path.join(menu, 'VOLS.DAT'), 'w', newline='\r\n').write('\n'.join(vols) + '\n')
EOF
    set -- "$LINKS"/D*.ISO
    IMGS=
    for f; do IMGS="$IMGS \"$f\""; done
    dosbox-staging -c "mount c \"$C\"" -c "imgmount d$IMGS -t iso" -c "c:" -c "cd \\SETUP86" -c "menu"
    exit
fi

ISO=${1:-1}
case $ISO in
    *[!0-9]*) ;;                                              # a path
    *) N=$(printf 'SETUP86-VOLUME-%02d.ISO' "$ISO")            # isos/, else .isos-dir's folder
       ISO=$HERE/isos/$N; [ -f "$ISO" ] || [ -z "$ALT" ] || ISO=$ALT/$N ;;
esac
C=${2:-$HOME/eXoDOS/dosbox-c}
[ -f "$ISO" ] || { echo "no such ISO: $ISO"; exit 1; }
mkdir -p "$C"
exec dosbox-staging -c "mount c \"$C\"" -c "imgmount d \"$ISO\" -t iso" -c "d:" -c "menu"
