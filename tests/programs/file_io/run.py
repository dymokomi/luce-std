#!/usr/bin/env python3
"""Exercise real files and targeted syscall failures under every native opt level."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[3]
compiler = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix="base-file-io-") as temporary:
    work = Path(temporary)
    for flags in [*[['--native', '--opt', str(level)] for level in range(4)],
                  ['--backend=c'], ['--backend=c', '--release']]:
        executable = work / "file-io"
        target = work / "data"
        fifo = work / "input-fifo"
        os.mkfifo(fifo)
        subprocess.run([sys.executable, root.parent / 'luce-base/tools/run_case.py', '--', compiler,
                        'build', root / 'tests/programs/file_io/main.lucb',
                        *flags, '-o', executable], cwd=root, check=True)
        producer = subprocess.Popen([sys.executable, '-c',
                                    'import sys; f = open(sys.argv[1], "wb"); f.write(b"streamed"); f.close()',
                                    str(fifo)])
        try:
            subprocess.run([sys.executable, root.parent / 'luce-base/tools/run_case.py', '--',
                            executable, target, fifo], cwd=root, check=True)
            assert producer.wait(timeout=10) == 0
        finally:
            if producer.poll() is None:
                producer.kill()
                producer.wait()
        assert target.read_bytes() == b'abcd12xy'
        target.unlink()
        fifo.unlink()
        print('PASS ' + ' '.join(flags), flush=True)
