#!/usr/bin/env python3
"""Exercise simultaneous buffered IPv4/IPv6 transfers against independent peers."""
import os
import json
import platform
import time
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


measurements = []
with tempfile.TemporaryDirectory(prefix="base-net-transfer-") as temporary:
    work = Path(temporary)
    run([*shlex.split(os.environ.get("CC", "cc")), "-Wall", "-Wextra", "-Werror",
         "-pthread", "-c", SOURCE / "reference.c", "-o", work / "reference.o"])
    run(["ar", "rcs", work / "libreference.a", work / "reference.o"])
    for flags in [*[["--native", "--opt", str(level)] for level in range(4)],
                  ["--backend=c"], ["--backend=c", "--release"]]:
        executable = work / "check"
        run([COMPILER, "build", SOURCE / "main.lucb", *flags,
             f"-L{work}", "-lreference", "-o", executable])
        started = time.perf_counter_ns()
        run([executable])
        elapsed = time.perf_counter_ns() - started
        # Four clients, two IP versions, two MiB each, in both directions.
        measurements.append(dict(flags=flags, wire_payload_bytes=32 * 1024 * 1024,
                                 elapsed_ns=elapsed, mib_per_second=32 * 1e9 / elapsed))
        print("PASS " + " ".join(flags), flush=True)

output = ROOT / "build/net-transfer.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(dict(schema=1, host=platform.platform(),
    measurements=measurements), indent=2) + "\n")
