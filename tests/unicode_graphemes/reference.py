#!/usr/bin/env python3
"""Write graphemes.bin into the directory given: extended grapheme boundaries from
Unicode 17's GraphemeBreakTest and long context runs, which main.luc hands to check.lucb."""
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(sys.argv[1])
corpus = bytearray()
cases = 0


def add(clusters):
    global cases
    encoded = [cluster.encode("utf-8") for cluster in clusters]
    assert all(encoded)
    text = b"".join(encoded)
    corpus.extend(struct.pack("<II", len(text), len(encoded)))
    corpus.extend(text)
    for cluster in encoded:
        corpus.extend(struct.pack("<I", len(cluster)))
    cases += 1


for line in (ROOT / "data/unicode/17.0.0/auxiliary/GraphemeBreakTest.txt").read_text().splitlines():
    body = line.split("#", 1)[0].strip()
    if not body:
        continue
    clusters, current = [], ""
    for token in body.split():
        if token == "÷":
            if current:
                clusters.append(current)
                current = ""
        elif token != "×":
            current += chr(int(token, 16))
    assert not current
    add(clusters)
for clusters in ([], ["\0"], ["a", "\0", "b"], ["\r\n", "\r", "x", "\n"],
                 ["a\u0301"], ["\ufeff", "a"], ["\uffff", "\U0010ffff"],
                 ["👩\u200d👩\u200d👧\u200d👦"], ["👩\u200d\u0301", "👩"],
                 ["🇦\u0301", "🇧🇨", "🇩"], ["\u0600🇦🇧", "🇨"],
                 ["\u1100\u1161\u11a8"], ["\u0915\u094d\u200d\u0915"],
                 ["a" + "\u0301" * 16384],
                 ["\u0600" * 16384 + "a"],
                 ["👩" + "\u0301" * 8192 + "\u200d👩"],
                 ["\u0915\u094d" * 8192 + "\u0915"],
                 ["🇦🇧"] * 8192 + ["🇨"]):
    add(clusters)
assert cases > 700

(OUTPUT / "graphemes.bin").write_bytes(corpus)
