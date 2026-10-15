#!/bin/sh
# SPDX-License-Identifier: MIT  (Copyright (c) 2026 Ariel Juszczyk, see LICENSE)
# Build the Debian/Ubuntu package: dist/setup86_<version>_all.deb
#   packaging/build-deb.sh
# It holds the Python scripts and MENU.EXE (all architectures); apt installs what they need
# (python3-tk, python3-pil, python3-pycdlib, ffmpeg):  sudo apt install ./dist/setup86_*_all.deb
#   setup86        the Disc Builder app (also in the desktop's app menu)
#   setup86-cli    the command line, setup86.py
set -e
umask 022                          # the package's files: rw-r--r--, folders rwxr-xr-x
SRC=$(cd "$(dirname "$0")/.." && pwd)
VERSION=$(sed -n "s/^VERSION = '\([^']*\)'.*/\1/p" "$SRC/setup86.py")
[ -n "$VERSION" ] || { echo "no VERSION in setup86.py"; exit 1; }
[ -f "$SRC/dosmenu/MENU.EXE" ] || { echo "dosmenu/MENU.EXE is missing (see dosmenu/menu.c)"; exit 1; }
OUT=$SRC/dist
ROOT=$(mktemp -d)
trap 'rm -rf "$ROOT"' EXIT
chmod 755 "$ROOT"                  # mktemp makes it 700: that would be the mode of /
APP=$ROOT/usr/share/setup86

install -Dm644 "$SRC/setup86.py" "$APP/setup86.py"
install -Dm644 "$SRC/setup86_gui.py" "$APP/setup86_gui.py"
install -Dm644 "$SRC/dosmenu/MENU.EXE" "$APP/dosmenu/MENU.EXE"
install -Dm644 "$SRC/art/setup86-icon-128.png" "$APP/art/setup86-icon-128.png"   # the window icon

mkdir -p "$ROOT/usr/bin"
cat > "$ROOT/usr/bin/setup86" <<'EOF'
#!/bin/sh
exec python3 /usr/share/setup86/setup86_gui.py "$@"
EOF
cat > "$ROOT/usr/bin/setup86-cli" <<'EOF'
#!/bin/sh
exec python3 /usr/share/setup86/setup86.py "$@"
EOF
chmod 755 "$ROOT/usr/bin/setup86" "$ROOT/usr/bin/setup86-cli"

install -Dm644 /dev/stdin "$ROOT/usr/share/applications/setup86.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Setup86
Comment=Build DOS game CDs from eXoDOS
Exec=setup86
Icon=setup86
StartupWMClass=setup86
Categories=Game;
Terminal=false
EOF
for s in 64 128 256 512; do
    install -Dm644 "$SRC/art/setup86-icon-$s.png" "$ROOT/usr/share/icons/hicolor/${s}x$s/apps/setup86.png"
done

DOC=$ROOT/usr/share/doc/setup86
install -Dm644 "$SRC/README.md" "$DOC/README.md"
{
    echo 'Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/'
    echo 'Upstream-Name: Setup86'
    echo 'Source: https://github.com/arieljuszczyk/setup86'
    echo
    echo 'Files: *'
    echo 'Copyright: 2026 Ariel Juszczyk'
    echo 'License: MIT'
    sed 's/^$/./; s/^/ /' "$SRC/LICENSE"
} > "$DOC/copyright"
chmod 644 "$DOC/copyright"

mkdir -p "$ROOT/DEBIAN"
cat > "$ROOT/DEBIAN/control" <<EOF
Package: setup86
Version: $VERSION
Architecture: all
Maintainer: Ariel Juszczyk <ariel.juszczyk@gmail.com>
Installed-Size: $(du -sk --exclude=DEBIAN "$ROOT" | cut -f1)
Depends: python3 (>= 3.8), python3-tk, python3-pil, python3-pycdlib, ffmpeg
Section: games
Priority: optional
Homepage: https://github.com/arieljuszczyk/setup86
Description: build CDs of eXoDOS games for real DOS PCs
 Setup86 turns the games of an eXoDOS collection (Exodium or classic eXoDOS)
 into CD images for a real 8086-Pentium PC with MS-DOS: each game's own DOS
 files, a VGA menu that installs them to the hard disk, and a text menu.
 .
 setup86 starts the Disc Builder app; setup86-cli is the command line.
EOF

mkdir -p "$OUT"
dpkg-deb --root-owner-group -Zxz --build "$ROOT" "$OUT/setup86_${VERSION}_all.deb" >/dev/null
echo "$OUT/setup86_${VERSION}_all.deb"
