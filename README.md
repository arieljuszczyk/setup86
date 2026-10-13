# Setup86 — from your eXoDOS install to CDs for a real DOS PC

Copies only the DOS files of the installed games in `~/eXoDOS/eXo/eXoDOS/<game>/` into
burnable folders/ISOs, with an install menu (`MENU.EXE`, with screenshots) on each disc. What's kept is what eXo's `dosbox.conf` mounted as `C:\` for the
game. Removed: eXo menus (`run.bat`), DOSBox commands, IPX/null-modem network scripts,
`.exo` and 0-byte marker files, DOSBox GUS driver folders, cracks, CD/floppy images,
eXo sound presets (`SB16\`, `GUS\`, `SC55\`, `MT32\`, `Tandy\`, `Herc\`...: folders
whose files are all copies of files in the parent; kept when a menu option copies from them),
and helpers eXo adds (DOOMATIC,
`*_patch.exe`, FAKEHMA, BMOUSE, glide/3dfx emulation DLLs, `.ips`, `.bak`, `.pdf`, `.chm`,
Duke3D's guide demos). **No launchers
or installers are added.**

```sh
python3 -m venv ~/.venvs/setup86 && ~/.venvs/setup86/bin/pip install pycdlib pillow   # once (+ ffmpeg)
~/.venvs/setup86/bin/python setup86.py ~/eXoDOS/eXo/eXoDOS ~/eXoDOS/SETUP86-VOLUME
```

**From a copy on another PC or a network share**: point `src` at the copied
`eXo/eXoDOS` folder. The inputs that live outside it go in an `setup86-data` folder
next to it (found automatically), or anywhere with `--data DIR`:

| In `setup86-data/` | Copied from (Exodium's own location) | Without it |
|---|---|---|
| `exodium.db` | `~/.local/share/com.redfox.exodium/exodium.db` | no titles/years/genres in the menu, `--genre` matches nothing |
| `shots/` | `~/eXoDOS/.setup86-cache/shots/` | screenshots are made again from `GameData/` or `posters/` |
| `GameData/` | `~/eXoDOS/Content/GameData/eXoDOS/` | no new video screenshots |
| `posters/` | `~/content/posters/eXoDOS/` | no box-art fallback |

When `src` is on another filesystem (e.g. SMB), the output folders are copies rather
than hardlinks, so they take real space.

Output (`~/eXoDOS/SETUP86-VOLUME`, rebuilt each run; folders are hardlinks, so only ISOs use space):

| Path | What |
|---|---|
| `SETUP86-VOLUME-nn.ISO` | the disc (CD label `SETUP86_Vnn`): one folder per game at the root, `\<GAME>\...` (exact DOS 8.3 names) |
| `DISCn/` | the same as folders |
| `MENU.EXE` + `_MENU\` (on each disc) | graphical install menu: `MENU.DAT` (list, run notes) + one `<GAME>.PIC` screenshot per game |
| `INSTALL.EXE` (on each disc) | the same program: started by this name, it installs the menu on the hard disk |
| `SETUP86.ID` (on each disc) | which disc this is: `SET <series>`, `VOL <n>`, `BUILD <yyyymmddhhmm>` |
| `TXTMENU.BAT` + `GETLINE.COM` (on each disc) | text-mode fallback menu, see below |
| `DISCn.TXT` | per game: where it goes on `C:` and how to start it (not on the disc) |

- **On the DOS PC**: from the CD drive (`D:`) run `MENU`. It needs VGA (any CPU, DOS 3.3+).
  - **Screen**: the game list on the left, and a screenshot, title, year, genre, language and size on the right.
  - **Keys**: arrows, PgUp/PgDn, Home/End, or a letter to jump to the next game with that initial.
  - **F1** shows a help screen. **F10** switches every screen between English and Spanish: header, help, dialogs, language and genre (`GENRE_ES` in `MENU.DAT`). Accents use the VGA font's own CP437 characters. Game titles and play commands aren't translated.
  - **Enter**: asks for the directory (default `C:\GAMES\<GAME>`, or `C:\JUEGOS\<GAME>` in Spanish; checked as an 8.3 path). It checks free space (cluster-rounded) and warns if the directory already has files. Then it copies with a progress bar (Esc stops) and shows how to start the game.
- **Menu on the hard disk** (the whole collection in one list): run `D:\INSTALL` (or press F2 in
  the disc's menu). It asks for the directory (default `C:\SETUP86`, editable) and copies the program
  plus that disc's list and screenshots there. Start it with `C:\SETUP86\MENU`.
  - It lists the games of every disc it knows, each with its disc ("Disc Volume 3"), sorted by name.
  - **Installing** looks for that disc in the CD drives (MSCDEX, any number of drives) by its
    `SETUP86.ID`, and asks "Insert Setup86 Volume 3" if it isn't there.
  - **Adding discs**: at start, and with F2, a disc in the drive that the list doesn't know yet is
    offered for adding. A disc with the same series and number but another `BUILD` (re-burned) is
    offered as an update of that disc's entries. Running `INSTALL` again on an existing folder also
    adds or updates that disc there.
  - **Files**: `_MENU\VOLS.DAT` (one line per disc, `<series> <n> <build>`; line n is disc n of the
    list), `_MENU\Vnnn.DAT` (that disc's `MENU.DAT`) and `_MENU\Vnnn\*.PIC`.
  - Disk errors (empty drive, disc being changed) are failed quietly by a critical-error handler,
    so DOS's "Abort, Retry, Fail?" never lands on the VGA screen.
- **Try a disc on this PC**: `./dosbox-test.sh [ISO] [C-folder]`. It mounts the ISO as `D:` and a folder (default `~/eXoDOS/dosbox-c`, kept between runs) as `C:` in Exodium's `dosbox-staging`, then starts the menu. For example: `./dosbox-test.sh ~/eXoDOS/SETUP86-ADVENTURE/SETUP86-ADVENTURE-01.ISO`. Ctrl+F10 frees the mouse; Ctrl+F9 or `exit` quits DOSBox.
- **MENU.EXE source**: `dosmenu/menu.c`, C for OpenWatcom 2 (16-bit real mode, mode 13h). The built `dosmenu/MENU.EXE` is committed and copied onto each disc.
  - **Build**: unpack OpenWatcom's `ow-snapshot.tar.xz` into `~/.local/opt/openwatcom`, then run `WATCOM=~/.local/opt/openwatcom PATH=$WATCOM/binl64:$PATH INCLUDE=$WATCOM/h wcl -q -w4 -bt=dos -ml -0 -os -k12288 -fe=MENU.EXE menu.c`.
  - **Test**: `MENU /T:KEYS.TXT` reads keys from a file (`UP DOWN ENTER ESC F1 F2 F10 SHOT TEXT:abc`...). `SHOT` dumps the screen to `SHOTnn.BIN` (768-byte palette + 64000 pixels). It runs headless in Exodium's `dosbox-staging` (`SDL_VIDEODRIVER=dummy`), with the ISO mounted via `imgmount d X.ISO -t iso`.
- **Screenshots**: a frame from eXo's gameplay video in `~/eXoDOS/Content/GameData/eXoDOS/<game>.zip`. Exodium downloads it with the game.
  - **Frame choice**: the most detailed of 7 frames (20-80% into the video). eXo's logo is painted out (ffmpeg `delogo`), then the frame is scaled to 192x120 and reduced to 240 colours.
  - **Fallback**: no video means the box art from Exodium's posters pack (`~/content/posters/eXoDOS/`).
  - **Cache**: `~/eXoDOS/.setup86-cache/shots/<game>.png`. Delete a file there to pick a new frame, or drop your own 192x120 PNG in its place.
- **Text menu** (`TXTMENU`, fallback without VGA): it lists the games (2 columns,
  `N`/`P` to page), you type the game number, then the destination (Enter =
  `C:\GAMES\<GAME>`), confirm `Y`, and it runs `XCOPY /S /E` + `ATTRIB -R /S` and shows
  how to start the game. By hand: `XCOPY D:\CKEEN1\*.* C:\GAMES\CKEEN1\ /S /E`.
  Games that had several C:\ folders (Blood, Final DOOM) have them as subfolders.
- **GETLINE.COM**: MS-DOS 6 batch files can't read typed text (`SET /P` is NT-only), so
  this 311-byte 8086 program reads a line and writes `SET <VAR>=<text>` to `C:\_M.BAT`,
  which `TXTMENU.BAT` then `CALL`s. Source is `getline.s` (the script embeds the built
  bytes). `test_getline.py` runs it in a CPU emulator with simulated keystrokes. The menu
  needs `CHOICE` (DOS 6) and writes the temp file to `C:\`. It uses only 4 short variables.
  If DOS still says "Out of environment space", add `/E:1024` to `SHELL=` in CONFIG.SYS.
- **Spanish first**: if a game's Spanish version is downloaded (`eXoDOS/!spanish/<game>` +
  `!dos/!spanish/<game>/dosbox.conf`), it's used instead of English (`[ESPANOL]` in
  `DISCn.TXT`). The `!spanish/*.zip` files are 0-byte Exodium placeholders. The run's
  output lists games with a Spanish version in eXo that isn't downloaded yet: get them
  in Exodium and rerun.
- **Packing**: alphabetical by folder name, 720 MB per disc (80-min CD-R). A game that
  doesn't fit waits, and the following (smaller) games still go on the current disc.
- **Left out**: any game where eXo mounts a CD (`imgmount`/`mount ... -t cdrom` in its
  config, or a CD from the game's own `cd\` folder in its `run.bat` menu). Each of those
  gets burned onto its own CD and installed from it. Exception: a Spanish pack that also
  ships a floppy version (Dark Seed, Dune, Gobliiins 1-3, Loom, Space Quest IV) goes on
  the data disc as that floppy version, via a hand entry.
- **Series and genre collections**: discs are named "Setup86 <series> <n>" (`--series`, default
  `Volume`). `--genre adventure --series Adventure` builds only one genre into
  `SETUP86-ADVENTURE-01.ISO`, ... Use its own output folder, e.g. `~/eXoDOS/SETUP86-ADVENTURE`. The genre
  comes from Exodium's database (`~/.local/share/com.redfox.exodium/exodium.db`, read-only).
  A game matches if its genre contains the word and not "Action" (so no action-adventures or
  interactive movies), unless you ask for `--genre action`.
- **ISOs**: by default only disc 1 gets an ISO. Use `--iso 2`, `--iso all` or `--iso none`.
- **After burning a disc**: keep its `DISCn.TXT` outside the output folder (it is rebuilt)
  and pass it on later runs: `--burned ~/eXoDOS/burned/DISC1.TXT`. Its games are skipped,
  so new games (even ones starting with A) go onto the next discs instead of reshuffling.
  Add `--first N` so the new discs continue the numbering of that series (e.g. `--first 3` builds
  Volume 3, 4...): an installed menu tells discs apart by series + number.
- **Special cases handled**:
  - **Games that run from a floppy image:** for example Italy 90, which eXo mounts as `A:` and starts there. The image is FAT12/16, and its files (minus the floppy's own DOS boot files) are extracted into the game folder.
  - **Self-booting games** (eXo uses `BOOT`) are skipped with a message: write their image to a real floppy.
  - **Windows-only folders** (all `.EXE` are Windows GUI, such as the AGS fan remakes KQ3 Redux and KQ4 Retold) are dropped.
  - **Folders whose name isn't 8.3** are dropped and listed.
  - **A `floppy` folder** is skipped only if it holds nothing but images.
  - **Original releases only**: fan-made content is left out.
    - **Fan add-ons**: the Monkey Island 1/2 Spanish fan talkies, the LSL3 mouse mod (`LS3pp`) and the Plutonia MIDI pack (`plutmid`). The official Indy 4 CD talkie stays.
    - **Fan games** (`FAN_GAMES`): Commander Keen 7-9.
    - **Fan translations** (`FAN_TRANSLATIONS`): KQ1, LSL1-3, SQ3, SQ5 (with a fan voice dub) and X-COM use the English original instead. If English isn't downloaded, the game is left out and listed.
  - **Hand entries per language**: an entry with `lang='es'` is used only for the Spanish version. Use the key `<game>:es` when the English version already has an entry (e.g. `dune:es`).
  - **Spanish versions eXo runs only in ScummVM** (no DOS config) are listed, so you can get the English one.
- **Auto-converted games**: the games in the `G` table have hand-checked notes. Any other
  game is auto-converted from its eXo config and listed under WARNINGS. Test those on the
  PC, and add a `G` entry if one needs fixing.
- **Sound**: each game keeps the config eXo last used (often Sound Blaster at DOSBox's
  `A220 I7 D1 H5`). For your real card, run the game's own SETUP/INSTALL program.

## Disclaimer

- **No games included.** Setup86 is a tool: it contains no games, eXoDOS files, screenshots or
  box art. It only works on an eXoDOS / Exodium install you already have.
- **Not affiliated** with eXoDOS, the eXo team or Exodium. All game names and trademarks belong
  to their owners.
- **Personal use.** The discs you build contain games that are still under copyright. Build them
  for your own computers, for games you are entitled to use. **Don't share, sell or upload the
  discs or ISOs**, and please don't ask for them: none will be provided.
- **No warranty.** Provided "as is" (see the license). It writes to your hard disk on a real DOS
  PC: keep backups of anything important there.

## Support the project

Setup86 is free and stays free. If it brought an old PC back to life and you'd like to say thanks,
you can buy me a coffee:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/setup86)

Donations support the development of this tool only. They never pay for games or discs, and
there are no rewards. Bug reports, tests on real hardware and pull requests are just as welcome.

## License

MIT, see [LICENSE](LICENSE). `MENU.EXE` shows the license notice when you quit it.
