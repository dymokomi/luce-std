#!/usr/bin/env python3
"""The Luce surface: every program under tests/luce is built by the Luce compiler against
this checkout and must print its main.expect. A built Luce program that leaves an object
alive exits with status 3, so each run also proves the owned results and objects it used
were released. With --leaks (macOS), each also runs under `leaks --atExit`.

Usage: tests/luce/run.py [--luce PATH] [--leaks] [CASE...]"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--luce", type=Path, default=ROOT.parent / "luce/build/luce")
parser.add_argument("--leaks", action="store_true", help="also run each program under leaks --atExit")
parser.add_argument("cases", nargs="*")
args = parser.parse_args()
compiler = str(args.luce.resolve())
cases = sorted(p.parent for p in HERE.glob("*/main.luc") if not args.cases or p.parent.name in args.cases)
failures = 0
for case in cases:
    with tempfile.TemporaryDirectory(prefix="luce-std-surface-") as temporary:
        work = Path(temporary)
        shutil.copy(case / "main.luc", work / "main.luc")
        (work / "package.prisma").write_text(
            '#prisma 4.0\ndef package "surface" {\n    str source = "."\n'
            f'    def dependency "luce-std" {{\n        str path = "{ROOT.as_posix()}"\n    }}\n}}\n')
        built = subprocess.run([compiler, "build", "main.luc", "-o", "program"], cwd=work,
                               capture_output=True, text=True, timeout=600)
        if built.returncode != 0:
            print(f"FAIL {case.name}: the build failed\n{built.stdout}{built.stderr}")
            failures += 1
            continue
        ran = subprocess.run([str(work / "program")], cwd=work, capture_output=True, text=True, timeout=120)
        expected = (case / "main.expect").read_text()
        if ran.returncode != 0 or ran.stdout != expected:
            print(f"FAIL {case.name}: status {ran.returncode}\n--- expected\n{expected}--- printed\n{ran.stdout}{ran.stderr}")
            failures += 1
            continue
        if args.leaks and sys.platform == "darwin":
            checked = subprocess.run(["leaks", "--atExit", "--", str(work / "program")], cwd=work,
                                     capture_output=True, text=True, timeout=300)
            if " 0 leaks for 0 total leaked bytes" not in checked.stdout:
                print(f"FAIL {case.name}: leaks\n{checked.stdout[-3000:]}")
                failures += 1
                continue
        print(f"ok   {case.name}")
if failures:
    sys.exit(f"FAIL luce surface: {failures} of {len(cases)} programs")
print(f"PASS luce surface: {len(cases)} programs" + (" without leaks" if args.leaks else ""))
