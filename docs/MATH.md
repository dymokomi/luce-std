# Numerical contracts and reference coverage

`math` operates on f64 and `math32` on f32. Native Base programs call the host
math library through the C ABI; f32 wrappers call its single-precision functions.
The wrappers allocate no Base storage. They return floating-point values directly,
including NaN and infinity, and do not translate host errno or floating-point
exception flags into Base errors. Those side effects follow the host library.
See [the host error model](https://man7.org/linux/man-pages/man7/math_error.7.html).
Base enforces the exact negative-infinity limit of expm1 and the dividend's sign
on a zero remainder; some host implementations violate these under directed rounding.

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
| `exp`, `exp2` | Exponentials with bases e and 2. Overflow and underflow follow host floating-point behavior. |
| `expm1` | `exp(x)-1` evaluated without the direct subtraction's cancellation near zero; signed zero is preserved. |
| `log`, `log2`, `log10` | Logarithms for positive inputs. Zero gives negative infinity; negative inputs give NaN. |
| `log1p` | `log(1+x)` retaining small x. At -1, negative infinity; below -1, NaN. Signed zero is preserved. |
| `sin`, `cos`, `tan` | Trigonometric functions; infinite inputs produce NaN. Sin and tan preserve signed zero. |
| `asin`, `acos` | Principal inverse functions on [-1,1], with ranges [-pi/2,pi/2] and [0,pi]. Outside the domain, NaN. |
| `atan` | Principal inverse tangent in [-pi/2,pi/2]; signed zero is preserved. |
| `atan2(y,x)` | Four-quadrant angle in [-pi,pi]. Both argument signs matter, including signed zeros on the axes. |
| `sinh`, `cosh`, `tanh` | Hyperbolic functions. Sinh and tanh preserve signed zero; tanh approaches signed 1 at infinite arguments. |
| `fma` | Multiply x and y, then add z with one final rounding; no separately rounded product. |
| `nextafter`, `next_up`, `next_down` | Adjacent representable values. Equal nextafter arguments return the destination, including its zero sign. NaN arguments give NaN. |
| `frexp` | Exact `(fraction, exponent)` decomposition for finite nonzero values, with absolute fraction in [0.5,1). Zero and nonfinite values return `(x,0)`. |
| `scalbn` | Scale by an integer power of two without materializing that power as a float. |
| `modf` | `(fractional, integral)` components, truncating toward zero. Both components have x's sign. Infinity gives a signed-zero fraction; NaN gives two NaNs. |

The complete special-case rules for [power](https://man7.org/linux/man-pages/man3/pow.3.html),
[atan2](https://man7.org/linux/man-pages/man3/atan2.3.html) and
[remainder](https://man7.org/linux/man-pages/man3/remainder.3.html) come from their
host interfaces. Base does not promise a particular NaN payload from arithmetic.

Classification, absolute value and copying a sign inspect or modify representation
bits. Classification therefore accepts signaling NaNs without doing floating-point
arithmetic. `abs` and `copysign` retain payload bits. `min` and `max` propagate a NaN
argument; at equal zero they select negative/positive zero respectively. `clamp`
propagates NaNs and traps on reversed non-NaN bounds. Integer helpers use i64;
checked absolute value and floor division return none on unrepresentable results,
and checked floor modulus accepts the minimum i64 modulo -1 as zero.

## Precision policy and evidence

Base does not currently promise identical transcendental bits across supported
hosts or a certified global ULP bound. The native compiler must preserve the
specified operation and precision, including fused arithmetic and special values.
Tests run native optimization levels 0–3 and both C comparison configurations.
The contract suite exercises all four host rounding directions, including halfway
fma, subnormal scalbn, sqrt rounding, exact remainder vectors, signed-zero and
infinity rules, and signaling-NaN classification without raising invalid. It also
verifies that calls retain the selected rounding direction.

The accuracy gate contains two independent reference campaigns:

- 100 log1p/expm1 vectors computed during each run with Python Decimal at 160 and
  240 digits. Their rounded references must agree; the test budget is two ULPs.
- 4,838 checked-in vectors across 28 operations and both precisions, generated
  with mpmath 1.3.0 at 500 and 800 decimal digits. Fma and remainder calculations
  use 1100 and 1300 digits to retain cancellation across wide exponent gaps.
  Inputs and expected outputs are stored as exact hexadecimal IEEE bits.

The broader corpus includes subnormal/normal boundaries, adjacent values around
one, large trigonometric arguments, domain violations, overflow, underflow,
negative powers and fused cancellation. Integral rounding, square root, remainders
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
