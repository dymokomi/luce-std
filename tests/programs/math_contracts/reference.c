/* Host headers define fenv constants; all expected numerical values live in Base. */
#include <assert.h>
#include <fenv.h>
#include <stdint.h>

static fenv_t saved_environment;
static int expected_rounding;

void math_environment_begin(void) {
    assert(fegetenv(&saved_environment) == 0);
    expected_rounding = FE_TONEAREST;
    assert(fesetround(expected_rounding) == 0);
}

void math_environment_round(int32_t mode) {
    const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
    assert(mode >= 0 && mode < 4);
    expected_rounding = modes[mode];
    assert(fesetround(expected_rounding) == 0);
}

void math_environment_check(void) {
    assert(fegetround() == expected_rounding);
}

void math_exceptions_clear(void) {
    assert(feclearexcept(FE_ALL_EXCEPT) == 0);
}

int32_t math_invalid_raised(void) {
    return (fetestexcept(FE_INVALID) != 0);
}

void math_environment_end(void) {
    math_environment_check();
    assert(fesetenv(&saved_environment) == 0);
}
