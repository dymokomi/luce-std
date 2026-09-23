#!/bin/sh
set -eu
cd "$(dirname "$0")/../../.."
mkdir -p build
python3 tests/programs/unicode_graphemes/run.py "${1:-../luce-base/build/luce-base}"
