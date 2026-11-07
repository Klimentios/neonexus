#!/bin/sh
# NEONEXUS - double-click in Finder to install and start on macOS
cd "$(dirname "$0")" || exit 1
sh ./install.sh
rc=$?
echo
[ "$rc" -ne 0 ] && echo "Install failed (exit code $rc). See the messages above."
printf "Press Enter to close this window. "
read _
exit "$rc"
