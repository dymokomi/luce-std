#!/usr/bin/env python3
"""Crash after asking for hooks and a relaunch, and check what followed: the report is named
by the program's package, the hooks ran (or were cut short), the recovery copy is noted, and
the program was started again with LUCE_CRASH_REPORT and no arguments to show the report."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
COMPILER = Path(sys.argv[1]).resolve()
WINDOWS = os.name == "nt"


def wait_for(found, seconds=15.0):
    """Poll until `found()` answers something, or fail."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        answer = found()
        if answer:
            return answer
        time.sleep(0.1)
    raise SystemExit("timed out waiting for the reporter")


def reports(home: Path):
    return sorted((home / ".luce" / "crashes").glob("crash-follow-*"))


def markers(home: Path):
    return sorted(home.glob("reporter-*.txt"))


def run(executable: Path, home: Path, *arguments, env_extra=None):
    """Run the program in a clean home; answer its exit status, report and stderr."""
    for stale in [*reports(home), *markers(home), home / "second-hook-ran"]:
        stale.unlink(missing_ok=True)
    env = {name: value for name, value in os.environ.items() if name != "LUCE_CRASH_REPORT"}
    env.update(HOME=str(home), USERPROFILE=str(home), **(env_extra or {}))
    started = time.monotonic()
    result = subprocess.run([executable, *arguments], env=env, capture_output=True, timeout=60)
    elapsed = time.monotonic() - started
    found = [Path(str(path).removesuffix(".seen")) for path in reports(home)]
    return result.returncode, report_text(found[0]) if found else "", elapsed, found


def report_text(report: Path) -> str:
    """The report's text, under its own name or, once the reporter has read it, `.seen`."""
    for _ in range(100):
        for path in (report, Path(f"{report}.seen")):
            try:
                return path.read_text(errors="replace")
            except FileNotFoundError:
                pass
        time.sleep(0.05)
    raise SystemExit(f"{report} vanished")


def same_file(path: str, expected: Path) -> bool:
    """Whether `path`, as the program spelled it, names `expected` (slashes may differ on Windows)."""
    return os.path.normcase(os.path.normpath(path)) == os.path.normcase(os.path.normpath(str(expected)))


def recovery_line(text: str) -> str:
    """The path a `recovery: ` line of the report gives, or ""."""
    for line in text.splitlines():
        if line.startswith("recovery: "):
            return line.removeprefix("recovery: ")
    return ""


def reporter(home: Path, report: Path) -> str:
    """The marker the relaunched program wrote: started with no arguments, shown `report`."""
    marker = wait_for(lambda: markers(home))[0]
    text = wait_for(lambda: marker.read_text(errors="replace"))
    lines = text.split("\n")
    assert lines[0] == "arguments: 1", text[:300]
    assert same_file(lines[1].removeprefix("path: "), report), text[:300]
    assert "luce crash report" in text, text[:300]
    # the reporter read it, so it is marked taken
    wait_for(lambda: Path(f"{report}.seen").exists())
    return text


# a reporter still finishing may write into the home while it is removed
with tempfile.TemporaryDirectory(prefix="std-crash-follow-", ignore_cleanup_errors=True) as temporary:
    work = Path(temporary)
    home = work / "home"
    (home / ".luce" / "crashes").mkdir(parents=True)
    project = work / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "main.lucb").write_text((ROOT / "tests/programs/crash_follow/main.lucb").read_text())
    (project / "package.prisma").write_text(
        '#prisma 4.0\ndef package "crash-follow" {\n    str version = "2.5.0"\n'
        f'    def dependency "luce-std" {{\n        str path = {json.dumps(ROOT.as_posix())}\n    }}\n}}\n')
    executable = work / ("crash-follow.exe" if WINDOWS else "crash-follow")
    # every backend traps through `core`: the report, the hooks and the relaunch alike
    for flags in [["--native"], ["--native", "--release"], ["--backend=c"]]:
        subprocess.run([COMPILER, "build", project / "src/main.lucb", *flags, "-o", executable], check=True)
        label = " ".join(flags)

        status, text, _, found = run(executable, home, "hooks")
        assert status == 1, f"{label} hooks: exit {status}"
        assert "app: crash-follow\nversion: 2.5.0\n" in text, text[:300]
        recovered = home / ".luce" / "recovery" / "crash-follow" / "scene.recovered"
        assert recovered.read_text() == "the scene, as it was"
        assert same_file(recovery_line(text), recovered), text
        assert (home / "second-hook-ran").exists(), "the second hook did not run"
        reporter(home, found[0])
        print(f"PASS {label} hooks, recovery note and relaunch", flush=True)

        status, text, _, found = run(executable, home, "hook-trap")
        assert status == 1, f"{label} hook-trap: exit {status}"
        assert "(and while the program handled that crash)" in text and "a trap inside a crash hook" in text, text
        assert not (home / "second-hook-ran").exists(), "a hook ran after one trapped"
        reporter(home, found[0])
        print(f"PASS {label} a trap in a hook ends the hooks", flush=True)

        status, text, elapsed, found = run(executable, home, "slow-hook")
        assert status == 1, f"{label} slow-hook: exit {status}"
        assert 4.5 < elapsed < 9.0, f"{label} slow-hook took {elapsed:.1f} s"
        assert "(the crash hooks ran out of time and were stopped)" in text, text
        reporter(home, found[0])
        print(f"PASS {label} the hooks' budget ends the process", flush=True)

        status, text, _, found = run(executable, home, "signal", "0")
        assert status == 128 + 11 or (WINDOWS and status != 0), f"{label} signal: exit {status}"
        assert "recovery:" not in text and not (home / "second-hook-ran").exists(), "a hook ran after a fatal signal"
        reporter(home, found[0])
        print(f"PASS {label} a fatal signal relaunches without hooks", flush=True)

        status, text, _, found = run(executable, home, "removed")
        assert status == 1 and "recovery:" not in text, f"{label} removed: a removed hook ran"
        assert (home / "second-hook-ran").exists(), "the hook still held did not run"
        reporter(home, found[0])
        print(f"PASS {label} a removed hook does not run", flush=True)

        # the reporter crashing starts nothing more
        shown = home / "shown.crash"
        shown.write_text("luce crash report\n")
        status, text, _, found = run(executable, home, "trap", env_extra={"LUCE_CRASH_REPORT": str(shown)})
        assert status == 1 and "the reporter crashed too" in text, f"{label} reporter trap: exit {status}"
        time.sleep(2)
        assert not markers(home), "a crash while showing a report started another process"
        print(f"PASS {label} a crashing reporter starts nothing", flush=True)

        # Reopen starts an ordinary run: without the report to show, so it crashes again
        # in its default mode, and that crash is shown in turn
        status, _, _, _ = run(executable, home, "reopen", env_extra={"LUCE_CRASH_REPORT": str(shown)})
        assert status == 0, f"{label} reopen: exit {status}"
        again = wait_for(lambda: [Path(str(path).removesuffix(".seen")) for path in reports(home)])
        reporter(home, again[0])
        print(f"PASS {label} reopen starts an ordinary run", flush=True)
