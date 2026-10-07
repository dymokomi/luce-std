/* Deterministic clock/poll sequences prove deadline accounting independently
 * of scheduler timing. Unarmed calls use the real host functions. */
#define _GNU_SOURCE
#include <assert.h>
#include <dlfcn.h>
#include <errno.h>
#include <poll.h>
#include <stdint.h>
#include <time.h>

static int mode, calls;
static int64_t elapsed;
static void (*cancel_callback)(void *);
static void *cancel_context;
void reference_begin(int kind) { assert(!mode); mode = kind; calls = 0; elapsed = 0; }
int reference_end(void) { int result = calls; mode = 0; return result; }
void reference_cancel_callback(void (*callback)(void *), void *context) {
    cancel_callback = callback;
    cancel_context = context;
}

int clock_gettime(clockid_t clock, struct timespec *stamp) {
    if (mode == 3) { errno = EIO; return -1; }
    if (mode == 1 || mode == 2) {
        assert(clock == CLOCK_MONOTONIC);
        stamp->tv_sec = 1;
        stamp->tv_nsec = elapsed;
        return 0;
    }
    __typeof__(&clock_gettime) real = (__typeof__(&clock_gettime))dlsym(RTLD_NEXT, "clock_gettime");
    assert(real);
    return real(clock, stamp);
}

int poll(struct pollfd *entries, nfds_t count, int timeout) {
    if (mode) {
        assert(count == 2 && entries[0].fd >= 0 && entries[0].events == POLLIN);
        assert(entries[0].revents == 0 && entries[1].revents == 0 && entries[1].fd == -1);
        ++calls;
        if (mode == 1) {
            if (calls == 1) {
                assert(timeout == 100);
                elapsed = 60000000;
                entries[0].revents = POLLERR;
                errno = EINTR;
                return -1;
            }
            assert(calls == 2 && timeout == 40);
            entries[0].revents = POLLIN;
            return 1;
        }
        if (mode == 2) {
            assert(timeout == (calls == 1 ? 100 : 70));
            assert(calls <= 2);
            elapsed = calls == 1 ? 30000000 : 100000000;
            return 0;
        }
        if (mode == 4) {
            assert(timeout == 10 && cancel_callback);
            entries[0].revents = POLLIN;
            cancel_callback(cancel_context);
            return 1;
        }
        assert(mode == 5);
        entries[0].revents = POLLIN;
        errno = EIO;
        return -1;
    }
    __typeof__(&poll) real = (__typeof__(&poll))dlsym(RTLD_NEXT, "poll");
    assert(real);
    return real(entries, count, timeout);
}

void reference_delay(void) {
    struct timespec delay = { .tv_sec = 0, .tv_nsec = 20000000 };
    while (nanosleep(&delay, &delay) != 0) assert(errno == EINTR);
}
