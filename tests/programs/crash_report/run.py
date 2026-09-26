#!/usr/bin/env python3
"""Crash on purpose and check the report names the faulting function and its callers."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
COMPILER = Path(sys.argv[1]).resolve()
CHAIN = ["crash_depth_three", "crash_depth_two", "crash_depth_one"]

def report(home: Path) -> str:
    reports = sorted((home / ".luce" / "crashes").glob("crashcheck-*.crash"))
    assert len(reports) == 1, f"expected one report, found {reports}"
    text = reports[0].read_text(errors="replace")
    reports[0].unlink()
    return text

with tempfile.TemporaryDirectory(prefix="std-crash-") as temporary:
    work = Path(temporary)
    home = work / "home"
    (home / ".luce" / "crashes").mkdir(parents=True)
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    executable = work / ("crashcheck.exe" if os.name == "nt" else "crashcheck")
    for flags in [["--native"], ["--native", "--release"]]:
        subprocess.run([COMPILER, "build", ROOT / "tests/programs/crash_report/main.lucb", *flags, "-o", executable],
                       cwd=ROOT, check=True)
        for mode in ["main", "thread", "trap"]:
            result = subprocess.run([executable, mode, "0"], env=env, capture_output=True)
            assert result.returncode != 0, f"{mode}: the program did not crash"
            text = report(home)
            stack = text.split("stack:", 1)[1] if "stack:" in text else ""
            places = [stack.find(name) for name in CHAIN]
            if any(place < 0 for place in places) or places != sorted(places):
                print(text)
                raise SystemExit(f"{' '.join(flags)} {mode}: the stack does not name {', '.join(CHAIN)} in order")
            print(f"PASS {' '.join(flags)} {mode}", flush=True)
