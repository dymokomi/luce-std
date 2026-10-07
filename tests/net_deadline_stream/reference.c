/* Inject failures after real partial transfers, preserving independent evidence
 * of exactly which bytes reached the peer. */
#define _GNU_SOURCE
#include <assert.h>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

static int mode, watched, calls;
static long elapsed;
static void (*cancel_callback)(void *);
static void *cancel_context;
void reference_begin(int kind, int fd) { assert(!mode); mode = kind; watched = fd; calls = 0; elapsed = 0; }
int reference_end(void) { int result = calls; mode = 0; return result; }
void reference_cancel_callback(void (*callback)(void *), void *context) { cancel_callback = callback; cancel_context = context; }
int reference_nonblocking(int fd) { int flags = fcntl(fd, F_GETFL); assert(flags >= 0); return (flags & O_NONBLOCK) != 0; }

ssize_t send(int fd, const void *data, size_t length, int flags) {
    __typeof__(&send) real = (__typeof__(&send))dlsym(RTLD_NEXT, "send");
    assert(real);
    if (mode && fd == watched) {
        assert(flags & MSG_DONTWAIT);
#ifndef __APPLE__
        assert(flags & MSG_NOSIGNAL);
#endif
        ++calls;
        if (mode == 1) {
            if (calls == 1) {
                ssize_t result = real(fd, data, length < 2 ? length : 2, flags);
                assert(result == 2);
                elapsed = 60000000;
                return result;
            }
            assert(calls == 2);
            errno = EAGAIN;
            return -1;
        }
        if (mode == 3) { elapsed = 100000000; errno = EINTR; return -1; }
        if (mode == 5) return 0;
        assert(mode == 7);
        errno = EPIPE;
        return -1;
    }
    return real(fd, data, length, flags);
}

ssize_t recv(int fd, void *data, size_t length, int flags) {
    __typeof__(&recv) real = (__typeof__(&recv))dlsym(RTLD_NEXT, "recv");
    assert(real);
    if (mode && fd == watched) {
        assert(flags & MSG_DONTWAIT);
        ++calls;
        if (mode == 2 || mode == 4) {
            if (calls == 1) {
                ssize_t result = real(fd, data, length < 2 ? length : 2, flags);
                assert(result == 2);
                elapsed = 60000000;
                if (mode == 4) { assert(cancel_callback); cancel_callback(cancel_context); }
                return result;
            }
            assert(mode == 2 && calls == 2);
            elapsed = 100000000;
            errno = EINTR;
            return -1;
        }
        assert(mode == 6);
        errno = EIO;
        return -1;
    }
    return real(fd, data, length, flags);
}

int poll(struct pollfd *entries, nfds_t count, int timeout) {
    if (mode == 1) {
        assert(count == 1 && entries[0].fd == watched && entries[0].events == POLLOUT && timeout == 40);
        elapsed = 100000000;
        return 0;
    }
    __typeof__(&poll) real = (__typeof__(&poll))dlsym(RTLD_NEXT, "poll");
    assert(real);
    return real(entries, count, timeout);
}

int clock_gettime(clockid_t clock, struct timespec *stamp) {
    if (mode >= 1 && mode <= 3) {
        assert(clock == CLOCK_MONOTONIC);
        stamp->tv_sec = 1;
        stamp->tv_nsec = elapsed;
        return 0;
    }
    __typeof__(&clock_gettime) real = (__typeof__(&clock_gettime))dlsym(RTLD_NEXT, "clock_gettime");
    assert(real);
    return real(clock, stamp);
}

int setsockopt(int fd, int level, int option, const void *value, socklen_t length) {
#ifdef __APPLE__
    if (mode == 8 && option == SO_NOSIGPIPE && calls == 0) { ++calls; errno = EINTR; return -1; }
#endif
    __typeof__(&setsockopt) real = (__typeof__(&setsockopt))dlsym(RTLD_NEXT, "setsockopt");
    assert(real);
    return real(fd, level, option, value, length);
}
