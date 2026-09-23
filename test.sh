#!/bin/sh
# The package's gate: its own checks, then every module's tests and program checks.
set -eu
cd "$(dirname "$0")"
compiler="${LUCE_BASE:-../luce-base/build/luce-base}"
python3 tools/unicode_tables.py --check
python3 tools/test_desktop_services.py --compiler "$compiler"
exec python3 tests/run.py --base "$compiler" "$@"
