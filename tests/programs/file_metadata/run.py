#!/usr/bin/env python3
"""Compare metadata with the host ABI, including a sparse file larger than 4 GiB."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
COMPILER = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix="base-file-metadata-") as temporary:
    work = Path(temporary)
    fifo = work / "fifo"
    os.mkfifo(fifo)
    for flags in [*[["--native", "--opt", str(level)] for level in range(4)],
                  ["--backend=c"], ["--backend=c", "--release"]]:
        executable = work / "metadata"
        for command in ([COMPILER, "build", ROOT / "tests/programs/file_metadata/main.lucb",
                         *flags, "-o", executable], [executable, work / "data", work / "link", fifo]):
            subprocess.run([sys.executable, ROOT.parent / "luce-base/tools/run_case.py", "--", *command],
                           cwd=ROOT, check=True)
        print("PASS " + " ".join(flags), flush=True)
