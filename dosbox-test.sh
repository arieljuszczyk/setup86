#!/bin/sh
# SPDX-License-Identifier: MIT  (Copyright (c) 2026 Ariel Juszczyk, see LICENSE)
# Try a disc in DOSBox on this PC: the ISO becomes the CD drive (D:), a folder
# becomes the hard disk (C:), and the menu starts.
#   ./dosbox-test.sh [ISO | disc number] [C-folder]
#   ./dosbox-test.sh 3          (isos/SETUP86-VOLUME-03.ISO)
#   ./dosbox-test.sh ~/eXoDOS/SETUP86-ADVENTURE/SETUP86-ADVENTURE-01.ISO
# Installed games stay in the C-folder (default ~/eXoDOS/dosbox-c) between runs.
# Needs dosbox-staging (Exodium installs it).
ISO=${1:-1}
case $ISO in
    *[!0-9]*) ;;                                              # a path
    *) ISO=$(printf '%s/isos/SETUP86-VOLUME-%02d.ISO' "$(dirname "$0")" "$ISO") ;;
esac
C=${2:-$HOME/eXoDOS/dosbox-c}
[ -f "$ISO" ] || { echo "no such ISO: $ISO"; exit 1; }
mkdir -p "$C"
exec dosbox-staging -c "mount c \"$C\"" -c "imgmount d \"$ISO\" -t iso" -c "d:" -c "menu"
