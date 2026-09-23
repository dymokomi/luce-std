#!/usr/bin/env python3
"""Portable command lifetime and owned file contracts; no desktop session needed."""
import argparse
from pathlib import Path
import subprocess
import tempfile
import os
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--compiler', type=Path, default=ROOT.parent / 'luce-base/build/luce-base')
args = parser.parse_args()
flags = [['--native', '--opt', str(level)] for level in range(4)] + [['--backend=c'], ['--backend=c', '--release']]
with tempfile.TemporaryDirectory(prefix='luce-desktop-services-') as temporary:
    binary = Path(temporary) / ('contract.exe' if os.name == 'nt' else 'contract')
    for case in ['command', 'file_text']:
        for mode in flags:
            subprocess.run([str(args.compiler.resolve()), 'build', str(ROOT / ('tests/programs/' + case + '/main.lucb')), *mode, '-o', str(binary)], check=True, timeout=120)
            subprocess.run([str(binary)] + ([temporary] if case == 'file_text' else []), check=True, timeout=15)
            print('PASS', case, *mode, flush=True)
