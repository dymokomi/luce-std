#!/usr/bin/env python3
"""Compare log1p/expm1 with Decimal references, never with the host libm.

Inputs are represented exactly before decimal evaluation. Recompute each reference
at two precisions and require the same binary result before using it as a vector.
The two-ulp limit is a gate for these vectors, not a proof over the whole domain.
"""
from decimal import Decimal, localcontext
import csv
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "build/math_accuracy"
OUTPUT.mkdir(parents=True, exist_ok=True)
COMPILER = Path(sys.argv[1]).resolve()


def encode(value, width):
    return int.from_bytes(struct.pack(">f" if width == 32 else ">d", value), "big")


def rounded_input(value, width):
    return struct.unpack(">f" if width == 32 else ">d",
                         struct.pack(">f" if width == 32 else ">d", value))[0]


def reference(operation, value, width, precision):
    with localcontext() as context:
        context.prec = precision
        exact = Decimal.from_float(value)
        answer = (Decimal(1) + exact).ln() if operation == "log1p" else exact.exp() - 1
        return encode(float(answer), width)


source = ["import math", "import math32", "",
          "func within_ulps(actual: u64, expected: u64) -> bool:",
          "    let distance = actual - expected if actual >= expected else expected - actual",
          "    return distance <= 2", "", "pub func main(arguments: str[]) -> i32:"]
count = 0
for width in (32, 64):
    # Powers of two exercise cancellation; ordinary values exercise each side of
    # zero, the logarithm boundary, and a broad range of exponential magnitudes.
    values = [sign * 2.0 ** -exponent for exponent in (4, 10, 20, 26, 54, 80, 100)
              for sign in (-1, 1)]
    values += [-0.999, -0.9, -0.75, -0.5, -0.1, 0.1, 0.5, 1.0, 2.0, 8.0, 20.0]
    for operation in ("log1p", "expm1"):
        for raw in values:
            value = rounded_input(raw, width)
            expected = reference(operation, value, width, 160)
            assert expected == reference(operation, value, width, 240)
            bits = encode(value, width)
            module = "math32" if width == 32 else "math"
            call = f"{module}.{operation}(f{width}.bits({bits})).bits()"
            source.append(f'    assert(within_ulps((u64){call}, {expected}), "{module}.{operation} input bits {bits}")')
            count += 1
source += [f'    print("ok math accuracy: {count} independent vectors")', "    return 0", ""]
program = OUTPUT / "vectors.lucb"
program.write_text("\n".join(source))
executable = OUTPUT / "vectors"
for flags in [*[['--native', '--opt', str(level)] for level in range(4)],
              ['--backend=c'], ['--backend=c', '--release']]:
    for command in ([COMPILER, 'build', program, *flags, '-o', executable], [executable]):
        subprocess.run([sys.executable, ROOT.parent / 'luce-base/tools/run_case.py', '--', *command],
                       cwd=ROOT, check=True)
    print("PASS " + " ".join(flags), flush=True)
executable.unlink()

# Offline arbitrary-precision references cover the broader libm surface. The
# generator is pinned separately; ordinary test runs use only Python's stdlib.
operations = "floor ceil round trunc sqrt cbrt hypot mod pow exp exp2 log log2 log10 log1p expm1 fma sin cos tan asin acos atan atan2 sinh cosh tanh remainder".split()
corpus = bytearray()
covered = set()
with (ROOT / "tests/programs/math_accuracy/reference.csv").open() as stream:
    for row in csv.DictReader(stream):
        width = int(row["width"])
        assert width in (32, 64)
        expected_limit = 0 if row["operation"] in {"floor", "ceil", "round", "trunc", "sqrt", "mod", "remainder", "fma"} else 4
        assert int(row["ulp_limit"]) == expected_limit
        covered.add((row["operation"], width))
        corpus.extend(struct.pack("<IIQQQQQ", operations.index(row["operation"]), int(row["width"]),
                                  *[int(row[name], 16) for name in ("x_bits", "y_bits", "z_bits", "result_bits")],
                                  int(row["ulp_limit"])))
assert covered == {(operation, width) for operation in operations for width in (32, 64)}
reference_path = OUTPUT / "reference.bin"
reference_path.write_bytes(corpus)
for flags in [*[["--native", "--opt", str(level)] for level in range(4)],
              ["--backend=c"], ["--backend=c", "--release"]]:
    for command in ([COMPILER, "build", ROOT / "tests/programs/math_accuracy/reference.lucb",
                     *flags, "-o", executable], [executable, reference_path]):
        subprocess.run([sys.executable, ROOT.parent / "luce-base/tools/run_case.py", "--", *command], cwd=ROOT, check=True)
    print("PASS broad reference " + " ".join(flags), flush=True)
executable.unlink()
