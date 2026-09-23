#!/usr/bin/env python3
"""Check Unicode casing against the pinned UCD mappings and contextual examples."""
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parent
DATA = ROOT / "data/unicode/17.0.0"
COMPILER = Path(sys.argv[1]).resolve()


def records(name):
    for line in (DATA / name).read_text().splitlines():
        body = line.split("#", 1)[0].strip()
        if body:
            yield [field.strip() for field in body.split(";")]


def text(values):
    return "".join(chr(int(value, 16)) for value in values.split())


upper, lower, folds, turkic, combining = {}, {}, {}, {}, {}
for row in records("UnicodeData.txt"):
    character = chr(int(row[0], 16))
    combining[ord(character)] = int(row[3])
    if row[12]: upper[character] = text(row[12])
    if row[13]: lower[character] = text(row[13])
for row in records("SpecialCasing.txt"):
    if not row[4]:
        character = chr(int(row[0], 16))
        lower[character], upper[character] = text(row[1]), text(row[3])
for row in records("CaseFolding.txt"):
    character = chr(int(row[0], 16))
    if row[1] in ("C", "F"): folds[character] = text(row[2])
    if row[1] == "T": turkic[character] = text(row[2])

corpus = bytearray()


def add(kind, value, expected):
    raw, result = value.encode("utf-8"), expected.encode("utf-8")
    corpus.extend(struct.pack("<III", kind, len(raw), len(result)))
    corpus.extend(raw + result)


characters = set(upper) | set(lower) | set(folds) | set(turkic)
characters.update(chr(value) for value in (0, 0x10FFFF, 0xFFFF, 0x378, 0xFEFF, 0x1F600))
randomizer = random.Random(1700)
for _ in range(5000):
    value = randomizer.randrange(0x110000)
    if not 0xD800 <= value <= 0xDFFF: characters.add(chr(value))
for character in sorted(characters):
    add(0, character, upper.get(character, character))
    add(1, character, lower.get(character, character))
    add(2, character, folds.get(character, character))
    add(3, character, turkic.get(character, folds.get(character, character)))
for value in ("", "Σ", "ΟΣ", "ΟΣΑ", "ΟΣ\u0301", "ΟΣ\u0301Α", "AΣ' B", "AΣ'B",
              "A\u0345Σ", " \u0345Σ", "AΣ\u0345", "AΣ\u0345B", "Iİıi", "ßẞ", "\0AΣ\0",
              "A" + "\u0301" * 2000 + "Σ", "AΣ" + "\u0301" * 2000 + "B"):
    # These long-established mappings independently exercise the context rules
    # in Python's implementation; newly added characters use the pinned UCD above.
    add(0, value, value.upper())
    add(1, value, value.lower())
    add(2, value, value.casefold())
add(3, "Iİıi", "ıiıi")

whitespace = set()
for row in records("PropList.txt"):
    if row[1] == "White_Space":
        ends = row[0].split("..")
        whitespace.update(range(int(ends[0], 16), int(ends[-1], 16) + 1))
scalars = {0, 0x10FFFF, 0x110000, 0xFFFFFFFF}
for value in whitespace | {key for key, value in combining.items() if value}:
    scalars.update((value-1, value, value+1))
scalars.update(ord(character) for character in characters)
properties = bytearray()
for value in sorted(scalars):
    properties.extend(struct.pack("<III", value, int(value in whitespace), combining.get(value, 0)))


def run(command):
    subprocess.run([sys.executable, ROOT.parent / "luce-base/tools/run_case.py", "--", *command], cwd=ROOT, check=True)


run([sys.executable, ROOT / "tools/unicode_tables.py", "--check"])
with tempfile.TemporaryDirectory(prefix="base-unicode-casing-") as temporary:
    work = Path(temporary)
    reference, property_path = work / "casing.bin", work / "properties.bin"
    reference.write_bytes(corpus)
    property_path.write_bytes(properties)
    executable = work / "check"
    for flags in [*[["--native", "--opt", str(level)] for level in range(4)],
                  ["--backend=c"], ["--backend=c", "--release"]]:
        run([COMPILER, "build", SOURCE / "main.lucb", *flags, "-o", executable])
        run([executable, reference, property_path])
        print("PASS " + " ".join(flags), flush=True)
