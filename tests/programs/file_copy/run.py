#!/usr/bin/env python3
"""Check exact binary contents, empty files and FIFO copying through native builds."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
COMPILER = Path(sys.argv[1]).resolve()
payload = bytes(index % 251 for index in range(11003))
with tempfile.TemporaryDirectory(prefix="base-file-copy-") as temporary:
    work = Path(temporary)
    source, fifo, empty = (work / name for name in ("source", "fifo", "empty"))
    source.write_bytes(payload)
    empty.touch()
    os.mkfifo(fifo)
    for flags in [*[["--native", "--opt", str(level)] for level in range(4)],
                  ["--backend=c"], ["--backend=c", "--release"]]:
        executable = work / "copy"
        targets = [work / name for name in ("copied", "streamed", "empty-copy")]
        subprocess.run([sys.executable, ROOT.parent / "luce-base/tools/run_case.py", "--", COMPILER,
                        "build", ROOT / "tests/programs/file_copy/main.lucb",
                        *flags, "-o", executable], cwd=ROOT, check=True)
        producer = subprocess.Popen([sys.executable, "-c",
                                     'import sys; f = open(sys.argv[1], "wb"); f.write(b"streamed"); f.close()',
                                     str(fifo)])
        try:
            subprocess.run([sys.executable, ROOT.parent / "luce-base/tools/run_case.py", "--",
                            executable, source, fifo, empty, *targets], cwd=ROOT, check=True)
            assert producer.wait(timeout=10) == 0
        finally:
            if producer.poll() is None:
                producer.kill()
                producer.wait()
        assert targets[0].read_bytes() == payload
        assert targets[1].read_bytes() == b"streamed"
        assert targets[2].read_bytes() == b""
        for target in targets:
            target.unlink()
        assert not list(work.glob(".luce-*"))
        print("PASS " + " ".join(flags), flush=True)
