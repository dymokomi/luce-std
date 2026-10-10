# Numerical contracts and reference coverage

`math` operates on f64 and `math32` on f32. The elementary functions (exp, exp2,
expm1, log, log2, log10, log1p, pow, sin, cos, sincos, tan, asin, acos, atan, atan2, sinh,
cosh, tanh, cbrt, hypot, erf and erfc) are written in Base in `src/math/`, so a
program gets the same bits from them on arm64-macos, x86_64-linux and
x86_64-windows; `math32` evaluates them in f64 and rounds once. The exactly
specified operations (floor, ceil, round, trunc, sqrt, fma, mod, remainder,
nextafter, frexp, scalbn, modf) call the host C library, whose results IEEE 754
fixes bit for bit. Nothing allocates. Results are returned directly, NaN and
infinity included; errno and floating-point exception flags are not translated
into Base errors and are whatever the arithmetic leaves. Base enforces the
dividend's sign on a zero remainder, which some hosts lose under directed rounding.

## Operations

Angles are radians. The mathematical descriptions below identify the operation,
not a promise that every transcendental result is correctly rounded. Ordinary
arithmetic uses the caller's floating-point environment. The explicitly named
rounding operations retain their specified direction regardless of that environment.

| Operations | Contract |
| --- | --- |
| `floor`, `ceil` | Integral floating-point value toward negative/positive infinity. |
| `round`, `trunc` | Nearest integral value with halves away from zero; integral value toward zero. Signed zero is preserved. |
| `sqrt` | Nonnegative square root; negative nonzero inputs produce NaN. Negative zero is preserved. |
| `cbrt` | Real cube root, including negative inputs; signed zero is preserved. |
| `hypot` | Magnitude of `(x,y)` without first overflowing or underflowing the squares; an infinite argument produces positive infinity, including with a NaN counterpart. |
| `mod` | `x - trunc(x/y)*y`, with the sign of x on a zero result. A zero divisor or infinite dividend produces NaN. |
| `remainder` | `x - n*y`, where n is the nearest integer quotient with ties to even, independently of the current rounding direction. A zero result has x's sign. |
| `pow` | Real x raised to y. Negative finite bases require an integral exponent for a real result. Zero exponent and base +1 produce 1, including with a NaN counterpart. |
| `exp`, `exp2` | Exponentials with bases e and 2. Overflow gives infinity; underflow rounds once into the subnormals. |
| `expm1` | `exp(x)-1` evaluated without the direct subtraction's cancellation near zero; signed zero is preserved. |
| `log`, `log2`, `log10` | Logarithms for positive inputs. Zero gives negative infinity; negative inputs give NaN. |
| `log1p` | `log(1+x)` retaining small x. At -1, negative infinity; below -1, NaN. Signed zero is preserved. |
| `sin`, `cos`, `tan` | Trigonometric functions; infinite inputs produce NaN. Sin and tan preserve signed zero. |
| `sincos` | `(sin(x), cos(x))` from one reduction, the same bits as the two calls. |
| `asin`, `acos` | Principal inverse functions on [-1,1], with ranges [-pi/2,pi/2] and [0,pi]. Outside the domain, NaN. |
| `atan` | Principal inverse tangent in [-pi/2,pi/2]; signed zero is preserved. |
| `atan2(y,x)` | Four-quadrant angle in [-pi,pi]. Both argument signs matter, including signed zeros on the axes. |
| `sinh`, `cosh`, `tanh` | Hyperbolic functions. Sinh and tanh preserve signed zero; tanh approaches signed 1 at infinite arguments. |
| `erf`, `erfc` | The error function, odd, from -1 to 1, and its complement `1 - erf(x)`, from 2 to 0, computed without the subtraction's cancellation; erfc underflows to zero above about 27.2. Written in Base after fdlibm's method; `math32` evaluates them in f64 and rounds once. Signed zero is preserved by erf; ±infinity gives ±1 (erf) and 0 or 2 (erfc). |
| `fma` | Multiply x and y, then add z with one final rounding; no separately rounded product. |
| `nextafter`, `next_up`, `next_down` | Adjacent representable values. Equal nextafter arguments return the destination, including its zero sign. NaN arguments give NaN. |
| `frexp` | Exact `(fraction, exponent)` decomposition for finite nonzero values, with absolute fraction in [0.5,1). Zero and nonfinite values return `(x,0)`. |
| `scalbn` | Scale by an integer power of two without materializing that power as a float. |
| `modf` | `(fractional, integral)` components, truncating toward zero. Both components have x's sign. Infinity gives a signed-zero fraction; NaN gives two NaNs. |

