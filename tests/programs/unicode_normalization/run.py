#!/usr/bin/env python3
"""Run every relation in Unicode 17 NormalizationTest plus independent stress cases."""
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile
import unicodedata

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parent
COMPILER = Path(sys.argv[1]).resolve()
expected = {}
relations = 0


def add(form, value, result):
    global relations
    key = form, value.encode("utf-8")
    encoded = result.encode("utf-8")
    assert key not in expected or expected[key] == encoded
    expected[key] = encoded
    relations += 1


for line in (ROOT / "data/unicode/17.0.0/NormalizationTest.txt").read_text().splitlines():
    body = line.split("#", 1)[0].strip()
    if not body or body.startswith("@"):
        continue
    columns = ["".join(chr(int(value, 16)) for value in field.split()) for field in body.split(";")[:5]]
    source, nfc, nfd, nfkc, nfkd = columns
    for index, value in enumerate(columns):
        add(0, value, nfc if index < 3 else nfkc)
        add(1, value, nfd if index < 3 else nfkd)
        add(2, value, nfkc)
        add(3, value, nfkd)
assert relations > 300000

forms = ("NFC", "NFD", "NFKC", "NFKD")
samples = ["", "\0", "e\u0301\0", "\ufb01", "\ufeffA", "\uffff\U0010ffff",
           "A" + "\u0315\u0300\u05ae" * 4096,
           "\u0315\u0300\u05ae" * 4096,
           "a\u0301" * 2048, "\u1100\u1161\u11a8" * 2048]
randomizer = random.Random(150057)
# Restrict the independent Python campaign to long-established characters, so
# its installed Unicode version need not equal the pinned version being tested.
pool = [chr(value) for value in range(256)] + [chr(value) for value in range(0x300, 0x370)]
pool += list("\u1100\u1161\u11a8\uac00\uac01\ufb01\u212b\u1e9b\u0323")
for _ in range(2000):
    samples.append("".join(randomizer.choice(pool) for _ in range(randomizer.randrange(16))))
for value in samples:
    for form, name in enumerate(forms):
        add(form, value, unicodedata.normalize(name, value))
corpus = bytearray()
for (form, value), result in sorted(expected.items()):
    corpus.extend(struct.pack("<III", form, len(value), len(result)))
    corpus.extend(value + result)


def run(command):
    subprocess.run([sys.executable, ROOT.parent / "luce-base/tools/run_case.py", "--", *command], cwd=ROOT, check=True)


with tempfile.TemporaryDirectory(prefix="base-unicode-normalization-") as temporary:
    work = Path(temporary)
    reference = work / "normalization.bin"
    reference.write_bytes(corpus)
    executable = work / "check"
    for flags in [*[["--native", "--opt", str(level)] for level in range(4)],
                  ["--backend=c"], ["--backend=c", "--release"]]:
        run([COMPILER, "build", SOURCE / "main.lucb", *flags, "-o", executable])
        run([executable, reference])
        print(f"PASS {' '.join(flags)}: {relations} relations, {len(expected)} distinct cases", flush=True)
