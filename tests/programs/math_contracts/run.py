#!/usr/bin/env python3
"""Check math special values and all four host rounding directions."""
import os
import csv
from pathlib import Path
import shlex
import subprocess
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parent
COMPILER = Path(sys.argv[1]).resolve()


def run(command):
    subprocess.run([sys.executable, ROOT.parent / "luce-base/tools/run_case.py", "--", *command],
                   cwd=ROOT, check=True)


with tempfile.TemporaryDirectory(prefix="base-math-contracts-") as temporary:
    work = Path(temporary)
    corpus = bytearray()
    with (ROOT / "tests/programs/math_accuracy/reference.csv").open() as source:
        for row in csv.DictReader(source):
            if row["operation"] in ("mod", "remainder"):
                corpus.extend(struct.pack("<IIQQQ", int(row["operation"] == "mod"), int(row["width"]),
                                          *[int(row[name], 16) for name in ("x_bits", "y_bits", "result_bits")]))
    reference = work / "remainders.bin"
    reference.write_bytes(corpus)
    run([*shlex.split(os.environ.get("CC", "cc")), "-Wall", "-Wextra", "-Werror",
         "-c", SOURCE / "reference.c", "-o", work / "reference.o"])
    run(["ar", "rcs", work / "libreference.a", work / "reference.o"])
    for flags in [*[["--native", "--opt", str(level)] for level in range(4)],
                  ["--backend=c"], ["--backend=c", "--release"]]:
        executable = work / "check"
        run([COMPILER, "build", SOURCE / "main.lucb", *flags,
             f"-L{work}", "-lreference", "-o", executable])
        run([executable, reference])
        print("PASS " + " ".join(flags), flush=True)
