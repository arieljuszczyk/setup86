# exo486 — eXoDOS games → CDs for a real DOS PC

Copies only the DOS files of the installed games in `~/eXoDOS/eXo/eXoDOS/<game>/` into
burnable folders/ISOs, with an install menu (`MENU.EXE`, with screenshots) on each disc. What's kept is what eXo's `dosbox.conf` mounted as `C:\` for the
game. Removed: eXo menus (`run.bat`), DOSBox commands, IPX/null-modem network scripts,
`.exo` and 0-byte marker files, DOSBox GUS driver folders, cracks, CD/floppy images,
eXo sound presets (`SB16\`, `GUS\`, `SC55\`, `MT32\`, `Tandy\`, `Herc\`...: folders
whose files are all copies of files in the parent), and helpers eXo adds (DOOMATIC,
`*_patch.exe`, FAKEHMA, BMOUSE, glide/3dfx emulation DLLs, `.ips`, `.bak`, `.pdf`, `.chm`,
Duke3D's guide demos). **No launchers
or installers are added.**

```sh
python3 -m venv ~/.venvs/exo486 && ~/.venvs/exo486/bin/pip install pycdlib pillow   # once (+ ffmpeg)
~/.venvs/exo486/bin/python exo486.py ~/eXoDOS/eXo/eXoDOS ~/eXoDOS/DOS-CD
```

Output (`~/eXoDOS/DOS-CD`, rebuilt each run; folders are hardlinks, so only ISOs use space):

| Path | What |
|---|---|
| `DOSGAMESn.ISO` | the disc: one folder per game at the root, `\<GAME>\...` (exact DOS 8.3 names) |
| `DISCn/` | the same as folders |
| `MENU.EXE` + `_MENU\` (on each disc) | graphical install menu: `MENU.DAT` (list, run notes) + one `<GAME>.PIC` screenshot per game |
| `TXTMENU.BAT` + `GETLINE.COM` (on each disc) | text-mode fallback menu, see below |
| `DISCn.TXT` | per game: where it goes on `C:` and how to start it (not on the disc) |

- **On the DOS PC**: from the CD drive (`D:`) run `MENU`. It needs VGA (any CPU, DOS 3.3+).
  - **Screen**: the game list on the left, and a screenshot, title, year, genre, language and size on the right.
  - **Keys**: arrows, PgUp/PgDn, Home/End, or a letter to jump to the next game with that initial.
  - **F1** shows a help screen. **F10** switches every screen between English and Spanish: header, help, dialogs, language and genre (`GENRE_ES` in `MENU.DAT`). Accents use the VGA font's own CP437 characters. Game titles and play commands aren't translated.
  - **Enter**: asks for the folder (default `C:\GAMES\<GAME>`, or `C:\JUEGOS\<GAME>` in Spanish; checked as an 8.3 path). It checks free space (cluster-rounded) and warns if the folder already has files. Then it copies with a progress bar (Esc stops) and shows how to start the game.
- **Try a disc on this PC**: `./dosbox-test.sh [ISO] [C-folder]`. It mounts the ISO as `D:` and a folder (default `~/eXoDOS/dosbox-c`, kept between runs) as `C:` in Exodium's `dosbox-staging`, then starts the menu. For example: `./dosbox-test.sh ~/eXoDOS/DOS-CD-AVENTURAS/AVENTURAS1.ISO`. Ctrl+F10 frees the mouse; Ctrl+F9 or `exit` quits DOSBox.
- **MENU.EXE source**: `dosmenu/menu.c`, C for OpenWatcom 2 (16-bit real mode, mode 13h). The built `dosmenu/MENU.EXE` is committed and copied onto each disc.
  - **Build**: unpack OpenWatcom's `ow-snapshot.tar.xz` into `~/.local/opt/openwatcom`, then run `WATCOM=~/.local/opt/openwatcom PATH=$WATCOM/binl64:$PATH INCLUDE=$WATCOM/h wcl -q -w4 -bt=dos -ml -0 -os -k12288 -fe=MENU.EXE menu.c`.
  - **Test**: `MENU /T:KEYS.TXT` reads keys from a file (`UP DOWN ENTER ESC SHOT TEXT:abc`...). `SHOT` dumps the screen to `SHOTnn.BIN` (768-byte palette + 64000 pixels). It runs headless in Exodium's `dosbox-staging` (`SDL_VIDEODRIVER=dummy`), with the ISO mounted via `imgmount d X.ISO -t iso`.
- **Screenshots**: a frame from eXo's gameplay video in `~/eXoDOS/Content/GameData/eXoDOS/<game>.zip`. Exodium downloads it with the game.
  - **Frame choice**: the most detailed of 7 frames (20-80% into the video). eXo's logo is painted out (ffmpeg `delogo`), then the frame is scaled to 192x120 and reduced to 240 colours.
  - **Fallback**: no video means the box art from Exodium's posters pack (`~/content/posters/eXoDOS/`).
  - **Cache**: `~/eXoDOS/.exo486-cache/shots/<game>.png`. Delete a file there to pick a new frame, or drop your own 192x120 PNG in its place.
- **Text menu** (`TXTMENU`, fallback without VGA): it lists the games (2 columns,
  `N`/`P` to page), you type the game number, then the destination (Enter =
  `C:\JUEGOS\<GAME>`), confirm `Y`, and it runs `XCOPY /S /E` + `ATTRIB -R /S` and shows
  how to start the game. By hand: `XCOPY D:\CKEEN1\*.* C:\JUEGOS\CKEEN1\ /S /E`.
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
- **Genre collections**: `--genre adventure --label AVENTURAS` builds only one genre into
  `AVENTURAS1.ISO`, ... Use its own output folder, e.g. `~/eXoDOS/DOS-CD-AVENTURAS`. The genre
  comes from Exodium's database (`~/.local/share/com.redfox.exodium/exodium.db`, read-only).
  A game matches if its genre contains the word and not "Action" (so no action-adventures or
  interactive movies), unless you ask for `--genre action`.
- **ISOs**: by default only disc 1 gets an ISO. Use `--iso 2`, `--iso all` or `--iso none`.
- **After burning a disc**: keep its `DISCn.TXT` outside `DOS-CD` (the folder is rebuilt)
  and pass it on later runs: `--burned ~/eXoDOS/burned/DISC1.TXT`. Its games are skipped,
  so new games (even ones starting with A) go onto the next discs instead of reshuffling.
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

## License

MIT, see [LICENSE](LICENSE). `MENU.EXE` shows the license notice when you quit it.

exo486 contains no eXoDOS games or files. It works on your own eXoDOS / Exodium install.
