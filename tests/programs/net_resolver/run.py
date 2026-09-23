#!/usr/bin/env python3
"""Check resolver ordering, filtering, allocation failure and retained ownership."""
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parent
COMPILER = Path(sys.argv[1]).resolve()


def run(command):
    subprocess.run([sys.executable, ROOT.parent / "luce-base/tools/run_case.py", "--", *command],
                   cwd=ROOT, check=True)


with tempfile.TemporaryDirectory(prefix="base-resolver-") as temporary:
    work = Path(temporary)
    run([*shlex.split(os.environ.get("CC", "cc")), "-Wall", "-Wextra", "-Werror",
         "-c", SOURCE / "reference.c", "-o", work / "reference.o"])
    run(["ar", "rcs", work / "libreference.a", work / "reference.o"])
    for flags in [*[["--native", "--opt", str(level)] for level in range(4)],
                  ["--backend=c"], ["--backend=c", "--release"]]:
        executable = work / "check"
        run([COMPILER, "build", SOURCE / "main.lucb", *flags,
             f"-L{work}", "-lreference", "-o", executable])
        run([executable])
        print("PASS " + " ".join(flags), flush=True)
