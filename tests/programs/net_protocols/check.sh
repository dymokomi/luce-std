#!/bin/sh
set -eu
cd "$(dirname "$0")/../../.."
mkdir -p build
python3 tests/programs/net_protocols/run.py "${1:-../luce-base/build/luce-base}"
