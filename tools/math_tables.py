#!/usr/bin/env python3
"""Generate src/math/tables.lucb, the constant tables of luce-std's own math functions.

The tables are values of the functions themselves: 2^(j/128) for exp, log(F) and 1/F for
log's reduction points, atan(j/64) for atan, and the bits of 2/pi for the trigonometric
argument reduction. Each value is computed here with mpmath at 2000 bits and split into a
double and the double nearest its remainder, so a table entry is a double-double good to
about 2^-106. asin's polynomial is a Chebyshev fit, also made here. Run it with mpmath 1.3.0 in an isolated environment; the build and tests
never import it.

    python3 tools/math_tables.py
"""
from pathlib import Path
import struct

import mpmath as mp

assert mp.__version__ == "1.3.0", "use the pinned reference generator version"
ROOT = Path(__file__).resolve().parents[1]
mp.mp.prec = 2000


def bits(value):
    """The IEEE double nearest `value` (an mpf), as its 64-bit pattern."""
    return struct.unpack("<Q", struct.pack("<d", float(value)))[0]


def double(value):
    return mp.mpf(float(value))


def split(value):
    """`value` as two doubles, high and low, the low the double nearest the remainder."""
    high = double(value)
    return high, double(value - high)


def quantized(value, step_exponent):
    """`value` rounded to a multiple of 2^step_exponent, checked to be a double."""
    step = mp.ldexp(1, step_exponent)
    result = mp.nint(value / step) * step
    assert double(result) == result
    return result


def words(name, values, comment):
    lines = [f"## {comment}", f"let {name}: u64[{len(values)}] = ["]
    for start in range(0, len(values), 4):
        lines.append("    " + ", ".join(f"0x{v:016x}" for v in values[start:start + 4]) + ",")
    lines.append("]")
    return "\n".join(lines)


def constant(name, value, comment):
    return f"## {comment}\nlet {name}: u64 = 0x{bits(value):016x}"


sections = []

# exp and exp2: 2^(j/128) for j in [0, 128), high and low parts.
exp_high, exp_low = [], []
for j in range(128):
    high, low = split(mp.power(2, mp.mpf(j) / 128))
    exp_high.append(bits(high))
    exp_low.append(bits(low))
sections.append(words("exp_table_high", exp_high, "2^(j/128), rounded to a double."))
sections.append(words("exp_table_low", exp_low, "2^(j/128) less its high part, rounded to a double."))

# log: the reduction point F of each of the 128 intervals the bits of x select (log.lucb),
# 1/F rounded, and log(F) as a multiple of 2^-42, so that k*ln2_high + it is exact, and the
# remainder.
OFFSET = 0x3FE6000000000000
log_point, log_inverse, log_high, log_low = [], [], [], []
for i in range(128):
    low_bits = OFFSET + (i << 45)
    start = mp.mpf(struct.unpack("<d", struct.pack("<Q", low_bits))[0])
    end = mp.mpf(struct.unpack("<d", struct.pack("<Q", low_bits + (1 << 45)))[0])
    point = mp.mpf(1) if start <= 1 <= end else (start + end) / 2
    assert double(point) == point
    logarithm = mp.log(point)
    high = quantized(logarithm, -42)
    log_point.append(bits(point))
    log_inverse.append(bits(1 / point))
    log_high.append(bits(high))
    log_low.append(bits(logarithm - high))
sections.append(words("log_point", log_point, "F: the interval's midpoint, or 1 for the two intervals beside 1."))
sections.append(words("log_inverse", log_inverse, "1/F rounded to a double."))
sections.append(words("log_table_high", log_high, "log(F) rounded to a multiple of 2^-42."))
sections.append(words("log_table_low", log_low, "log(F) less its high part, rounded to a double."))

# atan: atan(j/64) for j in [0, 64].
atan_high, atan_low = [], []
for j in range(65):
    high, low = split(mp.atan(mp.mpf(j) / 64))
    atan_high.append(bits(high))
    atan_low.append(bits(low))
sections.append(words("atan_table_high", atan_high, "atan(j/64), rounded to a double."))
sections.append(words("atan_table_low", atan_low, "atan(j/64) less its high part, rounded to a double."))

# asin: (asin w - w)/w³ as a polynomial in z = w² on [0, 1/4], a Chebyshev fit of degree 13
# (near minimax), good to about 2^-61 of asin w.
with mp.workdps(50):
    asin_tail = lambda z: (mp.asin(mp.sqrt(z)) - mp.sqrt(z)) / (z * mp.sqrt(z)) if z > 0 else mp.mpf(1) / 6
    asin_fit = [float(c) for c in reversed(mp.chebyfit(asin_tail, [0, 0.25], 14))]
sections.append("## (asin w - w)/w³ in z = w², 0 <= z <= 1/4: the coefficients of z^0 to z^13.\n"
                f"let asin_coefficients: f64[{len(asin_fit)}] = [" + ", ".join(repr(c) for c in asin_fit) + "]")

