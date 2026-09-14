#!/bin/bash
# Reference harness: run Castle of the Winds headless under wine + Xvfb.
#   tools/reference-harness.sh /path/to/CASTLE1.EXE
# Screenshots land in ./shots/cotw-NN.png; drive with xdotool key/type/click.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
export WINEPREFIX="$HERE/wp" WINEARCH=win32 WINEDEBUG=-all DISPLAY=:77
EXE="${1:?usage: cotw.sh /path/to/CASTLE1.EXE}"
mkdir -p "$HERE/shots"

pgrep -f "Xvfb :77" >/dev/null || { Xvfb :77 -screen 0 1024x768x16 >/dev/null 2>&1 & sleep 3; }
[ -d "$WINEPREFIX/drive_c" ] || wine wineboot -u >/dev/null 2>&1

wine "$EXE" >"$HERE/cotw.log" 2>&1 &
sleep 10

shot() { import -window root "$HERE/shots/cotw-$1.png"; echo "shots/cotw-$1.png"; }
shot 00
xdotool search --name "Castle" 2>/dev/null | head -5
