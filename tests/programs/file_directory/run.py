#!/usr/bin/env python3
"""Verify directory handles keep their identity across a pathname rename."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
COMPILER = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix="base-file-directory-") as temporary:
    work = Path(temporary)
    for flags in [*[["--native", "--opt", str(level)] for level in range(4)],
                  ["--backend=c"], ["--backend=c", "--release"]]:
        original, moved = work / "original", work / "moved"
        (original / "sub").mkdir(parents=True)
        (original / "data").write_bytes(b"data")
        (original / "sub/payload").write_bytes(b"payload")
        (original / "link").symlink_to("sub")
        (original / "dangling").symlink_to("missing")
        (original / "file_link").symlink_to("data")
        os.mkfifo(original / "pipe")
        executable = work / "directory"
        for command in ([COMPILER, "build", ROOT / "tests/programs/file_directory/main.lucb",
                         *flags, "-o", executable], [executable, original, moved]):
            subprocess.run([sys.executable, ROOT.parent / "luce-base/tools/run_case.py", "--", *command],
                           cwd=ROOT, check=True)
        assert not original.exists()
        assert (moved / "sub/payload").read_bytes() == b"payload"
        assert (moved / "created").read_bytes() == b"new"
        shutil.rmtree(moved)
        print("PASS " + " ".join(flags), flush=True)
