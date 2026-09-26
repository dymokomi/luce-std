#!/usr/bin/env python3
"""Crash on purpose and check the report names the faulting function and its callers."""
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
COMPILER = Path(sys.argv[1]).resolve()
CHAIN = ["crash_depth_three", "crash_depth_two", "crash_depth_one"]

def symbolicated(stack: str, executable: Path) -> str:
    """Windows reports give module+offset (no dladdr there); name the program's frames
    from its symbol table, as a debugger would, so the order can be checked."""
    listing = subprocess.run(["nm", "-n", "--defined-only", executable], capture_output=True, text=True, check=True).stdout
    symbols = []
    for line in listing.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1] in "tT":
            symbols.append((int(parts[0], 16), parts[2]))
    names = []
    for line in stack.splitlines():
        found = re.search(re.escape(executable.name) + r"\+0x([0-9a-f]+)", line)
        if not found:
            continue
        # A 64-bit PE's image base: nm lists addresses from it.
        address = 0x140000000 + int(found.group(1), 16)
        best = None
        for start, name in symbols:
            if start <= address:
                best = name
            else:
                break
        names.append(best or "?")
    return "\n".join(names)

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
            if os.name == "nt":
                stack = symbolicated(stack, executable)
            places = [stack.find(name) for name in CHAIN]
            if any(place < 0 for place in places) or places != sorted(places):
                print(text)
                raise SystemExit(f"{' '.join(flags)} {mode}: the stack does not name {', '.join(CHAIN)} in order")
            print(f"PASS {' '.join(flags)} {mode}", flush=True)