The complete special-case rules for [power](https://man7.org/linux/man-pages/man3/pow.3.html),
[atan2](https://man7.org/linux/man-pages/man3/atan2.3.html) and
[remainder](https://man7.org/linux/man-pages/man3/remainder.3.html) are C99 Annex F's.
Base does not promise a particular NaN payload from arithmetic.

Classification, absolute value and copying a sign inspect or modify representation
bits. Classification therefore accepts signaling NaNs without doing floating-point
arithmetic. `abs` and `copysign` retain payload bits. `min` and `max` propagate a NaN
argument; at equal zero they select negative/positive zero respectively. `clamp`
propagates NaNs and traps on reversed non-NaN bounds. Integer helpers use i64;
checked absolute value and floor division return none on unrepresentable results,
and checked floor modulus accepts the minimum i64 modulo -1 as zero.

## Methods

Each function names its reference method in its file; the code is written anew from
the method, and the tables are computed by `tools/math_tables.py` with mpmath.
Intermediate values are carried as pairs of doubles (`double_double.lucb`: Knuth's
two-sum, Dekker's fast two-sum, and a product's exact error by a fused multiply-add).

| Functions | Method |
| --- | --- |
| `exp`, `exp2`, `expm1` | Tang's table-driven exponential with 2^(j/128) as pairs (ARM optimized-routines, musl) |
| `log`, `log2`, `log10`, `log1p` | Tang's table-driven logarithm over 128 intervals (ARM optimized-routines' selection), log as a pair |
| `pow` | e^(y·log x) with log x as a pair to about 2^-68 (ARM optimized-routines, musl) |
| `sin`, `cos`, `sincos` | Below 2^20 first a table of sin(k·pi/128) as pairs, sin(a + r) = A·cos r + B·sin r with B·r exact (IBM's libultim, CORE-MATH), returned only when its error bound proves the rounding; otherwise as `tan` |
| `sin`, `cos`, `tan` | fdlibm: Cody-Waite reduction by pi/2 in four parts, Payne-Hanek with 2/pi's bits above 2^20·pi/2, Taylor kernels; tan as sin/cos in pairs |
| `atan`, `atan2` | Gal's accurate tables: atan(j/64) plus a short series in (y - c·x)/(x + c·y) |
| `asin`, `acos` | fdlibm: a fitted polynomial to 1/2, pi/2 - 2·asin(sqrt((1 - x)/2)) beyond |
| `sinh`, `cosh`, `tanh` | fdlibm's definitions in e^x, with e^x, its reciprocal and quotients as pairs; series near zero |
| `cbrt` | fdlibm's plan: a cubic guess, one Halley step, one Newton step from the exact residual |
| `hypot` | Exact squares as pairs and a corrected root (Borges 2019), scaled by 2^±600 |
| `erf`, `erfc` | fdlibm's rational approximations, with math's own exp |

## Precision policy and evidence

The elementary functions give identical bits on every supported target: Base
neither contracts nor reassociates float arithmetic, x86-64 uses SSE2 (no x87),
and the code's fused multiply-adds (`mul_add`) are IEEE 754's, the same bits everywhere:
an instruction where the processor has one and the C library's `fma` otherwise. Their results are
within one ulp, and in the measured inputs within 0.51 ulp for most and 0.6 ulp for
all; they are not promised correctly rounded. Where a function has a fast path, the
fast path returns only results its error bound proves correctly rounded and hands
every other input to the accurate method, so the results do not depend on how fast
the fast path is. Special values follow C99 Annex F.
These promises hold in the default rounding direction, which the exact sums and the
reductions assume; under a directed one the results stay close but may differ.
Which NaN an invalid operation returns is the processor's (x86-64's has the sign bit
set); Base promises none.

- `tests/math_identity` hashes the results of every math and math32 function over
  edge cases and three thousand inputs each from a fixed seed; the checked-in
  hashes must come out on every target.
- `tests/math_ulp` checks every elementary function, f64 and f32, against
  arbitrary-precision references (`generate.py`, mpmath 1.3.0 at 400 and 600 bits)
  and asserts one ulp, printing the largest error of each.
  `generate.py --count N` with `MATH_ULP_REFERENCE` runs the same check on more inputs.
- `tests/math_speed` times each function against the host library and prints the
  table; it fails only past ten times the library's time.

The older accuracy gate contains two independent reference campaigns:

- 100 log1p/expm1 vectors computed during each run with Python Decimal at 160 and
  240 digits. Their rounded references must agree; the test budget is two ULPs.
- 7,893 checked-in vectors across 30 operations and both precisions, generated
  with mpmath 1.3.0 at 500 and 800 decimal digits. Fma and remainder calculations
  use 1100 and 1300 digits to retain cancellation across wide exponent gaps.
  Inputs and expected outputs are stored as exact hexadecimal IEEE bits.

The broader corpus includes subnormal/normal boundaries, adjacent values around
one, large trigonometric arguments, domain violations, overflow, underflow,
negative powers and fused cancellation, and for erf and erfc a sweep through each
interval of their method, out to erfc's underflow, down to subnormals. Integral rounding, square root, remainders
and fma must match reference bits exactly. Other finite results have a four-ULP
budget **for these vectors**. NaN results are checked by classification, and expected
infinities and signed zeros must match exactly. These budgets are regression gates,
not whole-domain accuracy claims. Agreement at two high precisions also cannot
prove the reference implementation free of defects; the live Decimal campaign
provides a separate implementation for its overlapping operations.

To regenerate the broader data, use an isolated Python environment containing
`mpmath==1.3.0` and run `python tools/math_reference.py`. Review the resulting CSV
diff. The normal build and test gate do not import or download mpmath. Its
[representation and precision documentation](https://mpmath.org/doc/1.3.0/technical.html)
explains the reference model and its limits.
