/* Simulated asynchronous connects prove ownership and completion handling without
 * depending on packet loss or an unreachable external network. */
#define _GNU_SOURCE
#include <assert.h>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdint.h>
#include <sys/socket.h>
#include <time.h>

static int mode, acquired, descriptor = -1;
static long elapsed;
static void (*cancel_callback)(void *);
static void *cancel_context;
void reference_begin(int kind) { assert(!mode); mode = kind; acquired = 0; descriptor = -1; elapsed = 0; }
int reference_end(void) {
    assert(descriptor < 0 || (fcntl(descriptor, F_GETFD) == -1 && errno == EBADF));
    mode = 0;
    return acquired;
}
void reference_cancel_callback(void (*callback)(void *), void *context) { cancel_callback = callback; cancel_context = context; }

int socket(int family, int kind, int protocol) {
    __typeof__(&socket) real = (__typeof__(&socket))dlsym(RTLD_NEXT, "socket");
    assert(real);
    int fd = real(family, kind, protocol);
    if (mode) { assert(fd >= 0); descriptor = fd; ++acquired; }
    return fd;
}

int connect(int fd, const struct sockaddr *address, socklen_t length) {
    if (mode) {
        assert(fd == descriptor && (fcntl(fd, F_GETFL) & O_NONBLOCK));
        if (mode == 8) { elapsed = 100000000; return 0; }
        errno = mode == 4 ? EACCES : EINPROGRESS;
        return -1;
    }
    __typeof__(&connect) real = (__typeof__(&connect))dlsym(RTLD_NEXT, "connect");
    assert(real);
    return real(fd, address, length);
}

int poll(struct pollfd *entries, nfds_t count, int timeout) {
    if (mode) {
        assert(count == 1 && entries[0].fd == descriptor && entries[0].events == POLLOUT);
        if (mode == 1) { assert(timeout == 100); elapsed = 100000000; return 0; }
        if (mode == 2) { assert(timeout == 10 && cancel_callback); cancel_callback(cancel_context); return 0; }
        if (mode == 7) { errno = EIO; return -1; }
        assert(mode == 3 || mode == 6);
        entries[0].revents = POLLOUT;
        return 1;
    }
    __typeof__(&poll) real = (__typeof__(&poll))dlsym(RTLD_NEXT, "poll");
    assert(real);
    return real(entries, count, timeout);
}

int getsockopt(int fd, int level, int option, void *value, socklen_t *length) {
    if (mode == 3 || mode == 6) {
        assert(fd == descriptor && level == SOL_SOCKET && option == SO_ERROR && *length == sizeof(int));
        if (mode == 6) { errno = EIO; return -1; }
        *(int *)value = ECONNREFUSED;
        return 0;
    }
    __typeof__(&getsockopt) real = (__typeof__(&getsockopt))dlsym(RTLD_NEXT, "getsockopt");
    assert(real);
    return real(fd, level, option, value, length);
}

int clock_gettime(clockid_t clock, struct timespec *stamp) {
    if (mode == 1 || mode == 8) {
        assert(clock == CLOCK_MONOTONIC);
        stamp->tv_sec = 1;
        stamp->tv_nsec = elapsed;
        return 0;
    }
    __typeof__(&clock_gettime) real = (__typeof__(&clock_gettime))dlsym(RTLD_NEXT, "clock_gettime");
    assert(real);
    return real(clock, stamp);
}
