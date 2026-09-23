#!/usr/bin/env python3
"""Verify Base protocol APIs through Luce without adding a bootstrap dependency."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]


def run(command, environment):
    result = subprocess.run(list(map(str, command)), env=environment,
                            capture_output=True, timeout=120)
    if result.returncode != 0 or result.stderr:
        raise RuntimeError(f'{command}: status {result.returncode}\n'
                           f'{result.stdout.decode(errors="replace")}\n'
                           f'{result.stderr.decode(errors="replace")}')
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--luce', type=Path, required=True, help='an existing native Luce compiler')
    parser.add_argument('--base', type=Path, default=ROOT.parent / 'luce-base/build/luce-base')
    args = parser.parse_args()
    environment = dict(os.environ, LUCE_BASE=str(args.base.resolve()))
    entry = ROOT / 'tests/programs/net_protocols/interop/src/main.luc'
    with tempfile.TemporaryDirectory(prefix='net-protocol-interop-') as directory:
        for level in range(4):
            binary = Path(directory) / f'probe-{level}'
            run([args.luce.resolve(), 'build', entry, '--native', '--opt', level, '-o', binary], environment)
            output = run([binary], environment)
            assert output == b'ok Luce/Base HTTP and WebSocket boundary\n', output
            print(f'PASS Luce/Base protocol interop native opt {level}', flush=True)


if __name__ == '__main__':
    main()
