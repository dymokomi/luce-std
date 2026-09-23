/* Faults apply only to an explicitly watched descriptor in this test executable. */
#define _GNU_SOURCE
#include <assert.h>
#include <dlfcn.h>
#include <errno.h>
#include <unistd.h>

static int watched = -1, armed, hits, writes;
void file_fault_watch(int fd) { watched = fd; }
void file_fault_arm(int kind) { assert(!armed); armed = kind; hits = writes = 0; }
int file_fault_hits(void) { return hits; }
static int take(int fd, int kind) {
    if (fd != watched || armed != kind) return 0;
    armed = 0;
    ++hits;
    return 1;
}
#define REAL(name) __typeof__(&name) real = (__typeof__(&name))dlsym(RTLD_NEXT, #name); assert(real)
ssize_t read(int fd, void *data, size_t count) {
    REAL(read);
    if (take(fd, 1)) { errno = EINTR; return -1; }
    return real(fd, data, fd == watched && count > 2 ? 2 : count);
}
ssize_t write(int fd, const void *data, size_t count) {
    REAL(write);
    if (take(fd, 2)) { errno = EINTR; return -1; }
    if (fd == watched && armed == 3 && writes++ > 0 && take(fd, 3)) {
        errno = ENOSPC;
        return -1;
    }
    return real(fd, data, fd == watched && count > 2 ? 2 : count);
}
int close(int fd) {
    REAL(close);
    /* Model a delayed close failure after the descriptor has been released. */
    if (take(fd, 4)) { int result = real(fd); assert(result == 0); errno = EIO; return -1; }
    return real(fd);
}
int fsync(int fd) {
    REAL(fsync);
    if (take(fd, 5)) { errno = EINTR; return -1; }
    return real(fd);
}
