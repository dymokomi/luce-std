#!/usr/bin/env python3
"""Regenerate offline math vectors with mpmath 1.3.0 (not needed by the gate).

Inputs are exact IEEE values. Evaluate at 500 and 800 decimal digits and require
identical nearest-even binary rounding; fused arithmetic uses 1100/1300 digits.
This is independent of host libm, but agreement at two precisions is evidence,
not a proof that an arbitrary-precision implementation cannot contain defects.
"""
import csv
from pathlib import Path
import random
import struct

import mpmath as mp

assert mp.__version__ == "1.3.0", "use the pinned reference generator version"
ROOT = Path(__file__).resolve().parents[1]
OPERATIONS = "floor ceil round trunc sqrt cbrt hypot mod pow exp exp2 log log2 log10 log1p expm1 fma sin cos tan asin acos atan atan2 sinh cosh tanh remainder".split()
EXACT = {"floor", "ceil", "round", "trunc", "sqrt", "mod", "remainder", "fma"}


def encode(value, width):
    return int.from_bytes(struct.pack("<f" if width == 32 else "<d", value), "little")


def decode(bits, width):
    return struct.unpack("<f" if width == 32 else "<d", bits.to_bytes(width // 8, "little"))[0]


def rounded_bits(value, width, negative_zero=False):
    precision, bias = (24, 127) if width == 32 else (53, 1023)
    sign_bit = 1 << (width - 1)
    infinity = ((bias * 2 + 1) << (precision - 1))
    if mp.isnan(value):
        return infinity | (1 << (precision - 2))
    if mp.isinf(value):
        return infinity | (sign_bit if value < 0 else 0)
    sign, mantissa, exponent, bit_count = value._mpf_
    if not mantissa:
        return sign_bit if negative_zero else 0
    encoded_sign = sign_bit if sign else 0
    top = exponent + bit_count - 1
    if top > bias:
        return encoded_sign | infinity
    quantum = max(top, 1 - bias) - (precision - 1)
    shift = quantum - exponent
    if shift > 0:
        significand, remainder = divmod(mantissa, 1 << shift)
        half = 1 << (shift - 1)
        if remainder > half or (remainder == half and significand & 1):
            significand += 1
    else:
        significand = mantissa << -shift
    if significand == 1 << precision:
        significand >>= 1
        top += 1
    if top > bias:
        return encoded_sign | infinity
    if significand < 1 << (precision - 1):
        return encoded_sign | significand
    return encoded_sign | ((max(top, 1 - bias) + bias) << (precision - 1)) | (significand - (1 << (precision - 1)))


def trunc(value):
    return mp.ceil(value) if value < 0 else mp.floor(value)


def evaluate(operation, values):
    x, y, z = values
    if operation == "trunc": return trunc(x)
    if operation == "round": return mp.sign(x) * mp.floor(abs(x) + mp.mpf("0.5"))
    if operation == "cbrt": return mp.sign(x) * mp.root(abs(x), 3)
    if operation == "hypot": return mp.sqrt(x*x + y*y)
    if operation == "mod": return x - trunc(x/y)*y
    if operation == "remainder": return x - mp.nint(x/y)*y
    if operation == "pow": return mp.power(x, y)
    if operation == "exp2": return mp.power(2, x)
    if operation == "log2": return mp.log(x, 2)
    if operation == "log10": return mp.log10(x)
    if operation == "fma": return x*y + z
    if operation == "atan2": return mp.atan2(x, y)
    return getattr(mp, operation)(x)


def reference(operation, bits, width, precision):
    with mp.workdps(precision):
        values = [mp.mpf(decode(value, width)) for value in bits]
        answer = evaluate(operation, values)
        if isinstance(answer, mp.mpc):
            assert answer.imag != 0
            answer = mp.nan
        # mpmath has one zero. Restore the IEEE signs for exact-zero results of
        # the operations whose sign is determined by their first argument.
        negative_zero = bool(bits[0] >> (width - 1)) and operation in {
            "floor", "ceil", "round", "trunc", "sqrt", "cbrt", "mod", "remainder",
            "log1p", "expm1", "sin", "tan", "asin", "atan", "sinh", "tanh"}
        return rounded_bits(answer, width, negative_zero)


rows = []
randomizer = random.Random(5601)
for width in (32, 64):
    precision, bias = (24, 127) if width == 32 else (53, 1023)
    infinity = (bias * 2 + 1) << (precision - 1)
    one = bias << (precision - 1)
    minimum_normal = 1 << (precision - 1)
    general = [0, 1, 2, 3, minimum_normal-1, minimum_normal, minimum_normal+1,
               one-1, one, one+1, infinity-1]
    general += [randomizer.randrange(1, infinity) for _ in range(35)]
    general += [value | (1 << (width - 1)) for value in general]
    ordinary = [-1000, -745, -710, -104, -88, -20, -2, -1, -0.75, -0.5, -0.1,
                -2**-24, -2**-54, 0, 2**-54, 2**-24, 0.1, 0.5, 0.75, 1, 2, 20, 88, 104, 710]
    for operation in OPERATIONS:
        candidates = [(bits, encode(1.5, width), encode(-0.5, width)) for bits in general]
        if operation in {"exp", "exp2", "expm1", "sinh", "cosh", "tanh"}:
            candidates = [(encode(value, width), 0, 0) for value in ordinary]
        elif operation in {"asin", "acos"}:
            candidates += [(encode(value, width), 0, 0) for value in ordinary if -1 <= value <= 1]
        elif operation == "log1p":
            candidates = [row for row in candidates if decode(row[0], width) >= -1]
            candidates += [(encode(value, width), 0, 0) for value in ordinary if value >= -1]
        elif operation == "pow":
            candidates = [(encode(x, width), encode(y, width), 0)
                          for x in (0.1, 0.5, 0.999, 1, 1.001, 2, 10, 100)
                          for y in (-20, -2, -0.5, 0, 0.5, 2, 20)]
            candidates += [(encode(x, width), encode(y, width), 0)
                           for x in (-10, -2, -0.5) for y in (-3, -2, 2, 3)]
        elif operation in {"hypot", "mod", "remainder", "fma", "atan2"}:
            for _ in range(50):
                a, b, c = (randomizer.choice(general) for _ in range(3))
                if decode(b, width) != 0 and (operation != "atan2" or decode(a, width) != 0):
                    candidates.append((a, b, c))
            if operation == "fma":
                candidates += [(one+1, one-1, encode(-1, width)),
                               (infinity-1, encode(2, width), (infinity-1) | (1 << (width-1)))]
            if operation == "atan2":
                candidates = [row for row in candidates if decode(row[0], width) != 0]
        for bits in sorted(set(candidates)):
            precisions = (1100, 1300) if operation in {"fma", "mod", "remainder"} else (500, 800)
            expected = reference(operation, bits, width, precisions[0])
            checked = reference(operation, bits, width, precisions[1])
            assert expected == checked, (operation, width, bits, expected, checked)
            rows.append([operation, width, *[f"{value:0{width//4}x}" for value in bits],
                         f"{expected:0{width//4}x}", 0 if operation in EXACT else 4])
output = ROOT / "tests/programs/math_accuracy/reference.csv"
with output.open("w", newline="") as target:
    writer = csv.writer(target, lineterminator="\n")
    writer.writerow(["operation", "width", "x_bits", "y_bits", "z_bits", "result_bits", "ulp_limit"])
    writer.writerows(rows)
print(f"wrote {output.relative_to(ROOT)} ({len(rows)} vectors)")
