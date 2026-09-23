/* Host-header reference and deterministic option-call failures. */
#define _GNU_SOURCE
#include <assert.h>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdarg.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/socket.h>

static int armed, hits;
void fault_arm(int kind) { assert(!armed); armed = kind; hits = 0; }
int fault_hits(void) { assert(!armed); return hits; }

int getsockopt(int fd, int level, int option, void *value, socklen_t *length) {
    assert(*length == sizeof(int));
    if (armed == 1) {
        armed = 0;
        ++hits;
        *length = 1;
        errno = EINTR;
        return -1;
    }
    if (armed == 2) {
        armed = 0;
        ++hits;
        *length = 1;
        return 0;
    }
    __typeof__(&getsockopt) real = (__typeof__(&getsockopt))dlsym(RTLD_NEXT, "getsockopt");
    assert(real);
    return real(fd, level, option, value, length);
}

int setsockopt(int fd, int level, int option, const void *value, socklen_t length) {
    if (armed == 3 || armed == 4) {
        errno = armed == 3 ? EINTR : EINVAL;
        armed = 0;
        ++hits;
        return -1;
    }
    __typeof__(&setsockopt) real = (__typeof__(&setsockopt))dlsym(RTLD_NEXT, "setsockopt");
    assert(real);
    return real(fd, level, option, value, length);
}

int reference_option(int fd, int which) {
    int option = which == 1 ? SO_RCVBUF : which == 2 ? SO_SNDBUF : which == 3 ? TCP_NODELAY : SO_KEEPALIVE;
    int value = -1;
    socklen_t length = sizeof(value);
    assert(getsockopt(fd, which == 3 ? IPPROTO_TCP : SOL_SOCKET, option, &value, &length) == 0);
    assert(length == sizeof(value));
    return value;
}
int reference_flags(int fd) { int flags = fcntl(fd, F_GETFL); assert(flags >= 0); return flags; }
int reference_nonblocking_flag(void) { return O_NONBLOCK; }

void reference_wait_readable(int fd) {
    struct pollfd entry = { .fd = fd, .events = POLLIN };
    int result;
    do { result = poll(&entry, 1, 5000); } while (result < 0 && errno == EINTR);
    assert(result == 1 && (entry.revents & POLLIN));
}

static int failed_descriptor = -1;
int fcntl(int fd, int command, ...) {
    if ((command == F_GETFL && (armed == 5 || armed == 7)) ||
        (command == F_SETFL && (armed == 6 || armed == 8))) {
        errno = armed <= 6 ? EINTR : EIO;
        failed_descriptor = fd;
        armed = 0;
        ++hits;
        return -1;
    }
    __typeof__(&fcntl) real = (__typeof__(&fcntl))dlsym(RTLD_NEXT, "fcntl");
    assert(real);
    if (command == F_GETFL || command == F_GETFD) return real(fd, command);
    assert(command == F_SETFL || command == F_SETFD);
    va_list arguments;
    va_start(arguments, command);
    int value = va_arg(arguments, int);
    va_end(arguments);
    return real(fd, command, value);
}
int reference_failed_descriptor_closed(void) {
    return failed_descriptor >= 0 && fcntl(failed_descriptor, F_GETFD) == -1 && errno == EBADF;
}
