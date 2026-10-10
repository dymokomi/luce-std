#!/usr/bin/env python3
"""Regenerate reference.txt, the arbitrary-precision references of math_ulp (not run by tests).

For each of math's elementary functions, f64 and f32: edge cases, values spread over the
function's whole domain and the regions where methods switch or cancel, from a fixed seed.
Each row holds the exact result as a pair of doubles (the double nearest it and the double
nearest the rest), from mpmath at 400 bits, checked against a second evaluation at 600
bits. Run it with mpmath 1.3.0 in an isolated environment:

    python3 tests/math_ulp/generate.py [--count N] [--output PATH]

The default count keeps the checked-in file small; a larger --count and the test's
MATH_ULP_REFERENCE variable run the same check over many more inputs.
"""
import argparse
import math
import multiprocessing
import random
import struct
from pathlib import Path

import mpmath as mp

assert mp.__version__ == "1.3.0", "use the pinned reference generator version"
HERE = Path(__file__).resolve().parent
UNARY = ["exp", "exp2", "expm1", "log", "log2", "log10", "log1p", "sin", "cos", "tan",
         "asin", "acos", "atan", "sinh", "cosh", "tanh", "cbrt"]
BINARY = ["pow", "atan2", "hypot"]
FUNCTIONS = UNARY[:7] + ["pow"] + UNARY[7:13] + ["atan2"] + UNARY[13:] + ["hypot"]


def bits64(x):
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def to_f32(x):
    """x rounded to f32, values past its range clamped to its largest."""
    x = max(-3.4028234663852886e38, min(3.4028234663852886e38, x))
    return struct.unpack("<f", struct.pack("<f", x))[0]


def wide(rng, low=-1074, high=1023, signed=True):
    """A random double with exponent uniform in [low, high]."""
    v = math.ldexp(rng.random() + 1.0, rng.randint(low, high))
    return -v if signed and rng.random() < 0.5 else v


