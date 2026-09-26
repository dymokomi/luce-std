#!/bin/sh
set -eu
cd "$(dirname "$0")/../../.."
python3 tests/programs/crash_report/run.py "${1:-../luce-base/build/luce-base}"
