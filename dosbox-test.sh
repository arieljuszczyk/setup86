#!/bin/sh
# SPDX-License-Identifier: MIT  (Copyright (c) 2026 Ariel Juszczyk, see LICENSE)
# Try a disc in DOSBox on this PC: the ISO becomes the CD drive (D:), a folder
# becomes the hard disk (C:), and the menu starts.
#   ./dosbox-test.sh [ISO] [C-folder]
#   ./dosbox-test.sh ~/eXoDOS/SETUP86-ADVENTURE/SETUP86-ADVENTURE-01.ISO
# Installed games stay in the C-folder (default ~/eXoDOS/dosbox-c) between runs.
# Needs dosbox-staging (Exodium installs it).
ISO=${1:-$(dirname "$0")/isos/SETUP86-VOLUME-01.ISO}
C=${2:-$HOME/eXoDOS/dosbox-c}
[ -f "$ISO" ] || { echo "no such ISO: $ISO"; exit 1; }
mkdir -p "$C"
exec dosbox-staging -c "mount c \"$C\"" -c "imgmount d \"$ISO\" -t iso" -c "d:" -c "menu"