# sin and cos: sin(k·pi/128) for k in [0, 256), high and low parts interleaved, so one line
# of memory holds an entry; cos(k·pi/128) is entry k + 64.
sine = []
for k in range(256):
    high, low = split(mp.sin(k * mp.pi / 128))
    sine += [bits(high), bits(low)]
sections.append(words("sine_table", sine, "sin(k·pi/128) for k in [0, 256): high, low."))

# The bits of 2/pi after the binary point, 32 to a word, most significant first: enough for
# the largest double's exponent and 200 bits beyond it.
WORDS = 44
digits = int(mp.floor(2 / mp.pi * mp.mpf(2) ** (32 * WORDS)))
two_over_pi = [(digits >> (32 * (WORDS - 1 - k))) & 0xFFFFFFFF for k in range(WORDS)]
lines = ["## The bits of 2/pi after the binary point, 32 to a word, most significant first.",
         f"let two_over_pi: u32[{WORDS}] = ["]
for start in range(0, WORDS, 6):
    lines.append("    " + ", ".join(f"0x{w:08x}" for w in two_over_pi[start:start + 6]) + ",")
lines.append("]")
sections.append("\n".join(lines))

ln2 = mp.log(2)
ln2_high = quantized(ln2, -42)
ln2_over_128 = ln2 / 128
ln2_128_high = quantized(ln2_over_128, -42)
assert ln2_128_high * 2 ** 42 < 2 ** 35  # 35 bits: times k below 2^18, exact
pio2 = mp.pi / 2
pio2_1 = quantized(pio2, -32)
pio2_2 = quantized(pio2 - pio2_1, -65)
pio2_3 = quantized(pio2 - pio2_1 - pio2_2, -98)
pio2_4 = double(pio2 - pio2_1 - pio2_2 - pio2_3)
step = mp.pi / 128
step_1 = quantized(step, -32)
step_2 = quantized(step - step_1, -59)
assert step_1 * 2 ** 32 < 2 ** 27 and abs(step_2) * 2 ** 59 < 2 ** 27  # times n below 2^26, exact
constants = [
    ("ln2_high", ln2_high, "ln(2) as a multiple of 2^-42: times any exponent k, exact."),
    ("ln2_low", ln2 - ln2_high, "ln(2) less ln2_high."),
    ("ln2_double_high", split(ln2)[0], "ln(2) rounded to a double."),
    ("ln2_double_low", split(ln2)[1], "ln(2) less its double."),
    ("ln2_128_high", ln2_128_high, "ln(2)/128 as a multiple of 2^-42: 35 bits, times k below 2^18, exact."),
    ("ln2_128_low", ln2_over_128 - ln2_128_high, "ln(2)/128 less ln2_128_high."),
    ("inverse_ln2_128", 128 / ln2, "128/ln(2) rounded."),
    ("log2_e_high", split(1 / ln2)[0], "1/ln(2), high part."),
    ("log2_e_low", split(1 / ln2)[1], "1/ln(2), low part."),
    ("log10_e_high", split(1 / mp.log(10))[0], "1/ln(10), high part."),
    ("log10_e_low", split(1 / mp.log(10))[1], "1/ln(10), low part."),
    ("pio2_1", pio2_1, "pi/2 as a multiple of 2^-32 (33 bits): times n below 2^20, exact."),
    ("pio2_2", pio2_2, "The next 33 bits of pi/2."),
    ("pio2_3", pio2_3, "The next 33 bits of pi/2."),
    ("pio2_4", pio2_4, "pi/2 less the three parts above, rounded."),
    ("pio2_high", split(pio2)[0], "pi/2 rounded to a double."),
    ("pio2_low", split(pio2)[1], "pi/2 less its double."),
    ("pi_high", split(mp.pi)[0], "pi rounded to a double."),
    ("pi_low", split(mp.pi)[1], "pi less its double."),
    ("two_over_pi_double", 2 / mp.pi, "2/pi rounded to a double."),
    ("step_1", step_1, "pi/128 as a multiple of 2^-32 (27 bits): times n below 2^26, exact."),
    ("step_2", step_2, "The next 27 bits of pi/128."),
    ("step_3", step - step_1 - step_2, "pi/128 less the two parts above, rounded."),
    ("inverse_step", 128 / mp.pi, "128/pi rounded to a double."),
]
for name, value, comment in constants:
    sections.append(constant(name, value, comment))

header = """#==============================================================================================
#
#   tables - The constant tables of math's own functions
#
#   DESCRIPTION:
#       Generated by tools/math_tables.py with mpmath at 2000 bits; edit the generator, not
#       these tables. Doubles are stored as their bit patterns and read with `f64.bits`, so no
#       decimal conversion stands between a table and its value.
#
#==============================================================================================
"""
output = ROOT / "src/math/tables.lucb"
output.write_text(header + "\n" + "\n\n".join(sections) + "\n", encoding="utf-8")
print(f"wrote {output.relative_to(ROOT)}")
