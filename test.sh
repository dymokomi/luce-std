#!/bin/sh
# The package's gate: its own checks, every module's tests and program checks, then the
# surface Luce programs see, built by a Luce compiler when one is at hand.
set -eu
cd "$(dirname "$0")"
compiler="${LUCE_BASE:-../luce-base/build/luce-base}"
python3 tools/unicode_tables.py --check
python3 tools/test_desktop_services.py --compiler "$compiler"
python3 tests/run.py --base "$compiler" "$@"
# LUCE names the Luce compiler; a checkout beside this one is used otherwise
luce="${LUCE:-../luce/build/luce}"
if [ -x "$luce" ]; then
    python3 tests/luce/run.py --luce "$luce"
else
    echo "SKIP luce surface: no Luce compiler at $luce (set LUCE)"
fi
