#!/usr/bin/env python3
"""Walk a deep tree with symlink loops and a pruned branch while moving its root."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
COMPILER = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix="base-file-walk-") as temporary:
    work = Path(temporary)
    for flags in [*[["--native", "--opt", str(level)] for level in range(4)],
                  ["--backend=c"], ["--backend=c", "--release"]]:
        original, moved = work / "original", work / "moved"
        (original / "sub").mkdir(parents=True)
        (original / "data").write_bytes(b"data")
        (original / "sub/payload").write_bytes(b"payload")
        (original / "sub/back").symlink_to("..")
        (original / "link").symlink_to("sub")
        (original / "dangling").symlink_to("missing")
        (original / "skip").mkdir()
        (original / "skip/hidden").touch()
        leaf = original
        for index in range(24):
            leaf /= f"level-{index:02}"
            leaf.mkdir()
        (leaf / "leaf").write_bytes(b"leaf")
        executable = work / "walk"
        for command in ([COMPILER, "build", ROOT / "tests/programs/file_walk/main.lucb",
                         *flags, "-o", executable], [executable, original, moved]):
            subprocess.run([sys.executable, ROOT.parent / "luce-base/tools/run_case.py", "--", *command],
                           cwd=ROOT, check=True)
        assert (moved / "skip/hidden").exists()
        shutil.rmtree(moved)
        print("PASS " + " ".join(flags), flush=True)
