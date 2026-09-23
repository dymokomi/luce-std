#!/usr/bin/env python3
"""Exercise mutations only inside a fresh temporary directory for each build."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
COMPILER = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix="base-file-mutations-") as temporary:
    work = Path(temporary)
    for flags in [*[["--native", "--opt", str(level)] for level in range(4)],
                  ["--backend=c"], ["--backend=c", "--release"]]:
        executable = work / "mutations"
        directory = work / "directory"
        paths = [directory / name for name in
                 ("data", "hard", "link", "dangling", "renamed", "link-alias")]
        for command in ([COMPILER, "build", ROOT / "tests/programs/file_mutations/main.lucb",
                         *flags, "-o", executable], [executable, directory, *paths]):
            subprocess.run([sys.executable, ROOT.parent / "luce-base/tools/run_case.py", "--", *command],
                           cwd=ROOT, check=True)
        assert not directory.exists()
        print("PASS " + " ".join(flags), flush=True)
