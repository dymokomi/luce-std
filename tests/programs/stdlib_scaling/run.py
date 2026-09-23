#!/usr/bin/env python3
"""Record scaling without treating noisy wall-clock ratios as correctness limits."""
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parent
COMPILER = Path(sys.argv[1]).resolve()
OUTPUT = ROOT / "build/stdlib-scaling.json"


def run(command):
    return subprocess.run(
        [sys.executable, ROOT.parent / "luce-base/tools/run_case.py", "--", *map(str, command)],
        cwd=ROOT, check=True, capture_output=True, text=True).stdout


results = []
with tempfile.TemporaryDirectory(prefix="base-stdlib-scaling-") as temporary:
    work = Path(temporary)
    for level in range(4):
        executable = work / "measure"
        run([COMPILER, "build", SOURCE / "main.lucb", "--native", "--opt", level,
             "-o", executable])
        samples = {}
        for repetition in range(3):
            output = run([executable, work / "source", work / "destination"])
            seen = set()
            for line in output.splitlines():
                operation, size, elapsed, allocations, peak = line.split(",")
                key = (operation, int(size))
                assert key not in seen, f"duplicate measurement: {key}"
                seen.add(key)
                record = (int(elapsed), int(allocations), int(peak))
                assert record[0] > 0, "monotonic clock did not advance"
                samples.setdefault(key, []).append(record)
            assert len(seen) == 12, "missing workload measurements"
        file_counts = set()
        previous = {}
        for (operation, size), values in samples.items():
            assert len(values) == 3
            counts = {(value[1], value[2]) for value in values}
            assert len(counts) == 1, "allocator accounting changed between repetitions"
            allocations, peak = counts.pop()
            if operation == "file_copy":
                file_counts.add((allocations, peak))
            median = int(statistics.median(value[0] for value in values))
            record = dict(operation=operation, bytes=size, native_opt=level,
                          samples_ns=[value[0] for value in values], median_ns=median,
                          mib_per_second=size * 1e9 / median / (1024 * 1024),
                          allocations=allocations, peak_allocator_bytes=peak)
            if operation in previous:
                earlier_size, earlier_time = previous[operation]
                record["input_ratio"] = size / earlier_size
                record["time_ratio"] = median / earlier_time
            previous[operation] = (size, median)
            results.append(record)
            print(f"opt={level} {operation} bytes={size} ns={median} "
                  f"MiB/s={record['mib_per_second']:.2f} "
                  f"allocations={allocations} peak_bytes={peak}", flush=True)
        assert len(file_counts) == 1, "file-copy allocation grew with payload size"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(dict(
    schema=1, host=platform.platform(), machine=platform.machine(),
    compiler=str(COMPILER), measurements=results), indent=2) + "\n")
print(f"PASS native scaling and allocation bounds; measurements: {OUTPUT}")