def inputs(name, count, rng):
    """Inputs for one function: a mix over the domain and its delicate regions."""
    u = rng.uniform
    n = count
    q = max(1, n // 4)
    if name == "exp":
        pts = [u(-745.2, 709.8) for _ in range(n)] + [u(-1, 1) for _ in range(q)] + \
              [u(-745.2, -708) for _ in range(q)] + [wide(rng, -60, 0) for _ in range(q)]
    elif name == "exp2":
        pts = [u(-1075, 1024) for _ in range(n)] + [u(-1, 1) for _ in range(q)] + [u(-1080, -1020) for _ in range(q)]
    elif name == "expm1":
        pts = [u(-40, 709.7) for _ in range(n)] + [u(-1, 1) for _ in range(n)] + [wide(rng, -60, -1) for _ in range(n)]
    elif name in ("log", "log2", "log10"):
        pts = [abs(wide(rng)) for _ in range(n)] + [1 + u(-0.01, 0.01) for _ in range(n)] + \
              [1 + wide(rng, -60, -7) for _ in range(q)] + [u(0.3, 3) for _ in range(n)]
    elif name == "log1p":
        pts = [abs(wide(rng)) for _ in range(n)] + [u(-1, 1) for _ in range(n)] + \
              [wide(rng, -60, -1) for _ in range(n)] + [-1 + abs(wide(rng, -60, -2, False)) for _ in range(q)]
    elif name in ("sin", "cos", "tan"):
        pts = [u(-10, 10) for _ in range(n)] + [wide(rng, -30, 1023) for _ in range(n)] + \
              [u(-1e6, 1e6) for _ in range(q)] + [wide(rng, -60, -20) for _ in range(q)] + \
              [k * math.pi / 2 for k in range(1, q)] + [6381956970095103 * 2.0 ** 797, 5.319372648326541e+255]
    elif name in ("asin", "acos"):
        pts = [u(-1, 1) for _ in range(n)] + \
              [math.copysign(1 - abs(wide(rng, -53, -1, False)), rng.random() - 0.5) for _ in range(n)] + \
              [wide(rng, -60, -1) for _ in range(q)]
    elif name == "atan":
        pts = [wide(rng, -40, 60) for _ in range(n)] + [u(-4, 4) for _ in range(n)] + [wide(rng) for _ in range(q)]
    elif name in ("sinh", "cosh", "tanh"):
        pts = [u(-710.4, 710.4) for _ in range(n)] + [u(-3, 3) for _ in range(n)] + [wide(rng, -60, 0) for _ in range(n)]
    elif name == "cbrt":
        pts = [wide(rng) for _ in range(n)] + [u(-10, 10) for _ in range(n)]
    elif name == "pow":
        pts = []
        for _ in range(n):
            x = abs(wide(rng))
            limit = 745 / abs(math.log(x)) if x != 1 else 1e10
            pts.append((x, u(-limit, limit)))
        for _ in range(n):
            x = 1 + u(-2 ** -7, 2 ** -7)
            limit = 740 / abs(math.log(x))
            pts.append((x, u(-limit, limit)))
        pts += [(u(0, 10), u(-50, 50)) for _ in range(q)]
        pts += [(-u(0.5, 3), float(rng.randint(-200, 200))) for _ in range(q)]
        pts += [(float(rng.randint(2, 30)), float(rng.randint(-30, 30))) for _ in range(q)]
    elif name == "atan2":
        pts = [(wide(rng, -40, 40), wide(rng, -40, 40)) for _ in range(n)] + \
              [(wide(rng), wide(rng)) for _ in range(q)] + [(u(-2, 2), u(-2, 2)) for _ in range(n)]
    elif name == "hypot":
        pts = []
        for _ in range(n):
            x = wide(rng)
            pts.append((x, x * wide(rng, -60, 0)))
        pts += [(wide(rng, -1074, -1000), wide(rng, -1074, -1000)) for _ in range(q)]
        pts += [(u(-10, 10), u(-10, 10)) for _ in range(n)]
        pts += [(wide(rng, 1000, 1023), wide(rng, 1000, 1023)) for _ in range(q)]
    if name not in BINARY:
        pts = [(x, 0.0) for x in pts]
    return pts


def exact(name, x, y):
    x, y = mp.mpf(x), mp.mpf(y)
    if name == "exp2": return mp.power(2, x)
    if name == "log2": return mp.log(x, 2)
    if name == "pow":
        if x < 0:
            return mp.power(-x, y) * (-1 if int(y) % 2 else 1)
        return mp.power(x, y)
    if name == "atan2": return mp.atan2(x, y)
    if name == "cbrt": return mp.sign(x) * mp.root(abs(x), 3)
    if name == "hypot": return mp.sqrt(x * x + y * y)
    return getattr(mp, name)(x)


def nearest(value, precision, bias):
    """The binary float nearest `value` with `precision` bits and exponent bias `bias`,
    as a Python float (exact), or None past the largest finite value."""
    if value == 0:
        return 0.0
    sign = -1 if value < 0 else 1
    a = abs(value)
    e = max(int(mp.floor(mp.log(a, 2))), 1 - bias)
    quantum = mp.ldexp(1, e - precision + 1)
    rounded = mp.nint(a / quantum) * quantum  # mpmath's nint rounds halves to even
    if rounded >= mp.ldexp(1, bias + 1):
        return None
    return sign * float(rounded)


def row(job):
    name, single, x, y = job
    results = []
    for precision in (400, 600):
        with mp.workprec(precision):
            value = exact(name, x, y)
            if isinstance(value, mp.mpc) or mp.isnan(value):
                results.append(("nan",))
                continue
            if mp.isinf(value):
                results.append(("inf", 1 if value > 0 else -1))
                continue
            p, bias = (24, 127) if single else (53, 1023)
            rounded = nearest(value, p, bias)
            if rounded is None:
                results.append(("inf", 1 if value > 0 else -1))
                continue
            high = nearest(value, 53, 1023)
            low = float(value - mp.mpf(high))
            results.append(("finite", high, low, rounded))
    first, second = results
    assert first[0] == second[0] and first[:3] == second[:3] or first[0] == "finite" and abs(first[2] - second[2]) <= abs(first[1]) * 2.0 ** -100, (name, x, y, first, second)
    return name, single, x, y, first


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--output", default=str(HERE / "reference.txt"))
    arguments = parser.parse_args()
    rng = random.Random(5602)
    jobs = []
    for single in (False, True):
        for name in FUNCTIONS:
            count = arguments.count if not single else max(4, arguments.count // 3)
            for x, y in inputs(name, count, rng):
                if single:
                    x, y = to_f32(x), to_f32(y)
                if name == "atan2" and (x == 0 or y == 0):
                    # signed zeros decide atan2 there; mpmath has one zero (math_contracts checks them)
                    continue
                jobs.append((name, single, x, y))
    with multiprocessing.Pool() as pool:
        rows = pool.map(row, jobs, chunksize=64)
    lines = ["# function x y kind high low: math_ulp's references (generate.py); hex IEEE bits. kind is",
             "# f (finite: high + low is the exact value), i (an infinity, high its sign), n (NaN)."]
    for name, single, x, y, result in rows:
        label = name + ("32" if single else "")
        if result[0] == "nan":
            kind, high, low = "n", 0.0, 0.0
        elif result[0] == "inf":
            kind, high, low = "i", float(result[1]), 0.0
        else:
            kind, high, low = "f", result[1], result[2]
        lines.append(f"{label} {bits64(x):016x} {bits64(y):016x} {kind} {bits64(high):016x} {bits64(low):016x}")
    Path(arguments.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {arguments.output} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
