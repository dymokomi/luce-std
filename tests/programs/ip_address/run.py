#!/usr/bin/env python3
"""Independent IP parsing/formatting references from Python ipaddress, seed 5952."""
from pathlib import Path
import ipaddress
import random
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
COMPILER = Path(sys.argv[1]).resolve()
randomizer = random.Random(5952)
corpus = bytearray()


def add(text):
    raw = text.encode("utf-8")
    try:
        # Interface zones belong to socket endpoints, not bare IP values.
        if "%" in text:
            raise ValueError("zone")
        value = ipaddress.ip_address(text)
        canonical = str(value)
        if value.version == 6 and value.ipv4_mapped is not None:
            canonical = "::ffff:" + str(value.ipv4_mapped)
        encoded = canonical.encode("ascii")
        corpus.extend((len(raw), value.version, len(encoded)))
        corpus.extend(raw)
        corpus.extend(encoded)
        corpus.extend(value.packed)
    except ValueError:
        corpus.extend((len(raw), 0, 0))
        corpus.extend(raw)


for text in ("", "0.0.0.0", "255.255.255.255", "::", "::1", "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff",
             "2001:db8:0:0:1:0:0:1", "2001:db8:0:1:1:1:1:1", "::ffff:192.0.2.1", "::192.0.2.1",
             "1", "127.1", "127.0.1", "01.2.3.4", "1.2.3.256", "1.2.3.4.5", "0x7f.0.0.1",
             "1.2.3.4:80", "1.2.3.4\0suffix", "::1\0", " ::1", "::1 ", ":::1", "1::2::3",
             "1:2:3:4:5:6:7", "1:2:3:4:5:6:7:8:9", "10000::", "::ffff:001.2.3.4",
             "[::1]", "[::1]:80", "fe80::1%lo0", "::1/128", "é::1", "x" * 46):
    add(text)
for _ in range(1000):
    add(str(ipaddress.IPv4Address(randomizer.getrandbits(32))))
# Every zero-field pattern probes longest runs, ties, single zeroes and boundaries.
for mask in range(256):
    words = [0 if mask & (1 << index) else randomizer.randrange(1, 65536) for index in range(8)]
    add(":".join(f"{word:04X}" for word in words))
for _ in range(2000):
    value = ipaddress.IPv6Address(randomizer.getrandbits(128))
    add(value.exploded.upper())
    add(value.compressed)
    text = value.compressed
    position = randomizer.randrange(len(text) + 1)
    add(text[:position] + randomizer.choice((":", "g", "0", ".", "\0", " ")) + text[position:])
for _ in range(256):
    add("::FFFF:" + str(ipaddress.IPv4Address(randomizer.getrandbits(32))))

with tempfile.TemporaryDirectory(prefix="base-ip-address-") as temporary:
    work = Path(temporary)
    reference = work / "corpus.bin"
    reference.write_bytes(corpus)
    executable = work / "check"
    for flags in [*[["--native", "--opt", str(level)] for level in range(4)],
                  ["--backend=c"], ["--backend=c", "--release"]]:
        for command in ([COMPILER, "build", ROOT / "tests/programs/ip_address/main.lucb",
                         *flags, "-o", executable], [executable, reference]):
            subprocess.run([sys.executable, ROOT.parent / "luce-base/tools/run_case.py", "--", *command],
                           cwd=ROOT, check=True)
        print("PASS " + " ".join(flags), flush=True)
